import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException

from app.api.papers import _save_validated_pdf


class AsyncUpload:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.file = BytesIO(content)
        self.closed = False

    async def read(self, size: int) -> bytes:
        return self.file.read(size)

    async def close(self) -> None:
        self.closed = True
        self.file.close()


def make_upload(filename: str, content: bytes) -> AsyncUpload:
    return AsyncUpload(filename, content)


def test_streamed_pdf_upload_validates_signature_and_writes_file(tmp_path):
    destination = tmp_path / "paper.pdf"
    size = asyncio.run(_save_validated_pdf(
        make_upload("PAPER.PDF", b"%PDF-1.7\nvalid"), str(destination), 1024
    ))
    assert size == len(b"%PDF-1.7\nvalid")
    assert destination.read_bytes().startswith(b"%PDF-")


def test_fake_pdf_is_rejected_and_removed(tmp_path):
    destination = tmp_path / "fake.pdf"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_save_validated_pdf(
            make_upload("fake.pdf", b"not a pdf"), str(destination), 1024
        ))
    assert exc.value.status_code == 400
    assert not destination.exists()


def test_oversized_pdf_is_rejected_and_removed(tmp_path):
    destination = tmp_path / "large.pdf"
    with pytest.raises(HTTPException):
        asyncio.run(_save_validated_pdf(
            make_upload("large.pdf", b"%PDF-" + b"x" * 20), str(destination), 10
        ))
    assert not destination.exists()
