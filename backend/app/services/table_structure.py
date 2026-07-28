"""Normalize, merge and serialize complex tables for deterministic retrieval."""

from __future__ import annotations

import os
import re
import csv
import io
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


_NUMBER = re.compile(r"^[\s<>≈~+\-−–—]?\d[\d,.]*(?:\s*[%±])?(?:\s*[A-Za-z]+)?$")
_FOOTNOTE = re.compile(r"^(?:注|备注|note|source|来源|[*†‡])(?:\s*[:：.]|\s+)", re.I)
_UNIT = re.compile(
    r"(?:单位|unit)\s*[:：]\s*([^,，;；)\]]+)|"
    r"(?<!\w)(%|ms|s|sec|秒|分钟|小时|MB|GB|KB|px|dB|fps)(?!\w)",
    re.I,
)


def _clean_cell(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _rectangular_grid(raw: Any) -> list[list[str]]:
    if not isinstance(raw, list):
        return []
    rows = [
        [_clean_cell(cell) for cell in row]
        for row in raw
        if isinstance(row, list)
    ]
    width = max((len(row) for row in rows), default=0)
    return [row + [""] * (width - len(row)) for row in rows]


def _table_grid(table: dict[str, Any]) -> list[list[str]]:
    grid = _rectangular_grid(table.get("content"))
    if grid:
        return grid
    csv_text = str(table.get("csv") or table.get("csv_content") or "").strip()
    if csv_text:
        return _rectangular_grid(list(csv.reader(io.StringIO(csv_text))))
    markdown = str(table.get("markdown") or table.get("markdown_content") or "").strip()
    rows = []
    for line in markdown.splitlines():
        if "|" not in line:
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
            continue
        rows.append(cells)
    return _rectangular_grid(rows)


def _numeric_ratio(row: list[str]) -> float:
    nonempty = [cell for cell in row if cell]
    if not nonempty:
        return 0.0
    return sum(bool(_NUMBER.match(cell)) for cell in nonempty) / len(nonempty)


def detect_header_rows(grid: list[list[str]], max_rows: int = 3) -> list[int]:
    if len(grid) < 2:
        return [0] if grid else []
    headers = [0]
    for index in range(1, min(max_rows, len(grid) - 1)):
        current = grid[index]
        following = grid[index + 1]
        if _numeric_ratio(current) < 0.25 and _numeric_ratio(following) >= 0.25:
            headers.append(index)
        else:
            break
    return headers


def build_header_paths(grid: list[list[str]], header_rows: list[int]) -> list[list[str]]:
    if not grid:
        return []
    paths: list[list[str]] = []
    carry = [""] * len(grid[0])
    for column in range(len(grid[0])):
        values: list[str] = []
        for row_index in header_rows:
            value = grid[row_index][column]
            if value:
                carry[column] = value
            value = value or carry[column]
            if value and value not in values:
                values.append(value)
        paths.append(values or [f"第{column + 1}列"])
    return paths


def build_row_records(
    grid: list[list[str]],
    header_rows: list[int],
    header_paths: list[list[str]],
    caption: str,
    table_number: int,
    row_pages: list[int],
) -> list[dict[str, Any]]:
    records = []
    for row_index, row in enumerate(grid):
        if row_index in header_rows or not any(row):
            continue
        if _FOOTNOTE.match(next((cell for cell in row if cell), "")):
            continue
        fields = []
        for column, value in enumerate(row):
            if not value:
                continue
            label = " / ".join(header_paths[column]) if column < len(header_paths) else f"第{column + 1}列"
            fields.append({"column": column, "label": label, "value": value})
        if not fields:
            continue
        prefix = f"表{table_number}"
        if caption:
            prefix += f"（{caption}）"
        records.append({
            "row_index": row_index,
            "page": row_pages[row_index] if row_index < len(row_pages) else row_pages[-1],
            "fields": fields,
            "text": prefix + "：" + "；".join(
                f"{field['label']}={field['value']}" for field in fields
            ),
        })
    return records


def _header_signature(table: dict[str, Any]) -> str:
    grid = _table_grid(table)
    if not grid:
        return ""
    return "|".join(_clean_cell(cell).lower() for cell in grid[0])


def _caption_signature(table: dict[str, Any]) -> str:
    value = _clean_cell(table.get("caption") or table.get("table_title"))
    value = re.sub(r"(?:续表|continued|cont\.?)", "", value, flags=re.I)
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value.lower())


def should_merge_tables(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    previous_pages = previous.get("pages") or [previous.get("page", 1)]
    if int(current.get("page", 1)) != int(previous_pages[-1]) + 1:
        return False
    previous_grid = _rectangular_grid(previous.get("content"))
    current_grid = _rectangular_grid(current.get("content"))
    if not previous_grid or not current_grid or len(previous_grid[0]) != len(current_grid[0]):
        return False
    previous_caption = _caption_signature(previous)
    current_caption = _caption_signature(current)
    caption_match = bool(
        previous_caption
        and current_caption
        and SequenceMatcher(None, previous_caption, current_caption).ratio() >= 0.82
    )
    header_match = SequenceMatcher(
        None,
        _header_signature(previous),
        _header_signature(current),
    ).ratio() >= 0.86
    continuation_hint = bool(re.search(
        r"续表|continued|cont\.?",
        _clean_cell(current.get("caption") or current.get("table_title")),
        re.I,
    ))
    return header_match and (caption_match or continuation_hint or not current_caption)


def merge_cross_page_tables(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for source in sorted(tables, key=lambda item: (int(item.get("page", 1)), int(item.get("table_number", 0)))):
        current = dict(source)
        current["content"] = _table_grid(current)
        current["pages"] = list(current.get("pages") or [int(current.get("page", 1))])
        current["page_bboxes"] = list(current.get("page_bboxes") or [{
            "page": int(current.get("page", 1)),
            "bbox": list(current.get("bbox") or []),
        }])
        current["_row_pages"] = [int(current.get("page", 1))] * len(current["content"])
        current["source_table_count"] = int(current.get("source_table_count", 1))
        if not merged or not should_merge_tables(merged[-1], current):
            merged.append(current)
            continue

        target = merged[-1]
        target_grid = _rectangular_grid(target.get("content"))
        current_grid = current["content"]
        if target_grid and current_grid and _header_signature(target) == _header_signature(current):
            current_grid = current_grid[1:]
            current["_row_pages"] = current["_row_pages"][1:]
        target["content"] = target_grid + current_grid
        target["_row_pages"] = list(target.get("_row_pages") or []) + current["_row_pages"]
        target["pages"] = list(dict.fromkeys(target["pages"] + current["pages"]))
        target["page_bboxes"] = target["page_bboxes"] + current["page_bboxes"]
        target["source_table_count"] += current["source_table_count"]
        target["is_cross_page"] = True
    return merged


def normalize_table_structure(table: dict[str, Any], table_number: int) -> dict[str, Any]:
    grid = _table_grid(table)
    header_rows = detect_header_rows(grid)
    header_paths = build_header_paths(grid, header_rows)
    row_pages = list(table.get("_row_pages") or [int(table.get("page", 1))] * len(grid))
    caption = _clean_cell(table.get("caption") or table.get("table_title"))
    footnotes = [
        " | ".join(cell for cell in row if cell)
        for row in grid
        if _FOOTNOTE.match(next((cell for cell in row if cell), ""))
    ]
    units = []
    for value in [caption, *[cell for row in grid[:max(len(header_rows), 1)] for cell in row]]:
        for match in _UNIT.finditer(value):
            unit = next((group for group in match.groups() if group), "")
            unit = unit.strip().rstrip("）)]。.;；")
            if unit and unit not in units:
                units.append(unit)
    row_records = build_row_records(
        grid,
        header_rows,
        header_paths,
        caption,
        table_number,
        row_pages or [int(table.get("page", 1))],
    )
    nonempty = sum(bool(cell) for row in grid for cell in row)
    total = sum(len(row) for row in grid)
    confidence = min(0.98, 0.55 + 0.4 * nonempty / max(total, 1))
    return {
        "grid": grid,
        "header_rows": header_rows,
        "header_tree": header_paths,
        "row_records": row_records,
        "units": units,
        "footnotes": footnotes,
        "page_numbers": list(table.get("pages") or [int(table.get("page", 1))]),
        "page_bboxes": list(table.get("page_bboxes") or [{
            "page": int(table.get("page", 1)),
            "bbox": list(table.get("bbox") or []),
        }]),
        "parse_confidence": confidence,
        "is_cross_page": bool(table.get("is_cross_page")),
        "source_table_count": int(table.get("source_table_count", 1)),
    }


def build_table_cells(
    table: dict[str, Any],
    structure: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create source-addressable cells, retaining coordinates when available."""
    grid = structure["grid"]
    header_rows = set(structure["header_rows"])
    header_tree = structure["header_tree"]
    row_pages = list(table.get("_row_pages") or [int(table.get("page", 1))] * len(grid))
    boxes = table.get("cell_bboxes") or []
    cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(grid):
        for column_index, value in enumerate(row):
            bbox = []
            if row_index < len(boxes) and column_index < len(boxes[row_index]):
                bbox = list(boxes[row_index][column_index] or [])
            cells.append({
                "page_number": row_pages[row_index] if row_index < len(row_pages) else int(table.get("page", 1)),
                "row_index": row_index,
                "column_index": column_index,
                "row_span": 1,
                "column_span": 1,
                "text": value,
                "bbox": bbox,
                "header_path": header_tree[column_index] if column_index < len(header_tree) else [],
                "is_header": row_index in header_rows,
                "confidence": structure["parse_confidence"],
            })
    return cells


def save_table_screenshot(
    pdf_path: str,
    table: dict[str, Any],
    output_dir: str,
    table_number: int,
) -> str | None:
    bbox = list(table.get("bbox") or [])
    page_number = int(table.get("page", 1))
    if len(bbox) != 4:
        return table.get("image_path")
    try:
        import fitz

        os.makedirs(output_dir, exist_ok=True)
        path = str(Path(output_dir) / f"table_{table_number}_p{page_number}.png")
        with fitz.open(pdf_path) as document:
            page = document[page_number - 1]
            clip = fitz.Rect(*bbox) & page.rect
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
            pixmap.save(path)
        return path
    except Exception:
        return table.get("image_path")
