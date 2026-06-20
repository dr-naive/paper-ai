#!/usr/bin/env python3
"""Repair persisted sections and replace only a paper's text vector chunks."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

import app.main  # noqa: F401 - register all SQLAlchemy models
from app.agent.paper_parser.graph import _parse_sections_by_rules
from app.api.papers import (
    _build_text_chunks,
    _extract_pdf_page_texts,
    _find_content_page,
)
from app.database import AsyncSessionLocal
from app.models.paper import Paper, Section
from app.rag.knowledge_base import SmartChunker, get_knowledge_base


async def repair_paper(paper_id: str) -> None:
    async with AsyncSessionLocal() as db:
        paper_result = await db.execute(select(Paper).where(Paper.id == paper_id))
        paper = paper_result.scalar_one_or_none()
        if not paper:
            raise RuntimeError(f"论文不存在: {paper_id}")
        if not paper.full_text or not paper.pdf_path:
            raise RuntimeError("论文缺少全文或 PDF 路径")

        parsed_sections = _parse_sections_by_rules(paper.full_text)
        if len(parsed_sections) < 2:
            raise RuntimeError("规则章节解析结果不足，停止重建")

        page_texts = _extract_pdf_page_texts(paper.pdf_path)
        page_hint = 1
        section_pages = []
        for section in parsed_sections:
            page_hint = _find_content_page(
                page_texts,
                f"{section['title']}\n{section['content'][:200]}",
                page_hint,
            )
            section_pages.append(page_hint)

        existing_result = await db.execute(
            select(Section)
            .where(Section.paper_id == paper_id)
            .order_by(Section.order_index)
        )
        existing_sections = list(existing_result.scalars().all())
        for index, section_data in enumerate(parsed_sections):
            if index < len(existing_sections):
                section = existing_sections[index]
                section.section_title = section_data["title"]
                section.content = section_data["content"]
                section.key_points = section_data.get("key_points", [])
                section.start_page = section_pages[index]
            else:
                db.add(Section(
                    paper_id=paper_id,
                    section_title=section_data["title"],
                    order_index=index,
                    start_page=section_pages[index],
                    content=section_data["content"],
                    key_points=section_data.get("key_points", []),
                    tables=[],
                    figures=[],
                    formulas=[],
                ))

        for obsolete in existing_sections[len(parsed_sections):]:
            await db.delete(obsolete)
        await db.commit()

    chunks = _build_text_chunks(parsed_sections, SmartChunker(), page_texts)
    kb = get_knowledge_base()
    current = kb.vectorstore._collection.get(where={"paper_id": paper_id})
    old_text_ids = [
        item_id
        for item_id, metadata in zip(current.get("ids", []), current.get("metadatas", []))
        if metadata.get("chunk_type") in {"small", "large"}
    ]

    if not await kb.add_paper_chunks(paper_id, chunks):
        raise RuntimeError("新正文向量写入失败，旧向量已保留")
    if old_text_ids:
        kb.vectorstore._collection.delete(ids=old_text_ids)

    print(f"章节修复完成: {len(parsed_sections)} 章")
    print(f"正文向量替换完成: 新增 {len(chunks)} 块，删除旧块 {len(old_text_ids)} 块")
    for section, page in zip(parsed_sections, section_pages):
        print(f"  PDF 第{page}页: {section['title']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_id")
    args = parser.parse_args()
    asyncio.run(repair_paper(args.paper_id))


if __name__ == "__main__":
    main()
