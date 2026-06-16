"""论文 API 模块"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Dict, Any
import os
import uuid
import json
import pdfplumber
import logging
import asyncio

logger = logging.getLogger(__name__)

from app.database import get_db, AsyncSessionLocal
from app.models.paper import Paper, Section, QAPair
from app.agent.paper_parser.graph import run_paper_parser
from app.agent.summarizer.graph import run_summarizer_agent
from app.rag.knowledge_base import get_knowledge_base, SmartChunker
from app.llm.client import get_llm_client
from app.api.auth import decode_token
from app.config import settings
from app.parsers.multimedia_extractor import MultimediaExtractor
from app.utils.task_manager import create_task, update_task, get_task

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
                "key_points": s.key_points,
                "tables": s.tables or [],
                "figures": s.figures or [],
                "formulas": s.formulas or []
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


def _table_to_text(table_content: List[List[str]], caption: str = "") -> str:
    """将表格数据转换为文本格式，便于向量索引"""
    if not table_content or len(table_content) < 2:
        return ""
    
    lines = []
    if caption:
        lines.append(f"【表格】{caption}")
        lines.append("")
    
    max_cols = max(len(row) for row in table_content)
    
    for row_idx, row in enumerate(table_content):
        padded_row = row + [""] * (max_cols - len(row))
        line = "| " + " | ".join(str(cell).strip() for cell in padded_row) + " |"
        lines.append(line)
        
        if row_idx == 0 and len(table_content) > 1:
            lines.append("| " + " | ".join(["---"] * max_cols) + " |")
    
    lines.append("")
    return "\n".join(lines)


async def _process_paper_async(
    paper_id: str, 
    file_path: str, 
    user_id: str, 
    raw_text: str
):
    """异步处理论文的核心逻辑"""
    task_id = f"task_{paper_id}"
    
    try:
        update_task(task_id, status="processing", progress=10, message="正在解析论文结构...")
        
        # 解析论文结构
        parse_result = await run_paper_parser(paper_id, file_path, raw_text)
        
        update_task(task_id, progress=20, message="正在创建数据库记录...")
        
        # 创建数据库连接
        async with AsyncSessionLocal() as db:
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

            if not sections or len(sections) == 0:
                logger.warning("未解析到章节，创建默认章节")
                sections = [{
                    "title": "全文",
                    "content": raw_text[:3000],
                    "key_points": []
                }]

            update_task(task_id, progress=25, message="正在提取表格数据...")
            
            extractor = MultimediaExtractor(pdf_path=file_path)

            # 提取表格（优先使用 pdfplumber，失败则尝试 VLM 图片提取）
            pdf_tables = []
            vlm_tables = []
            try:
                pdf_tables = await extractor.extract_tables_from_pdf(file_path)
                logger.info(f"📊 从 PDF 提取到 {len(pdf_tables)} 个表格")
                
                # 如果 pdfplumber 没有提取到表格，尝试从图片中提取（VLM）
                if len(pdf_tables) == 0:
                    logger.info("📊 pdfplumber 未提取到表格，尝试从图片中提取（VLM）")
                    table_images = await extractor.extract_suspected_table_images_from_pdf(file_path, output_dir=tables_dir)
                    if table_images:
                        logger.info(f"📊 找到 {len(table_images)} 个疑似表格图片")
                        vlm_tables = await extractor.analyze_table_images(table_images)
                        logger.info(f"📊 VLM 确认为表格的有 {len(vlm_tables)} 个")
                    else:
                        logger.info("📊 未找到疑似表格图片")
                        
                    # 合并 VLM 提取的表格
                    pdf_tables.extend(vlm_tables)
            except Exception as e:
                logger.warning(f"PDF 表格提取失败: {e}")

            update_task(task_id, progress=30, message="正在提取图片...")

            # 创建规范存储目录
            import os
            paper_storage_dir = f"data/papers/{paper_id}"
            images_dir = os.path.join(paper_storage_dir, "images")
            tables_dir = os.path.join(paper_storage_dir, "tables")

            os.makedirs(images_dir, exist_ok=True)
            os.makedirs(tables_dir, exist_ok=True)

            # 提取图片（使用规范存储路径）
            pdf_images = []
            try:
                pdf_images = await extractor.extract_images_from_pdf(file_path, output_dir=images_dir)
                logger.info(f"从 PDF 提取到 {len(pdf_images)} 张图片，保存到 {images_dir}")
            except Exception as e:
                logger.warning(f"PDF 图片提取失败: {e}")

            # 收集表格和图片信息
            all_tables_text = []
            all_images_info = []

            update_task(task_id, progress=35, message="正在分析图片...")
            
            # 智能筛选和分析图片
            from app.parsers.image_analyzer import ImageAnalyzer
            image_analyzer = ImageAnalyzer()

            total_images = len(pdf_images)

            logger.info(f"📸 开始分析图片（共 {total_images} 张）...")

            # 直接分析所有图片（已在提取阶段过滤）
            async def analyze_one(img_idx, img_info):
                image_path = img_info.get("image_path")
                try:
                    # 使用新的标准化 Prompt
                    analysis = await image_analyzer.analyze_image(
                        image_path=image_path,
                        context="论文图片分析"
                    )

                    # 检查分析是否成功
                    if analysis.get("success"):
                        img_info["semantic_analysis"] = analysis

                        # 提取结构化信息
                        image_type = analysis.get("image_type", "other")
                        chart_type = analysis.get("chart_type", "")
                        core_conclusion = analysis.get("core_conclusion", "")
                        role_in_paper = analysis.get("role_in_paper", "")
                        key_data_points = analysis.get("key_data_points", [])
                        description = analysis.get("description", "")
                        qa_context = analysis.get("qa_context", "")

                        # 构建文本表示
                        parts = [f"【图片】类型：{image_type}"]
                        if chart_type and chart_type != "其他":
                            parts.append(f"（{chart_type}）")
                        if core_conclusion:
                            parts.append(f"\n核心结论：{core_conclusion}")
                        if role_in_paper:
                            parts.append(f"\n作用：{role_in_paper}")
                        if key_data_points:
                            parts.append(f"\n关键数据点：")
                            for i, point in enumerate(key_data_points, 1):
                                parts.append(f"  {i}. {point}")
                        if description:
                            parts.append(f"\n详细描述：{description}")

                        image_text = "\n".join(parts)

                        return {
                            "text": image_text,
                            "section": "图片",
                            "page": img_info.get("page", 1),
                            "image_type": image_type,
                            "chart_type": chart_type,
                            "image_path": image_path,
                            "analysis": analysis
                        }
                    else:
                        logger.warning(f"图片分析失败: {analysis.get('error', '未知错误')}")
                        return None

                except Exception as e:
                    logger.warning(f"⚠️ 图片处理失败: {e}")
                    return None

            # 并行分析图片（每批3张，避免API限流）
            BATCH_SIZE = 3
            for batch_start in range(0, len(pdf_images), BATCH_SIZE):
                batch = pdf_images[batch_start:batch_start + BATCH_SIZE]
                progress = 35 + int((batch_start + len(batch)) / max(total_images, 1) * 30)
                update_task(task_id, progress=progress, message=f"正在分析图片 {batch_start+1}-{batch_start+len(batch)}/{total_images}...")

                results = await asyncio.gather(*[analyze_one(idx, info) for idx, info in enumerate(batch)], return_exceptions=True)
                for r in results:
                    if isinstance(r, dict):
                        all_images_info.append(r)
                    elif isinstance(r, Exception):
                        logger.warning(f"️ 图片分析异常: {r}")

            logger.info(f"📊 图片分析完成：共 {total_images} 张，成功分析 {len(all_images_info)} 张")

            # 保存图片到数据库（新增）
            from app.models.paper import Image as ImageModel
            saved_images = []
            for image_info in all_images_info:
                try:
                    # 从 pdf_images 中找到对应的原始信息
                    original_info = None
                    for img in pdf_images:
                        if img.get("image_path") == image_info.get("image_path"):
                            original_info = img
                            break
                    
                    if original_info:
                        image_record = ImageModel(
                            paper_id=paper_id,
                            page_number=original_info.get("page", 1),
                            image_index=original_info.get("image_index", 1),
                            file_path=original_info.get("image_path", ""),
                            width=original_info.get("width", 0),
                            height=original_info.get("height", 0),
                            aspect_ratio=original_info.get("aspect_ratio", 0),
                            image_type=image_info.get("image_type", "other"),
                            chart_type=image_info.get("chart_type", ""),
                            analysis_result=image_info.get("analysis", {}),
                            is_filtered=False,
                            extraction_method=original_info.get("extraction_method", "pymupdf")
                        )
                        db.add(image_record)
                        saved_images.append(image_record)
                except Exception as e:
                    logger.warning(f"保存图片到数据库失败: {e}")
            
            if saved_images:
                await db.flush()  # 刷新以获取 ID
                logger.info(f"✅ 保存 {len(saved_images)} 张图片到数据库")

            # 为表格分配到章节
            tables_by_page = {}
            for table in pdf_tables:
                page_num = table.get("page", 1)
                if page_num not in tables_by_page:
                    tables_by_page[page_num] = []
                tables_by_page[page_num].append(table)

            update_task(task_id, progress=70, message="正在分析表格数据...")

            # 分析表格（使用文本模型）
            from app.parsers.table_analyzer import TableSemanticAnalyzer
            table_analyzer = TableSemanticAnalyzer(use_llm=True)

            analyzed_tables = []
            for table_idx, table in enumerate(pdf_tables):
                try:
                    # 使用新的 Markdown/CSV 格式（兼容 pdfplumber 和 VLM）
                    table_markdown = table.get("markdown", table.get("markdown_content", ""))
                    table_csv = table.get("csv", table.get("csv_content", ""))
                    table_content = table.get("content", [])

                    # 保存 Markdown 和 CSV 文件
                    table_filename = f"table_{table_idx+1}_p{table.get('page', 1)}"
                    markdown_path = None
                    csv_path = None
                    if table_markdown:
                        markdown_path = os.path.join(tables_dir, f"{table_filename}.md")
                        with open(markdown_path, 'w', encoding='utf-8') as f:
                            f.write(table_markdown)
                    if table_csv:
                        csv_path = os.path.join(tables_dir, f"{table_filename}.csv")
                        with open(csv_path, 'w', encoding='utf-8') as f:
                            f.write(table_csv)

                    # 优先使用文本模型分析
                    analysis = await table_analyzer.analyze_table(
                        table_data=table_content,
                        caption=table.get("caption", ""),
                        context="论文表格分析",
                        table_markdown=table_markdown,
                        table_csv=table_csv
                    )

                    if analysis.get("success"):
                        table["semantic_analysis"] = analysis

                        # 构建文本表示
                        parts = [f"【表格】"]
                        if table.get("caption"):
                            parts.append(f"标题：{table['caption']}")
                        if analysis.get("purpose"):
                            parts.append(f"\n目的：{analysis['purpose']}")
                        if analysis.get("data_summary"):
                            parts.append(f"\n总结：{analysis['data_summary']}")
                        if analysis.get("key_insights"):
                            parts.append(f"\n关键洞察：")
                            for i, insight in enumerate(analysis["key_insights"], 1):
                                parts.append(f"  {i}. {insight}")

                        table_text = "\n".join(parts)

                        analyzed_tables.append({
                            "table": table,
                            "analysis": analysis,
                            "text": table_text,
                            "page": table.get("page", 1),
                            "markdown_path": markdown_path if table_markdown else None,
                            "csv_path": csv_path if table_csv else None
                        })
                    else:
                        logger.warning(f"表格分析失败: {analysis.get('error', '未知错误')}")
                        # 使用原始格式
                        caption = table.get("caption", f"表{len(analyzed_tables)+1}")
                        table_text = _table_to_text(table.get("content", []), caption)
                        analyzed_tables.append({
                            "table": table,
                            "analysis": None,
                            "text": table_text,
                            "page": table.get("page", 1),
                            "markdown_path": markdown_path if table_markdown else None,
                            "csv_path": csv_path if table_csv else None
                        })
                except Exception as e:
                    logger.warning(f"⚠️ 表格处理失败: {e}")
                    # 使用原始格式
                    caption = table.get("caption", f"表{len(analyzed_tables)+1}")
                    table_text = _table_to_text(table.get("content", []), caption)
                    analyzed_tables.append({
                        "table": table,
                        "analysis": None,
                        "text": table_text,
                        "page": table.get("page", 1),
                        "markdown_path": markdown_path if table_markdown else None,
                        "csv_path": csv_path if table_csv else None
                    })
                except Exception as e:
                    logger.warning(f"⚠️ 表格处理失败: {e}")
                    # 使用原始格式
                    caption = table.get("caption", f"表{len(analyzed_tables)+1}")
                    table_text = _table_to_text(table.get("content", []), caption)
                    analyzed_tables.append({
                        "table": table,
                        "analysis": None,
                        "text": table_text,
                        "page": table.get("page", 1),
                        "markdown_path": None,
                        "csv_path": None
                    })

            logger.info(f"📊 表格分析完成：共 {len(pdf_tables)} 个表格，保存到 {tables_dir}")

            # 保存表格到数据库（新增）
            from app.models.paper import Table as TableModel
            saved_tables = []
            for table_idx, analyzed_table in enumerate(analyzed_tables):
                try:
                    table = analyzed_table["table"]
                    analysis = analyzed_table["analysis"]
                    
                    # 检测表格是否乱码
                    is_corrupted = False
                    if analysis:
                        is_corrupted = analysis.get("analysis_method") == "rules"
                    
                    table_record = TableModel(
                        paper_id=paper_id,
                        page_number=table.get("page", 1),
                        table_number=table_idx + 1,
                        caption=table.get("caption", table.get("table_title", "")),
                        markdown_content=table.get("markdown", table.get("markdown_content", "")),
                        csv_content=table.get("csv", table.get("csv_content", "")),
                        raw_content=table.get("content", []),
                        analysis_result=analysis or {},
                        markdown_path=analyzed_table.get("markdown_path"),
                        csv_path=analyzed_table.get("csv_path"),
                        is_corrupted=is_corrupted,
                        extraction_method=table.get("extraction_method", "pdfplumber")
                    )
                    db.add(table_record)
                    saved_tables.append(table_record)
                except Exception as e:
                    logger.warning(f"保存表格到数据库失败: {e}")
            
            if saved_tables:
                await db.flush()  # 刷新以获取 ID
                logger.info(f"✅ 保存 {len(saved_tables)} 个表格到数据库")

            update_task(task_id, progress=75, message="正在保存章节数据...")

            for i, section_data in enumerate(sections):
                section_title = section_data.get('title', f'第{i+1}节')
                section_content = section_data.get('content', '')

                key_points = section_data.get('key_points', [])
                if isinstance(key_points, list):
                    key_points = json.dumps(key_points, ensure_ascii=False)

                text_tables = extractor.extract_tables_from_text(section_content, section_title)
                figures = extractor.extract_figures_from_text(section_content, section_title)
                formulas = extractor.extract_formulas(section_content, section_title)

                merged_tables = []
                section_start_page = i * 2 + 1
                section_end_page = section_start_page + 1

                # 使用分析后的表格
                for analyzed_table in analyzed_tables:
                    page_num = analyzed_table["page"]
                    if section_start_page <= page_num <= section_end_page:
                        table = analyzed_table["table"]
                        table_text = analyzed_table["text"]
                        analysis = analyzed_table["analysis"]

                        if table_text:
                            all_tables_text.append({
                                "text": table_text,
                                "section": section_title,
                                "page": page_num,
                                "analysis": analysis
                            })

                        merged_tables.append({
                            "table_number": len(merged_tables) + 1,
                            "page": page_num,
                            "content": table.get("content", []),
                            "markdown": table.get("markdown", ""),
                            "csv": table.get("csv", ""),
                            "caption": table.get("caption", ""),
                            "source": "pdfplumber",
                            "text_representation": table_text,
                            "semantic_analysis": analysis
                        })

                if not merged_tables:
                    merged_tables = text_tables
                    for table in text_tables:
                        caption = table.get("caption", "")
                        table_text = _table_to_text(table.get("content", []), caption)
                        if table_text:
                            all_tables_text.append({"text": table_text, "section": section_title})

                section = Section(
                    paper_id=paper_id,
                    section_title=section_title,
                    order_index=i,
                    start_page=section_start_page,
                    content=section_content,
                    key_points=key_points,
                    tables=merged_tables,
                    figures=figures,
                    formulas=formulas
                )
                db.add(section)
            
            await db.commit()
            
            update_task(task_id, progress=85, message="正在构建向量索引...")
            
            kb = get_knowledge_base()
            chunker = SmartChunker()
            chunks = []
            
            for i, section_data in enumerate(parse_result.get('sections', [])):
                section_title = section_data.get('title', f'第{i+1}节')
                section_content = section_data.get('content', '')
                
                if section_content:
                    section_chunks = chunker.chunk_text(section_content, section_title)
                    chunks.extend(section_chunks)
            
            if not chunks:
                chunks = chunker.chunk_text(raw_text[:100000], "全文")
            
            for table_info in all_tables_text:
                table_chunk = {
                    "content": table_info["text"],
                    "type": "table",
                    "section": table_info["section"],
                    "page": table_info.get("page", 1),
                    "index": len(chunks)
                }
                chunks.append(table_chunk)
            
            for image_info in all_images_info:
                image_chunk = {
                    "content": image_info["text"],
                    "type": "image",
                    "section": image_info["section"],
                    "page": image_info.get("page", 1),
                    "image_type": image_info.get("image_type", "other"),
                    "image_path": image_info.get("image_path", ""),
                    "index": len(chunks)
                }
                chunks.append(image_chunk)
            
            logger.info(f"智能分块完成：共 {len(chunks)} 个片段")
            await kb.add_paper_chunks(paper_id, chunks)
            
            update_task(task_id, status="completed", progress=100, message="处理完成！")
            logger.info(f"✅ 论文处理完成: {paper_id}")
            
    except Exception as e:
        logger.error(f"❌ 论文处理失败: {e}")
        update_task(task_id, status="failed", progress=0, message=f"处理失败: {str(e)}")


async def _schedule_process_paper(paper_id: str, file_path: str, user_id: str, raw_text: str):
    """安排论文处理任务在后台执行"""
    await _process_paper_async(paper_id, file_path, user_id, raw_text)


@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...), 
    authorization: str = Header(None), 
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """异步上传论文 - 立即返回任务ID，后台处理"""
    logger.info("🔄 收到上传请求，开始处理...")
    
    user_id = await get_current_user_id(authorization, db)
    logger.info(f"👤 用户ID: {user_id}")
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持 PDF 格式")
    
    content = await file.read()
    file_size = len(content)
    logger.info(f"📄 文件名: {file.filename}, 大小: {file_size/1024/1024:.2f}MB")
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小不能超过 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB")
    
    paper_id = str(uuid.uuid4())
    file_path = f"{settings.FILE_STORAGE_PATH}/{paper_id}.pdf"
    os.makedirs(settings.FILE_STORAGE_PATH, exist_ok=True)
    
    with open(file_path, "wb") as f:
        f.write(content)
    logger.info(f"💾 文件已保存: {file_path}")
    
    # 提取文本
    raw_text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    raw_text += text + "\n\n"
                if i > 50:
                    break
        logger.info(f"📝 提取文本完成，长度: {len(raw_text)}")
    except Exception as e:
        logger.error(f"❌ PDF 解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 解析失败：{str(e)}")
    
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="无法从 PDF 中提取文字")
    
    # 创建任务
    task = create_task(paper_id, user_id)
    logger.info(f"✅ 任务创建成功: {task.task_id}")
    
    # 使用 asyncio.create_task 确保后台任务在响应返回后执行
    logger.info("🚀 启动后台处理任务...")
    asyncio.create_task(_schedule_process_paper(paper_id, file_path, user_id, raw_text))
    
    # 立即返回，不等待后台处理完成
    logger.info(f"🔔 上传接口立即返回，task_id={task.task_id}, paper_id={paper_id}")
    return {
        "task_id": task.task_id,
        "paper_id": paper_id,
        "message": "上传成功，正在后台处理论文...",
        "status_url": f"/api/v1/papers/tasks/{task.task_id}"
    }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, authorization: str = Header(None)):
    """查询任务状态"""
    # 验证token
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        if payload:
            user_id = payload.get("sub")
    
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "task_id": task.task_id,
        "paper_id": task.paper_id,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "details": task.details,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat()
    }


@router.delete("/{paper_id}")
async def delete_paper(paper_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    kb = get_knowledge_base()
    await kb.delete_paper(paper_id)
    
    await db.delete(paper)
    await db.commit()
    
    if paper.pdf_path and os.path.exists(paper.pdf_path):
        os.remove(paper.pdf_path)
    
    return {"message": "删除成功"}


async def run_enhanced_qa_agent(paper_id: str, question: str, chunks: List[Dict], paper_metadata: Dict[str, Any]):
    """增强版问答 Agent"""
    from app.agent.qa.graph import run_qa_agent
    return await run_qa_agent(paper_id, question, chunks, paper_metadata)


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
    
    paper_metadata = {
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "keywords": paper.keywords or [],
        "venue": getattr(paper, 'venue', None),
        "publication_year": getattr(paper, 'publication_year', None),
        "doi": getattr(paper, 'doi', None),
    }
    
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
    """深度解读论文"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    interpret_type = data.get("type", "concept")
    
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
        paragraphs = [p.strip() for p in paper.full_text.split('\n\n') if p.strip()]
        sections_data = [
            {
                "title": f"段落 {i+1}",
                "content": p,
                "order_index": i
            }
            for i, p in enumerate(paragraphs[:100])
        ]
    else:
        raise HTTPException(status_code=400, detail="论文内容为空，无法生成摘要")
    
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
    
    # 如果没有预先生成的摘要，临时生成
    return await generate_structured_summary(paper_id, authorization, db)