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
)
from app.services.paper_indexing import (
    build_complete_text_chunks,
    normalize_key_points,
    normalize_sections,
)
from app.services.paper_outline import enrich_sections_with_pdf


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
        parse_result = await run_paper_parser(paper_id, file_path, raw_text)
        sections = normalize_sections(parse_result.get("sections", []), raw_text)
        page_contents = extract_pdf_page_contents(file_path)
        sections = enrich_sections_with_pdf(sections, file_path, page_contents)
        elements = await asyncio.to_thread(extract_layout_elements, file_path)
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
    ) -> None:
        extractor = MultimediaExtractor(pdf_path=file_path)
        async with AsyncSessionLocal() as db:
            db.add(Paper(
                id=paper_id,
                user_id=user_id,
                title=structure.metadata.get("title", ""),
                authors=structure.metadata.get("authors", ""),
                abstract=structure.metadata.get("abstract", ""),
                full_text=raw_text[:100000],
                pdf_path=file_path,
                keywords=structure.metadata.get("keywords", []),
            ))

            persisted_sections: list[Section] = []
            for index, section_data in enumerate(structure.sections):
                section_title = section_data.get("title", f"第{index + 1}节")
                section_content = section_data.get("content", "")
                section = Section(
                    paper_id=paper_id,
                    section_title=section_title,
                    order_index=index,
                    start_page=int(section_data.get("start_page") or 1),
                    content=section_content,
                    key_points=normalize_key_points(section_data.get("key_points", [])),
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
                    str(value) for value in element.get("section_path", [])
                    if str(value).strip()
                ]
                section = section_by_title.get(
                    section_path[-1].strip().lower() if section_path else ""
                )
                db.add(DocumentElement(
                    id=str(element["id"]),
                    paper_id=paper_id,
                    section_id=section.id if section else None,
                    element_type=str(element["element_type"]),
                    page_number=int(element["page_number"]),
                    order_index=int(element["order_index"]),
                    page_order=int(element["page_order"]),
                    text=str(element.get("text") or ""),
                    bbox=list(element.get("bbox") or []),
                    section_path=section_path,
                    confidence=float(element.get("confidence") or 0),
                    extraction_method=str(
                        element.get("extraction_method") or "pymupdf_layout"
                    ),
                    is_indexable=bool(element.get("is_indexable")),
                    attributes=dict(element.get("attributes") or {}),
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
        chunker = SmartChunker()
        text_chunks = build_element_chunks(structure.elements, chunker)
        if not text_chunks:
            text_chunks = build_complete_text_chunks(
                structure.sections,
                chunker,
                extract_pdf_page_texts(file_path),
                structure.page_contents,
            )
        if not text_chunks:
            text_chunks = chunker.chunk_text(raw_text[:100000], "全文")
        if not await get_knowledge_base().add_paper_chunks(paper_id, text_chunks):
            raise RuntimeError("正文知识库构建失败")
        return len(text_chunks)


paper_core_processing_service = PaperCoreProcessingService()
