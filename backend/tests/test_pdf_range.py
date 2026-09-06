import os
import pytest

from app.api.papers import (
    PdfLoadTelemetry,
    _build_pdf_cache_headers,
    _parse_byte_range,
    _pdf_not_modified,
)
from app.services.paper_files import read_file_range


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
    assert first["Cache-Control"] == "private, max-age=86400"
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


def test_read_file_range_returns_exact_bytes(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n0123456789")

    assert read_file_range(str(pdf_path), 5, 10) == b"1.7\n01"


def test_read_file_range_rejects_a_short_body(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")

    try:
        read_file_range(str(pdf_path), 5, 20)
    except OSError as exc:
        assert "expected" in str(exc)
    else:
        raise AssertionError("short PDF ranges must not be returned with a false length")


def test_pdf_load_telemetry_is_bounded_and_typed():
    metric = PdfLoadTelemetry(
        outcome="success",
        source="cache",
        total_ms=42.5,
        pages=3,
        network_requests=0,
        cache_bytes=128,
    )

    assert metric.source == "cache"
    assert metric.pages == 3
    assert metric.document_ms == 0

    with pytest.raises(ValueError):
        PdfLoadTelemetry(outcome="success", source="range", total_ms=-1)
