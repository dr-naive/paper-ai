from app.api.papers import (
    _build_complete_text_chunks,
    _build_text_chunks,
    _find_content_page,
    _normalize_page_text,
)


class StubChunker:
    def chunk_text(self, content, title):
        return [
            {"content": content[:20], "type": "large", "section": title, "index": 0},
            {
                "content": content[20:],
                "type": "small",
                "section": title,
                "index": 1,
                "parent_index": 0,
            },
        ]


def test_find_content_page_uses_physical_page_text():
    pages = ["第一章介绍研究背景", "第二章消融研究删除模块后的结果"]

    assert _find_content_page(pages, "消融研究删除模块后的结果", 1) == 2


def test_text_chunk_indexes_are_unique_across_sections():
    sections = [
        {"title": "第一章", "content": "第一章介绍研究背景以及研究问题的详细内容"},
        {"title": "第二章", "content": "第二章介绍消融实验以及实验结果的详细内容"},
    ]
    chunks = _build_text_chunks(sections, StubChunker(), [])

    assert [chunk["index"] for chunk in chunks] == [0, 1, 2, 3]
    assert chunks[1]["parent_index"] == 0
    assert chunks[3]["parent_index"] == 2


def test_complete_chunks_preserve_front_matter_before_first_section():
    sections = [{
        "title": "2 方法",
        "content": "方法章节从第三页开始，并包含足够的信息用于章节定位和分块。",
    }]
    page_contents = [
        "第一页摘要介绍核心研究问题以及论文的主要贡献。" * 6,
        "第二页引言讨论研究背景以及已有工作的不足之处。" * 6,
        "2 方法\n" + "方法章节从第三页开始，并包含足够的信息用于章节定位和分块。" * 6,
    ]
    page_texts = [_normalize_page_text(text) for text in page_contents]

    chunks = _build_complete_text_chunks(
        sections,
        StubChunker(),
        page_texts,
        page_contents,
    )

    fallback_pages = {
        chunk["page"]
        for chunk in chunks
        if chunk.get("coverage_source") == "front_matter_fallback"
    }
    assert fallback_pages == {1, 2, 3}
    assert len({chunk["index"] for chunk in chunks}) == len(chunks)
