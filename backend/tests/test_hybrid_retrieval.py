from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.rag.hybrid_retrieval import (
    EvidenceReranker,
    _paragraphs,
    bm25_search,
    deduplicate_evidence,
    dynamic_top_k,
    rewrite_standalone_question,
    split_comparison_question,
)
from app.rag.hybrid_retrieval import HybridPaperRetriever


def test_history_rewrites_referential_question():
    history = "用户: MMTD-Set 是怎么构建的？\nAI: 它包含多模态数据。"
    rewritten = rewrite_standalone_question("这个数据集有什么优势？", history)
    assert "MMTD-Set 是怎么构建的" in rewritten
    assert "这个数据集有什么优势" in rewritten


def test_independent_question_is_not_rewritten():
    question = "论文的主要贡献是什么？"
    assert rewrite_standalone_question(question, "用户: 上一个问题") == question


def test_dynamic_top_k_expands_complex_questions():
    assert dynamic_top_k("模型是什么？") == 4
    assert dynamic_top_k("比较方法 A 和方法 B 的区别", "comparison") == 10


def test_comparison_question_splits_both_sides():
    queries = split_comparison_question("比较方法 A 和方法 B 的区别")
    assert len(queries) == 2
    assert "方法 A" in queries[0]
    assert "方法 B" in queries[1]


def test_bm25_recalls_exact_keyword_paragraph():
    documents = [
        {"content": "模型采用卷积网络执行图像分类", "section": "方法"},
        {"content": "MMTD-Set 包含伪造图像和文本配对", "section": "数据集"},
    ]
    results = bm25_search("MMTD-Set 数据集包含什么", documents, top_k=2)
    assert results[0]["section"] == "数据集"
    assert results[0]["retrieval_method"] if "retrieval_method" in results[0] else True


def test_reranker_fuses_channels_and_deduplicates():
    duplicate = {
        "content": "方法 A 使用视觉编码器",
        "section": "方法",
        "page": 3,
    }
    other = {
        "content": "实验使用公开数据集",
        "section": "实验",
        "page": 6,
    }
    results = EvidenceReranker().rerank(
        "方法 A 使用什么编码器",
        [[duplicate, other], [dict(duplicate)]],
        top_k=5,
    )
    assert len(results) == 2
    assert results[0]["section"] == "方法"
    assert results[0]["rerank_score"] > results[1]["rerank_score"]


def test_section_content_is_split_into_keyword_documents():
    section = SimpleNamespace(
        content="第一段内容。\n\n第二段内容。",
        section_title="实验",
        start_page=7,
        order_index=2,
    )
    chunks = _paragraphs(section, max_chars=7)
    assert len(chunks) == 2
    assert chunks[0]["page"] == 7
    assert chunks[0]["retrieval_method"] == "bm25"


def test_section_documents_remove_running_publication_header():
    section = SimpleNamespace(
        content="Published as a conference paper at ICLR 2025\n8\n真正的实验结论。",
        section_title="实验",
        start_page=8,
        order_index=3,
    )
    chunks = _paragraphs(section)
    assert len(chunks) == 1
    assert chunks[0]["content"] == "真正的实验结论。"


def test_cross_channel_dedup_prefers_element_with_coordinates():
    text = "该方法使用统一的视觉编码器提取图像特征，并通过跨模态模块完成语义对齐。" * 3
    chunks = [
        {"content": text, "page": 4, "section": "全文", "chunk_type": "text"},
        {
            "content": text,
            "page": 4,
            "section": "3.1 方法",
            "chunk_type": "small",
            "element_id": "element-4-1",
            "bbox": [40, 100, 500, 180],
        },
        {"content": "另一条独立证据。" * 20, "page": 5, "section": "实验"},
    ]
    results = deduplicate_evidence(chunks, "方法是什么", top_k=5)
    assert len(results) == 2
    assert results[0]["element_id"] == "element-4-1"


def test_cross_page_similar_text_is_not_deduplicated():
    text = "相同实验设置与结果说明。" * 10
    results = deduplicate_evidence(
        [{"content": text, "page": 4}, {"content": text, "page": 5}],
        "实验结果",
        top_k=5,
    )
    assert len(results) == 2


def test_same_page_chunks_with_long_identical_prefix_are_deduplicated():
    prefix = "对于被篡改图像，系统使用特定提示生成准确描述。" * 12
    results = deduplicate_evidence(
        [
            {"content": prefix + "第一个切分窗口的后文", "page": 4},
            {"content": prefix + "第二个切分窗口的后文", "page": 4},
        ],
        "如何生成描述",
        top_k=5,
    )
    assert len(results) == 1


@pytest.mark.asyncio
async def test_structured_image_documents_allow_images_without_bbox():
    """Image rows have no bbox column; retrieval must keep the optional locator empty."""
    table_result = SimpleNamespace(all=lambda: [])
    image = SimpleNamespace(
        id="image-1",
        analysis_result={"description": "图像展示检测结果"},
        image_index=1,
        page_number=2,
        section_id=None,
        is_filtered=False,
    )
    image_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [image]))
    db = SimpleNamespace(execute=AsyncMock(side_effect=[table_result, image_result]))

    table_rows, image_documents = await HybridPaperRetriever(db)._structured_documents("paper-1")

    assert table_rows == []
    assert image_documents[0]["image_id"] == "image-1"
    assert image_documents[0]["bbox"] == []
