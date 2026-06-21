import json
from types import SimpleNamespace

from evals.models import EvalCase
from evals.run_e2e_eval import load_or_create_report, save_report, select_cases


def _case(case_id: str, split: str, status: str) -> EvalCase:
    return EvalCase.from_dict({
        "id": case_id,
        "paper_id": "paper",
        "paper_title": "Paper",
        "question": "Question?",
        "task_type": "fact",
        "difficulty": "easy",
        "split": split,
        "answerable": True,
        "must_abstain": False,
        "reference_answer": "Answer",
        "reference_claims": ["Claim"],
        "evidence": [{"source_type": "text", "quote": "A sufficiently long evidence quotation."}],
        "annotation_status": status,
    })


def test_select_cases_uses_only_verified_split_and_limit():
    cases = [
        _case("verified", "test", "verified"),
        _case("silver", "test", "silver"),
        _case("dev", "dev", "verified"),
    ]
    assert [case.id for case in select_cases(cases, "test")] == ["verified"]
    assert select_cases(cases, "test", limit=1)[0].id == "verified"


def test_report_is_checkpointed_and_resumed(tmp_path):
    output = tmp_path / "raw.json"
    dataset = tmp_path / "dataset.jsonl"
    args = SimpleNamespace(split="test", top_k=5, resume=False)
    report = load_or_create_report(output, args, dataset)
    report["cases"].append({
        "case": {"id": "q1"},
        "status": "completed",
        "latency_ms": 100,
    })
    save_report(report, output)

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["summary"]["completed_count"] == 1
    assert saved["summary"]["p50_latency_ms"] == 100

    args.resume = True
    resumed = load_or_create_report(output, args, dataset)
    assert resumed["cases"][0]["case"]["id"] == "q1"


def test_report_p95_includes_tail_latency(tmp_path):
    output = tmp_path / "raw.json"
    report = {"cases": [
        {"case": {"id": str(index)}, "status": "completed", "latency_ms": latency}
        for index, latency in enumerate([100] * 11 + [1000])
    ]}
    save_report(report, output)
    assert report["summary"]["p95_latency_ms"] == 505.0
