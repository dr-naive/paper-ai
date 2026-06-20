import asyncio
import io
from collections import defaultdict

import fitz
from PIL import Image

from app.parsers.multimedia_extractor import MultimediaExtractor


def _full_page_png() -> bytes:
    image = Image.new("RGB", (600, 800), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_raster_page_with_caption_extracts_figure_region(tmp_path):
    pdf_path = tmp_path / "captioned.pdf"
    output_dir = tmp_path / "images"
    output_dir.mkdir()

    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=_full_page_png())
    page.insert_text((100, 650), "Figure 1: Example architecture.")
    doc.save(pdf_path)
    doc.close()

    images = asyncio.run(
        MultimediaExtractor(str(pdf_path)).extract_images_from_pdf(output_dir=str(output_dir))
    )

    assert len(images) == 1
    assert images[0]["extraction_method"] == "caption_region_cropping"
    assert images[0]["caption"].startswith("Figure 1")


def test_raster_page_without_text_keeps_full_page_fallback(tmp_path):
    pdf_path = tmp_path / "scan.pdf"
    output_dir = tmp_path / "images"
    output_dir.mkdir()

    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=_full_page_png())
    doc.save(pdf_path)
    doc.close()

    images = asyncio.run(
        MultimediaExtractor(str(pdf_path)).extract_images_from_pdf(output_dir=str(output_dir))
    )

    assert len(images) == 1
    assert images[0]["extraction_method"] == "full_page_scan_fallback"


def test_raster_document_without_vector_lines_skips_pdfplumber_path(tmp_path):
    pdf_path = tmp_path / "raster.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=_full_page_png())
    doc.save(pdf_path)
    doc.close()

    assert MultimediaExtractor._is_raster_document_without_vector_tables(str(pdf_path)) is True


def test_table_analysis_is_bounded_and_retries_transient_failure(monkeypatch):
    class FakeAnalyzer:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.calls = defaultdict(int)

        async def analyze_table_image(self, image_path):
            self.calls[image_path] += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            if image_path == "b.jpg" and self.calls[image_path] == 1:
                return {"success": False, "is_table": False, "error": "rate limited"}
            return {
                "success": True,
                "is_table": True,
                "table_title": image_path,
                "markdown_content": "| A |\n|---|\n| 1 |",
            }

    analyzer = FakeAnalyzer()
    monkeypatch.setattr(
        "app.parsers.image_analyzer.get_image_analyzer",
        lambda: analyzer,
    )
    candidates = [
        {"page": index, "image_index": index, "image_path": path}
        for index, path in enumerate(("a.jpg", "b.jpg", "c.jpg", "d.jpg"), 1)
    ]

    results = asyncio.run(MultimediaExtractor().analyze_table_images(candidates))

    assert [result["table_title"] for result in results] == [
        "a.jpg",
        "b.jpg",
        "c.jpg",
        "d.jpg",
    ]
    assert analyzer.max_active == 3
    assert analyzer.calls["b.jpg"] == 2
