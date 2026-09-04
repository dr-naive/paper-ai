"""Harness Agent —— 基于 tool calling 的 ReAct loop。

设计要点:
- lead_agent 不预设工作流,由 LLM 根据 SKILL.md 自主决策调哪个 tool
- 与现有 UnifiedQAWorkflow 并存(后者是确定性工作流,期 4 才决定是否替换)
- max_iterations 防死循环,默认 5(足够覆盖多跳检索场景)
- tool 调用通过 LangChain 的 ToolMessage 协议,LLM 能正确解析工具返回
- 支持 critique subagent 委派:批判性问题通过 delegate_to_critique 虚拟 tool 触发
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.agents.critique_subagent import run_critique_subagent
from app.harness.agents.routing import ExecutionMode, decide_agent_route
from app.harness.skills.registry import SkillRegistry
from app.llm.client import get_llm_client, invoke_with_retry

logger = logging.getLogger(__name__)

# ====== 断点续连配置 ======
CHECKPOINT_KEY_PREFIX = "paperai:agent:checkpoint:"
CHECKPOINT_TTL_SECONDS = 3600  # checkpoint 保留 1 小时
MAX_RESUME_COUNT = 3  # 同一 request_id 最多恢复 3 次,防死循环

DEFAULT_MAX_ITERATIONS = 5

# critique 委派的虚拟 tool 名,lead_agent 在循环里识别它走特殊分支
DELEGATE_TO_CRITIQUE_TOOL_NAME = "delegate_to_critique"


class DelegateToCritiqueInput(BaseModel):
    """critique 委派 tool 的输入 schema。"""
    critique_question: str = Field(
        ..., description="要委派给 critique subagent 的批判性问题,如'评估创新性'或'写审稿意见'"
    )


def _make_delegate_to_critique_tool() -> StructuredTool:
    """创建 critique 委派的虚拟 tool(仅用于让 LLM 知道有这个能力,实际执行在 lead_agent 循环里特殊处理)。"""
    async def _placeholder(critique_question: str) -> str:
        # 实际不会执行到这里,lead_agent 循环会拦截
        return f"(internal) critique 委派被触发: {critique_question}"

    return StructuredTool.from_function(
        _placeholder,
        name=DELEGATE_TO_CRITIQUE_TOOL_NAME,
        description=(
            "委派给 critique subagent 处理批判性问题。"
            "用于:写审稿意见、评估创新性、批判性分析、找论文不足。"
            "调用前应先用其他 tool 收集论文信息(元数据/正文/表格),"
            "本工具会基于已收集的证据生成审稿意见。"
            "输入:critique_question=具体的批判性问题。"
        ),
        args_schema=DelegateToCritiqueInput,
        coroutine=_placeholder,
    )


@dataclass
class AgentTrace:
    """单次 agent 运行的轨迹信息,供调试与未来 trace 展示。"""
    iterations: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)  # [{name, args, elapsed_ms, ok}]
    total_ms: float = 0.0
    failure_reason: str = ""
    final_answer: str = ""
    # 轻量级应用内 tracing:累计 LLM 调用 token 用量/次数
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AgentResult:
    """lead_agent 的返回结构。"""
    answer: str
    trace: AgentTrace
    # agent 是否成功完成(True=正常结束,False=达到 max_iter 或出错)
    success: bool
    # 检索类 tool 返回的 chunks,供上层生成 citations / confidence 用
    chunks: list[dict[str, Any]] = field(default_factory=list)


def _accumulate_token_usage(trace: AgentTrace, message: Any) -> None:
    """从 LLM 返回 AIMessage 里抽取 token 用量累加到 trace。

    兼容两种返回格式:
    - 标准 LangChain/LangSmith 兼容: message.usage_metadata = {input/output/total_tokens}
    - qwen(通义千问 DashScope OpenAI 兼容): message.response_metadata['token_usage']
      = {prompt_tokens, completion_tokens, total_tokens}
    """
    trace.llm_calls += 1
    usage: dict[str, Any] = {}
    # 1) 优先标准字段
    std = getattr(message, "usage_metadata", None)
    if isinstance(std, dict) and std:
        usage = std
    else:
        # 2) qwen 等兼容接口放 response_metadata['token_usage']
        rm = getattr(message, "response_metadata", None) or {}
        if isinstance(rm, dict) and isinstance(rm.get("token_usage"), dict):
            usage = rm["token_usage"]
    if not usage:
        return
    prompt_k = "input_tokens" if "input_tokens" in usage else "prompt_tokens"
    completion_k = "output_tokens" if "output_tokens" in usage else "completion_tokens"
    trace.input_tokens += int(usage.get(prompt_k) or 0)
    trace.output_tokens += int(usage.get(completion_k) or 0)
    trace.total_tokens += int(usage.get("total_tokens") or (
        int(usage.get(prompt_k) or 0) + int(usage.get(completion_k) or 0)
    ))


# ====== 错误信息用户友好化 ======

# 技术错误 → 用户可读消息的映射规则
_ERROR_RULES: list[tuple[str, str]] = [
    # 网络/连接类
    ("connection error", "AI 服务网络连接失败，请稍后重试"),
    ("connect error", "AI 服务网络连接失败，请稍后重试"),
    ("timeout", "请求超时，请稍后重试或简化问题"),
    ("timed out", "请求超时，请稍后重试或简化问题"),
    # 鉴权/配额类
    ("401", "AI 服务认证失败，请联系管理员"),
    ("403", "AI 服务拒绝访问，请联系管理员"),
    ("429", "AI 服务请求过多，请稍等片刻再试"),
    ("rate limit", "AI 服务请求过多，请稍等片刻再试"),
    ("quota", "AI 服务配额已用尽，请联系管理员"),
    # 服务端错误
    ("502", "AI 服务暂时不可用，请稍后重试"),
    ("503", "AI 服务暂时不可用，请稍后重试"),
    ("504", "AI 服务网关超时，请稍后重试"),
    ("overloaded", "AI 服务繁忙，请稍后重试"),
    # 内容类
    ("content filter", "问题内容被安全策略拦截，请调整后重试"),
    ("maximum context", "对话过长，请尝试新建会话或简化问题"),
    ("context length", "对话过长，请尝试新建会话或简化问题"),
]


def friendly_error_message(stage: str, raw_message: str) -> str:
    """把技术错误消息转译成用户可读的友好消息。"""
    msg_lower = raw_message.lower()
    for keyword, friendly in _ERROR_RULES:
        if keyword in msg_lower:
            return friendly
    # 未匹配到已知规则,根据 stage 给通用消息
    stage_messages = {
        "loading_context": "读取论文信息失败，请刷新页面重试",
        "agent": "AI 分析失败，请稍后重试或换一种问法",
        "generating": "生成回答失败，请稍后重试",
        "persisting": "保存回答失败，但回答已生成",
    }
    return stage_messages.get(stage, "回答生成失败，请稍后重试")


# ====== 断点续连:messages 序列化 / checkpoint 存取 ======

def _serialize_messages(messages: list) -> list[dict[str, Any]]:
    """把 LangChain messages 序列化为可 JSON 化的 dict 列表。"""
    result: list[dict[str, Any]] = []
    for msg in messages:
        d: dict[str, Any] = {"type": msg.type, "content": msg.content}
        if isinstance(msg, AIMessage) and msg.tool_calls:
            d["tool_calls"] = msg.tool_calls
        elif isinstance(msg, ToolMessage):
            d["tool_call_id"] = msg.tool_call_id
            d["name"] = msg.name or ""
        result.append(d)
    return result


def _deserialize_messages(data: list[dict[str, Any]]) -> list:
    """从 dict 列表重建 LangChain messages。"""
    messages: list = []
    for d in data:
        t = d.get("type", "")
        if t == "system":
            messages.append(SystemMessage(content=d["content"]))
        elif t == "human":
            messages.append(HumanMessage(content=d["content"]))
        elif t == "ai":
            messages.append(AIMessage(content=d["content"], tool_calls=d.get("tool_calls", [])))
        elif t == "tool":
            messages.append(ToolMessage(
                content=d["content"],
                tool_call_id=d.get("tool_call_id", ""),
                name=d.get("name", ""),
            ))
    return messages


async def _save_checkpoint(
    request_id: str,
    *,
    messages: list,
    iteration: int,
    collected_chunks: list[dict[str, Any]],
    collected_evidence: list[str],
    collected_metadata: str,
    resume_count: int,
) -> None:
    """把当前 agent 状态快照写入 Redis,崩溃后可恢复。Redis 不可用时静默跳过。"""
    if not request_id:
        return
    from app.redis_client import set_json
    checkpoint = {
        "messages": _serialize_messages(messages),
        "iteration": iteration,
        "collected_chunks": collected_chunks,
        "collected_evidence": collected_evidence,
        "collected_metadata": collected_metadata,
        "resume_count": resume_count,
    }
    ok = await set_json(
        f"{CHECKPOINT_KEY_PREFIX}{request_id}",
        checkpoint,
        CHECKPOINT_TTL_SECONDS,
    )
    if ok:
        logger.debug("checkpoint 已保存 request_id=%s iter=%d", request_id, iteration)


async def _load_checkpoint(request_id: str) -> Optional[dict[str, Any]]:
    """从 Redis 读取 checkpoint,不存在或 Redis 不可用返回 None。"""
    if not request_id:
        return None
    from app.redis_client import get_json
    return await get_json(f"{CHECKPOINT_KEY_PREFIX}{request_id}")


async def _delete_checkpoint(request_id: str) -> None:
    """正常完成后删除 checkpoint。"""
    if not request_id:
        return
    try:
        from app.redis_client import get_async_redis
        await get_async_redis().delete(f"{CHECKPOINT_KEY_PREFIX}{request_id}")
    except Exception:
        pass  # 删除失败不影响结果


# ====== 长度上限(控制 token 预算) ======
_PROJ_MEMORY_MAXLEN = 1500   # 长期记忆 summary + notes 拼接后最长字符
_PROJ_PAPERS_MAXLEN = 1500   # 文档库摘要最长字符
_PROJ_ARTIFACTS_MAXLEN = 1000  # 最近写作产物摘要最长字符


@dataclass
class _ProjectContext:
    """_load_project_context 的内部分层返回值,方便单元测试。"""
    project_id: str
    title: str
    research_topic: str
    phase: str
    status: str
    memory_summary: str = ""
    memory_notes_preview: list[dict] = field(default_factory=list)
    papers_preview: list[dict] = field(default_factory=list)
    recent_artifacts: list[dict] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        """格式化为 system prompt 中的上下文块,带长度截断。"""
        lines: list[str] = [
            "## 当前研究项目(Project Context)",
            f"- 项目名: {self.title}",
            f"- 研究主题: {self.research_topic}",
            f"- 当前阶段: {self.phase} | 状态: {self.status}",
        ]

        # 1. 长期记忆
        if self.memory_summary or self.memory_notes_preview:
            lines.append("- 项目长期记忆(用户调研要点):")
            if self.memory_summary:
                s = self.memory_summary[:_PROJ_MEMORY_MAXLEN]
                lines.append(f"  摘要: {s}")
            if self.memory_notes_preview:
                lines.append("  最近要点(部分):")
                buf: list[str] = []
                used = 0
                for n in reversed(self.memory_notes_preview[-12:]):
                    # 从最新开始,加完后若超 _PROJ_MEMORY_MAXLEN 剩余额度就停
                    tag = f"[{n.get('tag', '')}] " if n.get("tag") else ""
                    t = (n.get("time", "") or "")[:16]
                    text = (n.get("text", "") or "")[:200]
                    source = ""
                    if n.get("paper_title"):
                        source = f" (来源: {str(n['paper_title'])[:60]}"
                        if n.get("page"):
                            source += f", p.{n['page']}"
                        source += ")"
                    one = f"  · {t} {tag}{text}{source}"
                    if used + len(one) > _PROJ_MEMORY_MAXLEN:
                        break
                    buf.append(one)
                    used += len(one)
                lines.extend(reversed(buf))

        # 2. 项目文档库
        if self.papers_preview:
            lines.append(f"- 项目文档库(已加入 {len(self.papers_preview)} 篇论文,部分如下):")
            used = 0
            for p in self.papers_preview[:10]:
                title = (p.get("title", "") or "")[:100]
                role = p.get("role", "related")
                authors = (p.get("authors", "") or "")[:50]
                note = (p.get("notes", "") or "")[:80]
                card_summary = (p.get("card_summary", "") or "")[:160]
                paper_id = p.get("paper_id", "")
                reading_plan = p.get("reading_plan") or {}
                one = f"  · [{role}] {title} (paper_id={paper_id})"
                if authors:
                    one += f" ({authors})"
                if note:
                    one += f" - 备注: {note}"
                if card_summary:
                    one += f" - 阅读卡片: {card_summary}"
                if reading_plan:
                    one += (
                        f" - 阅读队列: #{reading_plan.get('order', '?')}"
                        f"/{reading_plan.get('status', 'pending')}"
                    )
                if used + len(one) > _PROJ_PAPERS_MAXLEN:
                    break
                lines.append(one)
                used += len(one)

        # 3. 最近写作产物
        if self.recent_artifacts:
            lines.append(f"- 最近写作产物(最近 {len(self.recent_artifacts)} 份):")
            used = 0
            for a in self.recent_artifacts:
                atype = a.get("artifact_type", "")
                title = (a.get("title", "") or "")[:100]
                ver = a.get("version", 1)
                updated = (a.get("updated_at", "") or "")[:16]
                one = f"  · [{atype}] {title} (v{ver}, 最近更新 {updated})"
                if used + len(one) > _PROJ_ARTIFACTS_MAXLEN:
                    break
                lines.append(one)
                used += len(one)

        return "\n".join(lines)


async def _load_project_context(
    db: AsyncSession, project_id: str, user_id: str = ""
) -> str:
    """加载研究项目上下文并返回可直接拼到 system prompt 的 markdown 字符串。

    所有输出都带长度上限,避免 token 爆炸:
    - 长期记忆:summary 限 1500 字,notes 最多 12 条,总字符 <= 1500
    - 文档库:最多显示前 10 篇,总字符 <= 1500
    - 最近产物:最多最近 3 份,总字符 <= 1000
    """
    from sqlalchemy import select as _s
    from app.models.project import ResearchProject, ProjectPaper, WritingArtifact
    from app.models.paper import Paper

    project = await db.get(ResearchProject, project_id)
    if project is None or (user_id and project.user_id != user_id):
        # 所有权不匹配:返回空串,不暴露存在性,agent 后续会因为找不到 project tool 而自然失败
        logger.warning("_load_project_context: project %s 不存在或 user_id 不匹配", project_id)
        return ""

    memory = project.memory or {"summary": "", "notes": []}
    mem_summary = memory.get("summary", "") or ""
    mem_notes = memory.get("notes") or []

    # 文档库预览
    pp_rows = (await db.execute(
        _s(ProjectPaper, Paper)
        .join(Paper, Paper.id == ProjectPaper.paper_id)
        .where(ProjectPaper.project_id == project_id)
        .order_by(ProjectPaper.reading_priority.desc(), ProjectPaper.added_at.desc())
    )).all()
    papers_preview = []
    for pp, paper in pp_rows:
        papers_preview.append({
            "paper_id": str(paper.id),
            "title": paper.title,
            "authors": paper.authors,
            "role": pp.role,
            "notes": pp.notes or "",
            "card_summary": str((pp.analysis_card or {}).get("summary") or ""),
            "reading_plan": pp.reading_plan or {},
        })

    # 最近写作产物(最近 3 份,按 updated_at 倒序)
    art_rows = (await db.execute(
        _s(WritingArtifact)
        .where(WritingArtifact.project_id == project_id)
        .order_by(WritingArtifact.updated_at.desc())
        .limit(3)
    )).scalars().all()
    recent_artifacts = []
    for a in art_rows:
        recent_artifacts.append({
            "artifact_type": a.artifact_type,
            "title": a.title,
            "version": a.version,
            "updated_at": a.updated_at.isoformat() if a.updated_at else "",
        })

    ctx = _ProjectContext(
        project_id=project.id,
        title=project.title,
        research_topic=project.research_topic,
        phase=project.phase,
        status=project.status,
        memory_summary=mem_summary,
        memory_notes_preview=list(mem_notes),
        papers_preview=papers_preview,
        recent_artifacts=recent_artifacts,
    )
    return ctx.to_prompt_block()


async def run_lead_agent(
    *,
    db: AsyncSession,
    paper_id: str,
    question: str,
    skill_names: Optional[list[str]] = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    history_context: str = "",
    enable_thinking: bool = False,
    enable_critique: bool = True,
    user_id: str = "",
    project_id: str = "",
    request_id: str = "",
    on_token: Optional[Any] = None,
) -> AgentResult:
    """运行 lead_agent 的 ReAct loop。

    Args:
        db: 异步数据库 session,会注入到 tool 工厂
        paper_id: 当前论文 id,LLM 需要把它作为 tool 参数
        question: 用户问题
        skill_names: 启用的 skill 列表,默认全部已注册 skill
        max_iterations: 最大 tool-calling 轮次,防死循环
        history_context: 历史对话上下文(可选)
        enable_thinking: 是否开启 reasoning tokens(qwen 支持)
        enable_critique: 是否启用 critique subagent 委派能力
        user_id: 当前用户 id,供 reading_assistant.get_reading_progress 使用
        project_id: (可选)研究项目 id。非空时:
                    1) 注入项目上下文到 system prompt(文档库/长期记忆/最近产物)
                    2) 追加 project_* scope tools(加论文/记笔记/存产物 等)
                    3) 作为写作产物的 owner 关联
        request_id: 请求唯一标识,用于断点续连。传入相同 request_id 可从上次中断处恢复
        on_token: 流式回调,传 None 时用 ainvoke(非流式);传 callback 时用 astream,
                  callback 接收每个 text 增量(仅最终答案轮次会触发)

    Returns:
        AgentResult,包含最终回答与运行轨迹
    """
    started_at = time.perf_counter()
    trace = AgentTrace()

    # 默认启用全部 skill
    if skill_names is None:
        skill_names = SkillRegistry.list_skills()

    registry = SkillRegistry(db)
    tools = list(registry.load_tools(skill_names))

    # ========== Project 上下文 + Project-scope tools 注入 ==========
    project_context_str = ""
    if project_id:
        from app.harness.tools.literature_research import make_project_tools
        # 1. 读 project_context(文档库 / 长期记忆 / 最近产物),带长度上限截断
        project_context_str = await _load_project_context(db, project_id, user_id)
        # 2. 追加 project_* tools
        project_tools = make_project_tools(db, project_id, user_id)
        tools.extend(project_tools)
        # 3. tool 名去重(按 name 合并,后注册的覆盖先注册,避免 project_ 前缀被其他 skill 占用)
        _dedup: dict[str, Any] = {}
        for t in tools:
            _dedup[t.name] = t
        tools = list(_dedup.values())

    # 启用 critique 委派时,加虚拟 tool 让 LLM 知道有这个能力
    if enable_critique:
        tools = list(tools) + [_make_delegate_to_critique_tool()]

    if not tools:
        # 没有 tool 可用时,退化为直接 LLM 回答
        logger.warning("lead_agent 无可用 tool,退化为直接 LLM 回答")
        answer = await _direct_llm_answer(question, paper_id, history_context, enable_thinking)
        trace.final_answer = answer
        trace.total_ms = round((time.perf_counter() - started_at) * 1000, 3)
        return AgentResult(answer=answer, trace=trace, chunks=[], success=True)

    # 构造 tool 名称 -> tool 实例的映射,便于按名调用
    tool_map = {t.name: t for t in tools}

    # 拼装 system prompt:SKILL.md + 行为规范 + paper_id 提示 + project_context
    system_prompt = registry.build_system_prompt(skill_names)
    system_prompt += "\n\n## 当前上下文\n"
    if paper_id:
        system_prompt += (
            f"当前论文 paper_id: `{paper_id}`\n"
            f"调用单篇论文 tool 时,paper_id 参数请用这个值,不要让用户自己提供。\n"
        )
    if project_id:
        system_prompt += (
            f"当前研究项目 project_id: `{project_id}`\n"
            f"这是一个写作全流程项目。与研究项目相关的操作请用 project_ 前缀的 tool。\n"
        )
        if not paper_id:
            system_prompt += (
                "当前项目文档库为空。可以先澄清选题、保存研究任务书，并使用 external_literature "
                "的 search_arxiv/search_semantic_scholar 检索外部候选文献；"
                "此时不要调用要求 paper_id 的单篇论文 tool。\n"
            )
        if project_context_str:
            system_prompt += "\n" + project_context_str + "\n"
    if user_id:
        system_prompt += (
            f"当前用户 user_id: `{user_id}`\n"
            f"调用 get_reading_progress 时,user_id 参数请用这个值。\n"
        )
    if enable_critique:
        system_prompt += (
            "\n## 子 agent 委派\n"
            "对于批判性问题(写审稿意见、评估创新性、找不足、critique),"
            "先用信息检索类 tool 收集论文信息,再调 `delegate_to_critique` 委派给 critique subagent。"
            "不要自己直接写审稿意见,critique subagent 更专业。\n"
        )
    if history_context:
        system_prompt += f"\n历史对话:\n{history_context}\n"

    messages: list = [SystemMessage(content=system_prompt), HumanMessage(content=question)]

    # bind_tools 拿到支持 tool calling 的 LLM 实例
    llm_with_tools = get_llm_client().bind_tools(tools)

    # 累积所有 tool 返回的证据,供 critique subagent 使用
    collected_evidence: list[str] = []
    collected_metadata: str = ""
    # 累积 search_paper_content 返回的 chunks,供上层生成 citations / confidence 用
    collected_chunks: list[dict[str, Any]] = []

    # ====== 断点续连:尝试从 checkpoint 恢复 ======
    resume_count = 0
    start_iteration = 1
    if request_id:
        checkpoint = await _load_checkpoint(request_id)
        if checkpoint:
            resume_count = checkpoint.get("resume_count", 0)
            if resume_count >= MAX_RESUME_COUNT:
                logger.warning(
                    "checkpoint 恢复次数已达上限 %d,放弃恢复 request_id=%s",
                    MAX_RESUME_COUNT, request_id,
                )
            else:
                # 恢复 messages 和累积状态
                messages = _deserialize_messages(checkpoint.get("messages", []))
                collected_chunks = checkpoint.get("collected_chunks", [])
                collected_evidence = checkpoint.get("collected_evidence", [])
                collected_metadata = checkpoint.get("collected_metadata", "")
                start_iteration = checkpoint.get("iteration", 0) + 1
                resume_count += 1
                logger.info(
                    "从 checkpoint 恢复 request_id=%s,从迭代 %d 继续(第 %d 次恢复)",
                    request_id, start_iteration, resume_count,
                )

    for iteration in range(start_iteration, max_iterations + 1):
        trace.iterations = iteration
        logger.info("lead_agent 迭代 %d/%d,question=%s", iteration, max_iterations, question[:50])

        try:
            if on_token is not None:
                # 流式模式:用 astream,边接收边推送 content 增量
                from langchain_core.messages import AIMessageChunk
                full_chunk: Optional[AIMessageChunk] = None
                async for chunk in llm_with_tools.astream(messages):
                    if full_chunk is None:
                        full_chunk = chunk
                    else:
                        full_chunk = full_chunk + chunk
                    # 有 content 且无 tool_call 时推送(最终答案轮次)
                    if chunk.content and not getattr(chunk, "tool_call_chunks", None):
                        on_token(chunk.content)
                response: AIMessage = full_chunk if full_chunk is not None else AIMessage(content="")
            else:
                response: AIMessage = await invoke_with_retry(llm_with_tools, messages)
        except Exception as exc:
            logger.exception("lead_agent LLM 调用失败 iter=%d", iteration)
            trace.failure_reason = f"LLM 调用失败: {type(exc).__name__}: {exc}"
            trace.total_ms = round((time.perf_counter() - started_at) * 1000, 3)
            return AgentResult(answer="", trace=trace, success=False)

        # 应用内 tracing:累计 LLM token 用量
        _accumulate_token_usage(trace, response)

        messages.append(response)

        # 无 tool_call → LLM 已生成最终回答
        if not response.tool_calls:
            answer = (response.content or "").strip()
            if not answer:
                # 极端情况:LLM 既无 tool_call 也无 content
                trace.failure_reason = "LLM 返回空内容且无 tool_call"
                trace.total_ms = round((time.perf_counter() - started_at) * 1000, 3)
                return AgentResult(answer="", trace=trace, success=False)
            trace.final_answer = answer
            trace.total_ms = round((time.perf_counter() - started_at) * 1000, 3)
            logger.info("lead_agent 完成,共 %d 轮迭代", iteration)
            # 正常完成 → 删除 checkpoint(不再需要恢复)
            await _delete_checkpoint(request_id)
            return AgentResult(answer=answer, trace=trace, success=True, chunks=collected_chunks)

        # 有 tool_call → 执行所有 tool,把结果作为 ToolMessage 喂回
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]
            tool_started_at = time.perf_counter()

            # paper_id 兜底:若 LLM 没传 paper_id,用当前上下文的值补上
            if "paper_id" in tool_args and not tool_args.get("paper_id"):
                tool_args["paper_id"] = paper_id

            tool_trace_entry: dict[str, Any] = {
                "name": tool_name,
                "args": tool_args,
                "ok": False,
            }
            trace.tool_calls.append(tool_trace_entry)

            if tool_name not in tool_map:
                tool_result = f"错误: 未知工具 {tool_name},可用工具: {list(tool_map.keys())}"
                logger.warning("lead_agent 调用了未知 tool: %s", tool_name)
            elif tool_name == DELEGATE_TO_CRITIQUE_TOOL_NAME:
                # critique 委派特殊分支:不调虚拟 tool 的 placeholder,
                # 而是调真实的 critique_subagent,把累积证据传过去
                critique_question = tool_args.get("critique_question", question)
                try:
                    critique_result = await run_critique_subagent(
                        question=critique_question,
                        evidence="\n---\n".join(collected_evidence) if collected_evidence else "",
                        paper_metadata=collected_metadata,
                        history_context=history_context,
                    )
                    tool_result = critique_result.review
                    tool_trace_entry["ok"] = critique_result.success
                    tool_trace_entry["critique_scores"] = {
                        "innovation": critique_result.innovation_score,
                        "rigor": critique_result.rigor_score,
                        "clarity": critique_result.clarity_score,
                    }
                except Exception as exc:
                    tool_result = f"critique subagent 失败: {type(exc).__name__}: {exc}"
                    logger.exception("lead_agent 调用 critique subagent 失败")
            else:
                try:
                    tool_result = await tool_map[tool_name].ainvoke(tool_args)
                    tool_trace_entry["ok"] = True
                    # 累积证据:把 tool 返回加到 collected_evidence
                    if tool_result:
                        collected_evidence.append(f"[{tool_name}] {tool_result}")
                        # 若是 get_paper_metadata,单独存一份供 critique 用
                        if tool_name == "get_paper_metadata":
                            collected_metadata = str(tool_result)
                        # 若是 search_paper_content,解析出 chunks 供上层生成 citations
                        if tool_name in {"search_paper_content", "project_search_content"}:
                            try:
                                parsed = json.loads(tool_result)
                                retrieved = parsed.get("chunks", [])
                                if retrieved:
                                    collected_chunks.extend(retrieved)
                            except (json.JSONDecodeError, TypeError):
                                pass
                except Exception as exc:
                    tool_result = f"工具执行失败: {type(exc).__name__}: {exc}"
                    logger.exception("lead_agent 调用 tool %s 失败", tool_name)

            tool_trace_entry["elapsed_ms"] = round(
                (time.perf_counter() - tool_started_at) * 1000, 3
            )
            messages.append(
                ToolMessage(content=str(tool_result), tool_call_id=tool_call_id)
            )
            logger.info(
                "lead_agent 调用 %s(%s) ok=%s 耗时=%.1fms",
                tool_name,
                tool_args,
                tool_trace_entry["ok"],
                tool_trace_entry["elapsed_ms"],
            )

        # 每轮迭代后保存 checkpoint(崩溃后可从此处恢复)
        await _save_checkpoint(
            request_id,
            messages=messages,
            iteration=iteration,
            collected_chunks=collected_chunks,
            collected_evidence=collected_evidence,
            collected_metadata=collected_metadata,
            resume_count=resume_count,
        )

    # 达到 max_iterations 仍未结束,让 LLM 基于已有信息做最终回答
    logger.warning("lead_agent 达到 max_iterations=%d,强制收尾", max_iterations)
    trace.failure_reason = f"达到最大迭代次数 {max_iterations}"
    # 最后一轮不带 tools,强制 LLM 收尾
    if on_token is not None:
        from langchain_core.messages import AIMessageChunk
        full_chunk: Optional[AIMessageChunk] = None
        async for chunk in get_llm_client().client.astream(messages):
            if full_chunk is None:
                full_chunk = chunk
            else:
                full_chunk = full_chunk + chunk
            if chunk.content:
                on_token(chunk.content)
        final_response = full_chunk if full_chunk is not None else AIMessage(content="")
    else:
        final_response = await invoke_with_retry(get_llm_client().client, messages)
    _accumulate_token_usage(trace, final_response)
    answer = (final_response.content or "").strip()
    trace.final_answer = answer
    trace.total_ms = round((time.perf_counter() - started_at) * 1000, 3)
    # 强制收尾也删 checkpoint(已有最终答案,不再需要恢复)
    await _delete_checkpoint(request_id)
    return AgentResult(answer=answer, trace=trace, success=False, chunks=collected_chunks)


async def _direct_llm_answer(
    question: str, paper_id: str, history_context: str, enable_thinking: bool
) -> str:
    """无 tool 可用时的退化路径:直接 LLM 回答。"""
    system = "你是一个论文阅读助手,基于上下文回答用户问题。"
    if history_context:
        system += f"\n\n历史对话:\n{history_context}"
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"(paper_id={paper_id}) {question}"),
    ]
    response = await get_llm_client().client.ainvoke(messages)
    return (response.content or "").strip()


# ====== 意图分析 + 多意图综合 ======

# 意图类型常量
INTENT_FACTUAL = "factual"                # 事实查询(可从论文直接找到)
INTENT_ANALYTICAL = "analytical"          # 分析型(需要推理/对比/评价)
INTENT_MULTI = "multi_intent"             # 多意图(需分解)
INTENT_CLARIFY = "needs_clarification"    # 需要澄清(问题模糊)

_INTENT_ANALYSIS_PROMPT = """你是一个论文问答系统的意图分析器。分析用户的问题,返回 JSON。

判断规则:
- factual: 事实查询,可从论文直接找到答案(如"用了什么算法""实验数据集是什么")
- analytical: 需要分析/对比/评价(如"这个方法有什么创新""和XXX相比有什么优势""为什么选择这个方案")
- multi_intent: 问题包含多个独立子问题(如"方法是什么?实验结果如何?有什么局限性?")
- needs_clarification: 问题太模糊或缺少关键信息,无法直接回答(如"帮我看看这个""这个怎么样")

复杂度判断:
- low: 简单事实,1-3句话能答完
- medium: 需要一定解释,2-3段
- high: 需要深入分析,结构化格式(标题+段落+列表)

返回严格 JSON(不要 markdown 代码块):
{"type": "factual|analytical|multi_intent|needs_clarification", "complexity": "low|medium|high", "sub_questions": ["子问题1", "子问题2"], "clarification_question": "向用户的追问"}

注意:sub_questions 仅 multi_intent 时填,clarification_question 仅 needs_clarification 时填,其他时候留空数组或空字符串。"""


async def analyze_question_intent(
    question: str,
    history_context: str = "",
) -> dict[str, Any]:
    """用 LLM 分析问题意图,返回结构化 JSON。

    Returns:
        {"type": str, "complexity": str, "sub_questions": list, "clarification_question": str}
    """
    import json as _json
    import re as _re

    user_msg = f"历史对话:\n{history_context}\n\n用户问题: {question}" if history_context else f"用户问题: {question}"
    messages: list = [
        SystemMessage(content=_INTENT_ANALYSIS_PROMPT),
        HumanMessage(content=user_msg),
    ]
    try:
        response = await invoke_with_retry(get_llm_client().client, messages)
        raw = (response.content or "").strip()
        # 提取 JSON(qwen 可能包在 markdown 代码块里)
        json_match = _re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, _re.DOTALL)
        if json_match:
            result = _json.loads(json_match.group())
        else:
            result = _json.loads(raw)
        # 补全缺失字段
        result.setdefault("type", INTENT_FACTUAL)
        result.setdefault("complexity", "medium")
        result.setdefault("sub_questions", [])
        result.setdefault("clarification_question", "")
        logger.info("意图分析: type=%s complexity=%s sub_questions=%d",
                    result["type"], result["complexity"], len(result["sub_questions"]))
        return result
    except Exception as exc:
        logger.warning("意图分析失败,回退到 factual: %s", exc)
        return {
            "type": INTENT_FACTUAL,
            "complexity": "medium",
            "sub_questions": [],
            "clarification_question": "",
        }


# 回答深度指引(注入到 question 前缀,不改 run_lead_agent 签名)
_DEPTH_HINTS = {
    "low": "[回答要求:简洁直接,1-3句话,不要多余的背景介绍] ",
    "medium": "[回答要求:适中详细,2-3段落,包含关键细节和引用] ",
    "high": "[回答要求:深入分析,使用结构化格式(标题+段落+列表),包含完整论证和引用] ",
}


# ====== 规则版意图预判(避免对所有问题都调 LLM 做意图分析) ======
# 多意图连词:问题里出现这些词,且含多个子问题
_MULTI_INTENT_CONJ = re.compile(r"[?？].{0,40}(?:和|以及|还有|同时|另外|分别|、).{0,40}[?？]")
# 多个问号
_MULTI_QUESTION_MARK = re.compile(r"[?？].{5,}[?？]")
# 模糊问题:太短或只有代词
_VAGUE_PATTERNS = re.compile(
    r"^(?:这个|那个|它|帮我看|帮我看看|看看|怎么样|如何呢|啥|什么情况)\s*[?？]?$"
    r"|^(?:帮我看看|看看|看一下|瞧瞧)(?:这个|那个|它)?$"
)
# 分析型关键词
_ANALYTICAL_PATTERNS = re.compile(
    r"分析|对比|比较|评价|评估|创新|局限|不足|优势|劣势|为什么|为何|如何"
    r"|analyze|compare|evaluate|innov|limitation|advantage|disadvantage|why|how",
    re.IGNORECASE,
)


def _quick_intent_detect(question: str) -> dict[str, Any]:
    """规则版意图预判,覆盖大部分场景,避免调 LLM。

    返回与 analyze_question_intent 相同的结构。
    无法确定时返回 None,由调用方决定是否调 LLM。
    """
    q = question.strip()
    if not q:
        return None

    # 1. 模糊问题 → needs_clarification
    if len(q) < 6 or _VAGUE_PATTERNS.match(q):
        return {
            "type": INTENT_CLARIFY,
            "complexity": "low",
            "sub_questions": [],
            "clarification_question": "您能具体说明一下想了解这篇论文的哪个方面吗?例如:研究方法、实验结果、创新点、局限性等。",
        }

    # 2. 多意图:多个问号 + 连词
    if _MULTI_INTENT_CONJ.search(q) or _MULTI_QUESTION_MARK.search(q):
        return None  # 多意图需要 LLM 拆分子问题,不能省

    # 3. 分析型 vs 事实型
    if _ANALYTICAL_PATTERNS.search(q):
        return {
            "type": INTENT_ANALYTICAL,
            "complexity": "high",
            "sub_questions": [],
            "clarification_question": "",
        }

    # 4. 默认事实型,复杂度根据长度判断
    complexity = "low" if len(q) < 20 else "medium"
    return {
        "type": INTENT_FACTUAL,
        "complexity": complexity,
        "sub_questions": [],
        "clarification_question": "",
    }


async def synthesize_multi_intent_answer(
    question: str,
    sub_answers: list[str],
    complexity: str,
) -> str:
    """把多个子问题的答案综合成一个完整、连贯的回答。"""
    # 限制每个子答案长度,避免综合 prompt 过长导致 LLM 超时
    _MAX_SUB_ANSWER_LEN = 800
    trimmed_answers = []
    for i, ans in enumerate(sub_answers):
        if not ans:
            continue
        if len(ans) > _MAX_SUB_ANSWER_LEN:
            ans = ans[:_MAX_SUB_ANSWER_LEN] + "..."
        trimmed_answers.append(f"### 子问题 {i + 1} 的回答:\n{ans}")

    if not trimmed_answers:
        return "抱歉,未能找到相关信息来回答您的问题。"

    sub_qa_text = "\n\n".join(trimmed_answers)

    depth_hint = _DEPTH_HINTS.get(complexity, _DEPTH_HINTS["medium"])
    prompt = f"""{depth_hint}

用户原始问题: {question}

以下是针对各子问题的检索结果,请综合成一个完整、连贯的回答:

{sub_qa_text}

要求:
1. 按逻辑顺序组织,不要简单拼接
2. 保留所有引用标记(如 [S1] [S2])
3. 如果子问题之间有关联,点明关联关系
4. 不要重复内容"""

    messages: list = [
        SystemMessage(content="你是一个论文问答助手,擅长综合多方面信息给出完整回答。"),
        HumanMessage(content=prompt),
    ]
    try:
        response = await invoke_with_retry(get_llm_client().client, messages)
        return (response.content or "").strip()
    except Exception as exc:
        logger.warning("多意图综合失败,回退拼接: %s", exc)
        return sub_qa_text

# ====== 流式版本:产出 SSE 兼容事件,供 worker/chat.py SSE 推送 ======

async def stream_lead_agent(
    *,
    db: AsyncSession,
    session_id: str,
    user_id: str,
    question: str,
    enable_thinking: bool = False,
    enable_critique: bool = True,
    project_id: str = "",
    request_id: str = "",
    history_context: str = "",
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """流式版本的 lead_agent,yield 与 UnifiedQAWorkflow.stream() 兼容的事件。

    事件格式:
    - ("status", {"stage": ..., "message": ...})
    - ("answer_delta", {"text": ...})
    - ("citations", {"items": [...]})
    - ("done", {message_id, intent, evidence_confidence, ...})
    - ("error", {"stage": ..., "message": ...})

    agent 的 ReAct 循环本身不逐 token 流式(用 ainvoke),
    但最终答案分块推送 answer_delta,让前端有流式打字效果。
    同时 agent_trace.tool_calls 让前端能看到 agent 调了哪些 tool。
    """
    import asyncio as _aio
    from datetime import datetime as _dt
    from sqlalchemy import select as _select, func as _func
    from app.utils.qa_helpers import (
        build_deterministic_citations as _build_citations,
        detect_metadata_intent as _detect_intent,
        calculate_evidence_confidence as _calc_confidence,
    )
    from app.models.chat import ChatSession as _ChatSession, ChatMessage as _ChatMessage

    # 1. 读取会话 + 历史
    yield "status", {"stage": "loading_context", "message": "正在读取论文与对话"}
    session_result = await db.execute(
        _select(_ChatSession).where(
            _ChatSession.id == session_id,
            _ChatSession.user_id == user_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        yield "error", {"stage": "loading_context", "message": "会话不存在或已过期，请刷新页面"}
        return
    # project_id 优先级:显式传入 > session 绑定。若都无则走原有单论文路径
    project_id = project_id or (str(session.project_id) if getattr(session, "project_id", None) else "")
    # paper_id:chat_sessions.paper_id 已改为 NULLABLE;project 模式下可能为 None
    # 此时需要任意一篇项目内论文作为"默认上下文"传给 tool 工厂(检索必须有具体 paper)
    paper_id: str
    if session.paper_id is None:
        if not project_id:
            yield "error", {
                "stage": "loading_context",
                "message": "会话缺少绑定的论文与项目,请刷新页面重试",
            }
            return
        # 从项目文档库挑一篇(优先 core,其次 reading_priority 最高的)
        from app.models.project import ProjectPaper as _PP
        from app.models.paper import Paper as _PPr
        # case 表达式:role = core 排在最前面
        _is_core = (_PP.role == "core")
        _pp_row = (await db.execute(
            _select(_PP, _PPr)
            .join(_PPr, _PPr.id == _PP.paper_id)
            .where(_PP.project_id == project_id)
            .order_by(
                _is_core.desc(),
                _PP.reading_priority.desc(),
                _PP.added_at.desc(),
            )
            .limit(1)
        )).first()
        if _pp_row is None:
            # 研究任务书、外部文献检索和候选筛选本来就发生在论文入库之前。
            # 空字符串明确表示“当前没有默认单篇论文”，后续强制走项目 ReAct 路径。
            paper_id = ""
        else:
            _pp, _paper = _pp_row
            paper_id = str(_paper.id)
    else:
        paper_id = str(session.paper_id)

    if not history_context:
        history_result = await db.execute(
            _select(_ChatMessage)
            .where(_ChatMessage.session_id == session_id)
            .order_by(_ChatMessage.order_index)
        )
        history_messages = history_result.scalars().all()
        history_context = "\n\n".join(
            f"用户: {m.question}\nAI: {m.answer}"
            for m in history_messages[-5:]
            if m.answer  # 过滤掉空回答(之前失败的 QA),避免污染 LLM 上下文
        )

    # 2. 快速路径:元数据问题直接查 DB,跳过 ReAct 循环
    _CHUNK_SIZE = 40  # 分块推送大小,快速路径和 ReAct 路径共用
    from app.models.paper import Paper as _Paper
    from app.utils.qa_helpers import detect_metadata_intent as _detect_intent
    metadata_field = _detect_intent(question)
    if metadata_field and paper_id:
        yield "status", {"stage": "fast_path", "message": "正在查询论文信息..."}

        paper_result = await db.execute(_select(_Paper).where(_Paper.id == paper_id))
        paper = paper_result.scalar_one_or_none()

        # 根据字段构造快速回答
        fast_answer = ""
        if paper:
            field_map = {
                "title": ("title", "标题"),
                "authors": ("authors", "作者"),
                "abstract": ("abstract", "摘要"),
                "keywords": ("keywords", "关键词"),
                "venue": ("venue", "发表期刊/会议"),
                "publication_year": ("publication_year", "发表年份"),
                "doi": ("doi", "DOI"),
            }
            col_name, label = field_map.get(metadata_field, (metadata_field, metadata_field))
            value = getattr(paper, col_name, None)
            if metadata_field == "keywords" and isinstance(value, list):
                value = "、".join(str(k) for k in value)
            if value:
                fast_answer = f"这篇论文的{label}是：{value}"
            else:
                fast_answer = f"这篇论文的{label}信息暂未录入。"

        if fast_answer:
            # 分块推送
            yield "status", {"stage": "generating", "message": "正在组织回答", "source_count": 0}
            for i in range(0, len(fast_answer), _CHUNK_SIZE):
                yield "answer_delta", {"text": fast_answer[i:i + _CHUNK_SIZE]}
                await _aio.sleep(0.02)

            # persist ChatMessage
            yield "status", {"stage": "persisting", "message": "正在保存回答"}
            message_count = await db.execute(
                _select(_func.count()).select_from(_ChatMessage)
                .where(_ChatMessage.session_id == session_id)
            )
            order_index = message_count.scalar() or 0
            message = _ChatMessage(
                session_id=session_id,
                order_index=order_index + 1,
                question=question,
                answer=fast_answer,
                citations=[],
                follow_up_questions=[],
                confidence=1.0,
            )
            db.add(message)
            if order_index == 0:
                session.title = question[:20] + ("..." if len(question) > 20 else "")
                session.updated_at = _dt.utcnow()
            await db.flush()
            message_id = str(message.id)
            await db.commit()

            yield "citations", {"items": []}
            yield "done", {
                "message_id": message_id,
                "intent": metadata_field,
                "sources": [],
                "evidence_confidence": 1.0,
                "confidence": 1.0,
                "confidence_type": "metadata_fast_path",
                "follow_up_pending": True,
                "trace_id": request_id,
                "agent_trace": {
                    "iterations": 0,
                    "tool_calls": [],
                    "total_ms": 0,
                    "llm_calls": 0,
                    "total_tokens": 0,
                    "fast_path": True,
                },
            }
            return

    # 3. 意图分析:先用规则预判(省 3-8s LLM 调用),规则无法判断时才调 LLM
    quick_intent = _quick_intent_detect(question)
    if quick_intent is not None:
        intent = quick_intent
        logger.info("规则预判意图: type=%s complexity=%s", intent["type"], intent["complexity"])
    else:
        yield "status", {"stage": "intent_analysis", "message": "正在分析问题意图..."}
        intent = await analyze_question_intent(question, history_context)
    intent_type = intent.get("type", INTENT_FACTUAL)
    complexity = intent.get("complexity", "medium")

    # ---- 路径 A: 澄清机制 ----
    if intent_type == INTENT_CLARIFY and intent.get("clarification_question"):
        clarification = intent["clarification_question"]
        yield "status", {"stage": "clarification", "message": "需要更多信息才能回答"}

        # 分块推送追问
        for i in range(0, len(clarification), _CHUNK_SIZE):
            yield "answer_delta", {"text": clarification[i:i + _CHUNK_SIZE]}
            await _aio.sleep(0.02)

        # persist ChatMessage
        yield "status", {"stage": "persisting", "message": "正在保存"}
        message_count = await db.execute(
            _select(_func.count()).select_from(_ChatMessage)
            .where(_ChatMessage.session_id == session_id)
        )
        order_index = message_count.scalar() or 0
        message = _ChatMessage(
            session_id=session_id,
            order_index=order_index + 1,
            question=question,
            answer=clarification,
            citations=[],
            follow_up_questions=[],
            confidence=0.0,
        )
        db.add(message)
        if order_index == 0:
            session.title = question[:20] + ("..." if len(question) > 20 else "")
            session.updated_at = _dt.utcnow()
        await db.flush()
        message_id = str(message.id)
        await db.commit()

        yield "citations", {"items": []}
        yield "done", {
            "message_id": message_id,
            "intent": "clarification",
            "sources": [],
            "evidence_confidence": 0.0,
            "confidence": 0.0,
            "confidence_type": "clarification",
            "follow_up_pending": False,
            "trace_id": request_id,
            "agent_trace": {
                "iterations": 0,
                "tool_calls": [],
                "total_ms": 0,
                "llm_calls": 1,
                "total_tokens": 0,
                "intent_analysis": intent,
            },
        }
        return

    # ---- 路径 B: 多意图分解 ----
    if intent_type == INTENT_MULTI and intent.get("sub_questions"):
        sub_questions = intent["sub_questions"]
        yield "status", {
            "stage": "multi_intent",
            "message": f"检测到 {len(sub_questions)} 个子问题,逐个分析...",
        }

        sub_answers: list[str] = []
        all_chunks: list[dict[str, Any]] = []
        sub_tool_calls: list[dict[str, Any]] = []
        total_tokens = 0
        total_llm_calls = 0

        for si, sub_q in enumerate(sub_questions):
            yield "status", {
                "stage": "multi_intent",
                "message": f"正在分析子问题 {si + 1}/{len(sub_questions)}: {sub_q[:40]}",
            }
            # 用 task + 心跳包装:非流式 run_lead_agent 可能耗时较长,
            # 每 8s yield 一个 status 防止 chat.py 监控误判 task 超时
            sub_task = _aio.create_task(run_lead_agent(
                db=db,
                paper_id=paper_id,
                project_id=project_id,
                question=sub_q,
                skill_names=None,
                max_iterations=3,  # 子问题更简单,减少迭代
                enable_critique=False,
                user_id=user_id,
                request_id=f"{request_id}_sub{si}",
            ))
            while not sub_task.done():
                try:
                    await _aio.wait_for(_aio.shield(sub_task), timeout=8.0)
                except _aio.TimeoutError:
                    yield "status", {
                        "stage": "multi_intent",
                        "message": f"正在分析子问题 {si + 1}/{len(sub_questions)}: {sub_q[:40]}...",
                    }
            sub_result = sub_task.result()
            sub_answers.append(sub_result.answer)
            all_chunks.extend(sub_result.chunks)
            sub_tool_calls.extend(sub_result.trace.tool_calls)
            total_tokens += sub_result.trace.total_tokens
            total_llm_calls += sub_result.trace.llm_calls

        # 综合回答(同样用心跳包装,防止 LLM 综合时超时)
        yield "status", {"stage": "generating", "message": "正在综合各子问题的回答..."}
        synth_task = _aio.create_task(synthesize_multi_intent_answer(
            question, sub_answers, complexity,
        ))
        while not synth_task.done():
            try:
                await _aio.wait_for(_aio.shield(synth_task), timeout=8.0)
            except _aio.TimeoutError:
                yield "status", {"stage": "generating", "message": "正在综合各子问题的回答..."}
        final_answer = synth_task.result()

        # 生成 citations(从所有子问题的 chunks)
        citations = _build_citations(final_answer, all_chunks)
        detected_intent = _detect_intent(question)
        intent_label = detected_intent or "multi_intent"
        evidence_confidence = _calc_confidence(
            final_answer, citations, all_chunks, intent=detected_intent,
        )

        # 分块推送综合回答
        for i in range(0, len(final_answer), _CHUNK_SIZE):
            yield "answer_delta", {"text": final_answer[i:i + _CHUNK_SIZE]}
            await _aio.sleep(0.02)

        # persist
        yield "status", {"stage": "persisting", "message": "正在保存回答"}
        message_count = await db.execute(
            _select(_func.count()).select_from(_ChatMessage)
            .where(_ChatMessage.session_id == session_id)
        )
        order_index = message_count.scalar() or 0
        message = _ChatMessage(
            session_id=session_id,
            order_index=order_index + 1,
            question=question,
            answer=final_answer,
            citations=citations,
            follow_up_questions=[],
            confidence=evidence_confidence,
        )
        db.add(message)
        if order_index == 0:
            session.title = question[:20] + ("..." if len(question) > 20 else "")
            session.updated_at = _dt.utcnow()
        await db.flush()
        message_id = str(message.id)
        await db.commit()

        yield "citations", {"items": citations}
        yield "done", {
            "message_id": message_id,
            "intent": intent_label,
            "sources": [c.get("section", "") for c in citations],
            "evidence_confidence": evidence_confidence,
            "confidence": evidence_confidence,
            "confidence_type": "agent_evidence",
            "follow_up_pending": True,
            "trace_id": request_id,
            "agent_trace": {
                "iterations": len(sub_questions),
                "tool_calls": sub_tool_calls,
                "total_ms": 0,
                "llm_calls": total_llm_calls + 1,  # +1 综合
                "total_tokens": total_tokens,
                "intent_analysis": intent,
                "multi_intent": True,
            },
        }
        return

    # ---- 路径 C: 单意图(factual/analytical)----
    # 大部分问题用快速路径:检索1次 + 流式生成1次(和原 workflow 一样快,首字 2-3s)
    # 只有 critique 相关问题走 ReAct(需要多轮收集信息 + critique subagent)
    route = decide_agent_route(
        question,
        project_id=project_id,
        intent_type=intent_type,
        complexity=complexity,
    )
    # 空项目不能走依赖 paper_id 的单篇论文快速检索；项目 Agent 仍可创建任务书、
    # 调用 arXiv/Semantic Scholar，并把筛选结果保存为项目产物。
    use_react = route.mode is ExecutionMode.REACT or bool(project_id and not paper_id)
    logger.info(
        "agent 路由: mode=%s reason=%s project_action=%s",
        route.mode.value,
        route.reason,
        route.project_action.value,
    )

    if not use_react:
        # ====== 快速路径:检索1次 + 流式生成1次 ======
        yield "status", {"stage": "retrieving", "message": "正在检索论文内容..."}

        fast_start = time.perf_counter()
        first_token_ms: Optional[float] = None

        # 1. 检索一次
        from app.harness.tools.paper_internal import _search_paper_content_impl
        retrieval_start = time.perf_counter()
        search_result_str = await _search_paper_content_impl(db, paper_id, question, intent=intent_type)
        retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 3)
        search_result = json.loads(search_result_str)
        chunks = search_result.get("chunks", [])
        yield "status", {"stage": "generating", "message": "正在生成回答...", "source_count": len(chunks)}

        # 2. 构造 prompt
        chunks_text = "\n\n".join([
            f"[S{c['source_id']}] {c['content']}" for c in chunks
        ]) or "(未检索到相关内容)"
        system_prompt = "你是一个论文阅读助手。基于以下检索到的论文片段回答用户问题,在相关处标注 [Sx] 引用。"
        if history_context:
            system_prompt += f"\n\n历史对话:\n{history_context}"
        system_prompt += f"\n\n检索到的论文片段:\n{chunks_text}"

        depth_hint = _DEPTH_HINTS.get(complexity, "")
        user_msg = f"{depth_hint}{question}" if depth_hint else question
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]

        # 3. 流式生成(真流式,首字延迟 ≈ 检索 + LLM 首 token)
        answer = ""
        llm_calls = 0
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        last_chunk = None
        try:
            async for chunk in get_llm_client().client.astream(messages):
                if chunk.content:
                    if first_token_ms is None:
                        first_token_ms = round((time.perf_counter() - fast_start) * 1000, 3)
                    answer += chunk.content
                    yield "answer_delta", {"text": chunk.content}
                last_chunk = chunk
            llm_calls = 1
            # 从最后一个 chunk 提取 token 用量(LangChain 末尾 chunk 含 usage_metadata)
            if last_chunk is not None:
                std = getattr(last_chunk, "usage_metadata", None)
                if isinstance(std, dict) and std:
                    input_tokens = std.get("input_tokens", 0)
                    output_tokens = std.get("output_tokens", 0)
                    total_tokens = std.get("total_tokens", 0)
                else:
                    rm = getattr(last_chunk, "response_metadata", None) or {}
                    if isinstance(rm, dict) and isinstance(rm.get("token_usage"), dict):
                        tu = rm["token_usage"]
                        input_tokens = tu.get("prompt_tokens", 0)
                        output_tokens = tu.get("completion_tokens", 0)
                        total_tokens = tu.get("total_tokens", 0)
        except Exception as exc:
            yield "error", {"stage": "generating", "message": friendly_error_message("llm", str(exc))}
            return

        total_ms = round((time.perf_counter() - fast_start) * 1000, 3)

        # 4. 生成 citations + confidence
        citations = _build_citations(answer, chunks)
        detected_intent = _detect_intent(question)
        intent_label = detected_intent or "general"
        evidence_confidence = _calc_confidence(answer, citations, chunks, intent=detected_intent)

        agent_trace = {
            "iterations": 1,
            "tool_calls": [{"name": "search_paper_content", "args": {"query": question}, "elapsed_ms": retrieval_ms, "ok": True}],
            "total_ms": total_ms,
            "first_token_ms": first_token_ms,
            "retrieval_ms": retrieval_ms,
            "llm_calls": llm_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
                "intent_analysis": intent,
                "route_reason": route.reason,
                "project_action": route.project_action.value,
                "fast_path": True,
        }
    else:
        # ====== ReAct 路径:复杂问题(critique/深度分析)走多轮 tool calling ======
        depth_hint = _DEPTH_HINTS.get(complexity, "")
        question_with_hint = f"{depth_hint}{question}" if depth_hint else question

        yield "status", {"stage": "agent_thinking", "message": "Agent 正在分析问题..."}

        # 真流式:用 deque 缓冲 LLM token,后台 task 跑 run_lead_agent,主循环边取边 yield
        import collections as _collections
        token_buffer: _collections.deque = _collections.deque()
        agent_start_ms = time.perf_counter()
        first_token_ms: Optional[float] = None
        agent_task = _aio.create_task(run_lead_agent(
            db=db,
            paper_id=paper_id,
            project_id=project_id,
            question=question_with_hint,
            skill_names=None,
            max_iterations=DEFAULT_MAX_ITERATIONS,
            history_context=history_context,
            enable_thinking=enable_thinking,
            enable_critique=enable_critique,
            user_id=user_id,
            request_id=request_id,
            on_token=lambda text: token_buffer.append(text),
        ))

        # 边等 agent 完成边推送 token(真流式,首字延迟 ≈ LLM 第一个 token 时间)
        while not agent_task.done() or token_buffer:
            while token_buffer:
                if first_token_ms is None:
                    first_token_ms = round((time.perf_counter() - agent_start_ms) * 1000, 3)
                yield "answer_delta", {"text": token_buffer.popleft()}
            if not agent_task.done():
                await _aio.sleep(0.01)

        agent_result = agent_task.result()

        if not agent_result.answer:
            yield "error", {
                "stage": "agent",
                "message": friendly_error_message(
                    "agent",
                    agent_result.trace.failure_reason or "Agent 未产出回答",
                ),
            }
            return

        # 生成 citations + confidence
        chunks = agent_result.chunks
        answer = agent_result.answer
        citations = _build_citations(answer, chunks)
        detected_intent = _detect_intent(question)
        intent_label = detected_intent or "general"
        evidence_confidence = _calc_confidence(
            answer, citations, chunks, intent=detected_intent
        )

        agent_trace = {
            "iterations": agent_result.trace.iterations,
            "tool_calls": agent_result.trace.tool_calls,
            "total_ms": agent_result.trace.total_ms,
            "first_token_ms": first_token_ms,
            "llm_calls": agent_result.trace.llm_calls,
            "input_tokens": agent_result.trace.input_tokens,
            "output_tokens": agent_result.trace.output_tokens,
            "total_tokens": agent_result.trace.total_tokens,
            "intent_analysis": intent,
            "route_reason": route.reason,
            "project_action": route.project_action.value,
            "fast_path": False,
        }

    # persist ChatMessage(同步,0.1s 级别,需拿 message_id 给追问用)
    message_count = await db.execute(
        _select(_func.count())
        .select_from(_ChatMessage)
        .where(_ChatMessage.session_id == session_id)
    )
    order_index = message_count.scalar() or 0
    message = _ChatMessage(
        session_id=session_id,
        order_index=order_index + 1,
        question=question,
        answer=answer,
        citations=citations,
        follow_up_questions=[],
        confidence=evidence_confidence,
    )
    db.add(message)
    if order_index == 0:
        session.title = question[:20] + ("..." if len(question) > 20 else "")
        session.updated_at = _dt.utcnow()
    await db.flush()
    message_id = str(message.id)
    await db.commit()

    # 推送 citations + done(不再推 "正在保存回答" status,减少无意义 SSE 往返)
    yield "citations", {"items": citations}
    yield "done", {
        "message_id": message_id,
        "intent": intent_label,
        "sources": [c.get("section", "") for c in citations],
        "evidence_confidence": evidence_confidence,
        "confidence": evidence_confidence,
        "confidence_type": "agent_evidence",
        "follow_up_pending": True,
        "trace_id": request_id,
        "agent_trace": agent_trace,
    }
