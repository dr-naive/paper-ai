from evals.score_e2e_eval import score_report


def test_score_report_excludes_generation_timeout_from_quality_metrics():
    raw = {
        "dataset": "dataset.jsonl",
        "summary": {"p50_latency_ms": 100, "p95_latency_ms": 100},
        "cases": [
            {
                "case": {
                    "id": "ok",
                    "reference_claims": ["准确率达到百分之九十五"],
                    "evidence": [{
                        "source_type": "text",
                        "page": 2,
                        "quote": "该方法在测试集上的准确率达到百分之九十五",
                    }],
                },
                "status": "completed",
                "answer": "该方法在测试集上的准确率达到百分之九十五。",
                "citations": [{
                    "source_id": "S1",
                    "page": 2,
                    "text": "该方法在测试集上的准确率达到百分之九十五",
                }],
                "retrieved": [{
                    "page": 2,
                    "content": "该方法在测试集上的准确率达到百分之九十五",
                }],
                "latency_ms": 100,
            },
            {
                "case": {"id": "timeout", "reference_claims": [], "evidence": []},
                "status": "generation_timeout",
                "answer": "抱歉，无法生成回答，请尝试重新提问。",
                "citations": [],
                "retrieved": [],
                "latency_ms": 65000,
            },
        ],
    }

    report = score_report(raw)
    summary = report["summary"]
    assert summary["case_count"] == 1
    assert summary["raw_case_count"] == 2
    assert summary["valid_answer_count"] == 1
    assert summary["generation_timeout_count"] == 1
    assert summary["valid_answer_rate"] == 0.5
    assert summary["timeout_rate"] == 0.5
    assert len(report["cases"]) == 1
