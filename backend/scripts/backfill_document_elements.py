"""Backfill the layout element layer for already uploaded papers.

This command only reads local PDF files and writes PostgreSQL rows. It does not
call language, vision or embedding APIs and does not modify the vector index.
"""

from __future__ import annotations

import argparse
import asyncio
import os

from sqlalchemy import delete, select

from app.database import AsyncSessionLocal, close_db, init_db
from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache
from app.models.paper import DocumentElement, Paper, Section
from app.models.user import User
from app.services.document_layout import extract_layout_elements


async def backfill(paper_id: str | None = None) -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        paper_query = select(Paper).order_by(Paper.uploaded_at)
        if paper_id:
            paper_query = paper_query.where(Paper.id == paper_id)
        papers = list((await db.execute(paper_query)).scalars().all())

        for paper in papers:
            if not paper.pdf_path or not os.path.exists(paper.pdf_path):
                print({"paper_id": paper.id, "status": "skipped", "reason": "pdf_missing"})
                continue
            elements = await asyncio.to_thread(extract_layout_elements, paper.pdf_path)
            sections = list((await db.execute(
                select(Section).where(Section.paper_id == paper.id)
            )).scalars().all())
            section_by_title = {
                section.section_title.strip().lower(): section for section in sections
            }

            await db.execute(
                delete(DocumentElement).where(DocumentElement.paper_id == paper.id)
            )
            counts: dict[str, int] = {}
            for element in elements:
                section_path = [
                    str(value) for value in element.get("section_path", [])
                    if str(value).strip()
                ]
                section = section_by_title.get(
                    section_path[-1].strip().lower() if section_path else ""
                )
                element_type = str(element["element_type"])
                counts[element_type] = counts.get(element_type, 0) + 1
                db.add(DocumentElement(
                    id=str(element["id"]),
                    paper_id=paper.id,
                    section_id=section.id if section else None,
                    element_type=element_type,
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
            print({
                "paper_id": paper.id,
                "status": "backfilled",
                "elements": len(elements),
                "types": counts,
            })


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-id", default=None)
    args = parser.parse_args()
    try:
        await backfill(args.paper_id)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
