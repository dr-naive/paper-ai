"""Build a reliable paper outline from parser output and PDF layout metadata."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from statistics import median
from typing import Any

from app.services.paper_files import find_content_page, normalize_page_text

logger = logging.getLogger(__name__)

_SPECIAL_HEADING = re.compile(
    r"^(摘要|abstract|参考文献|references|bibliography|致谢|acknowledg(?:e)?ments?|"
    r"[A-Z]\s*(?:附录|appendix)|"
    r"附录|appendix|补充材料|supplementary materials?)$",
    re.IGNORECASE,
)
_NUMBERED_HEADING = re.compile(
    r"^(?:\d+\s+\S|\d+(?:\.\d+)+[.)、]?\s+\S|[A-Z](?:\.\d+)+[.)、]?\s+\S).{0,78}$",
    re.IGNORECASE,
)
_CHINESE_HEADING = re.compile(r"^第[一二三四五六七八九十百\d]+[章节]\s*\S.{0,116}$")


@dataclass(frozen=True)
class OutlineCandidate:
    title: str
    start_page: int
    level: int = 1
    source: str = "layout"
    confidence: float = 0.8


def _clean_heading(value: str) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n-—")
    return re.sub(r"^([A-Z])(?=附录|appendix)", r"\1 ", title, flags=re.IGNORECASE)


def _heading_level(title: str, fallback: int = 1) -> int:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)[.)、]?(?:\s+|$)", title)
    if match:
        return min(4, len(match.group(1).split(".")))
    appendix = re.match(r"^\s*[A-Z](?:\.(\d+(?:\.\d+)*))?[.)、]?(?:\s+|$)", title, re.I)
    if appendix:
        return 1 if not appendix.group(1) else min(4, 1 + len(appendix.group(1).split(".")))
    if re.match(r"^\s*第[一二三四五六七八九十百\d]+章", title):
        return 1
    if re.match(r"^\s*第[一二三四五六七八九十百\d]+节", title):
        return 2
    return max(1, min(4, fallback))


def _outline_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    title = str(item.get("title") or "")
    page = int(item.get("start_page") or 1)
    numeric = re.match(r"^\s*(\d+(?:\.\d+)*)[.)、]?(?:\s+|$)", title)
    if numeric:
        return page, 1, tuple(int(part) for part in numeric.group(1).split("."))
    appendix = re.match(r"^\s*([A-Z])(?:\.(\d+(?:\.\d+)*))?[.)、]?(?:\s+|$)", title, re.I)
    if appendix:
        suffix = tuple(int(part) for part in appendix.group(2).split(".")) if appendix.group(2) else ()
        return page, 2, appendix.group(1).upper(), suffix
    return page, 0, ()


def _looks_like_heading(title: str) -> bool:
    if not title or len(title) > 120 or title.endswith(("。", ".", "，", ",", "；", ";", "：", ":")):
        return False
    return bool(
        _SPECIAL_HEADING.match(title)
        or _NUMBERED_HEADING.match(title)
        or _CHINESE_HEADING.match(title)
    )


def extract_pdf_outline(file_path: str) -> list[OutlineCandidate]:
    """Extract native bookmarks first, then supplement them with visual headings."""
    try:
        import fitz

        with fitz.open(file_path) as document:
            native = [
                OutlineCandidate(
                    title=_clean_heading(title),
                    start_page=max(1, int(page)),
                    level=max(1, int(level)),
                    source="bookmark",
                    confidence=1.0,
                )
                for level, title, page, *_ in document.get_toc(simple=True)
                if _clean_heading(title) and int(page) > 0
            ]

            layout: list[OutlineCandidate] = []
            for page_index, page in enumerate(document):
                page_dict = page.get_text("dict")
                lines: list[tuple[str, float, bool]] = []
                font_sizes: list[float] = []
                for block in page_dict.get("blocks", []):
                    for line in block.get("lines", []):
                        spans = [span for span in line.get("spans", []) if str(span.get("text", "")).strip()]
                        if not spans:
                            continue
                        title = _clean_heading("".join(str(span.get("text", "")) for span in spans))
                        size = max(float(span.get("size") or 0) for span in spans)
                        bold = any(int(span.get("flags") or 0) & 16 for span in spans)
                        lines.append((title, size, bold))
                        font_sizes.extend(float(span.get("size") or 0) for span in spans)

                body_size = median(font_sizes) if font_sizes else 0
                for title, size, bold in lines:
                    if not _looks_like_heading(title):
                        continue
                    visually_distinct = bold or size >= body_size * 1.14
                    if not visually_distinct and not _SPECIAL_HEADING.match(title):
                        continue
                    layout.append(OutlineCandidate(
                        title=title,
                        start_page=page_index + 1,
                        level=_heading_level(title),
                        source="layout",
                        confidence=0.94 if _SPECIAL_HEADING.match(title) else 0.86,
                    ))
    except Exception as exc:
        logger.warning("PDF 目录版面提取失败: %s", exc)
        return []

    return merge_outline_candidates(native, layout)


def merge_outline_candidates(*candidate_groups: list[OutlineCandidate]) -> list[OutlineCandidate]:
    """Merge candidates in source priority order and remove repeated headings."""
    merged: list[OutlineCandidate] = []
    seen: set[tuple[str, int]] = set()
    for group in candidate_groups:
        for candidate in group:
            normalized = normalize_page_text(candidate.title)
            key = (normalized, candidate.start_page)
            if not normalized or key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
    return sorted(merged, key=lambda item: item.start_page)


def enrich_sections_with_pdf(
    sections: list[dict[str, Any]],
    file_path: str,
    page_contents: list[str],
) -> list[dict[str, Any]]:
    """Add missing PDF headings and assign physical pages to parsed sections."""
    page_texts = [normalize_page_text(content) for content in page_contents]
    enriched: list[dict[str, Any]] = []
    page_hint = 1
    for section in sections:
        item = dict(section)
        page_hint = find_content_page(
            page_texts,
            f"{item.get('title', '')}\n{str(item.get('content', ''))[:200]}",
            page_hint,
        )
        item["start_page"] = page_hint
        item.setdefault("source", "parser")
        item.setdefault("confidence", 0.82)
        enriched.append(item)

    existing_titles = {normalize_page_text(item.get("title", "")) for item in enriched}
    candidates = extract_pdf_outline(file_path)
    for index, candidate in enumerate(candidates):
        normalized = normalize_page_text(candidate.title)
        if not normalized or normalized in existing_titles:
            continue
        next_page = candidates[index + 1].start_page if index + 1 < len(candidates) else len(page_contents) + 1
        content = "\n\n".join(page_contents[candidate.start_page - 1:max(candidate.start_page, next_page - 1)]).strip()
        enriched.append({
            "title": candidate.title,
            "content": content,
            "key_points": [],
            "start_page": candidate.start_page,
            "level": candidate.level,
            "source": candidate.source,
            "confidence": candidate.confidence,
        })
        existing_titles.add(normalized)

    enriched.sort(key=_outline_sort_key)
    for index, item in enumerate(enriched):
        item["order_index"] = index
    return enriched
