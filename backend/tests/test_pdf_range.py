import os

from app.api.papers import (
    _build_pdf_cache_headers,
    _parse_byte_range,
    _pdf_not_modified,
)


def test_parse_byte_range_supports_pdfjs_requests():
    assert _parse_byte_range("bytes=0-65535", 100_000) == (0, 65_535)
    assert _parse_byte_range("bytes=65536-", 100_000) == (65_536, 99_999)
    assert _parse_byte_range("bytes=-1000", 100_000) == (99_000, 99_999)


def test_parse_byte_range_clamps_end_and_rejects_invalid_ranges():
    assert _parse_byte_range("bytes=90000-200000", 100_000) == (90_000, 99_999)
    assert _parse_byte_range("bytes=100000-", 100_000) is None
    assert _parse_byte_range("bytes=0-1,4-5", 100_000) is None
    assert _parse_byte_range("invalid", 100_000) is None


def test_pdf_cache_headers_are_stable_for_unchanged_file(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\ncached")

    first = _build_pdf_cache_headers(str(pdf_path), "paper-1")
    second = _build_pdf_cache_headers(str(pdf_path), "paper-1")

    assert first["ETag"] == second["ETag"]
    assert first["Cache-Control"] == "private, max-age=86400, immutable"
    assert first["Accept-Ranges"] == "bytes"
    assert "Last-Modified" in first


def test_pdf_cache_validator_changes_when_file_changes(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nfirst")
    first = _build_pdf_cache_headers(str(pdf_path), "paper-1")

    pdf_path.write_bytes(b"%PDF-1.7\nsecond version")
    os.utime(pdf_path, None)
    second = _build_pdf_cache_headers(str(pdf_path), "paper-1")

    assert first["ETag"] != second["ETag"]
    assert _pdf_not_modified(second, second["ETag"], None)
    assert not _pdf_not_modified(second, first["ETag"], None)
