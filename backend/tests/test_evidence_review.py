from app.rag.evidence_review import review_evidence


def test_filters_layout_noise_and_calculates_table_maximum():
    chunks = [
        {"content": "Published as a conference paper", "element_type": "header"},
        {
            "content": "表1：方法A F1=81；方法B F1=84",
            "chunk_type": "table_row",
            "section": "实验",
            "fields": [
                {"label": "F1", "value": "81"},
                {"label": "F1", "value": "84"},
            ],
        },
    ]
    result = review_evidence("F1最高是多少", chunks, "table")
    assert len(result.chunks) == 1
    assert "最大值为84" in result.calculation


def test_comparison_flags_single_sided_evidence():
    result = review_evidence(
        "比较A与B",
        [{"content": "A方法的结果", "section": "A"}],
        "comparison",
    )
    assert "比较对象覆盖不完整" in result.issues
