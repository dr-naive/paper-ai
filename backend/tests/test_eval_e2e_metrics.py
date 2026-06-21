from evals.metrics.e2e import aggregate_e2e_metrics, score_e2e_case


def test_e2e_citation_grounding_evidence_and_page_metrics():
    quote = "该方法在测试集上的准确率达到百分之九十五并显著优于基线方法"
    row = {
        "case": {
            "id": "q1",
            "reference_claims": ["准确率达到百分之九十五"],
            "evidence": [{"source_type": "text", "page": 2, "quote": quote}],
        },
        "answer": "实验显示准确率达到百分之九十五。",
        "citations": [{"source_id": "S1", "page": 2, "text": quote}],
        "retrieved": [{"page": 2, "content": quote}],
    }
    metrics = score_e2e_case(row)
    assert metrics.citation_precision == 1
    assert metrics.citation_recall == 1
    assert metrics.page_accuracy == 1
    assert metrics.claim_coverage_proxy == 1
    assert aggregate_e2e_metrics([metrics])["grounded_citations"] == 1


def test_invalid_source_is_not_grounded():
    metrics = score_e2e_case({
        "case": {"id": "q2", "reference_claims": [], "evidence": []},
        "answer": "",
        "citations": [{"source_id": "S9", "page": 2, "text": "不存在的引用内容"}],
        "retrieved": [],
    })
    assert metrics.citation_precision == 0
    assert metrics.page_accuracy is None
