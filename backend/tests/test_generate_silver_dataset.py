from evals.generate_silver_dataset import to_unanswerable_eval_case
from evals.models import validate_case


def test_unanswerable_generated_case_shape_requires_abstention():
    case = to_unanswerable_eval_case(
        {
            "question": "论文是否报告了移动端部署延迟？",
            "difficulty": "medium",
            "reference_answer": "论文未报告移动端部署延迟。",
            "tags": ["deployment"],
        },
        {
            "id": "paper-1",
            "title": "Example Paper",
        },
        "p01",
        "test",
        7,
    )

    assert case.id == "p01_q007"
    assert case.task_type == "unanswerable"
    assert case.answerable is False
    assert case.must_abstain is True
    assert case.reference_claims == ()
    assert case.evidence == ()
    assert case.expected_tables == ()
    assert case.annotation_status == "draft"
    assert "abstention" in case.tags
    assert validate_case(case) == []
