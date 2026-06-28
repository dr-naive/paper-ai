from types import SimpleNamespace

from app.rag.table_retrieval import (
    extract_table_numbers,
    merge_retrieval_chunks,
    table_to_chunk,
)
from app.agent.qa_agent.enhanced_graph import (
    _enrich_citations,
    calculate_evidence_confidence,
    detect_metadata_intent,
    needs_deep_thinking,
)


def test_extract_table_numbers_supports_common_references():
    assert extract_table_numbers("表1里有什么数据？") == [1]
    assert extract_table_numbers("比较 Table 2 和表3") == [2, 3]
    assert extract_table_numbers("第一张表和表十分别说明什么") == [1, 10]


def test_table_title_question_is_not_misclassified_as_paper_metadata():
    assert detect_metadata_intent("表1的标题是什么？") is None


def test_table_to_chunk_preserves_raw_table_data():
    table = SimpleNamespace(
        table_number=1,
        caption="模型性能对比",
        page_number=7,
        markdown_content="| 模型 | 准确率 |\n| A | 92% |",
        csv_content="",
        raw_content=[],
        analysis_result={"data_summary": "A 的准确率为 92%。"},
    )

    chunk = table_to_chunk(table)

    assert chunk["chunk_type"] == "table"
    assert chunk["table_number"] == 1
    assert "| A | 92% |" in chunk["content"]
    assert chunk["retrieval_method"] == "exact_table_number"


def test_merge_keeps_exact_table_first_and_deduplicates_semantic_copy():
    exact = [{"chunk_type": "table", "table_number": 1, "content": "exact"}]
    semantic = [
        {"chunk_type": "table", "table_number": "1", "content": "semantic"},
        {"chunk_type": "small", "chunk_index": 2, "content": "text"},
    ]

    merged = merge_retrieval_chunks(exact, semantic, top_k=5)

    assert [chunk["content"] for chunk in merged] == ["exact", "text"]


def test_citation_enrichment_adds_table_page_and_exact_search_text():
    chunks = [{
        "section": "表1：性能比较",
        "content": "【表1】性能比较\n表格数据：FakeShield 的 ACC 为 0.95。",
        "chunk_type": "table",
        "table_number": 1,
        "page": 7,
        "chunk_index": "table-1",
    }]
    citations = [{
        "source_id": "S1",
        "section": "表1：性能比较",
        "text": "表格显示该方法取得了较高性能。",
    }]

    enriched = _enrich_citations(citations, chunks)

    assert enriched[0]["page"] == 7
    assert enriched[0]["position"] == "PDF 第7页"
    assert enriched[0]["table_number"] == 1
    assert "FakeShield" in enriched[0]["search_text"]


def test_evidence_confidence_is_not_intent_confidence():
    chunks = [{"content": "实验结果显示 FakeShield 的准确率为百分之九十五。"}]
    grounded = [{"source_id": "S1", "text": "FakeShield 的准确率为百分之九十五"}]

    assert calculate_evidence_confidence("答案", grounded, chunks) == 0.85
    assert calculate_evidence_confidence("答案", [], chunks) == 0.0
    assert calculate_evidence_confidence("作者是张三", [{"section": "论文元数据"}], [], "metadata") == 0.95


def test_mechanism_question_does_not_force_deep_thinking():
    question = "H-PSRO 框架旨在解决什么核心问题，并通过什么机制实现？"
    assert needs_deep_thinking(question) is False


def test_proof_and_formula_questions_use_deep_thinking():
    assert needs_deep_thinking("请推导公式 3 为什么成立") is True
    assert needs_deep_thinking("prove why this mechanism guarantees convergence") is True
