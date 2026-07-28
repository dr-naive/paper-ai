"""Create normalized table representations for previously uploaded papers."""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import delete, select

from app.database import AsyncSessionLocal, close_db, init_db
from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache  # noqa: F401
from app.models.paper import Table, TableCell, TableStructure
from app.models.user import User  # noqa: F401
from app.services.table_structure import build_table_cells, normalize_table_structure


async def backfill(paper_id: str | None) -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        query = select(Table).order_by(Table.paper_id, Table.table_number)
        if paper_id:
            query = query.where(Table.paper_id == paper_id)
        tables = (await db.execute(query)).scalars().all()
        for table in tables:
            source = {
                "page": table.page_number or 1,
                "content": table.raw_content or [],
                "caption": table.caption or "",
                "csv_content": table.csv_content or "",
                "markdown_content": table.markdown_content or "",
            }
            structure = normalize_table_structure(source, table.table_number or 0)
            await db.execute(delete(TableCell).where(TableCell.table_id == table.id))
            await db.execute(delete(TableStructure).where(TableStructure.table_id == table.id))
            db.add(TableStructure(
                table_id=table.id,
                paper_id=table.paper_id,
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
                screenshot_path=table.screenshot_path,
            ))
            for cell in build_table_cells(source, structure):
                db.add(TableCell(table_id=table.id, **cell))
        await db.commit()
        print({"tables": len(tables), "status": "backfilled"})


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
