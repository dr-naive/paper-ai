"""Layout-aware PDF element extraction.

This module creates a stable physical document layer between PDF parsing and
semantic chunking. It deliberately uses deterministic PDF metadata first; OCR
and model-based layout analysis can be added as fallbacks without changing the
stored element contract.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Any


INDEXABLE_TYPES = {
    "title",
    "paragraph",
    "list",
    "caption",
    "equation",
}
NON_INDEXABLE_TYPES = {"header", "footer", "page_number", "figure", "unknown"}

_NUMBERED_TITLE = re.compile(
    r"^(?:第[一二三四五六七八九十百]+[章节篇]|"
    r"\d+(?:\.\d+){0,4}(?:\s+|、|．|\.)|"
    r"(?:abstract|摘要|introduction|引言|conclusion|结论|references|参考文献)\b)",
    re.IGNORECASE,
)
_LIST_PREFIX = re.compile(
    r"^(?:[-•●▪◦]\s*|\(?\d+\)?[.)、](?!\d)\s*|"
    r"[（(]?[一二三四五六七八九十]+[）)、.]\s*)"
)
_CAPTION_PREFIX = re.compile(
    r"^(?:fig(?:ure)?\.?\s*\d+|图\s*\d+|table\s*\d+|表\s*\d+)",
    re.IGNORECASE,
)
_PAGE_NUMBER = re.compile(r"^(?:page\s*)?[-–—]?\s*\d+\s*[-–—]?$", re.IGNORECASE)
_EQUATION_HINT = re.compile(r"[=∑∏√∞≤≥±×÷∫]|\\(?:frac|sum|alpha|beta|gamma)")


@dataclass
class LayoutElement:
    id: str
    element_type: str
    page_number: int
    order_index: int
    page_order: int
    text: str
    bbox: list[float]
    section_path: list[str] = field(default_factory=list)
    confidence: float = 1.0
    extraction_method: str = "pymupdf_layout"
    is_indexable: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "element_type": self.element_type,
            "page_number": self.page_number,
            "order_index": self.order_index,
            "page_order": self.page_order,
            "text": self.text,
            "bbox": self.bbox,
            "section_path": self.section_path,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "is_indexable": self.is_indexable,
            "attributes": self.attributes,
        }


def _clean_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(value or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _repeat_signature(value: str) -> str:
    normalized = str(value or "").lower()
    normalized = re.sub(r"\d+", "#", normalized)
    return re.sub(r"[^\w\u4e00-\u9fff#]+", "", normalized)


def _title_level(text: str) -> int:
    match = re.match(r"^(\d+(?:\.\d+)*)", text)
    if match:
        return min(len(match.group(1).split(".")), 6)
    if re.match(r"^第[一二三四五六七八九十百]+[篇章]", text):
        return 1
    if re.match(r"^第[一二三四五六七八九十百]+节", text):
        return 2
    return 1


def _span_metrics(lines: list[dict[str, Any]]) -> tuple[float, bool, list[str]]:
    sizes: list[float] = []
    fonts: list[str] = []
    bold = False
    for line in lines:
        for span in line.get("spans", []):
            size = float(span.get("size") or 0)
            if size > 0:
                sizes.append(size)
            font = str(span.get("font") or "")
            if font:
                fonts.append(font)
            flags = int(span.get("flags") or 0)
            bold = bold or "bold" in font.lower() or bool(flags & 16)
    return (max(sizes, default=0.0), bold, fonts)


def _looks_like_equation(text: str) -> bool:
    if len(text) > 240 or not _EQUATION_HINT.search(text):
        return False
    letters = len(re.findall(r"[A-Za-z\u4e00-\u9fff]", text))
    operators = len(_EQUATION_HINT.findall(text))
    return operators >= 2 or (operators >= 1 and letters <= 24)


def _classify_text_block(
    *,
    text: str,
    max_font_size: float,
    body_font_size: float,
    bold: bool,
) -> tuple[str, float]:
    compact = re.sub(r"\s+", " ", text).strip()
    if _PAGE_NUMBER.fullmatch(compact):
        return "page_number", 0.99
    if _CAPTION_PREFIX.match(compact):
        return "caption", 0.96
    if _LIST_PREFIX.match(compact):
        return "list", 0.9
    if _looks_like_equation(compact):
        return "equation", 0.78
    title_by_font = (
        len(compact) <= 180
        and body_font_size > 0
        and max_font_size >= body_font_size * 1.22
    )
    if len(compact) <= 220 and (_NUMBERED_TITLE.match(compact) or title_by_font):
        return "title", 0.9 if _NUMBERED_TITLE.match(compact) else 0.76
    return "paragraph", 0.9


def _apply_section_paths(elements: list[LayoutElement]) -> None:
    path: list[str] = []
    for element in elements:
        if element.element_type == "title" and element.text:
            level = _title_level(element.text)
            path = path[:level - 1]
            path.append(element.text[:200])
        element.section_path = list(path)


def _sort_page_reading_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order common one/two-column pages while preserving full-width separators."""
    if len(items) < 3:
        return sorted(items, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    page_width = max(float(items[0].get("page_width") or 0), 1)
    content = [
        item for item in items
        if item["bbox"][2] - item["bbox"][0] < page_width * 0.72
        and item["kind"] == "text"
    ]
    left = [
        item for item in content
        if (item["bbox"][0] + item["bbox"][2]) / 2 < page_width * 0.47
    ]
    right = [
        item for item in content
        if (item["bbox"][0] + item["bbox"][2]) / 2 > page_width * 0.53
    ]
    if len(left) < 2 or len(right) < 2:
        return sorted(items, key=lambda item: (item["bbox"][1], item["bbox"][0]))

    full_width = [
        item for item in items
        if item not in left and item not in right
        or item["bbox"][2] - item["bbox"][0] >= page_width * 0.72
    ]
    separators = sorted(full_width, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    ordered: list[dict[str, Any]] = []
    remaining = list(items)
    segment_top = float("-inf")
    for separator in separators:
        separator_top = separator["bbox"][1]
        segment = [
            item for item in remaining
            if segment_top <= item["bbox"][1] < separator_top and item is not separator
        ]
        segment_left = sorted(
            [item for item in segment if item in left],
            key=lambda item: (item["bbox"][1], item["bbox"][0]),
        )
        segment_right = sorted(
            [item for item in segment if item in right],
            key=lambda item: (item["bbox"][1], item["bbox"][0]),
        )
        segment_other = sorted(
            [item for item in segment if item not in left and item not in right],
            key=lambda item: (item["bbox"][1], item["bbox"][0]),
        )
        ordered.extend(segment_other + segment_left + segment_right)
        for item in segment:
            if item in remaining:
                remaining.remove(item)
        if separator in remaining:
            ordered.append(separator)
            remaining.remove(separator)
        segment_top = separator["bbox"][3]

    tail_left = sorted(
        [item for item in remaining if item in left],
        key=lambda item: (item["bbox"][1], item["bbox"][0]),
    )
    tail_right = sorted(
        [item for item in remaining if item in right],
        key=lambda item: (item["bbox"][1], item["bbox"][0]),
    )
    tail_other = sorted(
        [item for item in remaining if item not in left and item not in right],
        key=lambda item: (item["bbox"][1], item["bbox"][0]),
    )
    ordered.extend(tail_other + tail_left + tail_right)
    return ordered


def extract_layout_elements(file_path: str) -> list[dict[str, Any]]:
    """Extract page-bound elements with type, reading order and coordinates."""
    import fitz

    raw_elements: list[dict[str, Any]] = []
    page_body_font_sizes: dict[int, float] = {}
    with fitz.open(file_path) as document:
        page_count = len(document)
        for page_index, page in enumerate(document):
            page_dict = page.get_text("dict")
            page_height = float(page.rect.height)
            page_width = float(page.rect.width)
            page_sizes: list[float] = []
            for page_order, block in enumerate(page_dict.get("blocks", [])):
                bbox = [round(float(value), 3) for value in block.get("bbox", [0, 0, 0, 0])]
                if int(block.get("type", 0)) == 1:
                    raw_elements.append({
                        "kind": "figure",
                        "page_number": page_index + 1,
                        "page_order": page_order,
                        "text": "",
                        "bbox": bbox,
                        "page_height": page_height,
                        "page_width": page_width,
                        "max_font_size": 0.0,
                        "bold": False,
                        "fonts": [],
                        "attributes": {
                            "width": block.get("width"),
                            "height": block.get("height"),
                            "extension": block.get("ext"),
                        },
                    })
                    continue

                lines = block.get("lines", [])
                text = _clean_text("\n".join(
                    "".join(str(span.get("text") or "") for span in line.get("spans", []))
                    for line in lines
                ))
                if not text:
                    continue
                max_size, bold, fonts = _span_metrics(lines)
                if max_size > 0:
                    page_sizes.append(max_size)
                raw_elements.append({
                    "kind": "text",
                    "page_number": page_index + 1,
                    "page_order": page_order,
                    "text": text,
                    "bbox": bbox,
                    "page_height": page_height,
                    "page_width": page_width,
                    "max_font_size": max_size,
                    "bold": bold,
                    "fonts": fonts,
                    "attributes": {"line_count": len(lines)},
                })
            if page_sizes:
                page_body_font_sizes[page_index + 1] = median(page_sizes)

    page_groups: dict[int, list[dict[str, Any]]] = {}
    for item in raw_elements:
        page_groups.setdefault(item["page_number"], []).append(item)
    raw_elements = [
        item
        for page_number in sorted(page_groups)
        for item in _sort_page_reading_order(page_groups[page_number])
    ]
    for page_number, items in page_groups.items():
        ordered_page = _sort_page_reading_order(items)
        for page_order, item in enumerate(ordered_page):
            item["page_order"] = page_order

    edge_signatures: Counter[str] = Counter()
    for item in raw_elements:
        if item["kind"] != "text":
            continue
        top_ratio = item["bbox"][1] / max(item["page_height"], 1)
        bottom_ratio = item["bbox"][3] / max(item["page_height"], 1)
        signature = _repeat_signature(item["text"])
        if len(signature) >= 4 and (top_ratio <= 0.08 or bottom_ratio >= 0.92):
            edge_signatures[signature] += 1
    repeated_threshold = max(2, math.ceil(max(page_count, 1) * 0.3))
    repeated_edges = {
        signature for signature, count in edge_signatures.items()
        if count >= repeated_threshold
    }

    elements: list[LayoutElement] = []
    for order_index, item in enumerate(raw_elements):
        if item["kind"] == "figure":
            element_type, confidence = "figure", 0.98
        else:
            element_type, confidence = _classify_text_block(
                text=item["text"],
                max_font_size=item["max_font_size"],
                body_font_size=page_body_font_sizes.get(item["page_number"], 10.0),
                bold=item["bold"],
            )
            signature = _repeat_signature(item["text"])
            top_ratio = item["bbox"][1] / max(item["page_height"], 1)
            bottom_ratio = item["bbox"][3] / max(item["page_height"], 1)
            if signature in repeated_edges:
                if top_ratio <= 0.08:
                    prominent_first_page = (
                        item["page_number"] == 1
                        and item["max_font_size"]
                        >= page_body_font_sizes.get(1, 10.0) * 1.35
                    )
                    if not prominent_first_page:
                        element_type, confidence = "header", 0.96
                elif bottom_ratio >= 0.92:
                    element_type, confidence = "footer", 0.96

        attributes = dict(item["attributes"])
        attributes.update({
            "page_width": item["page_width"],
            "page_height": item["page_height"],
            "max_font_size": item["max_font_size"],
            "bold": item["bold"],
            "fonts": item["fonts"],
        })
        elements.append(LayoutElement(
            id=str(uuid.uuid4()),
            element_type=element_type,
            page_number=item["page_number"],
            order_index=order_index,
            page_order=item["page_order"],
            text=item["text"],
            bbox=item["bbox"],
            confidence=confidence,
            is_indexable=element_type in INDEXABLE_TYPES,
            attributes=attributes,
        ))

    _apply_section_paths(elements)
    return [element.as_dict() for element in elements]


def build_element_chunks(elements: list[dict[str, Any]], chunker: Any) -> list[dict[str, Any]]:
    """Build retrieval chunks without losing physical element provenance."""
    chunks: list[dict[str, Any]] = []
    next_index = 0
    pages = {int(element.get("page_number") or 0) for element in elements}
    signature_pages: dict[str, set[int]] = {}
    for element in elements:
        page = int(element.get("page_number") or 0)
        for line in str(element.get("text") or "").splitlines():
            signature = re.sub(
                r"[^\w\u4e00-\u9fff]+", "", str(line or "").lower()
            )
            if len(signature) >= 4:
                signature_pages.setdefault(signature, set()).add(page)
    repeated_threshold = max(2, math.ceil(max(len(pages), 1) * 0.3))
    repeated_lines = {
        signature for signature, line_pages in signature_pages.items()
        if len(line_pages) >= repeated_threshold
    }
    for element in elements:
        clean_text = "\n".join(
            line for line in str(element.get("text") or "").splitlines()
            if re.sub(r"[^\w\u4e00-\u9fff]+", "", line.lower()) not in repeated_lines
            and not _PAGE_NUMBER.fullmatch(line.strip())
        ).strip()
        if not element.get("is_indexable") or not clean_text:
            continue
        element_type = str(element.get("element_type") or "paragraph")
        if element_type == "title":
            continue
        section_path = [
            str(value) for value in element.get("section_path", []) if str(value).strip()
        ]
        section = section_path[-1] if section_path else f"PDF 第{element['page_number']}页"
        local_chunks = chunker.chunk_text(clean_text, section)
        for local_chunk in local_chunks:
            local_index = int(local_chunk.get("index") or 0)
            local_chunk["index"] = next_index + local_index
            if local_chunk.get("parent_index") is not None:
                local_chunk["parent_index"] = (
                    next_index + int(local_chunk["parent_index"])
                )
            local_chunk.update({
                "page": int(element["page_number"]),
                "element_id": str(element["id"]),
                "element_type": element_type,
                "bbox": list(element.get("bbox") or []),
                "section_path": section_path,
                "layout_confidence": float(element.get("confidence") or 0),
                "coverage_source": "document_element",
            })
        chunks.extend(local_chunks)
        next_index += len(local_chunks)
    return chunks
