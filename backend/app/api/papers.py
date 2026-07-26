"""论文 API 模块"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict, Any
import os
import uuid
import logging
import asyncio
import time

logger = logging.getLogger(__name__)

from app.database import get_db, AsyncSessionLocal
from app.models.paper import Paper, Section, Table as TableModel
from app.api.auth import decode_token
from app.agent.paper_parser.graph import run_paper_parser
from app.rag.knowledge_base import get_knowledge_base, SmartChunker
from app.api.dependencies import get_current_user_id
from app.config import settings
from app.parsers.multimedia_extractor import MultimediaExtractor
from app.utils.task_manager import create_task, update_task, get_task
from app.utils.background_tasks import spawn_background_task
from app.services.paper_files import (
    extract_pdf_page_contents as _extract_pdf_page_contents,
    extract_pdf_page_texts as _extract_pdf_page_texts,
    extract_pdf_text as _extract_pdf_text,
    find_content_page as _find_content_page,
    iter_file_range as _iter_file_range,
    normalize_page_text as _normalize_page_text,
    parse_byte_range as _parse_byte_range,
    save_validated_pdf as _save_validated_pdf,
)
from app.services.paper_indexing import (
    build_complete_text_chunks as _build_complete_text_chunks,
    build_text_chunks as _build_text_chunks,
    normalize_key_points as _normalize_key_points,
    normalize_sections as _normalize_sections,
)
from app.services.paper_outline import enrich_sections_with_pdf as _enrich_sections_with_pdf
from app.services.paper_core_processing import paper_core_processing_service
from app.services.paper_upload import (
    PaperTextExtractionError,
    PaperTextMissingError,
    paper_upload_service,
)

router = APIRouter(prefix="/api/v1/papers")


def _get_paper_media_state(paper_id: str) -> Dict[str, Any]:
    """Read the persisted enrichment state for a paper without requiring a DB column."""
    task = get_task(f"task_{paper_id}")
    if not task:
        return {"media_status": "completed", "media_message": "图表已完成"}

    media_status = task.details.get("media_status")
    if not media_status:
        if task.status.value == "ready":
            media_status = "processing"
        elif task.status.value == "completed":
            media_status = "completed"
        elif task.status.value == "failed":
            media_status = "failed"
        else:
            media_status = "processing"

    messages = {
        "processing": "图表增强中",
        "completed": "图表已完成",
        "failed": "图表增强失败",
        "interrupted": "图表增强因服务重启中断",
        "not_started": "图表尚未处理",
    }
    return {
        "media_status": media_status,
        "media_message": messages.get(media_status, "图表状态未知"),
        "media_updated_at": task.updated_at.isoformat(),
    }


def _build_timing_details(
    timings: Dict[str, float],
    total_seconds: float,
    counts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rounded_total = round(max(total_seconds, 0), 3)
    rounded_timings = {name: round(seconds, 3) for name, seconds in timings.items()}
    measured_total = sum(timings.values())
    if rounded_total > measured_total:
        rounded_timings["other"] = round(rounded_total - measured_total, 3)
    percentages = {
        name: round(seconds / rounded_total * 100, 1) if rounded_total else 0
        for name, seconds in rounded_timings.items()
        if name != "total"
    }
    rounded_timings["total"] = rounded_total
    return {
        "timings_seconds": rounded_timings,
        "timing_percentages": percentages,
        "counts": counts or {},
    }


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
        query = query.filter(Paper.reading_status == status)
    
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
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                **_get_paper_media_state(p.id),
            }
            for p in papers
        ],
        "total": len(papers)
    }


@router.get("/{paper_id}/pdf")
async def get_paper_pdf(
    paper_id: str,
    token: str = Query(None),
    authorization: str = Header(None),
    range_header: str = Header(None, alias="Range"),
    db: AsyncSession = Depends(get_db),
):
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
    
    file_size = os.path.getsize(paper.pdf_path)
    common_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{safe_filename}"',
        "Cache-Control": "private, max-age=3600",
    }

    if range_header:
        byte_range = _parse_byte_range(range_header, file_size)
        if byte_range is None:
            return Response(
                status_code=416,
                headers={**common_headers, "Content-Range": f"bytes */{file_size}"},
            )

        start, end = byte_range
        return StreamingResponse(
            _iter_file_range(paper.pdf_path, start, end),
            status_code=206,
            media_type="application/pdf",
            headers={
                **common_headers,
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(end - start + 1),
            },
        )

    return FileResponse(
        paper.pdf_path,
        media_type="application/pdf",
        headers=common_headers,
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
    tables_result = await db.execute(
        select(TableModel)
        .where(TableModel.paper_id == paper_id)
        .order_by(TableModel.table_number)
    )
    paper_tables = tables_result.scalars().all()
    
    return {
        "tables": [
            {
                "id": table.id,
                "table_number": table.table_number,
                "caption": table.caption,
                "page": table.page_number,
            }
            for table in paper_tables
        ],
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


@router.post("/{paper_id}/sections/rebuild")
async def rebuild_paper_sections(
    paper_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Rebuild an existing paper outline from parser data and PDF layout metadata."""
    user_id = await get_current_user_id(authorization, db)
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    if not paper.pdf_path or not os.path.exists(paper.pdf_path):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    section_result = await db.execute(
        select(Section)
        .where(Section.paper_id == paper_id)
        .order_by(Section.order_index)
    )
    existing = list(section_result.scalars().all())
    base_sections = [
        {
            "title": section.section_title,
            "content": section.content or "",
            "key_points": section.key_points or [],
        }
        for section in existing
    ]
    rebuilt = _enrich_sections_with_pdf(
        base_sections,
        paper.pdf_path,
        _extract_pdf_page_contents(paper.pdf_path),
    )
    by_title = {
        _normalize_page_text(section.section_title): section
        for section in existing
    }
    extractor = MultimediaExtractor(pdf_path=paper.pdf_path)
    added = 0
    for item in rebuilt:
        title = str(item.get("title") or "未命名章节")[:200]
        normalized = _normalize_page_text(title)
        section = by_title.get(normalized)
        if section is None:
            content = str(item.get("content") or "")
            section = Section(
                paper_id=paper_id,
                section_title=title,
                content=content,
                key_points=_normalize_key_points(item.get("key_points", [])),
                tables=extractor.extract_tables_from_text(content, title),
                figures=extractor.extract_figures_from_text(content, title),
                formulas=extractor.extract_formulas(content, title),
            )
            db.add(section)
            by_title[normalized] = section
            added += 1
        section.order_index = int(item.get("order_index") or 0)
        section.start_page = int(item.get("start_page") or 1)

    await db.commit()
    return {
        "message": "目录重新抽取完成",
        "sections": len(rebuilt),
        "added": added,
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
        "updated_at": paper.updated_at.isoformat() if paper.updated_at else None,
        **_get_paper_media_state(paper.id),
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
    raw_text: str,
    initial_timings: Optional[Dict[str, float]] = None,
    pipeline_started_at: Optional[float] = None,
    initial_counts: Optional[Dict[str, Any]] = None,
):
    """异步处理论文的核心逻辑"""
    task_id = f"task_{paper_id}"
    
    timings = dict(initial_timings or {})
    counts: Dict[str, Any] = dict(initial_counts or {})
    started_at = pipeline_started_at or time.perf_counter()
    core_ready = False
    ready_seconds: Optional[float] = None

    def finish_stage(name: str, stage_started_at: float) -> None:
        timings[name] = time.perf_counter() - stage_started_at
        logger.info("⏱️ %s 耗时 %.2fs", name, timings[name])
        details = _build_timing_details(
            timings,
            time.perf_counter() - started_at,
            counts,
        )
        if core_ready and ready_seconds is not None:
            details["ready_seconds"] = round(ready_seconds, 3)
            details["media_status"] = "processing"
        update_task(
            task_id,
            details=details,
        )

    try:
        update_task(task_id, status="processing", progress=10, message="正在解析论文结构...")
        
        # 解析论文结构
        parse_started_at = time.perf_counter()
        structure = await paper_core_processing_service.extract_structure(
            paper_id=paper_id,
            file_path=file_path,
            raw_text=raw_text,
        )
        finish_stage("structure_parsing", parse_started_at)

        sections = structure.sections
        page_contents = structure.page_contents
        extractor = MultimediaExtractor(pdf_path=file_path)
        logger.info(f"标准化后解析到 {len(sections)} 个有效章节")

        update_task(task_id, progress=45, message="正在保存正文和章节...")
        core_persistence_started_at = time.perf_counter()
        await paper_core_processing_service.persist_core(
            paper_id=paper_id,
            user_id=user_id,
            file_path=file_path,
            raw_text=raw_text,
            structure=structure,
        )
        finish_stage("core_database_persistence", core_persistence_started_at)

        update_task(task_id, progress=70, message="正在构建正文知识库...")
        core_vector_started_at = time.perf_counter()
        counts["text_vector_chunks"] = await paper_core_processing_service.build_text_index(
            paper_id=paper_id,
            raw_text=raw_text,
            file_path=file_path,
            structure=structure,
        )
        finish_stage("core_vector_indexing", core_vector_started_at)

        ready_seconds = time.perf_counter() - started_at
        ready_details = _build_timing_details(timings, ready_seconds, counts)
        ready_details["ready_seconds"] = round(ready_seconds, 3)
        ready_details["media_status"] = "processing"
        update_task(
            task_id,
            status="ready",
            progress=100,
            message="论文已可用，图表继续后台增强",
            details=ready_details,
        )
        core_ready = True

        # 媒体增强使用独立事务；失败不会回滚已经可用的正文论文。
        async with AsyncSessionLocal() as db:
            update_task(task_id, message="论文已可用，正在增强表格和图片...")
            import os
            paper_storage_dir = f"data/papers/{paper_id}"
            images_dir = os.path.join(paper_storage_dir, "images")
            tables_dir = os.path.join(paper_storage_dir, "tables")
            os.makedirs(images_dir, exist_ok=True)
            os.makedirs(tables_dir, exist_ok=True)

            update_task(task_id, message="论文已可用，正在提取表格数据...")

            # 提取表格（优先使用 pdfplumber，失败则尝试 VLM 图片提取）
            pdf_tables = []
            vlm_tables = []
            table_extraction_started_at = time.perf_counter()
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
            finish_stage("table_extraction", table_extraction_started_at)
            counts["tables_extracted"] = len(pdf_tables)
            counts["tables_from_vision"] = len(vlm_tables)

            update_task(task_id, message="论文已可用，正在提取图片...")

            # 提取图片（使用规范存储路径）
            pdf_images = []
            image_extraction_started_at = time.perf_counter()
            try:
                pdf_images = await extractor.extract_images_from_pdf(file_path, output_dir=images_dir)
                logger.info(f"从 PDF 提取到 {len(pdf_images)} 张图片，保存到 {images_dir}")
            except Exception as e:
                logger.warning(f"PDF 图片提取失败: {e}")
            finish_stage("image_extraction", image_extraction_started_at)
            counts["image_candidates"] = len(pdf_images)

            # 收集表格和图片信息
            all_tables_text = []
            all_images_info = []

            update_task(task_id, message="论文已可用，正在分析图片...")
            
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
            image_analysis_started_at = time.perf_counter()
            for batch_start in range(0, len(pdf_images), BATCH_SIZE):
                batch = pdf_images[batch_start:batch_start + BATCH_SIZE]
                update_task(
                    task_id,
                    message=f"论文已可用，正在分析图片 {batch_start+1}-{batch_start+len(batch)}/{total_images}...",
                )

                results = await asyncio.gather(*[analyze_one(idx, info) for idx, info in enumerate(batch)], return_exceptions=True)
                for r in results:
                    if isinstance(r, dict):
                        all_images_info.append(r)
                    elif isinstance(r, Exception):
                        logger.warning(f"️ 图片分析异常: {r}")

            logger.info(f"📊 图片分析完成：共 {total_images} 张，成功分析 {len(all_images_info)} 张")
            finish_stage("image_analysis", image_analysis_started_at)
            counts["images_analyzed"] = len(all_images_info)

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
                # 这些记录的 ID 在后续流程中不会使用，延迟到最终提交时统一写入，
                # 避免在表格模型调用期间长期持有 SQLite 写锁。
                logger.info(f"✅ 待保存 {len(saved_images)} 张图片到数据库")

            # 为表格分配到章节
            tables_by_page = {}
            for table in pdf_tables:
                page_num = table.get("page", 1)
                if page_num not in tables_by_page:
                    tables_by_page[page_num] = []
                tables_by_page[page_num].append(table)

            update_task(task_id, message="论文已可用，正在整理表格数据...")

            # 分析表格（使用文本模型）
            from app.parsers.table_analyzer import TableSemanticAnalyzer
            table_analyzer = TableSemanticAnalyzer(use_llm=True)

            analyzed_tables = []
            table_analysis_started_at = time.perf_counter()
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

                    if table.get("extraction_method") == "vlm_table_extraction":
                        # 视觉模型已经读取过该表格，避免对同一内容再次调用文本模型。
                        analysis = {
                            "success": True,
                            "caption": table.get("table_title", table.get("caption", "")),
                            "purpose": "",
                            "data_summary": table.get("core_conclusion", ""),
                            "key_insights": table.get("key_data_points", []),
                            "analysis_method": "vision",
                        }
                    else:
                        analysis = await table_analyzer.analyze_table(
                            table_data=table_content,
                            caption=table.get("caption", ""),
                            context="论文表格分析",
                            table_markdown=table_markdown,
                            table_csv=table_csv
                        )

                    if analysis.get("success"):
                        table["semantic_analysis"] = analysis

                        # 构建包含表号、标题和实际数据的文本表示，供表格问答检索。
                        table_number = table_idx + 1
                        table_caption = (
                            table.get("caption")
                            or table.get("table_title")
                            or f"表{table_number}"
                        )
                        table["caption"] = table_caption
                        table["table_number"] = table_number
                        parts = [f"【表{table_number}】{table_caption}"]
                        if table_markdown:
                            parts.append(f"\n表格数据：\n{table_markdown}")
                        elif table_csv:
                            parts.append(f"\n表格数据：\n{table_csv}")
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
                            "table_number": table_number,
                            "caption": table_caption,
                            "page": table.get("page", 1),
                            "markdown_path": markdown_path if table_markdown else None,
                            "csv_path": csv_path if table_csv else None
                        })
                    else:
                        logger.warning(f"表格分析失败: {analysis.get('error', '未知错误')}")
                        # 使用原始格式
                        table_number = table_idx + 1
                        caption = table.get("caption") or table.get("table_title") or f"表{table_number}"
                        table["caption"] = caption
                        table["table_number"] = table_number
                        table_text = _table_to_text(table.get("content", []), caption)
                        analyzed_tables.append({
                            "table": table,
                            "analysis": None,
                            "text": table_text,
                            "table_number": table_number,
                            "caption": caption,
                            "page": table.get("page", 1),
                            "markdown_path": markdown_path if table_markdown else None,
                            "csv_path": csv_path if table_csv else None
                        })
                except Exception as e:
                    logger.warning(f"⚠️ 表格处理失败: {e}")
                    # 使用原始格式
                    table_number = table_idx + 1
                    caption = table.get("caption") or table.get("table_title") or f"表{table_number}"
                    table["caption"] = caption
                    table["table_number"] = table_number
                    table_text = _table_to_text(table.get("content", []), caption)
                    analyzed_tables.append({
                        "table": table,
                        "analysis": None,
                        "text": table_text,
                        "table_number": table_number,
                        "caption": caption,
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
            finish_stage("table_analysis", table_analysis_started_at)

            # 保存表格到数据库（新增）
            persistence_started_at = time.perf_counter()
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

            update_task(task_id, message="论文已可用，正在保存媒体数据...")

            section_result = await db.execute(
                select(Section)
                .where(Section.paper_id == paper_id)
                .order_by(Section.order_index)
            )
            persisted_sections = {
                section.order_index: section
                for section in section_result.scalars().all()
            }

            for i, section_data in enumerate(sections):
                section_title = section_data.get('title', f'第{i+1}节')
                section_content = section_data.get('content', '')

                key_points = section_data.get('key_points', [])
                key_points = _normalize_key_points(key_points)

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
                                "analysis": analysis,
                                "table_number": table.get("table_number"),
                                "caption": table.get("caption", ""),
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

                section = persisted_sections.get(i)
                if section:
                    section.tables = merged_tables
                    section.figures = figures
                    section.formulas = formulas
            
            await db.commit()
            finish_stage("database_persistence", persistence_started_at)
            
            update_task(task_id, message="论文已可用，正在追加图表知识库...")

            media_chunks = []
            vector_started_at = time.perf_counter()

            for table_info in all_tables_text:
                table_chunk = {
                    "content": table_info["text"],
                    "type": "table",
                    "section": table_info["section"],
                    "page": table_info.get("page", 1),
                    "table_number": table_info.get("table_number"),
                    "caption": table_info.get("caption", ""),
                    "index": len(text_chunks) + len(media_chunks)
                }
                media_chunks.append(table_chunk)
            
            for image_info in all_images_info:
                image_chunk = {
                    "content": image_info["text"],
                    "type": "image",
                    "section": image_info["section"],
                    "page": image_info.get("page", 1),
                    "image_type": image_info.get("image_type", "other"),
                    "image_path": image_info.get("image_path", ""),
                    "index": len(text_chunks) + len(media_chunks)
                }
                media_chunks.append(image_chunk)
            
            logger.info(f"媒体分块完成：共 {len(media_chunks)} 个片段")
            if media_chunks and not await kb.add_paper_chunks(paper_id, media_chunks):
                raise RuntimeError("图表知识库追加失败")
            finish_stage("media_vector_indexing", vector_started_at)
            counts["media_vector_chunks"] = len(media_chunks)

            total_seconds = time.perf_counter() - started_at
            details = _build_timing_details(timings, total_seconds, counts)
            details["ready_seconds"] = round(ready_seconds or total_seconds, 3)
            details["media_status"] = "completed"
            
            update_task(
                task_id,
                status="completed",
                progress=100,
                message="处理完成！",
                details=details,
            )
            logger.info("✅ 论文处理完成: %s，总耗时 %.2fs，阶段统计: %s", paper_id, total_seconds, details)
            
    except Exception as e:
        logger.error(f"❌ 论文处理失败: {e}")
        details = _build_timing_details(timings, time.perf_counter() - started_at, counts)
        if ready_seconds is not None:
            details["ready_seconds"] = round(ready_seconds, 3)
        details["media_status"] = "failed" if core_ready else "not_started"
        details["media_error"] = str(e) if core_ready else None
        update_task(
            task_id,
            status="completed" if core_ready else "failed",
            progress=100 if core_ready else 0,
            message="论文可用，但图表增强失败" if core_ready else f"处理失败: {str(e)}",
            details=details,
        )


async def _schedule_process_paper(
    paper_id: str,
    file_path: str,
    user_id: str,
    raw_text: str,
    initial_timings: Optional[Dict[str, float]] = None,
    pipeline_started_at: Optional[float] = None,
    initial_counts: Optional[Dict[str, Any]] = None,
):
    """安排论文处理任务在后台执行"""
    await _process_paper_async(
        paper_id,
        file_path,
        user_id,
        raw_text,
        initial_timings,
        pipeline_started_at,
        initial_counts,
    )


@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...), 
    authorization: str = Header(None), 
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """异步上传论文 - 立即返回任务ID，后台处理"""
    pipeline_started_at = time.perf_counter()
    initial_timings: Dict[str, float] = {}
    logger.info("🔄 收到上传请求，开始处理...")
    
    user_id = await get_current_user_id(authorization, db)
    logger.info(f"👤 用户ID: {user_id}")
    
    paper_id = str(uuid.uuid4())
    original_filename = file.filename
    try:
        upload_result = await paper_upload_service.receive(
            upload=file,
            paper_id=paper_id,
            storage_path=settings.FILE_STORAGE_PATH,
            max_upload_size=settings.MAX_UPLOAD_SIZE,
        )
    except PaperTextExtractionError as exc:
        logger.error("❌ PDF 解析失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"PDF 解析失败：{exc}") from exc
    except PaperTextMissingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    initial_timings.update(upload_result.timings)
    file_path = upload_result.file_path
    raw_text = upload_result.raw_text
    text_extraction_method = upload_result.text_extraction_method
    logger.info(
        "📄 文件名: %s, 大小: %.2fMB",
        original_filename,
        upload_result.file_size / 1024 / 1024,
    )
    logger.info("💾 文件已保存: %s", file_path)
    logger.info(
        "📝 提取文本完成，方式: %s，长度: %s",
        text_extraction_method,
        len(raw_text),
    )
    
    # 创建任务
    task = create_task(paper_id, user_id)
    initial_counts = {"text_extraction_method": text_extraction_method}
    update_task(
        task.task_id,
        details=_build_timing_details(
            initial_timings,
            time.perf_counter() - pipeline_started_at,
            initial_counts,
        ),
    )
    logger.info(f"✅ 任务创建成功: {task.task_id}")
    
    # 登记后台任务，确保异常可见并在应用关闭时正确取消。
    logger.info("🚀 启动后台处理任务...")
    spawn_background_task(
        _schedule_process_paper(
            paper_id,
            file_path,
            user_id,
            raw_text,
            initial_timings,
            pipeline_started_at,
            initial_counts,
        ),
        name=f"paper-upload-{paper_id}",
    )
    
    # 立即返回，不等待后台处理完成
    logger.info(f"🔔 上传接口立即返回，task_id={task.task_id}, paper_id={paper_id}")
    return {
        "task_id": task.task_id,
        "paper_id": paper_id,
        "message": "上传成功，正在后台处理论文...",
        "status_url": f"/api/v1/papers/tasks/{task.task_id}"
    }


async def _recover_one_paper_task(task) -> None:
    """Restart an interrupted pre-ready upload from its persisted PDF."""
    file_path = f"{settings.FILE_STORAGE_PATH}/{task.paper_id}.pdf"
    details = dict(task.details or {})
    recovery_count = int(details.get("recovery_count", 0))
    if recovery_count >= 2:
        update_task(
            task.task_id,
            status="failed",
            progress=0,
            message="服务重启恢复次数已达上限，请重新上传",
        )
        return
    if not os.path.exists(file_path):
        update_task(
            task.task_id,
            status="failed",
            progress=0,
            message="恢复失败：原始 PDF 不存在，请重新上传",
        )
        return

    details["recovery_count"] = recovery_count + 1
    update_task(
        task.task_id,
        status="processing",
        progress=5,
        message=f"服务重启后正在恢复任务（第 {recovery_count + 1} 次）",
        details=details,
    )
    raw_text, extraction_method = await asyncio.to_thread(_extract_pdf_text, file_path)
    if not raw_text.strip():
        update_task(task.task_id, status="failed", progress=0, message="恢复失败：PDF 无可提取文字")
        return

    # PROCESSING may have committed a partial core record before interruption.
    # Remove it and rebuild from the persisted source to keep the pipeline idempotent.
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Paper).where(Paper.id == task.paper_id))
        existing = result.scalar_one_or_none()
        if existing is not None:
            await db.delete(existing)
            await db.commit()
    await get_knowledge_base().delete_paper(task.paper_id)
    await _schedule_process_paper(
        task.paper_id,
        file_path,
        task.user_id,
        raw_text,
        initial_counts={"text_extraction_method": extraction_method, "recovered": True},
    )


def recover_incomplete_paper_tasks() -> int:
    """Schedule persisted tasks after application startup; return scheduled count."""
    from app.utils.task_manager import TaskStatus, list_tasks

    scheduled = 0
    for task in list_tasks({TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.READY}):
        if task.status == TaskStatus.READY:
            details = dict(task.details or {})
            details["media_status"] = "interrupted"
            update_task(
                task.task_id,
                status="completed",
                message="论文正文可用；图表增强因服务重启中断",
                details=details,
            )
            continue
        spawn_background_task(
            _recover_one_paper_task(task),
            name=f"paper-recovery-{task.paper_id}",
        )
        scheduled += 1
    return scheduled


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, authorization: str = Header(None)):
    """查询任务状态"""
    user_id = await get_current_user_id(authorization)
    task = get_task(task_id)
    # 对非任务所有者也返回 404，避免泄露任务是否存在。
    if not task or task.user_id != user_id:
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
