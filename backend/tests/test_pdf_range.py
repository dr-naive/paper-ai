from app.api.papers import _parse_byte_range


def test_parse_byte_range_supports_pdfjs_requests():
    assert _parse_byte_range("bytes=0-65535", 100_000) == (0, 65_535)
    assert _parse_byte_range("bytes=65536-", 100_000) == (65_536, 99_999)
    assert _parse_byte_range("bytes=-1000", 100_000) == (99_000, 99_999)


def test_parse_byte_range_clamps_end_and_rejects_invalid_ranges():
    assert _parse_byte_range("bytes=90000-200000", 100_000) == (90_000, 99_999)
    assert _parse_byte_range("bytes=100000-", 100_000) is None
    assert _parse_byte_range("bytes=0-1,4-5", 100_000) is None
    assert _parse_byte_range("invalid", 100_000) is None
