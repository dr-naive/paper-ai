"""Paper question answering, interpretation and structured summaries."""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.qa_agent.enhanced_graph import run_enhanced_qa_agent
from app.agent.summarizer.graph import run_summarizer_agent
from app.api.dependencies import get_current_user_id
from app.database import get_db
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
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")

    exact_chunks = await get_exact_table_chunks(db, paper_id, question)
    semantic_chunks = await get_knowledge_base().query(paper_id, question, top_k=5)
    chunks = merge_retrieval_chunks(exact_chunks, semantic_chunks, top_k=5)
    metadata = {
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "keywords": paper.keywords or [],
        "venue": paper.venue,
        "publication_year": paper.publication_year,
        "doi": paper.doi,
    }
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
