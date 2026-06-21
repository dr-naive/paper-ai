"""Normalization and chunk construction for parsed papers."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.paper_files import find_content_page, normalize_page_text

logger = logging.getLogger(__name__)


def normalize_key_points(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except json.JSONDecodeError:
            pass
        return [stripped]
    return []


def normalize_sections(raw_sections: list, raw_text: str) -> list[dict]:
    sections = []
    for index, section in enumerate(raw_sections or []):
        if not isinstance(section, dict):
            continue
        title = (
            section.get("title")
            or section.get("section_title")
            or section.get("heading")
            or f"第{index + 1}节"
        )
        content = section.get("content") or section.get("text") or section.get("body") or ""
        title = str(title).strip()[:200] or f"第{index + 1}节"
        content = str(content).strip()
        if content:
            sections.append({
                "title": title,
                "content": content,
                "key_points": normalize_key_points(section.get("key_points", [])),
            })
    if sections:
        return sections
    logger.warning("未解析到有效章节，创建默认全文章节")
    return [{"title": "全文", "content": raw_text[:100000], "key_points": []}]


def build_text_chunks(
    sections: list[dict],
    chunker: Any,
    page_texts: list[str] | None = None,
) -> list[dict]:
    chunks: list[dict] = []
    next_index = 0
    page_hint = 1
    for section in sections:
        title = section.get("title", "全文")
        content = section.get("content", "")
        if not content:
            continue
        section_page = find_content_page(page_texts or [], f"{title}\n{content[:200]}", page_hint)
        page_hint = section_page
        local_chunks = chunker.chunk_text(content, title)
        for chunk in local_chunks:
            local_index = int(chunk.get("index") or 0)
            chunk["index"] = next_index + local_index
            if chunk.get("parent_index") is not None:
                chunk["parent_index"] = next_index + int(chunk["parent_index"])
            chunk["page"] = find_content_page(
                page_texts or [], chunk.get("content", ""), section_page
            )
        chunks.extend(local_chunks)
        next_index += len(local_chunks)
    return chunks


def build_complete_text_chunks(
    sections: list[dict],
    chunker: Any,
    page_texts: list[str] | None = None,
    page_contents: list[str] | None = None,
) -> list[dict]:
    chunks = build_text_chunks(sections, chunker, page_texts)
    if not sections or not page_contents:
        return chunks

    first_section = sections[0]
    is_single_full_text = len(sections) == 1 and first_section.get("title") == "全文"
    persisted_length = len(normalize_page_text(first_section.get("content", "")))
    pdf_length = sum(len(normalize_page_text(content)) for content in page_contents)
    if is_single_full_text and persisted_length < pdf_length * 0.8:
        fallback_end = len(page_contents)
    elif is_single_full_text:
        fallback_end = 0
    else:
        first_section_page = find_content_page(
            page_texts or [],
            f"{first_section.get('title', '')}\n{first_section.get('content', '')[:200]}",
            1,
        )
        fallback_end = min(max(1, first_section_page), len(page_contents))
    next_index = max((int(chunk.get("index") or 0) for chunk in chunks), default=-1) + 1

    for page_number in range(1, fallback_end + 1):
        page_content = page_contents[page_number - 1].strip()
        if len(normalize_page_text(page_content)) < 80:
            continue
        title = f"前置内容（PDF 第{page_number}页）"
        local_chunks = chunker.chunk_text(page_content, title)
        for chunk in local_chunks:
            local_index = int(chunk.get("index") or 0)
            chunk["index"] = next_index + local_index
            if chunk.get("parent_index") is not None:
                chunk["parent_index"] = next_index + int(chunk["parent_index"])
            chunk["page"] = page_number
            chunk["coverage_source"] = "front_matter_fallback"
        chunks.extend(local_chunks)
        next_index += len(local_chunks)
    return chunks
