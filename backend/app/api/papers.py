"""论文 API 模块"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Header, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from typing import Optional, List, Dict, Any, Literal
import os
import uuid
import logging
import asyncio
import json
import time
from datetime import datetime
from email.utils import formatdate, parsedate_to_datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.database import get_db, AsyncSessionLocal
from app.models.paper import (
    DocumentElement,
    Image as ImageModel,
    Paper,
    Section,
    Table as TableModel,
    TableCell,
    TableStructure,
)
from app.models.project import ResearchProject
from app.api.auth import decode_token
from app.agent.paper_parser.graph import run_paper_parser
from app.rag.knowledge_base import get_knowledge_base, SmartChunker
from app.api.dependencies import get_current_user_id
from app.config import settings
from app.job_queue import enqueue_job
from app.redis_client import get_async_redis
from app.parsers.multimedia_extractor import MultimediaExtractor
from app.utils.task_manager import TaskStatus, create_task, get_task, list_tasks, remove_task, update_task
from app.utils.background_tasks import spawn_background_task
from app.services.paper_files import (
    extract_pdf_page_contents as _extract_pdf_page_contents,
    extract_pdf_page_texts as _extract_pdf_page_texts,
    extract_pdf_text as _extract_pdf_text,
    find_content_page as _find_content_page,
    normalize_page_text as _normalize_page_text,
    parse_byte_range as _parse_byte_range,
    save_validated_pdf as _save_validated_pdf,
    read_file_range as _read_file_range,
    sanitize_text as _sanitize_text,
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
    paper_upload_service,
)
from app.services.table_structure import (
    build_table_cells,
    merge_cross_page_tables,
    normalize_table_structure,
    save_table_screenshot,
)

router = APIRouter(prefix="/api/v1/papers")


class PdfLoadTelemetry(BaseModel):
    """Client-side PDF timings used for log-based performance monitoring."""

    outcome: Literal["success", "error"]
    source: Literal["cache", "range", "fallback"]
    total_ms: float = Field(ge=0, le=300_000)
    cache_lookup_ms: float = Field(default=0, ge=0, le=300_000)
    document_ms: float = Field(default=0, ge=0, le=300_000)
    first_page_render_ms: float = Field(default=0, ge=0, le=300_000)
    pages: int = Field(default=0, ge=0, le=100_000)
    network_requests: int = Field(default=0, ge=0, le=10_000)
    cache_bytes: int = Field(default=0, ge=0, le=500_000_000)
    error: Optional[str] = Field(default=None, max_length=160)


def _build_pdf_cache_headers(file_path: str, paper_id: str) -> Dict[str, str]:
    stat = os.stat(file_path)
    etag = f'"{paper_id}-{stat.st_size:x}-{stat.st_mtime_ns:x}"'
    return {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{paper_id}.pdf"',
        # Keep a private browser cache for a day so repeated Reader opens do
        # not re-download the same paper. The ETag still allows revalidation
        # after expiry, while omitting `immutable` keeps file replacement safe.
        "Cache-Control": "private, max-age=86400",
        "ETag": etag,
        "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
        "Vary": "Authorization",
    }


def _pdf_not_modified(
    headers: Dict[str, str],
    if_none_match: Optional[str],
    if_modified_since: Optional[str],
) -> bool:
    if if_none_match:
        candidates = {value.strip() for value in if_none_match.split(",")}
        return "*" in candidates or headers["ETag"] in candidates
    if if_modified_since:
        try:
            cached_at = parsedate_to_datetime(if_modified_since).timestamp()
            modified_at = parsedate_to_datetime(headers["Last-Modified"]).timestamp()
            return modified_at <= cached_at
        except (TypeError, ValueError, OverflowError):
            return False
    return False


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
    
    # 独立阅读只展示用户独立上传/导入的论文；从项目内新建的论文仍由
    # Project Papers 管理。历史记录通过迁移默认 is_project_only=false，保持兼容。
    query = select(Paper).filter(
        Paper.user_id == user_id,
        Paper.is_project_only.is_(False),
    )
    
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
    paper_ids = {str(p.id) for p in papers}
    import_tasks = []
    for task in list_tasks({TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.FAILED}):
        if task.user_id != user_id or task.paper_id in paper_ids:
            continue
        details = dict(task.details or {})
        counts = dict(details.get("counts") or {})
        file_path = os.path.join(settings.FILE_STORAGE_PATH, f"{task.paper_id}.pdf")
        import_tasks.append({
            "task_id": task.task_id,
            "paper_id": task.paper_id,
            "filename": counts.get("original_filename") or f"{task.paper_id}.pdf",
            "status": task.status.value,
            "message": task.message or "等待处理",
            "retry_available": task.status == TaskStatus.FAILED and os.path.exists(file_path),
            "project_only": bool(counts.get("project_only") or counts.get("project_id")),
            "delete_available": task.status == TaskStatus.FAILED,
            "updated_at": task.updated_at.isoformat(),
        })
    
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
        "total": len(papers),
        "import_tasks": import_tasks,
    }


@router.get("/{paper_id}/pdf")
async def get_paper_pdf(
    paper_id: str,
    token: str = Query(None),
    authorization: str = Header(None),
    range_header: str = Header(None, alias="Range"),
    if_none_match: str = Header(None, alias="If-None-Match"),
    if_modified_since: str = Header(None, alias="If-Modified-Since"),
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
    
    file_size = os.path.getsize(paper.pdf_path)
    common_headers = _build_pdf_cache_headers(paper.pdf_path, paper_id)

    if not range_header and _pdf_not_modified(
        common_headers, if_none_match, if_modified_since
    ):
        return Response(status_code=304, headers=common_headers)

    if range_header:
        byte_range = _parse_byte_range(range_header, file_size)
        if byte_range is None:
            return Response(
                status_code=416,
                headers={**common_headers, "Content-Range": f"bytes */{file_size}"},
            )

        start, end = byte_range
        try:
            # Keep the range bounded to the requested chunk (normally 1 MiB)
            # and materialise it before setting Content-Length.  This avoids
            # advertising more bytes than a streaming iterator could deliver
            # if the backing file is replaced during a retry/import.
            range_body = await asyncio.to_thread(
                _read_file_range, paper.pdf_path, start, end
            )
        except (OSError, ValueError) as exc:
            logger.warning("读取 PDF 范围失败 paper_id=%s: %s", paper_id, exc)
            raise HTTPException(status_code=503, detail="PDF 文件正在更新，请稍后重试") from exc

        return Response(
            content=range_body,
            status_code=206,
            media_type="application/pdf",
            headers={
                **common_headers,
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(len(range_body)),
            },
        )

    return FileResponse(
        paper.pdf_path,
        media_type="application/pdf",
        headers={**common_headers, "Content-Length": str(file_size)},
    )


@router.post("/{paper_id}/pdf/telemetry", status_code=204, response_class=Response)
async def record_pdf_load_telemetry(
    paper_id: str,
    metric: PdfLoadTelemetry,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Log client-visible PDF loading timings without persisting telemetry."""
    user_id = await get_current_user_id(authorization, db)
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="论文不存在")

    error = (metric.error or "-").replace("\n", " ").replace("\r", " ")[:160]
    logger.info(
        "pdf_client_load paper_id=%s outcome=%s source=%s total_ms=%.1f "
        "cache_lookup_ms=%.1f document_ms=%.1f first_page_render_ms=%.1f "
        "pages=%d network_requests=%d cache_bytes=%d error=%s",
        paper_id,
        metric.outcome,
        metric.source,
        metric.total_ms,
        metric.cache_lookup_ms,
        metric.document_ms,
        metric.first_page_render_ms,
        metric.pages,
        metric.network_requests,
        metric.cache_bytes,
        error,
    )
    return Response(status_code=204)


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


@router.get("/{paper_id}/elements")
async def get_paper_elements(
    paper_id: str,
    page: Optional[int] = Query(None, ge=1),
    element_type: Optional[str] = Query(None),
    indexable_only: bool = Query(False),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Return layout-aware elements for source inspection and precise citation."""
    user_id = await get_current_user_id(authorization, db)
    paper_result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    )
    if not paper_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="论文不存在")

    query = select(DocumentElement).where(DocumentElement.paper_id == paper_id)
    if page is not None:
        query = query.where(DocumentElement.page_number == page)
    if element_type:
        query = query.where(DocumentElement.element_type == element_type)
    if indexable_only:
        query = query.where(DocumentElement.is_indexable.is_(True))
    result = await db.execute(
        query.order_by(DocumentElement.page_number, DocumentElement.page_order)
    )
    elements = result.scalars().all()
    return {
        "items": [
            {
                "id": element.id,
                "type": element.element_type,
                "page": element.page_number,
                "order_index": element.order_index,
                "page_order": element.page_order,
                "text": element.text,
                "bbox": element.bbox or [],
                "section_path": element.section_path or [],
                "confidence": element.confidence,
                "is_indexable": element.is_indexable,
                "attributes": element.attributes or {},
            }
            for element in elements
        ],
        "total": len(elements),
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


@router.patch("/{paper_id}/status")
async def update_paper_status(
    paper_id: str,
    data: dict,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Update user-owned reading progress, status or favorite state."""
    user_id = await get_current_user_id(authorization, db)
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    )
    paper = result.scalar_one_or_none()
    if paper is None:
        raise HTTPException(status_code=404, detail="论文不存在")

    if "status" in data:
        status = str(data.get("status") or "").strip()
        if status not in {"unread", "reading", "completed"}:
            raise HTTPException(status_code=400, detail="无效的阅读状态")
        paper.reading_status = status
    if "progress" in data:
        try:
            progress = float(data["progress"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="阅读进度必须是数字")
        paper.reading_progress = round(max(0.0, min(100.0, progress)), 2)
    if "favorite" in data:
        paper.is_favorite = bool(data["favorite"])
    paper.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "id": paper.id,
        "status": paper.reading_status,
        "reading_progress": paper.reading_progress,
        "is_favorite": paper.is_favorite,
        "updated_at": paper.updated_at.isoformat(),
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
    raw_text: Optional[str] = None,
    initial_timings: Optional[Dict[str, float]] = None,
    pipeline_started_at: Optional[float] = None,
    initial_counts: Optional[Dict[str, Any]] = None,
    media_only: bool = False,
    project_only: bool = False,
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
        if raw_text is not None:
            raw_text = _sanitize_text(raw_text)
        if media_only:
            async with AsyncSessionLocal() as db:
                paper = await db.scalar(
                    select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
                )
                if paper is None:
                    raise RuntimeError("媒体重试目标论文不存在")
                file_path = str(paper.pdf_path or file_path)
                raw_text = _sanitize_text(paper.full_text)
                section_rows = (
                    await db.execute(
                        select(Section)
                        .where(Section.paper_id == paper_id)
                        .order_by(Section.order_index)
                    )
                ).scalars().all()
                sections = [
                    {
                        "title": section.section_title,
                        "content": section.content or "",
                        "key_points": section.key_points or [],
                        "start_page": section.start_page or 1,
                    }
                    for section in section_rows
                ]
                table_ids = select(TableModel.id).where(TableModel.paper_id == paper_id)
                await db.execute(delete(TableCell).where(TableCell.table_id.in_(table_ids)))
                await db.execute(delete(TableStructure).where(TableStructure.paper_id == paper_id))
                await db.execute(delete(TableModel).where(TableModel.paper_id == paper_id))
                await db.execute(delete(ImageModel).where(ImageModel.paper_id == paper_id))
                for section in section_rows:
                    section.tables = []
                    section.figures = []
                    section.formulas = []
                await db.commit()
            if not file_path or not os.path.exists(file_path):
                raise RuntimeError("原始 PDF 不存在，无法重试图表增强")
            if not await get_knowledge_base().delete_paper_media(paper_id):
                raise RuntimeError("旧图表知识库清理失败")
            previous_task = get_task(task_id)
            previous_details = dict(previous_task.details or {}) if previous_task else {}
            counts.update(dict(previous_details.get("counts") or {}))
            ready_seconds = float(previous_details.get("ready_seconds") or 0)
            core_ready = True
            ready_details = dict(previous_details)
            ready_details["media_status"] = "processing"
            ready_details.pop("media_error", None)
            update_task(
                task_id,
                status="ready",
                progress=100,
                message="论文已可用，正在重新增强图表",
                details=ready_details,
            )
            logger.info("重新执行论文图表增强 paper_id=%s", paper_id)
        else:
            if raw_text is None:
                update_task(task_id, status="processing", progress=5, message="正在提取 PDF 文字...")
                text_extraction_started_at = time.perf_counter()
                text_result = await paper_upload_service.extract_text(file_path)
                raw_text = text_result.raw_text
                counts["text_extraction_method"] = text_result.extraction_method
                finish_stage("initial_text_extraction", text_extraction_started_at)
                logger.info(
                    "📝 后台文本提取完成，方式: %s，长度: %s",
                    text_result.extraction_method,
                    len(raw_text),
                )

            update_task(task_id, status="processing", progress=10, message="正在解析论文结构...")
            parse_started_at = time.perf_counter()
            structure = await paper_core_processing_service.extract_structure(
                paper_id=paper_id,
                file_path=file_path,
                raw_text=raw_text,
            )
            finish_stage("structure_parsing", parse_started_at)

            sections = structure.sections
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
                is_project_only=project_only,
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

        extractor = MultimediaExtractor(pdf_path=file_path)

        # 媒体增强使用独立事务；失败不会回滚已经可用的正文论文。
        async with AsyncSessionLocal() as db:
            update_task(task_id, message="论文已可用，正在增强表格和图片...")
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
                pdf_tables = merge_cross_page_tables(pdf_tables)
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
                        screenshot_path=save_table_screenshot(
                            file_path, table, tables_dir, table_idx + 1
                        ),
                        is_corrupted=is_corrupted,
                        extraction_method=table.get("extraction_method", "pdfplumber")
                    )
                    db.add(table_record)
                    await db.flush()
                    structure = normalize_table_structure(table, table_idx + 1)
                    db.add(TableStructure(
                        table_id=table_record.id,
                        paper_id=paper_id,
                        page_numbers=structure["page_numbers"],
                        page_bboxes=structure["page_bboxes"],
                        grid=structure["grid"],
                        header_rows=structure["header_rows"],
                        header_tree=structure["header_tree"],
                        row_records=structure["row_records"],
                        units=structure["units"],
                        footnotes=structure["footnotes"],
                        parse_confidence=structure["parse_confidence"],
                        is_cross_page=structure["is_cross_page"],
                        source_table_count=structure["source_table_count"],
                        screenshot_path=table_record.screenshot_path,
                    ))
                    for cell in build_table_cells(table, structure):
                        db.add(TableCell(table_id=table_record.id, **cell))
                    analyzed_table["table_id"] = table_record.id
                    analyzed_table["structure"] = structure
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
                                "table_id": analyzed_table.get("table_id"),
                                "structure": analyzed_table.get("structure"),
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
            text_chunk_count = int(counts.get("text_vector_chunks") or 0)
            vector_started_at = time.perf_counter()

            for table_info in all_tables_text:
                table_chunk = {
                    "content": table_info["text"],
                    "type": "table",
                    "section": table_info["section"],
                    "page": table_info.get("page", 1),
                    "table_number": table_info.get("table_number"),
                    "caption": table_info.get("caption", ""),
                    "index": text_chunk_count + len(media_chunks)
                }
                media_chunks.append(table_chunk)
                structure = table_info.get("structure") or {}
                for record in structure.get("row_records", []):
                    media_chunks.append({
                        "content": record["text"],
                        "type": "table_row",
                        "section": table_info["section"],
                        "page": record.get("page", table_info.get("page", 1)),
                        "table_number": table_info.get("table_number"),
                        "table_id": table_info.get("table_id"),
                        "row_index": record.get("row_index"),
                        "caption": table_info.get("caption", ""),
                        "fields": record.get("fields", []),
                        "index": text_chunk_count + len(media_chunks),
                    })
            
            for image_info in all_images_info:
                image_chunk = {
                    "content": image_info["text"],
                    "type": "image",
                    "section": image_info["section"],
                    "page": image_info.get("page", 1),
                    "image_type": image_info.get("image_type", "other"),
                    "image_path": image_info.get("image_path", ""),
                    "index": text_chunk_count + len(media_chunks)
                }
                media_chunks.append(image_chunk)
            
            logger.info(f"媒体分块完成：共 {len(media_chunks)} 个片段")
            if media_chunks and not await get_knowledge_base().add_paper_chunks(
                paper_id, media_chunks
            ):
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
    raw_text: Optional[str] = None,
    initial_timings: Optional[Dict[str, float]] = None,
    pipeline_started_at: Optional[float] = None,
    initial_counts: Optional[Dict[str, Any]] = None,
    media_only: bool = False,
    project_only: bool = False,
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
        media_only,
        project_only,
    )


@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...), 
    project_id: Optional[str] = Form(None),
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

    if project_id:
        project = await db.scalar(
            select(ResearchProject).where(
                ResearchProject.id == project_id,
                ResearchProject.user_id == user_id,
            )
        )
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在或无访问权限")
    
    paper_id = str(uuid.uuid4())
    original_filename = file.filename
    upload_result = await paper_upload_service.receive(
        upload=file,
        paper_id=paper_id,
        storage_path=settings.FILE_STORAGE_PATH,
        max_upload_size=settings.MAX_UPLOAD_SIZE,
    )

    initial_timings.update(upload_result.timings)
    file_path = upload_result.file_path
    logger.info(
        "📄 文件名: %s, 大小: %.2fMB",
        original_filename,
        upload_result.file_size / 1024 / 1024,
    )
    logger.info("💾 文件已保存: %s", file_path)

    # An atomic Redis key prevents repeated clicks or concurrent containers from
    # scheduling the same PDF for the same user more than once.
    # 项目上传和独立上传即使内容相同，也属于两个独立业务范围，不能共享去重锁。
    upload_scope = project_id or "standalone"
    upload_lock_key = (
        f"paperai:upload-dedupe:{user_id}:{upload_scope}:{upload_result.file_sha256}"
    )
    try:
        redis_client = get_async_redis()
        lock_value = json.dumps({
            "task_id": f"task_{paper_id}",
            "paper_id": paper_id,
            "project_id": project_id,
        })
        claimed = await redis_client.set(upload_lock_key, lock_value, nx=True, ex=3600)
        if not claimed:
            existing_raw = await redis_client.get(upload_lock_key)
            existing = json.loads(existing_raw) if existing_raw else {}
            existing_task = get_task(str(existing.get("task_id", "")))
            if existing_task and existing_task.user_id == user_id and existing_task.status.value != "failed":
                paper_upload_service._remove_file(file_path)
                return {
                    "task_id": existing_task.task_id,
                    "paper_id": existing_task.paper_id,
                    "message": "该论文已在上传或处理，请勿重复提交",
                    "status_url": f"/api/v1/papers/tasks/{existing_task.task_id}",
                    "duplicate": True,
                }
            await redis_client.set(upload_lock_key, lock_value, ex=3600)
    except Exception:
        logger.warning("Redis 上传防重复锁不可用，继续执行上传", exc_info=True)
    
    # 创建任务
    task = create_task(paper_id, user_id)
    initial_counts = {
        "original_filename": original_filename,
        "project_id": project_id,
        "project_only": bool(project_id),
    }
    update_task(
        task.task_id,
        details=_build_timing_details(
            initial_timings,
            time.perf_counter() - pipeline_started_at,
            initial_counts,
        ),
    )
    logger.info(f"✅ 任务创建成功: {task.task_id}")
    
    logger.info("🚀 论文处理任务进入 Worker 队列...")
    try:
        await enqueue_job(
            "paper_process",
            {
                "paper_id": paper_id,
                "file_path": file_path,
                "user_id": user_id,
                "raw_text": None,
                "initial_timings": initial_timings,
                "pipeline_started_at": pipeline_started_at,
                "initial_counts": initial_counts,
                "project_only": bool(project_id),
            },
            job_id=task.task_id,
        )
    except Exception:
        logger.exception("论文处理任务入队失败 paper_id=%s", paper_id)
        update_task(
            task.task_id,
            status="failed",
            progress=0,
            message="处理任务入队失败，请稍后重新上传",
        )
        raise HTTPException(status_code=503, detail="论文处理 Worker 暂时不可用")
    
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
    counts = dict(details.get("counts") or {})
    project_only = bool(counts.get("project_only") or counts.get("project_id"))
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
        initial_counts={
            "text_extraction_method": extraction_method,
            "recovered": True,
            "project_id": counts.get("project_id"),
            "project_only": project_only,
        },
        project_only=project_only,
    )


def recover_incomplete_paper_tasks() -> int:
    """Schedule persisted tasks after application startup; return scheduled count."""
    from app.utils.task_manager import TaskStatus, list_tasks

    try:
        asyncio.get_running_loop()
        can_schedule = True
    except RuntimeError:
        can_schedule = False

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
        if not can_schedule:
            logger.warning(
                "跳过论文任务恢复：当前线程没有运行中的事件循环 (task_id=%s)",
                task.task_id,
            )
            continue
        spawn_background_task(
            _recover_one_paper_task(task),
            name=f"paper-recovery-{task.paper_id}",
        )
        scheduled += 1
    return scheduled


@router.post("/tasks/{task_id}/retry", status_code=202)
async def retry_paper_task(
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed core import or only the failed media enhancement stage."""
    user_id = await get_current_user_id(authorization, db)
    task = get_task(task_id)
    if task is None or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="任务不存在")

    paper = await db.scalar(
        select(Paper).where(Paper.id == task.paper_id, Paper.user_id == user_id)
    )
    details = dict(task.details or {})
    media_status = str(details.get("media_status") or "")
    retry_count = int(details.get("manual_retry_count") or 0) + 1
    details["manual_retry_count"] = retry_count
    details["last_manual_retry_at"] = datetime.utcnow().isoformat()

    if paper is not None:
        if media_status not in {"failed", "interrupted", "not_started"}:
            raise HTTPException(status_code=409, detail="当前图表状态不需要重试")
        file_path = str(paper.pdf_path or "")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=409, detail="原始 PDF 不存在，无法重试图表增强")
        details["media_status"] = "processing"
        details.pop("media_error", None)
        update_task(
            task_id,
            status="ready",
            progress=100,
            message="论文已可用，图表增强重试已排队",
            details=details,
        )
        payload = {
            "paper_id": task.paper_id,
            "file_path": file_path,
            "user_id": user_id,
            "initial_counts": dict(details.get("counts") or {}),
            "media_only": True,
        }
        job_type = "paper_media_enhance"
        response_message = "图表增强重试已排队"
    else:
        if task.status != TaskStatus.FAILED:
            raise HTTPException(status_code=409, detail="当前导入任务仍在处理中")
        file_path = os.path.join(settings.FILE_STORAGE_PATH, f"{task.paper_id}.pdf")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=409, detail="原始 PDF 不存在，请重新上传")
        await get_knowledge_base().delete_paper(task.paper_id)
        details["media_status"] = "not_started"
        details.pop("media_error", None)
        update_task(
            task_id,
            status="pending",
            progress=0,
            message="导入重试已排队",
            details=details,
        )
        payload = {
            "paper_id": task.paper_id,
            "file_path": file_path,
            "user_id": user_id,
            "raw_text": None,
            "initial_counts": dict(details.get("counts") or {}),
            "project_only": bool(
                (details.get("counts") or {}).get("project_only")
                or (details.get("counts") or {}).get("project_id")
            ),
        }
        job_type = "paper_process"
        response_message = "导入重试已排队"

    try:
        await enqueue_job(
            job_type,
            payload,
            job_id=f"{task_id}:manual:{retry_count}:{uuid.uuid4().hex[:8]}",
        )
    except Exception as exc:
        logger.exception("论文任务重试入队失败 task_id=%s", task_id)
        if paper is not None:
            details["media_status"] = media_status or "failed"
        update_task(
            task_id,
            status=task.status,
            progress=task.progress,
            message="重试任务入队失败，请稍后再试",
            details=details,
        )
        raise HTTPException(status_code=503, detail="论文处理 Worker 暂时不可用") from exc

    return {
        "task_id": task_id,
        "paper_id": task.paper_id,
        "retry_type": "media" if paper is not None else "import",
        "status": "queued",
        "message": response_message,
    }


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


@router.delete("/tasks/{task_id}")
async def delete_failed_import_task(
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """删除失败的导入任务、残留文件和可能已经写入的部分论文记录。"""
    user_id = await get_current_user_id(authorization, db)
    task = get_task(task_id)
    if task is None or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != TaskStatus.FAILED:
        raise HTTPException(status_code=409, detail="只有失败的导入任务可以删除")

    paper = await db.scalar(
        select(Paper).where(Paper.id == task.paper_id, Paper.user_id == user_id)
    )
    details = dict(task.details or {})
    counts = dict(details.get("counts") or {})
    project_id = str(counts.get("project_id") or "")
    file_path = str(getattr(paper, "pdf_path", "") or "") if paper else ""
    if not file_path:
        file_path = os.path.join(settings.FILE_STORAGE_PATH, f"{task.paper_id}.pdf")

    # 清理向量库时即使正文事务未提交也要执行，避免失败重试/删除后留下孤立向量。
    await get_knowledge_base().delete_paper(task.paper_id)
    if paper is not None:
        await db.delete(paper)

    # arXiv 项目导入会把任务镜像写入项目 preferences；删除任务时一并移除。
    if project_id:
        project = await db.scalar(
            select(ResearchProject).where(
                ResearchProject.id == project_id,
                ResearchProject.user_id == user_id,
            )
        )
        if project is not None:
            preferences = dict(project.preferences or {})
            imports = [dict(item) for item in preferences.get("paper_imports") or []]
            remaining = [item for item in imports if item.get("task_id") != task_id]
            if len(remaining) != len(imports):
                preferences["paper_imports"] = remaining
                project.preferences = preferences

    await db.commit()
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    remove_task(task_id)
    return {"message": "失败导入已删除"}


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
