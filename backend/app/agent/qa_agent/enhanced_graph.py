"""增强版问答 Agent 工作流模块 - 支持引用溯源和智能追问"""
from app.agent.state import QAAgentState
from app.llm.client import get_llm_client
from app.utils.qa_helpers import (
    _enrich_citations,
    build_deterministic_citations,
    calculate_evidence_confidence,
    detect_metadata_intent,
    needs_deep_thinking,
    safe_json_loads,
)
import logging
from loguru import logger

logger = logging.getLogger(__name__)




async def generate_follow_up(state: QAAgentState) -> QAAgentState:
    """生成智能追问"""
    logger.info(f"[增强问答 Agent] 生成智能追问")
    if not state.get('generate_follow_up', True):
        state['follow_up_questions'] = []
        logger.info("[增强问答 Agent] 跳过同步追问生成")
        return state
    
    llm = get_llm_client()
    question = state['question']
    answer = state.get('answer', '')
    intent = state.get('intent', 'general')
    
    prompt = f"""
    基于以下问答内容，生成 3 个相关的追问问题，帮助用户深入理解论文。
    
    用户问题：{question}
    问题类型：{intent}
    回答摘要：{answer[:300]}
    
    要求：
    1. 问题要有深度，能引导用户探索论文的关键内容
    2. 问题类型要多样化（方法细节、实验结果、局限性等）
    3. 每个问题不超过 30 字
    
    返回 JSON 格式：
    {{"follow_up_questions": ["问题1", "问题2", "问题3"]}}
    """
    
    try:
        response = await llm.agenerate([prompt], json_mode=True, enable_thinking=False)
        text = response.generations[0][0].text.strip()
        result = safe_json_loads(text)
        state['follow_up_questions'] = result.get('follow_up_questions', [])
        logger.info(f"✅ 追问生成成功：{len(state['follow_up_questions'])} 个")
    except Exception as e:
        logger.error(f"❌ 追问生成失败：{e}")
        state['follow_up_questions'] = []
    
    return state



async def generate_follow_up_questions(question: str, answer: str, intent: str = "general") -> list[str]:
    state = QAAgentState(
        paper_id="",
        question=question,
        paper_metadata={},
        history_context="",
        intent=intent,
        relevant_chunks=[],
        answer=answer,
        sources=[],
        citations=[],
        follow_up_questions=[],
        generate_follow_up=True,
        metadata_field=None,
        simple_question=False,
        intent_confidence=0.0,
        evidence_confidence=0.0,
        error=None
    )
    result = await generate_follow_up(state)
    return result.get("follow_up_questions", [])


async def run_enhanced_qa_agent(
    paper_id: str,
    question: str,
    relevant_chunks: list,
    paper_metadata: dict = None,
    history_context: str = None,
    generate_follow_up: bool = True
) -> dict:
    """Compatibility wrapper around the same workflow used by streaming chat."""
    from app.agent.qa_agent.workflow import run_preloaded_qa_workflow

    logger.info("[统一问答工作流] 处理预检索问题：%s...", question[:50])
    result = await run_preloaded_qa_workflow(
        paper_id=paper_id,
        question=question,
        chunks=relevant_chunks,
        paper_metadata=paper_metadata,
        history_context=history_context or "",
        enable_thinking=needs_deep_thinking(question),
    )
    if generate_follow_up:
        result["follow_up_questions"] = await generate_follow_up_questions(
            question,
            result.get("answer", ""),
            result.get("intent", "general"),
        )
    return result
