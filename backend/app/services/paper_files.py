"""PDF upload, byte-range and physical-page utilities."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator

import pdfplumber
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)
UPLOAD_CHUNK_SIZE = 1024 * 1024


def parse_byte_range(range_header: str, file_size: int) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes=") or file_size <= 0:
        return None
    value = range_header[6:].strip()
    if "," in value or "-" not in value:
        return None
    start_text, end_text = value.split("-", 1)
    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
            if start < 0 or start >= file_size or end < start:
                return None
            end = min(end, file_size - 1)
    except ValueError:
        return None
    return start, end


def iter_file_range(
    file_path: str,
    start: int,
    end: int,
    chunk_size: int = 256 * 1024,
) -> Iterator[bytes]:
    remaining = end - start + 1
    with open(file_path, "rb") as file_obj:
        file_obj.seek(start)
        while remaining > 0:
            data = file_obj.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


async def save_validated_pdf(upload: UploadFile, file_path: str, max_size: int) -> int:
    filename = str(upload.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 格式")
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    total = 0
    try:
        with open(file_path, "wb") as destination:
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                if total == 0 and chunk[:5] != b"%PDF-":
                    raise HTTPException(status_code=400, detail="文件内容不是有效的 PDF")
                total += len(chunk)
                if total > max_size:
                    raise HTTPException(
                        status_code=400,
                        detail=f"文件大小不能超过 {max_size // 1024 // 1024}MB",
                    )
                destination.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="PDF 文件为空")
        return total
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    finally:
        await upload.close()


def extract_pdf_text(file_path: str, max_pages: int = 51) -> tuple[str, str]:
    try:
        import fitz

        with fitz.open(file_path) as document:
            text = "\n\n".join(
                document[index].get_text("text")
                for index in range(min(max_pages, len(document)))
            )
        if text.strip():
            return text, "pymupdf"
    except Exception as exc:
        logger.warning("PyMuPDF 文字提取失败，回退 pdfplumber: %s", exc)

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[:max_pages]:
            if page_text := page.extract_text():
                text_parts.append(page_text)
    return "\n\n".join(text_parts), "pdfplumber"


def normalize_page_text(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(value or "").lower())


def extract_pdf_page_texts(file_path: str) -> list[str]:
    try:
        import fitz

        with fitz.open(file_path) as document:
            return [normalize_page_text(page.get_text("text")) for page in document]
    except Exception as exc:
        logger.warning("提取 PDF 分页文本失败，页码定位将回退: %s", exc)
        return []


def extract_pdf_page_contents(file_path: str) -> list[str]:
    try:
        import fitz

        with fitz.open(file_path) as document:
            return [page.get_text("text").strip() for page in document]
    except Exception as exc:
        logger.warning("提取 PDF 原始分页文本失败: %s", exc)
        return []


def find_content_page(page_texts: list[str], content: str, start_page: int = 1) -> int:
    if not page_texts:
        return max(1, start_page)
    normalized = normalize_page_text(content)
    if not normalized:
        return max(1, start_page)

    anchor_length = min(48, len(normalized))
    anchors = []
    for offset in (0, 48, 96, max(0, len(normalized) - anchor_length)):
        anchor = normalized[offset:offset + anchor_length]
        if len(anchor) >= 12 and anchor not in anchors:
            anchors.append(anchor)

    order = list(range(max(0, start_page - 1), len(page_texts)))
    order.extend(range(0, max(0, start_page - 1)))
    best_index = max(0, min(start_page - 1, len(page_texts) - 1))
    best_score = 0
    for index in order:
        score = sum(1 for anchor in anchors if anchor in page_texts[index])
        if score > best_score:
            best_index = index
            best_score = score
        if score == len(anchors) and score > 0:
            break
    return best_index + 1
