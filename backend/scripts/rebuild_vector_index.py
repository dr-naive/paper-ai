"""Rebuild every paper into a separate Chroma directory for an atomic swap."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionLocal, close_db, init_db
# Import relationship targets before SQLAlchemy configures mappers.
from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache  # noqa: F401
from app.models.paper import DocumentElement, Image, Paper, Section, Table, TableStructure
from app.models.user import User  # noqa: F401
from app.rag.knowledge_base import PaperKnowledgeBase, SmartChunker
from app.rag.table_retrieval import table_to_chunk
from app.services.document_layout import build_element_chunks


def _image_chunk(image: Image, index: int) -> dict | None:
    analysis = image.analysis_result or {}
    if isinstance(analysis, dict):
        text = "\n".join(
            f"{key}：{json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value}"
            for key, value in analysis.items()
            if value not in (None, "", [], {})
        )
    else:
        text = str(analysis)
    if not text.strip():
        return None
    return {
        "content": text,
        "type": "image",
        "section": f"论文图片 {image.image_index or index + 1}",
        "index": 900000 + index,
        "page": image.page_number or 1,
    }


async def rebuild(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f"临时目标目录必须为空: {target}")
    target.mkdir(parents=True, exist_ok=True)
    os.environ["VECTOR_STORE_PATH"] = str(target)
    settings.VECTOR_STORE_PATH = str(target)

    await init_db()
    knowledge_base = PaperKnowledgeBase()
    totals = {"papers": 0, "text": 0, "tables": 0, "images": 0}
    try:
        async with AsyncSessionLocal() as db:
            papers = (await db.execute(select(Paper).order_by(Paper.uploaded_at))).scalars().all()
            for paper in papers:
                paper_id = str(paper.id)
                sections = (
                    await db.execute(
                        select(Section)
                        .where(Section.paper_id == paper_id)
                        .order_by(Section.order_index)
                    )
                ).scalars().all()
                pdf_path = str(paper.pdf_path or "")
                if not pdf_path or not Path(pdf_path).exists():
                    raise FileNotFoundError(f"论文 PDF 不存在: paper_id={paper_id}")
                elements = (
                    await db.execute(
                        select(DocumentElement)
                        .where(DocumentElement.paper_id == paper_id)
                        .order_by(DocumentElement.order_index)
                    )
                ).scalars().all()
                text_chunks = build_element_chunks([{
                    "id": element.id,
                    "element_type": element.element_type,
                    "page_number": element.page_number,
                    "text": element.text,
                    "bbox": element.bbox,
                    "section_path": element.section_path,
                    "confidence": element.confidence,
                    "is_indexable": element.is_indexable,
                } for element in elements], SmartChunker())
                if not text_chunks:
                    raise RuntimeError(f"论文没有可索引正文: paper_id={paper_id}")
                if not await knowledge_base.add_paper_chunks(paper_id, text_chunks):
                    raise RuntimeError(f"正文索引失败: paper_id={paper_id}")

                tables = (
                    await db.execute(
                        select(Table)
                        .options(selectinload(Table.structure))
                        .where(Table.paper_id == paper_id)
                        .order_by(Table.table_number)
                    )
                ).scalars().all()
                table_chunks = []
                for index, table in enumerate(tables):
                    chunk = table_to_chunk(table)
                    chunk["type"] = "table"
                    chunk["index"] = 800000 + index
                    table_chunks.append(chunk)
                    if table.structure:
                        for row in table.structure.row_records or []:
                            table_chunks.append({
                                "content": row.get("text", ""),
                                "type": "table_row",
                                "section": table.caption or f"表{table.table_number}",
                                "index": 810000 + len(table_chunks),
                                "page": row.get("page") or table.page_number,
                                "table_number": table.table_number,
                                "table_id": str(table.id),
                                "row_index": row.get("row_index"),
                                "fields": row.get("fields", []),
                            })
                if table_chunks and not await knowledge_base.add_paper_chunks(paper_id, table_chunks):
                    raise RuntimeError(f"表格索引失败: paper_id={paper_id}")

                images = (
                    await db.execute(
                        select(Image)
                        .where(Image.paper_id == paper_id, Image.is_filtered.is_(False))
                        .order_by(Image.image_index)
                    )
                ).scalars().all()
                image_chunks = [
                    chunk
                    for index, image in enumerate(images)
                    if (chunk := _image_chunk(image, index)) is not None
                ]
                if image_chunks and not await knowledge_base.add_paper_chunks(paper_id, image_chunks):
                    raise RuntimeError(f"图片索引失败: paper_id={paper_id}")

                totals["papers"] += 1
                totals["text"] += len(text_chunks)
                totals["tables"] += len(table_chunks)
                totals["images"] += len(image_chunks)
                print(json.dumps({
                    "paper_id": paper_id,
                    "text_chunks": len(text_chunks),
                    "table_chunks": len(table_chunks),
                    "image_chunks": len(image_chunks),
                }, ensure_ascii=False), flush=True)

        collection = knowledge_base.vectorstore._collection
        stored = collection.count()
        expected = totals["text"] + totals["tables"] + totals["images"]
        if stored != expected:
            raise RuntimeError(f"索引计数不一致 expected={expected} stored={stored}")
        if totals["papers"]:
            sample_paper = str(papers[0].id)
            results = await knowledge_base.query(sample_paper, "论文的主要实验结果", top_k=3)
            if not results:
                raise RuntimeError("新索引检索验证没有返回结果")
        print(json.dumps({**totals, "stored": stored, "status": "verified"}, ensure_ascii=False))
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    asyncio.run(rebuild(Path(args.target).resolve()))


if __name__ == "__main__":
    main()
