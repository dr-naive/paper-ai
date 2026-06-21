from dataclasses import replace

from evals.metrics.retrieval import (
    aggregate_retrieval_metrics,
    evidence_matches_chunk,
    score_retrieval_case,
)
from evals.models import EvalCase
from evals.run_retrieval_eval import _retrieval_cases


def _case():
    return EvalCase.from_dict({
        "id": "paper01_q001",
        "paper_id": "paper-1",
        "paper_title": "Example Paper",
        "question": "表 6 的消融结果是什么？",
        "task_type": "table",
        "difficulty": "medium",
        "split": "dev",
        "answerable": True,
        "must_abstain": False,
        "reference_answer": "移除 DTG 后准确率下降。",
        "reference_claims": ["移除 DTG 后准确率下降"],
        "evidence": [{
            "source_type": "table",
            "page": 10,
            "section": "表6 消融实验",
            "table_number": 6,
            "quote": "表6显示移除DTG后，IMD2020数据集上的检测准确率明显下降。",
        }],
        "expected_tables": [6],
        "annotation_status": "verified",
    })


def test_table_number_is_a_deterministic_evidence_match():
    evidence = _case().evidence[0]
    assert evidence_matches_chunk(evidence, {"table_number": "6", "content": "表格内容"})


def test_retrieval_metrics_score_rank_and_recall():
    chunks = [
        {"content": "无关内容", "section": "引言"},
        {
            "content": "表6显示移除DTG后，IMD2020数据集上的检测准确率明显下降。",
            "section": "表6 消融实验",
            "page": 10,
            "table_number": 6,
        },
    ]
    metrics = score_retrieval_case(_case(), chunks, top_k=5)
    assert metrics.hit_at_k == 1.0
    assert metrics.evidence_recall_at_k == 1.0
    assert metrics.reciprocal_rank == 0.5
    assert metrics.precision_at_k == 0.2
    assert metrics.table_hit_at_k == 1.0
    assert aggregate_retrieval_metrics([metrics])["hit_at_k"] == 1.0


def test_retrieval_selection_keeps_silver_out_of_verified_baseline():
    silver = replace(_case(), annotation_status="silver")
    assert _retrieval_cases([silver], "dev", include_silver=False, include_drafts=False) == []
    assert _retrieval_cases([silver], "dev", include_silver=True, include_drafts=False) == [silver]
