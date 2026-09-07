"""Core paper processing stages shared by upload and future worker entrypoints."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.agent.paper_parser.graph import run_paper_parser
from app.database import AsyncSessionLocal
from app.models.paper import DocumentElement, Paper, Section
from app.parsers.multimedia_extractor import MultimediaExtractor
from app.rag.knowledge_base import SmartChunker, get_knowledge_base
from app.services.document_layout import build_element_chunks, extract_layout_elements
from app.services.paper_files import (
    extract_pdf_page_contents,
    extract_pdf_page_texts,
    sanitize_text,
)
from app.services.paper_indexing import (
    build_complete_text_chunks,
    normalize_key_points,
    normalize_sections,
)
from app.services.paper_outline import enrich_sections_with_pdf


def _sanitize_value(value: Any) -> Any:
    """Recursively remove NUL bytes from parser output before persistence/indexing."""
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    if isinstance(value, dict):
        return {
            sanitize_text(str(key)): _sanitize_value(item)
            for key, item in value.items()
        }
    return value


@dataclass(frozen=True)
class PaperStructureResult:
    metadata: dict[str, Any]
    sections: list[dict[str, Any]]
    page_contents: list[str]
    elements: list[dict[str, Any]]


class PaperCoreProcessingService:
    """Core processing interface with explicit, independently testable stages."""

    async def extract_structure(
        self,
        *,
        paper_id: str,
        file_path: str,
        raw_text: str,
    ) -> PaperStructureResult:
        raw_text = sanitize_text(raw_text)
        parse_result = _sanitize_value(await run_paper_parser(paper_id, file_path, raw_text))
        if not isinstance(parse_result, dict):
            parse_result = {}
        sections = normalize_sections(parse_result.get("sections", []), raw_text)
        sections = _sanitize_value(sections)
        page_contents = [sanitize_text(item) for item in extract_pdf_page_contents(file_path)]
        sections = enrich_sections_with_pdf(sections, file_path, page_contents)
        sections = _sanitize_value(sections)
        elements = _sanitize_value(await asyncio.to_thread(extract_layout_elements, file_path))
        return PaperStructureResult(
            metadata=parse_result,
            sections=sections,
            page_contents=page_contents,
            elements=elements,
        )

    async def persist_core(
        self,
        *,
        paper_id: str,
        user_id: str,
        file_path: str,
        raw_text: str,
        structure: PaperStructureResult,
        is_project_only: bool = False,
    ) -> None:
        extractor = MultimediaExtractor(pdf_path=file_path)
        metadata = _sanitize_value(structure.metadata)
        if not isinstance(metadata, dict):
            metadata = {}
        raw_text = sanitize_text(raw_text)
        async with AsyncSessionLocal() as db:
            db.add(Paper(
                id=paper_id,
                user_id=user_id,
                title=sanitize_text(metadata.get("title", "")),
                authors=sanitize_text(metadata.get("authors", "")),
                abstract=sanitize_text(metadata.get("abstract", "")),
                full_text=raw_text[:100000],
                pdf_path=file_path,
                keywords=_sanitize_value(metadata.get("keywords", [])),
                is_project_only=is_project_only,
            ))

            persisted_sections: list[Section] = []
            for index, section_data in enumerate(structure.sections):
                section_title = sanitize_text(section_data.get("title", f"第{index + 1}节"))
                section_content = sanitize_text(section_data.get("content", ""))
                section = Section(
                    paper_id=paper_id,
                    section_title=section_title,
                    order_index=index,
                    start_page=int(section_data.get("start_page") or 1),
                    content=section_content,
                    key_points=_sanitize_value(
                        normalize_key_points(section_data.get("key_points", []))
                    ),
                    tables=extractor.extract_tables_from_text(section_content, section_title),
                    figures=extractor.extract_figures_from_text(section_content, section_title),
                    formulas=extractor.extract_formulas(section_content, section_title),
                )
                db.add(section)
                persisted_sections.append(section)
            await db.flush()

            section_by_title = {
                section.section_title.strip().lower(): section
                for section in persisted_sections
            }
            for element in structure.elements:
                section_path = [
                    sanitize_text(str(value)) for value in element.get("section_path", [])
                    if sanitize_text(str(value)).strip()
                ]
                section = section_by_title.get(
                    section_path[-1].strip().lower() if section_path else ""
                )
                db.add(DocumentElement(
                    id=sanitize_text(str(element["id"])),
                    paper_id=paper_id,
                    section_id=section.id if section else None,
                    element_type=sanitize_text(str(element["element_type"])),
                    page_number=int(element["page_number"]),
                    order_index=int(element["order_index"]),
                    page_order=int(element["page_order"]),
                    text=sanitize_text(str(element.get("text") or "")),
                    bbox=_sanitize_value(list(element.get("bbox") or [])),
                    section_path=section_path,
                    confidence=float(element.get("confidence") or 0),
                    extraction_method=sanitize_text(str(
                        element.get("extraction_method") or "pymupdf_layout"
                    )),
                    is_indexable=bool(element.get("is_indexable")),
                    attributes=_sanitize_value(dict(element.get("attributes") or {})),
                ))
            await db.commit()

    async def build_text_index(
        self,
        *,
        paper_id: str,
        raw_text: str,
        file_path: str,
        structure: PaperStructureResult,
    ) -> int:
        raw_text = sanitize_text(raw_text)
        chunker = SmartChunker()
        text_chunks = _sanitize_value(build_element_chunks(structure.elements, chunker))
        if not text_chunks:
            text_chunks = _sanitize_value(build_complete_text_chunks(
                structure.sections,
                chunker,
                extract_pdf_page_texts(file_path),
                structure.page_contents,
            ))
        if not text_chunks:
            text_chunks = chunker.chunk_text(raw_text[:100000], "全文")
        if not await get_knowledge_base().add_paper_chunks(paper_id, text_chunks):
            raise RuntimeError("正文知识库构建失败")
        return len(text_chunks)


paper_core_processing_service = PaperCoreProcessingService()
