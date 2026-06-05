"""论文 API 模块"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import os
import uuid
import json
import pdfplumber
import logging

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.paper import Paper, Section, QAPair
from app.agent.paper_parser.graph import run_paper_parser
from app.agent.summarizer.graph import run_summarizer_agent
from app.rag.knowledge_base import get_knowledge_base
from app.llm.client import get_llm_client
from app.api.auth import decode_token
from app.config import settings

router = APIRouter(prefix="/api/v1/papers")


async def get_current_user_id(authorization: str = Header(None), db: AsyncSession = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="令牌无效")
    return payload.get("sub")


@router.get("/")
async def get_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    user_id = await get_current_user_id(authorization, db)
    
    query = select(Paper).filter(Paper.user_id == user_id)
    
    if status:
        query = query.filter(Paper.status == status)
    
    if search:
        query = query.filter(
            (Paper.title.ilike(f"%{search}%")) | 
            (Paper.authors.ilike(f"%{search}%"))
        )
    
    query = query.order_by(Paper.uploaded_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    papers = result.scalars().all()
    
    return {
        "items": [
            {
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "pdf_path": p.pdf_path,
                "status": p.reading_status,
                "reading_progress": p.reading_progress,
                "is_favorite": p.is_favorite,
                "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None
            }
            for p in papers
        ],
        "total": len(papers)
    }


@router.get("/{paper_id}/pdf")
async def get_paper_pdf(paper_id: str, token: str = Query(None), authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """Serve the PDF file for a paper. Supports token via query param for iframe embedding."""
    # Support token from query parameter (for iframe) or Authorization header
    auth_token = token or (authorization.replace("Bearer ", "") if authorization and authorization.startswith("Bearer ") else None)
    if not auth_token:
        raise HTTPException(status_code=401, detail="未授权")
    
    payload = decode_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="令牌无效")
    user_id = payload.get("sub")
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    if not paper.pdf_path or not os.path.exists(paper.pdf_path):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")
    
    # Use ASCII-safe filename for Content-Disposition to avoid download issues
    safe_filename = f"{paper_id}.pdf"
    
    return FileResponse(
        paper.pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'}
    )


@router.get("/{paper_id}/sections")
async def get_paper_sections(paper_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """Get sections of a paper for TOC"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    sections_result = await db.execute(
        select(Section)
        .where(Section.paper_id == paper_id)
        .order_by(Section.order_index)
    )
    sections = sections_result.scalars().all()
    
    return {
        "sections": [
            {
                "id": s.id,
                "title": s.section_title,
                "section_title": s.section_title,
                "order_index": s.order_index,
                "start_page": s.start_page,
                "summary": s.summary,
                "key_points": s.key_points
            }
            for s in sections
        ]
    }


@router.get("/{paper_id}")
async def get_paper(paper_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "full_text": paper.full_text,
        "pdf_path": paper.pdf_path,
        "status": paper.reading_status,
        "reading_progress": paper.reading_progress,
        "is_favorite": paper.is_favorite,
        "uploaded_at": paper.uploaded_at.isoformat() if paper.uploaded_at else None,
        "updated_at": paper.updated_at.isoformat() if paper.updated_at else None
    }


@router.post("/upload")
async def upload_paper(file: UploadFile = File(...), authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(authorization, db)
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持 PDF 格式")
    
    content = await file.read()
    file_size = len(content)
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小不能超过 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB")
    
    paper_id = str(uuid.uuid4())
    file_path = f"{settings.FILE_STORAGE_PATH}/{paper_id}.pdf"
    os.makedirs(settings.FILE_STORAGE_PATH, exist_ok=True)
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    raw_text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    raw_text += text + "\n\n"
                if i > 50:
                    break
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 解析失败：{str(e)}")
    
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="无法从 PDF 中提取文字")
    
    parse_result = await run_paper_parser(paper_id, file_path, raw_text)
    
    paper = Paper(
        id=paper_id,
        user_id=user_id,
        title=parse_result.get('title', ''),
        authors=parse_result.get('authors', ''),
        abstract=parse_result.get('abstract', ''),
        full_text=raw_text[:100000],
        pdf_path=file_path,
        keywords=parse_result.get('keywords', [])
    )
    db.add(paper)
    
    sections = parse_result.get('sections', [])
    logger.info(f"解析到 {len(sections)} 个章节")
    
    # 如果没有解析到章节，创建一个默认的"全文"章节
    if not sections or len(sections) == 0:
        logger.warning("未解析到章节，创建默认章节")
        sections = [{
            "title": "全文",
            "content": raw_text[:3000],
            "key_points": []
        }]
    
    for i, section_data in enumerate(sections):
        section_title = section_data.get('title', f'第{i+1}节')
        section_content = section_data.get('content', '')
        
        # 确保 key_points 是字符串格式
        key_points = section_data.get('key_points', [])
        if isinstance(key_points, list):
            key_points = json.dumps(key_points, ensure_ascii=False)
        
        section = Section(
            paper_id=paper_id,
            section_title=section_title,
            order_index=i,
            start_page=None,  # 暂时不提取页码
            content=section_content,
            key_points=key_points
        )
        db.add(section)
    
    await db.commit()
    
    kb = get_knowledge_base()
    
    # 构建带章节信息的chunks，让RAG检索更精准
    chunks = []
    chunk_idx = 0
    
    # 先按章节切分内容
    for i, section_data in enumerate(parse_result.get('sections', [])):
        section_title = section_data.get('title', f'第{i+1}节')
        section_content = section_data.get('content', '')
        
        if section_content:
            # 将章节内容按每 800 字符切分成多个 chunk
            for j in range(0, len(section_content), 800):
                chunk_content = section_content[j:j+800]
                if chunk_content.strip():
                    chunks.append({
                        "content": chunk_content,
                        "type": "text",
                        "index": chunk_idx,
                        "section": section_title
                    })
                    chunk_idx += 1
    
    # 如果没有解析到章节或chunks为空，使用全文切分
    if not chunks:
        chunks = [{"content": raw_text[i:i+1000], "type": "text", "index": idx, "section": "全文"} 
                  for idx, i in enumerate(range(0, min(len(raw_text), 100000), 1000))]
    
    await kb.add_paper_chunks(paper_id, chunks)
    
    return {
        "paper_id": paper_id,
        "title": parse_result.get('title'),
        "authors": parse_result.get('authors'),
        "sections_count": len(parse_result.get('sections', [])),
        "message": "上传成功"
    }


@router.delete("/{paper_id}")
async def delete_paper(paper_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    # 删除向量库中的片段
    kb = get_knowledge_base()
    await kb.delete_paper(paper_id)
    
    # 删除数据库记录（级联删除 sections 和 qa_pairs）
    await db.delete(paper)
    await db.commit()
    
    # 删除 PDF 文件
    if paper.pdf_path and os.path.exists(paper.pdf_path):
        os.remove(paper.pdf_path)
    
    return {"message": "删除成功"}


@router.post("/{paper_id}/qa")
async def ask_question(paper_id: str, data: dict, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(authorization, db)
    
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    kb = get_knowledge_base()
    chunks = await kb.query(paper_id, question, top_k=5)
    
    # 构建论文元数据
    paper_metadata = {
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "keywords": paper.keywords or [],
        "venue": getattr(paper, 'venue', None),
        "publication_year": getattr(paper, 'publication_year', None),
        "doi": getattr(paper, 'doi', None),
    }
    
    # 使用增强版问答 Agent，传入元数据
    qa_result = await run_enhanced_qa_agent(paper_id, question, chunks, paper_metadata)
    
    qa_count = await db.execute(select(func.count()).select_from(QAPair).where(QAPair.paper_id == paper_id))
    order_index = qa_count.scalar() or 0
    
    qa_pair = QAPair(
        paper_id=paper_id,
        order_index=order_index + 1,
        question=question,
        answer=qa_result.get('answer'),
        chunk_context="\n\n".join([c.get('content', '') for c in chunks[:3]]),
        relevance_score=qa_result.get('confidence')
    )
    db.add(qa_pair)
    await db.commit()
    
    return {
        "answer": qa_result.get("answer"),
        "intent": qa_result.get("intent"),
        "sources": qa_result.get("sources", []),
        "citations": qa_result.get("citations", []),
        "follow_up_questions": qa_result.get("follow_up_questions", []),
        "confidence": qa_result.get("confidence", 0.0),
        "qa_id": str(qa_pair.id)
    }


@router.post("/{paper_id}/interpret")
async def interpret_paper(paper_id: str, data: dict, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """深度解读论文 - 解释概念、对比方法、提取关键信息"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    interpret_type = data.get("type", "concept")  # concept, compare, key_info
    
    # 获取论文章节
    sections_result = await db.execute(
        select(Section)
        .where(Section.paper_id == paper_id)
        .order_by(Section.order_index)
    )
    sections = sections_result.scalars().all()
    
    sections_data = []
    if sections:
        sections_data = [
            {"title": s.section_title, "content": s.content or "", "order_index": s.order_index}
            for s in sections
        ]
    elif paper.full_text:
        paragraphs = [p.strip() for p in paper.full_text.split('\n\n') if p.strip()]
        sections_data = [
            {"title": f"段落 {i+1}", "content": p, "order_index": i}
            for i, p in enumerate(paragraphs[:100])
        ]
    
    if not sections_data:
        raise HTTPException(status_code=400, detail="论文内容为空")
    
    llm = get_llm_client()
    text = "\n\n".join([f"## {s['title']}\n{s['content'][:2000]}" for s in sections_data[:10]])
    
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
        {text[:8000]}
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
        {text[:8000]}
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
        {text[:8000]}
        """
    }
    
    prompt = prompts.get(interpret_type, prompts["concept"])
    
    try:
        response = await llm.agenerate([prompt])
        text_result = response.generations[0][0].text.strip()
        if "```json" in text_result:
            text_result = text_result.split("```json")[1].split("```")[0]
        result_data = json.loads(text_result.strip())
        
        return {
            "paper_id": paper_id,
            "type": interpret_type,
            "data": result_data
        }
    except Exception as e:
        logger.error(f"❌ 深度解读失败：{e}")
        raise HTTPException(status_code=500, detail=f"解读失败：{str(e)}")


@router.post("/{paper_id}/summarize")
async def generate_structured_summary(paper_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """生成论文的结构化摘要"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    # 优先使用章节数据，如果没有则使用 full_text
    sections_result = await db.execute(
        select(Section)
        .where(Section.paper_id == paper_id)
        .order_by(Section.order_index)
    )
    sections = sections_result.scalars().all()
    
    if sections:
        sections_data = [
            {
                "title": s.section_title,
                "content": s.content or "",
                "order_index": s.order_index
            }
            for s in sections
        ]
    elif paper.full_text:
        # 如果没有章节，将 full_text 按段落拆分
        paragraphs = [p.strip() for p in paper.full_text.split('\n\n') if p.strip()]
        sections_data = [
            {
                "title": f"段落 {i+1}",
                "content": p,
                "order_index": i
            }
            for i, p in enumerate(paragraphs[:100])  # 限制最多100段
        ]
    else:
        raise HTTPException(status_code=400, detail="论文内容为空，无法生成摘要")
    
    # 运行结构化摘要 Agent
    summary_result = await run_summarizer_agent(paper_id, sections_data)
    
    return {
        "paper_id": paper_id,
        "overview": summary_result.get("overview", {}),
        "methodology": summary_result.get("methodology", {}),
        "experiments": summary_result.get("experiments", {}),
        "contributions": summary_result.get("contributions", {})
    }


@router.get("/{paper_id}/summary")
async def get_structured_summary(paper_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """获取论文的结构化摘要（如果已生成）"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    # 检查是否有章节数据（如果有章节，说明可以生成摘要）
    sections_result = await db.execute(
        select(Section)
        .where(Section.paper_id == paper_id)
        .order_by(Section.order_index)
    )
    sections = sections_result.scalars().all()
    
    return {
        "paper_id": paper_id,
        "has_sections": len(sections) > 0,
        "sections_count": len(sections),
        "message": "调用 POST /{paper_id}/summarize 生成结构化摘要"
    }
