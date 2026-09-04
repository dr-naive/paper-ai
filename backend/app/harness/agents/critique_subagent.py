"""Harness Agents: critique_subagent —— 审稿意见/批判性分析子 agent。

设计要点:
- 不用 tool,纯 LLM 推理(基于 lead_agent 已收集的证据)
- 由 lead_agent 通过 delegate_to_critique 触发,不是独立入口
- 专注批判性分析,与 lead_agent 的"信息检索"职责分离
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class CritiqueResult:
    """critique subagent 的返回结构。"""
    review: str
    innovation_score: int  # 0-10
    rigor_score: int  # 0-10
    clarity_score: int  # 0-10
    success: bool


CRITIQUE_SYSTEM_PROMPT = """你是一个资深学术论文审稿人,擅长批判性分析。

你的任务是基于提供的论文信息,给出专业的审稿意见。包括:

1. **创新性评估**(0-10分):方法/思路是否新颖,与现有工作的差异
2. **严谨性评估**(0-10分):实验设计是否合理,论证是否充分
3. **清晰度评估**(0-10分):写作是否清晰,结构是否合理
4. **主要优点**:列出 2-3 条
5. **主要不足**:列出 2-3 条
6. **修改建议**:列出 1-2 条可操作的改进建议

输出格式(JSON):
```json
{
  "innovation_score": 0-10,
  "rigor_score": 0-10,
  "clarity_score": 0-10,
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1", "不足2"],
  "suggestions": ["建议1", "建议2"],
  "summary": "一段话总结审稿意见"
}
```

注意:
- 基于提供的论文信息客观评价,不要臆测未提供的内容
- 若信息不足以评估某项,该项给 5 分并注明"信息不足"
- 用中文回答
"""


async def run_critique_subagent(
    *,
    question: str,
    evidence: str,
    paper_metadata: str = "",
    history_context: str = "",
) -> CritiqueResult:
    """运行 critique subagent。

    Args:
        question: 用户的批判性问题(如"评估这篇论文的创新性""写审稿意见")
        evidence: lead_agent 已收集的证据(tool 返回的 chunks/表格等)
        paper_metadata: 论文元数据(标题/作者/摘要等)
        history_context: 历史对话上下文(可选)

    Returns:
        CritiqueResult,包含审稿意见和评分
    """
    # 拼装用户消息:问题 + 证据 + 元数据
    user_parts = [f"## 用户问题\n{question}"]
    if paper_metadata:
        user_parts.append(f"## 论文元数据\n{paper_metadata}")
    if evidence:
        user_parts.append(f"## 已收集证据\n{evidence}")
    if history_context:
        user_parts.append(f"## 历史对话\n{history_context}")
    user_parts.append("请基于以上信息给出审稿意见(JSON 格式)。")

    messages = [
        SystemMessage(content=CRITIQUE_SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(user_parts)),
    ]

    try:
        response = await get_llm_client().client.ainvoke(messages)
        content = (response.content or "").strip()
    except Exception as exc:
        logger.exception("critique subagent LLM 调用失败")
        return CritiqueResult(
            review=f"审稿失败: {type(exc).__name__}: {exc}",
            innovation_score=0,
            rigor_score=0,
            clarity_score=0,
            success=False,
        )

    # 尝试从回复里解析 JSON(LLM 可能包裹在 ```json ``` 里)
    import json
    import re

    json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 退而求其次,找第一个 { 到最后一个 }
        first_brace = content.find("{")
        last_brace = content.rfind("}")
        if first_brace != -1 and last_brace != -1:
            json_str = content[first_brace : last_brace + 1]
        else:
            json_str = ""

    if json_str:
        try:
            data = json.loads(json_str)
            return CritiqueResult(
                review=content,  # 完整回复作为 review
                innovation_score=int(data.get("innovation_score", 5)),
                rigor_score=int(data.get("rigor_score", 5)),
                clarity_score=int(data.get("clarity_score", 5)),
                success=True,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("critique subagent JSON 解析失败: %s", exc)

    # JSON 解析失败,降级:返回原始内容,评分默认 5
    return CritiqueResult(
        review=content,
        innovation_score=5,
        rigor_score=5,
        clarity_score=5,
        success=True,
    )
