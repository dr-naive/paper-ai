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


def test_abstention_metrics_for_unanswerable_cases():
    metrics = score_e2e_case({
        "case": {
            "id": "q3",
            "answerable": False,
            "must_abstain": True,
            "reference_claims": [],
            "evidence": [],
        },
        "answer": "论文未报告移动端部署延迟，因此无法确定。",
        "citations": [],
        "retrieved": [],
    })
    assert metrics.abstained is True
    assert metrics.abstention_correct == 1
    assert metrics.critical_hallucination == 0


def test_unanswerable_case_with_definitive_answer_is_critical_hallucination():
    metrics = score_e2e_case({
        "case": {
            "id": "q4",
            "answerable": False,
            "must_abstain": True,
            "reference_claims": [],
            "evidence": [],
        },
        "answer": "论文报告移动端部署延迟为 12 ms。",
        "citations": [],
        "retrieved": [],
    })
    assert metrics.abstention_correct == 0
    assert metrics.unsupported_number_count == 1
    assert metrics.critical_hallucination == 1


def test_unsupported_numbers_are_counted_against_evidence_corpus():
    row = {
        "case": {
            "id": "q5",
            "answerable": True,
            "must_abstain": False,
            "reference_answer": "训练集占80%，测试集占20%。",
            "reference_claims": ["训练集占80%", "测试集占20%"],
            "evidence": [{"source_type": "text", "page": 1, "quote": "训练集占80%，测试集占20%。"}],
        },
        "answer": "训练集占80%，测试集占20%，训练了30轮。",
        "citations": [{"source_id": "S1", "page": 1, "text": "训练集占80%，测试集占20%。"}],
        "retrieved": [{"page": 1, "content": "训练集占80%，测试集占20%。"}],
    }
    metrics = score_e2e_case(row)
    assert metrics.answer_number_count == 3
    assert metrics.unsupported_number_count == 1
    assert metrics.unsupported_number_rate == 1 / 3
    assert aggregate_e2e_metrics([metrics])["critical_hallucination_rate"] == 1
