import json

from evals.review_dataset import (
    discard_case,
    load_rows,
    render_markdown,
    review_candidates,
    set_case_status,
    write_rows,
)


def _row(case_id="q1", status="silver"):
    return {
        "id": case_id,
        "paper_id": "paper-1",
        "paper_title": "Example Paper",
        "question": "实验结果是什么？",
        "task_type": "experiment",
        "difficulty": "medium",
        "split": "dev",
        "answerable": True,
        "must_abstain": False,
        "reference_answer": "准确率达到95%。",
        "reference_claims": ["准确率达到95%"],
        "evidence": [{
            "source_type": "text",
            "page": 1,
            "section": "Experiment",
            "quote": "The final accuracy reached 95 percent on the test set.",
        }],
        "expected_tables": [],
        "tags": [],
        "annotation_status": status,
    }


def test_review_candidates_defaults_to_draft_and_silver():
    rows = [_row("q1", "silver"), _row("q2", "draft"), _row("q3", "verified")]
    assert [row["id"] for row in review_candidates(rows)] == ["q1", "q2"]


def test_set_case_status_validates_and_updates_note():
    rows = [_row()]
    assert set_case_status(rows, "q1", "verified", "人工核对通过") is True
    assert rows[0]["annotation_status"] == "verified"
    assert rows[0]["review_note"] == "人工核对通过"


def test_discard_case_removes_row_by_id():
    rows = [_row("q1"), _row("q2")]
    assert discard_case(rows, "q1") is True
    assert [row["id"] for row in rows] == ["q2"]
    assert discard_case(rows, "missing") is False


def test_read_write_rows_round_trip(tmp_path):
    path = tmp_path / "dataset.jsonl"
    write_rows(path, [_row()])
    assert load_rows(path)[0]["id"] == "q1"
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["id"] == "q1"


def test_render_markdown_contains_review_fields():
    markdown = render_markdown([_row()], limit=1)
    assert "## q1 [silver]" in markdown
    assert "**Question**" in markdown
    assert "Review decision" in markdown
