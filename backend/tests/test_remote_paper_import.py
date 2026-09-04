import pytest

from app.services.remote_paper_import import normalize_arxiv_id


@pytest.mark.parametrize("value,expected", [
    ("2401.12345", "2401.12345"),
    ("2401.12345v2", "2401.12345v2"),
    ("https://arxiv.org/abs/2401.12345", "2401.12345"),
    ("https://export.arxiv.org/pdf/cs/9901001.pdf", "cs/9901001"),
])
def test_normalize_arxiv_id_accepts_only_canonical_arxiv_forms(value, expected):
    assert normalize_arxiv_id(value) == expected


@pytest.mark.parametrize("value", [
    "https://example.com/paper.pdf", "file:///etc/passwd", "../../secret", "2401.1", "2401.12345?x=1",
])
def test_normalize_arxiv_id_rejects_arbitrary_urls_and_paths(value):
    with pytest.raises(ValueError):
        normalize_arxiv_id(value)
