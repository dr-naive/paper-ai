"""Upload intake service for validating, storing and reading paper PDFs."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from fastapi import UploadFile

from app.services.paper_files import extract_pdf_text, save_validated_pdf


class PaperTextExtractionError(RuntimeError):
    """Raised when the stored PDF cannot be parsed."""


class PaperTextMissingError(ValueError):
    """Raised when a valid PDF has no extractable text."""


@dataclass(frozen=True)
class PaperUploadResult:
    paper_id: str
    file_path: str
    file_size: int
    timings: dict[str, float]


@dataclass(frozen=True)
class PaperTextResult:
    raw_text: str
    extraction_method: str
    elapsed_seconds: float


class PaperUploadService:
    """Stable boundary for upload intake and deferred text extraction."""

    async def receive(
        self,
        *,
        upload: UploadFile,
        paper_id: str,
        storage_path: str,
        max_upload_size: int,
    ) -> PaperUploadResult:
        file_path = os.path.join(storage_path, f"{paper_id}.pdf")
        timings: dict[str, float] = {}

        started_at = time.perf_counter()
        file_size = await save_validated_pdf(upload, file_path, max_upload_size)
        timings["file_save"] = time.perf_counter() - started_at

        return PaperUploadResult(
            paper_id=paper_id,
            file_path=file_path,
            file_size=file_size,
            timings=timings,
        )

    async def extract_text(self, file_path: str) -> PaperTextResult:
        """Extract PDF text outside the request path."""
        started_at = time.perf_counter()
        try:
            raw_text, extraction_method = await asyncio.to_thread(extract_pdf_text, file_path)
        except Exception as exc:
            self._remove_file(file_path)
            raise PaperTextExtractionError(str(exc)) from exc

        if not raw_text.strip():
            self._remove_file(file_path)
            raise PaperTextMissingError("无法从 PDF 中提取文字")

        return PaperTextResult(
            raw_text=raw_text,
            extraction_method=extraction_method,
            elapsed_seconds=time.perf_counter() - started_at,
        )

    @staticmethod
    def _remove_file(file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)


paper_upload_service = PaperUploadService()
