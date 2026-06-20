from app.agent.paper_parser.graph import (
    _extract_metadata_by_rules,
    _parse_sections_by_rules,
    _select_title,
)


FAKESHIELD_FRONT_PAGE = """Published as a conference paper at ICLR 2025
fakshield:可解释的图像伪造检测 定位，
和 通过
多模态大语言模型
徐志培1,2，张轩宇1，李润毅1，唐泽成1，黄清4，张健1,2,3†
1北京大学电子与计算机工程学院
摘要
生成式AI的快速发展是一把双刃剑，它不仅为内容创作提供了便利，也使图像
处理变得更容易，更难以被发现。
"""


def test_rule_title_stops_before_authors_and_abstract():
    metadata = _extract_metadata_by_rules(FAKESHIELD_FRONT_PAGE)

    assert metadata["title"] == "fakshield:可解释的图像伪造检测 定位， 和 通过 多模态大语言模型"
    assert "生成式AI" not in metadata["title"]
    assert "徐志培" not in metadata["title"]


def test_corrupted_model_title_falls_back_to_front_page_title():
    bad_title = (
        "fakshield:可解释的图像伪造检测 定位 多模态大语言模型 "
        + "生成式AI的快速发展是一把双刃剑，它不仅为内容创作提供了便利。" * 8
    )

    title = _select_title(bad_title, FAKESHIELD_FRONT_PAGE)

    assert title == "fakshield:可解释的图像伪造检测 定位， 和 通过 多模态大语言模型"
    assert len(title) < 200


def test_valid_model_title_is_preserved():
    assert _select_title("A Reliable Paper Title", FAKESHIELD_FRONT_PAGE) == "A Reliable Paper Title"


def test_english_rule_title_stops_before_authors():
    text = """A Reliable Method for Document Understanding
Alice Smith, Bob Jones
Department of Computer Science, Example University
Abstract
This paper presents a reliable method.
"""

    metadata = _extract_metadata_by_rules(text)

    assert metadata["title"] == "A Reliable Method for Document Understanding"


def test_rule_parser_does_not_truncate_sections_after_ten():
    text = "\n".join(
        f"{index} 章节标题{index}\n这是第{index}章的正文内容，包含足够的信息用于章节解析。"
        for index in range(1, 13)
    )

    sections = _parse_sections_by_rules(text)

    assert len(sections) == 12
    assert sections[-1]["title"] == "12 章节标题12"
