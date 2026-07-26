from app.services.paper_outline import (
    OutlineCandidate,
    _heading_level,
    _looks_like_heading,
    merge_outline_candidates,
    _outline_sort_key,
)


def test_heading_rules_cover_references_and_appendices():
    assert _looks_like_heading("参考文献")
    assert _looks_like_heading("A 附录")
    assert _looks_like_heading("A.3 更多消融实验")
    assert not _looks_like_heading("2. 头发的方向和流动缺乏一致性")
    assert _heading_level("A 附录") == 1
    assert _heading_level("A.3 更多消融实验") == 2


def test_outline_merge_preserves_page_order_and_removes_duplicates():
    bookmark = [OutlineCandidate("1 介绍", 2, source="bookmark", confidence=1.0)]
    layout = [
        OutlineCandidate("1 介绍", 2),
        OutlineCandidate("参考文献", 11),
        OutlineCandidate("A 附录", 16),
    ]

    merged = merge_outline_candidates(bookmark, layout)

    assert [(item.title, item.start_page) for item in merged] == [
        ("1 介绍", 2),
        ("参考文献", 11),
        ("A 附录", 16),
    ]
    assert merged[0].source == "bookmark"


def test_same_page_sections_use_natural_number_order():
    sections = [
        {"title": "5 结语", "start_page": 10},
        {"title": "4.6 消融研究", "start_page": 10},
    ]

    assert [item["title"] for item in sorted(sections, key=_outline_sort_key)] == [
        "4.6 消融研究",
        "5 结语",
    ]
