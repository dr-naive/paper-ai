"""Exact table retrieval helpers used alongside semantic RAG retrieval."""
import json
import re
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Table


_CHINESE_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def extract_table_numbers(question: str) -> List[int]:
    """Extract explicit table references such as 表1, Table 2, or 表一."""
    numbers: List[int] = []
    patterns = (
        r"(?:表|table)\s*([0-9]+)",
        r"第\s*([0-9]+)\s*(?:张|个)?表",
    )
    for pattern in patterns:
        numbers.extend(int(value) for value in re.findall(pattern, question, re.IGNORECASE))

    for value in re.findall(r"(?:表|第)\s*([一二三四五六七八九十])\s*(?:张|个)?表?", question):
        numbers.append(_CHINESE_DIGITS[value])

    return list(dict.fromkeys(number for number in numbers if number > 0))


def _serialize_raw_content(raw_content: Any) -> str:
    if not raw_content:
        return ""
    if isinstance(raw_content, list):
        rows = []
        for row in raw_content:
            if isinstance(row, list):
                rows.append(" | ".join(str(cell or "").strip() for cell in row))
            else:
                rows.append(str(row))
        return "\n".join(rows)
    if isinstance(raw_content, dict):
        return json.dumps(raw_content, ensure_ascii=False)
    return str(raw_content)


def table_to_chunk(table: Table, max_content_chars: int = 12000) -> Dict[str, Any]:
    """Convert a persisted table into an authoritative RAG context chunk."""
    table_number = int(table.table_number or 0)
    label = f"表{table_number}" if table_number else "表格"
    caption = (table.caption or "").strip()
    data = (table.markdown_content or table.csv_content or "").strip()
    if not data:
        data = _serialize_raw_content(table.raw_content)

    parts = [f"【{label}】{caption}".strip()]
    if table.page_number:
        parts.append(f"所在页：第{table.page_number}页")
    if data:
        parts.append(f"表格数据：\n{data[:max_content_chars]}")

    analysis = table.analysis_result or {}
    summary = analysis.get("data_summary") or analysis.get("core_conclusion")
    if summary:
        parts.append(f"表格总结：{summary}")

    return {
        "content": "\n\n".join(parts),
        "section": caption or label,
        "chunk_index": f"table-{table_number}",
        "chunk_type": "table",
        "table_number": table_number,
        "caption": caption,
        "page": table.page_number,
        "score": 0.0,
        "retrieval_method": "exact_table_number",
    }


async def get_exact_table_chunks(
    db: AsyncSession,
    paper_id: str,
    question: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Fetch explicitly referenced tables directly from the relational database."""
    table_numbers = extract_table_numbers(question)[:limit]
    if not table_numbers:
        return []

    result = await db.execute(
        select(Table)
        .where(Table.paper_id == paper_id, Table.table_number.in_(table_numbers))
        .order_by(Table.table_number)
    )
    tables_by_number = {int(table.table_number): table for table in result.scalars().all()}
    return [table_to_chunk(tables_by_number[number]) for number in table_numbers if number in tables_by_number]


def merge_retrieval_chunks(
    exact_chunks: List[Dict[str, Any]],
    semantic_chunks: List[Dict[str, Any]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Keep exact table matches first and remove duplicate retrieval results."""
    merged: List[Dict[str, Any]] = []
    seen = set()
    for chunk in exact_chunks + semantic_chunks:
        if chunk.get("chunk_type") == "table" and chunk.get("table_number") is not None:
            key = ("table", str(chunk["table_number"]))
        else:
            key = (
                chunk.get("chunk_type"),
                chunk.get("chunk_index"),
                chunk.get("content", "")[:160],
            )
        if key in seen:
            continue
        seen.add(key)
        merged.append(chunk)
        if len(merged) >= top_k:
            break
    return merged
