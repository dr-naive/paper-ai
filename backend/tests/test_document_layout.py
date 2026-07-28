from app.services.document_layout import build_element_chunks, extract_layout_elements


class StubChunker:
    def chunk_text(self, text, section):
        return [{
            "content": text,
            "section": section,
            "index": 0,
            "parent_index": None,
            "chunk_type": "small",
        }]


def test_layout_extraction_filters_repeated_headers_and_keeps_provenance(tmp_path):
    import fitz

    pdf_path = tmp_path / "layout.pdf"
    document = fitz.open()
    for page_number in range(1, 4):
        page = document.new_page(width=595, height=842)
        page.insert_text((50, 35), "Published at Test Conference 2026", fontsize=9)
        page.insert_text((50, 100), f"{page_number}.1 Method Design", fontsize=16)
        page.insert_text(
            (50, 140),
            f"这是第{page_number}页的正文段落，包含足够信息用于版面结构测试。",
            fontsize=11,
        )
        page.insert_text((292, 820), str(page_number), fontsize=9)
    document.save(pdf_path)
    document.close()

    elements = extract_layout_elements(str(pdf_path))

    headers = [item for item in elements if item["element_type"] == "header"]
    titles = [item for item in elements if item["element_type"] == "title"]
    paragraphs = [item for item in elements if item["element_type"] == "paragraph"]
    assert len(headers) == 3
    assert all(not item["is_indexable"] for item in headers)
    assert len(titles) == 3
    assert len(paragraphs) == 3
    assert paragraphs[0]["section_path"] == ["1.1 Method Design"]
    assert len(paragraphs[0]["bbox"]) == 4


def test_element_chunks_exclude_noise_and_keep_element_coordinates():
    elements = [
        {
            "id": "header-1",
            "element_type": "header",
            "page_number": 1,
            "text": "Conference header",
            "bbox": [0, 0, 100, 20],
            "section_path": [],
            "confidence": 0.99,
            "is_indexable": False,
        },
        {
            "id": "paragraph-1",
            "element_type": "paragraph",
            "page_number": 2,
            "text": "正文证据",
            "bbox": [40, 120, 300, 150],
            "section_path": ["2 方法", "2.1 模型"],
            "confidence": 0.91,
            "is_indexable": True,
        },
    ]

    chunks = build_element_chunks(elements, StubChunker())

    assert len(chunks) == 1
    assert chunks[0]["content"] == "正文证据"
    assert chunks[0]["element_id"] == "paragraph-1"
    assert chunks[0]["bbox"] == [40, 120, 300, 150]
    assert chunks[0]["section"] == "2.1 模型"


def test_layout_extraction_reorders_two_columns_left_then_right(tmp_path):
    import fitz

    pdf_path = tmp_path / "columns.pdf"
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_text((330, 120), "RIGHT FIRST", fontsize=11)
    page.insert_text((330, 160), "RIGHT SECOND", fontsize=11)
    page.insert_text((40, 120), "LEFT FIRST", fontsize=11)
    page.insert_text((40, 160), "LEFT SECOND", fontsize=11)
    document.save(pdf_path)
    document.close()

    elements = [
        item for item in extract_layout_elements(str(pdf_path))
        if item["element_type"] == "paragraph"
    ]

    assert [item["text"] for item in elements] == [
        "LEFT FIRST",
        "LEFT SECOND",
        "RIGHT FIRST",
        "RIGHT SECOND",
    ]


def test_element_chunks_strip_repeated_lines_embedded_in_body_blocks():
    elements = [{
        "id": str(page),
        "element_type": "paragraph",
        "page_number": page,
        "text": f"正文内容第{page}页\n{page}\nPublished as a conference paper at ICLR 2025",
        "bbox": [0, 100, 500, 700],
        "section_path": ["实验"],
        "confidence": 0.9,
        "is_indexable": True,
    } for page in range(1, 5)]

    chunks = build_element_chunks(elements, StubChunker())

    assert len(chunks) == 4
    assert all("Published as" not in chunk["content"] for chunk in chunks)
