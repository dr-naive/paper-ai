#!/usr/bin/env python3
"""Add bounded page-level fallback chunks for an already indexed paper."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

import app.main  # noqa: F401 - register all SQLAlchemy models
from app.api.papers import (
    _build_complete_text_chunks,
    _extract_pdf_page_contents,
    _extract_pdf_page_texts,
)
from app.database import AsyncSessionLocal
from app.models.paper import Paper, Section
from app.rag.knowledge_base import SmartChunker, get_knowledge_base


async def index_front_matter(paper_id: str) -> None:
    async with AsyncSessionLocal() as db:
        paper = await db.scalar(select(Paper).where(Paper.id == paper_id))
        if not paper or not paper.pdf_path:
            raise RuntimeError(f"论文不存在或缺少 PDF：{paper_id}")
        section_rows = (
            await db.execute(
                select(Section)
                .where(Section.paper_id == paper_id)
                .order_by(Section.order_index)
            )
        ).scalars().all()
        sections = [
            {"title": section.section_title, "content": section.content or ""}
            for section in section_rows
            if section.content
        ]

    chunks = _build_complete_text_chunks(
        sections,
        SmartChunker(),
        _extract_pdf_page_texts(paper.pdf_path),
        _extract_pdf_page_contents(paper.pdf_path),
    )
    fallback_chunks = [
        chunk for chunk in chunks
        if chunk.get("coverage_source") == "front_matter_fallback"
    ]
    if not fallback_chunks:
        print("没有需要补充索引的前置页面。")
        return

    kb = get_knowledge_base()
    current = kb.vectorstore._collection.get(where={"paper_id": paper_id})
    old_ids = [
        item_id
        for item_id, metadata in zip(current.get("ids", []), current.get("metadatas", []))
        if metadata.get("coverage_source") == "front_matter_fallback"
    ]
    if not await kb.add_paper_chunks(paper_id, fallback_chunks):
        raise RuntimeError("补充向量写入失败，旧向量已保留")
    if old_ids:
        kb.vectorstore._collection.delete(ids=old_ids)

    pages = sorted({int(chunk["page"]) for chunk in fallback_chunks})
    print(f"前置内容索引完成：PDF 第 {pages[0]}-{pages[-1]} 页")
    print(f"新增 {len(fallback_chunks)} 块，删除旧补充块 {len(old_ids)} 块")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_id")
    args = parser.parse_args()
    asyncio.run(index_front_matter(args.paper_id))


if __name__ == "__main__":
    main()
