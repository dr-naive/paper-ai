import asyncio
import hashlib
from io import BytesIO

from app.services.paper_core_processing import PaperCoreProcessingService, PaperStructureResult
from app.services.paper_files import sanitize_text
from app.services.paper_upload import PaperUploadService
from app.models.paper import DocumentElement, Paper


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
    assert set(result.timings) == {"file_save", "file_hash"}
    assert result.file_sha256 == hashlib.sha256(b"%PDF-1.7\ncontent").hexdigest()
    assert (tmp_path / "paper-1.pdf").exists()


def test_upload_service_extracts_text_in_deferred_stage(tmp_path, monkeypatch):
    paper_path = tmp_path / "paper-1.pdf"
    paper_path.write_bytes(b"%PDF-1.7\ncontent")
    monkeypatch.setattr(
        "app.services.paper_upload.extract_pdf_text",
        lambda path: ("论文\x00正文", "test-parser"),
    )

    result = asyncio.run(PaperUploadService().extract_text(str(paper_path)))

    assert result.raw_text == "论文正文"
    assert result.extraction_method == "test-parser"
    assert result.elapsed_seconds >= 0


def test_sanitize_text_removes_postgresql_unsupported_nul_bytes():
    assert sanitize_text("前文\x00后文") == "前文后文"
    assert sanitize_text(None) == ""


def test_core_structure_service_keeps_parser_and_outline_stages_separate(monkeypatch):
    async def fake_parser(paper_id, file_path, raw_text):
        assert "\x00" not in raw_text
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
    monkeypatch.setattr(
        "app.services.paper_core_processing.extract_layout_elements",
        lambda path: [{
            "id": "element-1",
            "element_type": "paragraph",
            "page_number": 1,
            "order_index": 0,
            "page_order": 0,
            "text": "足够长的章节正文内容用于测试服务边界。",
            "bbox": [10, 10, 200, 40],
            "section_path": ["1 引言"],
            "confidence": 0.9,
            "extraction_method": "test",
            "is_indexable": True,
            "attributes": {},
        }],
    )

    result = asyncio.run(PaperCoreProcessingService().extract_structure(
        paper_id="paper-1",
        file_path="/tmp/paper.pdf",
        raw_text="1 引言\x00\n足够长的章节正文内容用于测试服务边界。",
    ))

    assert result.metadata["title"] == "测试论文"
    assert result.sections[0]["start_page"] == 1
    assert len(result.page_contents) == 1
    assert result.elements[0]["element_type"] == "paragraph"


def test_core_persistence_sanitizes_text_and_preserves_project_scope(monkeypatch):
    added = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def add(self, item):
            added.append(item)

        async def flush(self):
            return None

        async def commit(self):
            return None

    class FakeExtractor:
        def __init__(self, pdf_path):
            self.pdf_path = pdf_path

        def extract_tables_from_text(self, content, title):
            return []

        def extract_figures_from_text(self, content, title):
            return []

        def extract_formulas(self, content, title):
            return []

    monkeypatch.setattr(
        "app.services.paper_core_processing.AsyncSessionLocal",
        lambda: FakeSession(),
    )
    monkeypatch.setattr(
        "app.services.paper_core_processing.MultimediaExtractor",
        FakeExtractor,
    )

    structure = PaperStructureResult(
        metadata={"title": "标题\x00", "authors": "作者\x00", "abstract": "摘要\x00", "keywords": ["词\x00"]},
        sections=[{"title": "引言\x00", "content": "正文\x00", "key_points": ["要点\x00"]}],
        page_contents=[],
        elements=[{
            "id": "element-1",
            "element_type": "paragraph",
            "page_number": 1,
            "order_index": 0,
            "page_order": 0,
            "text": "元素\x00",
            "section_path": ["引言\x00"],
            "is_indexable": True,
        }],
    )

    asyncio.run(PaperCoreProcessingService().persist_core(
        paper_id="paper-1",
        user_id="user-1",
        file_path="/tmp/paper.pdf",
        raw_text="全文\x00",
        structure=structure,
        is_project_only=True,
    ))

    paper = next(item for item in added if isinstance(item, Paper))
    element = next(item for item in added if isinstance(item, DocumentElement))
    assert paper.full_text == "全文"
    assert paper.title == "标题"
    assert paper.is_project_only is True
    assert "\x00" not in element.text
