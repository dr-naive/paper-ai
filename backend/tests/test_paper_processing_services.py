import asyncio
from io import BytesIO

from app.services.paper_core_processing import PaperCoreProcessingService
from app.services.paper_upload import PaperUploadService


class AsyncUpload:
    def __init__(self, content: bytes):
        self.filename = "paper.pdf"
        self.file = BytesIO(content)

    async def read(self, size: int) -> bytes:
        return self.file.read(size)

    async def close(self) -> None:
        self.file.close()


def test_upload_service_returns_stable_intake_result(tmp_path, monkeypatch):
    result = asyncio.run(PaperUploadService().receive(
        upload=AsyncUpload(b"%PDF-1.7\ncontent"),
        paper_id="paper-1",
        storage_path=str(tmp_path),
        max_upload_size=1024,
    ))

    assert result.paper_id == "paper-1"
    assert set(result.timings) == {"file_save"}
    assert (tmp_path / "paper-1.pdf").exists()


def test_upload_service_extracts_text_in_deferred_stage(tmp_path, monkeypatch):
    paper_path = tmp_path / "paper-1.pdf"
    paper_path.write_bytes(b"%PDF-1.7\ncontent")
    monkeypatch.setattr(
        "app.services.paper_upload.extract_pdf_text",
        lambda path: ("论文正文", "test-parser"),
    )

    result = asyncio.run(PaperUploadService().extract_text(str(paper_path)))

    assert result.raw_text == "论文正文"
    assert result.extraction_method == "test-parser"
    assert result.elapsed_seconds >= 0


def test_core_structure_service_keeps_parser_and_outline_stages_separate(monkeypatch):
    async def fake_parser(paper_id, file_path, raw_text):
        return {
            "title": "测试论文",
            "sections": [{"title": "1 引言", "content": "足够长的章节正文内容用于测试服务边界。"}],
        }

    monkeypatch.setattr(
        "app.services.paper_core_processing.run_paper_parser",
        fake_parser,
    )
    monkeypatch.setattr(
        "app.services.paper_core_processing.extract_pdf_page_contents",
        lambda path: ["1 引言\n足够长的章节正文内容用于测试服务边界。"],
    )
    monkeypatch.setattr(
        "app.services.paper_core_processing.enrich_sections_with_pdf",
        lambda sections, path, pages: [{**sections[0], "start_page": 1}],
    )

    result = asyncio.run(PaperCoreProcessingService().extract_structure(
        paper_id="paper-1",
        file_path="/tmp/paper.pdf",
        raw_text="1 引言\n足够长的章节正文内容用于测试服务边界。",
    ))

    assert result.metadata["title"] == "测试论文"
    assert result.sections[0]["start_page"] == 1
    assert len(result.page_contents) == 1
