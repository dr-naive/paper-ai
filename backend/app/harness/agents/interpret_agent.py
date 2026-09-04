"""Harness Agent: interpret_agent —— 深度解读代理。

把原先硬编码在 chat.py /interpret 路由里的 3 种深度解读逻辑(concept/compare/key_info)
收敛到 harness 层,复用 paper_internal skill 的 tools(search_paper_content 等),
产出带 citations 的结构化解读结果。

设计权衡:
- 不重写 ReAct 循环,直接包装 run_lead_agent,传入 interpret_type 特化的 system prompt
- 要求 LLM 输出的 JSON 里每个条目都嵌入 [S1][S2] 引用标记
  → 这样 build_deterministic_citations 能从 result_data 里挖 citations,与 qa 路径对齐
- 对外返回兼容原 chat.py /interpret 路由的结构:
  {"paper_id", "type", "cached", "data": {...}, "message"}
  附加 "citations" / "chunks" / "agent_trace" 三个增强字段
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.agents.lead_agent import AgentTrace, run_lead_agent

logger = logging.getLogger(__name__)


# 3 种解读类型的强约束 prompt。嵌入 system prompt,强制 LLM:
#   1) 先搜索论文正文,不要凭空总结
#   2) 输出严格 JSON
#   3) 每个条目的 explanation/difference 等文本里,必须用 [S1][S2] 形式标明出处
INTERPRET_TYPE_PROMPTS: dict[str, str] = {
    "concept": """
你当前的任务 =「关键概念与技术术语解读」(interpret_type=concept)

## 强制步骤
1. 先调用至少一次 search_paper_content,检索论文里的关键概念/术语定义
2. 基于检索到的 chunk(带 [S1][S2]... 编号),输出严格 JSON

## 输出 JSON Schema(严格遵守,不要加额外字段)
{
  "concepts": [
    {
      "name": "概念或术语名称",
      "explanation": "通俗解释(100字以内),引用出处用 [S1][S2] 形式标注在句末",
      "context": "在论文中的作用/出现场景,出处同样用 [S1][S2] 标注"
    }
  ]
}

## 强制约束
- 至少提取 3 个概念,最多 10 个
- explanation / context 两个字段 **必须** 至少出现一个 [Sn] 引用标记
- 引用只能用 search_paper_content 返回的 [S1]~[S10] 编号
- 不要输出 JSON 以外的任何内容(不要 ```json 包裹)
""",
    "compare": """
你当前的任务 =「不同方法/模型/实验对比」(interpret_type=compare)

## 强制步骤
1. 先调用至少一次 search_paper_content(多次也可以),检索论文里提到的方法对比、
   实验对比、baseline 对比、消融实验表格。
2. 如有需要,可调用 lookup_table_data 检索表格内容。
3. 基于检索到的 chunk(带 [S1][S2]... 编号),输出严格 JSON

## 输出 JSON Schema
{
  "comparisons": [
    {
      "item_a": "方法/模型/Ablation A",
      "item_b": "方法/模型/Ablation B",
      "difference": "主要差异描述,必须用 [S1][S2] 标注出处",
      "advantage": "各自的优势/性能表现,必须用 [S1][S2] 标注出处"
    }
  ]
}

## 强制约束
- 至少列出 2 组对比,最多 8 组
- difference / advantage 字段 **必须** 至少出现一个 [Sn] 引用标记
- 不要输出 JSON 以外的任何内容
""",
    "key_info": """
你当前的任务 =「关键信息摘要」(interpret_type=key_info)

## 强制步骤
1. 先调用至少一次 search_paper_content,检索关键公式、关键图表说明、关键发现、要点。
2. 如有需要,可调用 lookup_table_data 看表格数值。
3. 基于检索到的 chunk,输出严格 JSON

## 输出 JSON Schema
{
  "key_formulas": ["每个条目不超过 150 字,必须 [S1][S2] 标注出处"],
  "key_figures":  ["每个条目不超过 150 字,说明图表含义,必须 [S1] 标注出处"],
  "key_findings": ["关键发现/结论,必须 [S1][S2] 标注出处"],
  "takeaways":    ["值得关注的要点/启示,必须 [S1][S2] 标注出处"]
}

## 强制约束
- 每个列表至少 2 条,最多 8 条
- 每条 **必须** 至少出现一个 [Sn] 引用标记
- 不要输出 JSON 以外的任何内容
""",
}


@dataclass
class InterpretResult:
    """interpret agent 返回结构。"""
    # LLM 输出的结构化解读(concepts/comparisons/key_formulas 等)
    data: dict[str, Any]
    # 解析出的引用列表(可点击跳转 PDF,与 qa 路径 citations 同格式)
    citations: list[dict[str, Any]]
    # 检索到的 chunks 快照(供未来增量缓存用)
    chunks: list[dict[str, Any]]
    # agent trace(含 token 用量)
    trace: AgentTrace
    # 是否正常完成
    success: bool
    failure_reason: str = ""


async def run_interpret_agent(
    *,
    db: AsyncSession,
    paper_id: str,
    interpret_type: str,
    user_id: str = "",
    max_iterations: int = 6,
    request_id: str = "",
) -> InterpretResult:
    """运行深度解读 agent。

    Args:
        db: AsyncSession
        paper_id: 论文 ID
        interpret_type: concept / compare / key_info
        user_id: 用户 ID(传给 lead_agent 供 reading_assistant skill 用)
        max_iterations: 最多迭代次数(解读任务 4-6 轮通常足够)

    Returns:
        InterpretResult,含结构化 data + citations + chunks + trace
    """
    if interpret_type not in INTERPRET_TYPE_PROMPTS:
        return InterpretResult(
            data={},
            citations=[],
            chunks=[],
            trace=AgentTrace(),
            success=False,
            failure_reason=f"未知 interpret_type: {interpret_type},支持: {list(INTERPRET_TYPE_PROMPTS.keys())}",
        )

    # 通过 lead_agent 跑 ReAct 循环:
    # - skill_names=None → 所有 skill(paper_internal 必选,这样能调 search_paper_content)
    # - enable_critique=False: 解读不需要审稿意见
    # - 在 system_prompt 层叠加上 interpret_type 的强约束
    type_prompt = INTERPRET_TYPE_PROMPTS[interpret_type]

    # 包装:调用 lead_agent 的 wrapper_system_prompt 没开放,所以这里直接 run_lead_agent
    # 并依赖 SKILL.md + 下面注入的用户问题("按你的任务 prompt 执行解读")来驱动正确行为
    # 构造一个特殊的用户 question,把 interpret_type prompt 一起塞进去
    question = (
        f"请为这篇论文生成【{interpret_type}】深度解读。\n"
        f"严格遵循下面的执行规范与输出格式:\n"
        f"{type_prompt}\n\n"
        f"解读完成后,直接输出 JSON,不要写额外的说明文字。"
    )

    agent_result = await run_lead_agent(
        db=db,
        paper_id=paper_id,
        question=question,
        skill_names=None,  # 至少 paper_internal skill(含 search_paper_content)
        max_iterations=max_iterations,
        enable_critique=False,
        user_id=user_id,
        request_id=request_id,
    )

    # 从 agent_result.answer 里解析 JSON
    data: dict[str, Any] = {}
    answer = (agent_result.answer or "").strip()
    try:
        data = _parse_interpret_json(answer)
    except Exception as exc:
        logger.exception("interpret agent JSON 解析失败,answer 前 500 字符: %s", answer[:500])
        return InterpretResult(
            data={},
            citations=[],
            chunks=agent_result.chunks,
            trace=agent_result.trace,
            success=False,
            failure_reason=f"JSON 解析失败: {type(exc).__name__}: {exc}",
        )

    # 生成 citations:把 data 里所有字符串字段拼成一个"伪 answer",丢给
    # build_deterministic_citations 扫 [Sn] 标记,和 qa 路径完全一致
    try:
        from app.utils.qa_helpers import build_deterministic_citations
        pseudo_answer = _join_all_string_values(data)
        citations = build_deterministic_citations(pseudo_answer, agent_result.chunks)
    except Exception as exc:
        logger.warning("interpret agent citations 构造失败: %s", exc)
        citations = []

    return InterpretResult(
        data=data,
        citations=citations,
        chunks=agent_result.chunks,
        trace=agent_result.trace,
        success=agent_result.success and bool(data),
        failure_reason="" if (agent_result.success and data) else agent_result.trace.failure_reason,
    )


# ================================================================
# 内部辅助
# ================================================================

_JSON_CODE_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _parse_interpret_json(answer: str) -> dict[str, Any]:
    """从 LLM answer 里解析出解读 JSON,兼容 ```json 包裹 / 前后废话。"""
    if not answer:
        raise ValueError("LLM 回答为空")

    # 1) 优先找 ```json ... ``` 代码块
    m = _JSON_CODE_BLOCK_RE.search(answer)
    candidate = m.group(1) if m else None

    # 2) 没包裹时找最外层 {...}
    if not candidate:
        start = answer.find("{")
        end = answer.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"未在回答里找到 JSON 对象,回答: {answer[:200]!r}")
        candidate = answer[start : end + 1]

    data = json.loads(candidate)
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层不是对象: {type(data).__name__}")
    return data


def _join_all_string_values(obj: Any, _sep: str = " ") -> str:
    """递归把 dict/list 里的所有字符串拼起来,供 build_deterministic_citations 扫引用用。"""
    pieces: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            pieces.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return _sep.join(pieces)
