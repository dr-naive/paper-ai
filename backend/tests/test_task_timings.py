import fitz

from app.api.papers import _build_timing_details, _extract_pdf_text


def test_timing_details_include_seconds_percentages_and_other_time():
    details = _build_timing_details(
        {"text_extraction": 2.0, "image_analysis": 5.0},
        total_seconds=10.0,
        counts={"image_candidates": 3},
    )

    assert details["timings_seconds"] == {
        "text_extraction": 2.0,
        "image_analysis": 5.0,
        "other": 3.0,
        "total": 10.0,
    }
    assert details["timing_percentages"]["image_analysis"] == 50.0
    assert details["counts"]["image_candidates"] == 3


def test_extract_pdf_text_uses_pymupdf_primary_path(tmp_path):
    pdf_path = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Reliable document text")
    doc.save(pdf_path)
    doc.close()

    text, method = _extract_pdf_text(str(pdf_path))

    assert method == "pymupdf"
    assert "Reliable document text" in text
