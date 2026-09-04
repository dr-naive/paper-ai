"""SkillRegistry —— skill 发现、tool 加载、system prompt 拼装。

设计权衡:
- skill → tool 工厂的映射当前硬编码在本模块,而非每个 skill 目录放 manifest.py
- 理由:期 2 只有 paper_internal 有 tool,其他 skill 的 SKILL.md 仅占位
- 等期 3 全部 tool 实现后,若 skill 数量增长,再抽 manifest 文件
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# skill 目录所在路径(本文件同级的子目录)
SKILLS_DIR = Path(__file__).parent


@dataclass
class SkillManifest:
    """单个 skill 的元信息。"""
    name: str
    skill_md_path: Path
    # tool 工厂的导入路径,格式 "module.path:func_name",None 表示该 skill 暂无 tool
    tool_factory_import: Optional[str] = None
    # 该 skill 提供的 tool 名称列表(用于 LLM prompt 与按需加载)
    provided_tools: list[str] = field(default_factory=list)


# === skill 注册表(硬编码,期 3 tool 实现后可迁移到 manifest 文件) ===
# 注意:tool_factory_import 用字符串而非直接 import,避免 import 未实现模块报错
_SKILL_REGISTRY: dict[str, SkillManifest] = {
    "paper_internal": SkillManifest(
        name="paper_internal",
        skill_md_path=SKILLS_DIR / "paper_internal" / "SKILL.md",
        tool_factory_import="app.harness.tools.paper_internal:make_paper_internal_tools",
        provided_tools=[
            "get_paper_metadata",
            "list_paper_sections",
            "search_paper_content",
            "lookup_table_data",
            "compute_over_tables",
            "export_citation_format",
        ],
    ),
    "external_literature": SkillManifest(
        name="external_literature",
        skill_md_path=SKILLS_DIR / "external_literature" / "SKILL.md",
        tool_factory_import="app.harness.tools.external_literature:make_external_literature_tools",
        provided_tools=["search_arxiv", "search_semantic_scholar"],
    ),
    "reading_assistant": SkillManifest(
        name="reading_assistant",
        skill_md_path=SKILLS_DIR / "reading_assistant" / "SKILL.md",
        tool_factory_import="app.harness.tools.reading_assistant:make_reading_assistant_tools",
        provided_tools=["get_reading_progress", "locate_term_definition"],
    ),
    "literature_research": SkillManifest(
        name="literature_research",
        skill_md_path=SKILLS_DIR / "literature_research" / "SKILL.md",
        # project_* 工具不通过 registry 加载(需要 project_id/user_id,registry 只有 db)
        # 真实 tool 实例在 run_lead_agent 里用 make_project_tools(db, project_id, user_id) closure 注入
        # 这里注册只是为了 build_system_prompt 能拼上 SKILL.md,让 LLM 知道有这个 skill
        tool_factory_import=None,
        provided_tools=[
            "project_search_content",
            "project_add_paper",
            "project_remove_paper",
            "project_import_arxiv_paper",
            "project_append_memory",
            "project_save_paper_card",
            "project_save_research_brief",
            "project_save_literature_screening",
            "project_save_research_map",
            "project_save_reading_plan",
            "project_build_evidence_matrix",
            "project_save_experiment_design",
            "project_save_experiment_results",
            "project_save_paper_blueprint",
            "project_save_section_draft",
            "project_assemble_full_draft",
            "project_build_reference_list",
            "project_audit_full_draft",
            "project_finalize_manuscript",
            "project_read_memory",
            "project_save_artifact",
        ],
    ),
}


class SkillRegistry:
    """skill 发现、按需加载 tool、拼装 system prompt。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tool_cache: dict[str, list] = {}  # skill_name -> tools,避免重复构建

    @classmethod
    def list_skills(cls) -> list[str]:
        """列出所有已注册 skill 名。"""
        return list(_SKILL_REGISTRY.keys())

    @classmethod
    def get_manifest(cls, skill_name: str) -> SkillManifest:
        """获取单个 skill 的 manifest,不存在则抛 KeyError。"""
        if skill_name not in _SKILL_REGISTRY:
            raise KeyError(f"未知 skill: {skill_name},已注册: {list(_SKILL_REGISTRY.keys())}")
        return _SKILL_REGISTRY[skill_name]

    def load_tools(self, skill_names: list[str]) -> list:
        """按 skill 名加载 tool 实例列表。

        Args:
            skill_names: 要加载的 skill 名列表

        Returns:
            合并后的 LangChain BaseTool 实例列表,可直接传给 LLMClient.bind_tools
        """
        all_tools: list = []
        for skill_name in skill_names:
            manifest = self.get_manifest(skill_name)
            if not manifest.tool_factory_import:
                logger.debug("skill %s 暂无 tool 实现,跳过", skill_name)
                continue
            if skill_name in self._tool_cache:
                all_tools.extend(self._tool_cache[skill_name])
                continue
            tools = self._import_and_call_factory(manifest.tool_factory_import)
            self._tool_cache[skill_name] = tools
            all_tools.extend(tools)
            logger.info("加载 skill %s 的 %d 个 tool", skill_name, len(tools))
        return all_tools

    def _import_and_call_factory(self, import_path: str) -> list:
        """根据 "module.path:func_name" 导入并调用 tool 工厂。"""
        module_path, func_name = import_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        factory: Callable = getattr(module, func_name)
        return factory(self.db)

    def build_system_prompt(self, skill_names: list[str]) -> str:
        """把指定 skill 的 SKILL.md 内容拼成 system prompt。

        Args:
            skill_names: 要注入的 skill 名列表

        Returns:
            system prompt 字符串,包含所有 skill 的 SKILL.md 内容
        """
        parts = [
            "你是一个论文阅读助手。根据用户问题,选择合适的工具调用。",
            "以下是你可以使用的技能(skill)说明,每个 skill 包含若干工具:\n",
        ]
        for skill_name in skill_names:
            manifest = self.get_manifest(skill_name)
            if not manifest.skill_md_path.exists():
                logger.warning("skill %s 的 SKILL.md 不存在: %s", skill_name, manifest.skill_md_path)
                continue
            skill_md = manifest.skill_md_path.read_text(encoding="utf-8")
            parts.append(f"---\n# Skill: {skill_name}\n\n{skill_md}\n")
        parts.append(
            "\n---\n## 行为规范\n"
            "1. 优先用工具获取信息,不要凭论文标题或常识猜测\n"
            "2. 工具返回结果后,基于结果回答,不要复述工具调用过程\n"
            "3. 若一个工具返回的信息不足以回答,可继续调用其他工具\n"
            "4. 若所有相关工具都返回空或失败,如实告知用户\n"
        )
        return "\n".join(parts)
