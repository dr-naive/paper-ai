import json

from evals.build_dashboard import build_dashboard, percentile


def test_percentile_interpolates_values():
    assert percentile([100, 200, 300, 400], 0.5) == 250.0
    assert percentile([], 0.95) == 0.0


def test_dashboard_embeds_report_and_gold_data(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({
        "id": "q1",
        "annotation_status": "verified",
        "reference_answer": "标准答案",
        "reference_claims": ["事实"],
        "evidence": [{"page": 2, "section": "方法", "source_type": "text", "quote": "证据原文"}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    (reports / "retrieval_dev_baseline.json").write_text(json.dumps({
        "summary": {"case_count": 1, "hit_at_k": 1, "evidence_recall_at_k": 1, "precision_at_k": .2, "mrr": 1},
        "slices": {},
        "cases": [{
            "case": {"id": "q1", "question": "问题"},
            "metrics": {"hit_at_k": 1, "evidence_recall_at_k": 1, "reciprocal_rank": 1},
            "latency_ms": 120,
            "retrieved": [{"rank": 1, "page": 2, "section": "方法", "content_preview": "检索内容", "score": .1}],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    (reports / "e2e_test_scored.json").write_text(json.dumps({
        "report_type": "e2e_scored",
        "summary": {"citation_precision": 1, "citation_recall": .5, "page_accuracy": 1, "claim_coverage_proxy": .5},
        "cases": [],
    }), encoding="utf-8")
    output = reports / "dashboard.html"

    build_dashboard(reports, dataset, output)

    html = output.read_text(encoding="utf-8")
    assert "PaperAI 评测面板" in html
    assert "标准答案" in html
    assert "检索内容" in html
    assert "端到端回答与引用" in html
    assert '"citation_precision": 1' in html


def test_dashboard_embeds_existing_agent_runtime_report_without_new_navigation(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({"id": "q1", "annotation_status": "draft"}) + "\n", encoding="utf-8")
    (reports / "retrieval_dev_baseline.json").write_text(json.dumps({
        "summary": {"case_count": 0}, "slices": {}, "cases": [],
    }), encoding="utf-8")
    (reports / "agent_runtime_20260906_120000.json").write_text(json.dumps({
        "summary": {
            "task_success_rate": 0.75, "failure_rate": 0.2,
            "duplicate_rate": 0.1, "calls_per_task": 2,
            "avg_input_tokens_per_task": 10, "avg_output_tokens_per_task": 5,
            "budget": {"avg_token_utilization": 0.4},
        },
        "failures": {
            "failure_reason_distribution": {"TOOL_TIMEOUT": 2},
            "details": [{"reason": "TOOL_TIMEOUT", "execution_id": "e1", "task_id": "t1", "trace_id": "x1", "error_code": "TOOL_TIMEOUT"}],
        },
    }, ensure_ascii=False), encoding="utf-8")
    output = reports / "dashboard.html"

    build_dashboard(reports, dataset, output)

    html = output.read_text(encoding="utf-8")
    assert "Agent Runtime 运行观测" in html
    assert "当前有哪些真实/Mock 样本" in html
    assert "ResearchTask 样本阈值" in html
    assert "样本不足，仅供调试" in html
    assert "Worker" not in html
