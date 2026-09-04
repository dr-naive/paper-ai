import asyncio

import pytest

from app.services import remote_paper_import
from app.services.remote_paper_import import RemotePaperImportError, normalize_arxiv_id


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


class _SlowResponse:
    url = "https://export.arxiv.org/pdf/2401.12345"
    headers = {}

    def raise_for_status(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def aiter_bytes(self, _chunk_size):
        yield b"%PDF-"
        await asyncio.sleep(10)


class _SlowClient:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, *_args, **_kwargs):
        return _SlowResponse()


@pytest.mark.asyncio
async def test_download_has_total_deadline_and_removes_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(remote_paper_import.httpx, "AsyncClient", _SlowClient)

    with pytest.raises(RemotePaperImportError, match="超过总时限"):
        await remote_paper_import.download_arxiv_pdf(
            "2401.12345",
            paper_id="paper-timeout",
            storage_path=str(tmp_path),
            max_size=1024 * 1024,
            timeout_seconds=1,
            total_timeout_seconds=0.05,
        )

    assert not (tmp_path / "paper-timeout.pdf.part").exists()
    assert not (tmp_path / "paper-timeout.pdf").exists()


@pytest.mark.asyncio
async def test_download_cancellation_removes_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(remote_paper_import.httpx, "AsyncClient", _SlowClient)
    task = asyncio.create_task(remote_paper_import.download_arxiv_pdf(
        "2401.12345",
        paper_id="paper-cancelled",
        storage_path=str(tmp_path),
        max_size=1024 * 1024,
        timeout_seconds=30,
        total_timeout_seconds=30,
    ))
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert not (tmp_path / "paper-cancelled.pdf.part").exists()
    assert not (tmp_path / "paper-cancelled.pdf").exists()
