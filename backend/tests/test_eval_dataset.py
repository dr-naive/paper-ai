from evals.models import EvalCase, validate_case, validate_dataset


def _valid_case(**overrides):
    data = {
        "id": "paper01_q001",
        "paper_id": "paper-1",
        "paper_title": "Example Paper",
        "question": "消融实验有什么结论？",
        "task_type": "experiment",
        "difficulty": "medium",
        "split": "dev",
        "answerable": True,
        "must_abstain": False,
        "reference_answer": "移除模块后性能下降。",
        "reference_claims": ["移除模块后性能下降"],
        "evidence": [{
            "source_type": "text",
            "page": 7,
            "section": "Ablation",
            "quote": "After removing the module, accuracy decreased from 95 to 90 percent.",
        }],
        "annotation_status": "verified",
    }
    data.update(overrides)
    return EvalCase.from_dict(data)


def test_valid_case_has_no_validation_errors():
    assert validate_case(_valid_case()) == []


def test_silver_case_is_a_valid_annotation_stage():
    assert validate_case(_valid_case(annotation_status="silver")) == []


def test_answerable_case_requires_evidence_and_claims():
    errors = validate_case(_valid_case(evidence=[], reference_claims=[]))
    assert any("reference_claims" in error for error in errors)
    assert any("evidence" in error for error in errors)


def test_dataset_rejects_duplicate_ids():
    case = _valid_case()
    errors = validate_dataset([case, case])
    assert any("重复" in error for error in errors)
