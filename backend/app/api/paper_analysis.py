"""Paper question answering, interpretation and structured summaries."""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.qa_helpers import (
    build_deterministic_citations,
    calculate_evidence_confidence,
    detect_metadata_intent,
)
from app.agent.qa_agent.enhanced_graph import run_enhanced_qa_agent
from app.agent.summarizer.graph import run_summarizer_agent
from app.api.dependencies import get_current_user_id
from app.application.project_execution_entrypoint import classify_instant_interaction
from app.database import get_db
from app.harness.agents.lead_agent import run_lead_agent
from app.harness.tools.paper_internal import _get_paper_metadata_impl
from app.llm.client import get_llm_client
from app.models.paper import Paper, QAPair, Section
from app.rag.knowledge_base import get_knowledge_base
from app.rag.table_retrieval import get_exact_table_chunks, merge_retrieval_chunks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/papers")


@router.post("/{paper_id}/qa")
async def ask_question(
    paper_id: str,
    data: dict,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    classify_instant_interaction("paper_chat")
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")

    # mode 默认 agent:走 lead_agent(自主选 tool + 全部 skill + critique 委派)
    # mode=workflow: 退回原确定性 workflow(保留作为 fallback)
    mode = data.get("mode", "agent")
    if mode == "agent":
        # request_id:客户端可传(用于断点续连重试),不传则生成新的
        import uuid as _uuid
        request_id = data.get("request_id") or _uuid.uuid4().hex
        agent_result = await run_lead_agent(
            db=db,
            paper_id=paper_id,
            question=question,
            skill_names=None,  # None=全部已注册 skill(paper_internal/external/reading)
            enable_critique=True,
            user_id=user_id,
            request_id=request_id,
        )
        # 用 enhanced_graph 的函数补齐 citations / confidence / intent,与原 workflow 对齐
        chunks = agent_result.chunks
        citations = build_deterministic_citations(agent_result.answer, chunks)
        detected_intent = detect_metadata_intent(question)
        # intent 分类:元数据问题标具体类型(authors/title/...),否则标 "general"
        intent_label = detected_intent or "general"
        evidence_confidence = calculate_evidence_confidence(
            agent_result.answer, citations, chunks, intent=detected_intent
        )
        # 元数据类问题 intent_confidence=1.0(检测到具体类型),其他 0.8
        intent_confidence = 1.0 if detected_intent else 0.8
        count_result = await db.execute(
            select(func.count()).select_from(QAPair).where(QAPair.paper_id == paper_id)
        )
        qa_pair = QAPair(
            paper_id=paper_id,
            order_index=(count_result.scalar() or 0) + 1,
            question=question,
            answer=agent_result.answer,
            chunk_context="\n\n".join(chunk.get("content", "") for chunk in chunks[:3]),
            relevance_score=evidence_confidence,
        )
        db.add(qa_pair)
        await db.commit()
        return {
            "answer": agent_result.answer,
            "intent": intent_label,
            "sources": [c.get("section", "") for c in citations],
            "citations": citations,
            "follow_up_questions": [],
            "intent_confidence": intent_confidence,
            "evidence_confidence": evidence_confidence,
            "confidence": evidence_confidence,
            "confidence_type": "agent_evidence",
            "qa_id": str(qa_pair.id),
            "agent_trace": {
                "iterations": agent_result.trace.iterations,
                "tool_calls": agent_result.trace.tool_calls,
                "total_ms": agent_result.trace.total_ms,
                "success": agent_result.success,
                # 应用内 tracing:LLM token 用量累计
                "llm_calls": agent_result.trace.llm_calls,
                "input_tokens": agent_result.trace.input_tokens,
                "output_tokens": agent_result.trace.output_tokens,
                "total_tokens": agent_result.trace.total_tokens,
            },
        }

    # 默认路径:原确定性 workflow(行为不变)
    exact_chunks = await get_exact_table_chunks(db, paper_id, question)
    semantic_chunks = await get_knowledge_base().query(paper_id, question, top_k=5)
    chunks = merge_retrieval_chunks(exact_chunks, semantic_chunks, top_k=5)
    # 元数据通过 harness tool 统一入口(行为等价于原手动拼 dict)
    metadata = json.loads(await _get_paper_metadata_impl(db, paper_id))
    qa_result = await run_enhanced_qa_agent(paper_id, question, chunks, metadata)
    count_result = await db.execute(
        select(func.count()).select_from(QAPair).where(QAPair.paper_id == paper_id)
    )
    qa_pair = QAPair(
        paper_id=paper_id,
        order_index=(count_result.scalar() or 0) + 1,
        question=question,
        answer=qa_result.get("answer"),
        chunk_context="\n\n".join(chunk.get("content", "") for chunk in chunks[:3]),
        relevance_score=qa_result.get("evidence_confidence"),
    )
    db.add(qa_pair)
    await db.commit()
    return {
        "answer": qa_result.get("answer"),
        "intent": qa_result.get("intent"),
        "sources": qa_result.get("sources", []),
        "citations": qa_result.get("citations", []),
        "follow_up_questions": qa_result.get("follow_up_questions", []),
        "intent_confidence": qa_result.get("intent_confidence", 0.0),
        "evidence_confidence": qa_result.get("evidence_confidence", 0.0),
        "confidence": qa_result.get("evidence_confidence", 0.0),
        "confidence_type": "evidence_support",
        "qa_id": str(qa_pair.id),
    }


def _sections_data(paper: Paper, sections: list[Section]) -> list[dict]:
    if sections:
        return [
            {"title": item.section_title, "content": item.content or "", "order_index": item.order_index}
            for item in sections
        ]
    if paper.full_text:
        paragraphs = [part.strip() for part in paper.full_text.split("\n\n") if part.strip()]
        return [
            {"title": f"段落 {index + 1}", "content": part, "order_index": index}
            for index, part in enumerate(paragraphs[:100])
        ]
    return []


async def _owned_paper_with_sections(db: AsyncSession, paper_id: str, user_id: str):
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    result = await db.execute(
        select(Section).where(Section.paper_id == paper_id).order_by(Section.order_index)
    )
    return paper, list(result.scalars().all())


@router.post("/{paper_id}/interpret")
async def interpret_paper(
    paper_id: str,
    data: dict,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    classify_instant_interaction("paper_interpretation")
    paper, sections = await _owned_paper_with_sections(db, paper_id, user_id)
    content = _sections_data(paper, sections)
    if not content:
        raise HTTPException(status_code=400, detail="论文内容为空")

    source_text = "\n\n".join(
        f"## {section['title']}\n{section['content'][:2000]}" for section in content[:10]
    )
    interpret_type = data.get("type", "concept")
    prompts = {
        "concept": f"""
        请分析以下论文内容，提取并解释其中的关键概念和技术术语。
        返回 JSON 格式：
        {{
            "concepts": [
                {{"name": "概念名称", "explanation": "通俗解释（100字以内）", "context": "在论文中的作用"}}
            ]
        }}
        论文内容：
        {source_text[:8000]}
        """,
        "compare": f"""
        请分析以下论文内容，对比论文中提到的不同方法、模型或实验设置。
        返回 JSON 格式：
        {{
            "comparisons": [
                {{"item_a": "方法A", "item_b": "方法B", "difference": "主要差异", "advantage": "各自优势"}}
            ]
        }}
        论文内容：
        {source_text[:8000]}
        """,
        "key_info": f"""
        请分析以下论文内容，提取最关键的信息点。
        返回 JSON 格式：
        {{
            "key_formulas": ["关键公式或算法描述"],
            "key_figures": ["关键图表说明"],
            "key_findings": ["关键发现"],
            "takeaways": ["值得关注的要点"]
        }}
        论文内容：
        {source_text[:8000]}
        """,
    }
    prompt = prompts.get(interpret_type, prompts["concept"])
    try:
        response = await get_llm_client().agenerate([prompt], json_mode=True, enable_thinking=False)
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        return {"paper_id": paper_id, "type": interpret_type, "data": json.loads(text)}
    except Exception as exc:
        logger.error("深度解读失败: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="解读失败，请稍后重试") from exc


@router.post("/{paper_id}/summarize")
async def generate_structured_summary(
    paper_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    classify_instant_interaction("paper_summary")
    paper, sections = await _owned_paper_with_sections(db, paper_id, user_id)
    content = _sections_data(paper, sections)
    if not content:
        raise HTTPException(status_code=400, detail="论文内容为空，无法生成摘要")
    summary = await run_summarizer_agent(paper_id, content)
    return {
        "paper_id": paper_id,
        "overview": summary.get("overview", {}),
        "methodology": summary.get("methodology", {}),
        "experiments": summary.get("experiments", {}),
        "contributions": summary.get("contributions", {}),
    }


@router.get("/{paper_id}/summary")
async def get_structured_summary(
    paper_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    return await generate_structured_summary(paper_id, authorization, db)
