from types import SimpleNamespace

from app.harness.tools.literature_research import _rank_project_chunks
from app.utils.qa_helpers import build_deterministic_citations


def _project_paper(project_id: str, role: str = "core"):
    return SimpleNamespace(project_id=project_id, role=role)


def _paper(paper_id: str, title: str):
    return SimpleNamespace(id=paper_id, title=title, authors="Test Author")


def test_project_ranking_keeps_cross_paper_provenance_and_diversity():
    groups = [
        (
            _project_paper("project-1"),
            _paper("paper-a", "Paper A"),
            [
                {"section": "实验", "page": 3, "content": "使用 Dataset-X 进行训练和评估。", "rerank_score": 0.8},
                {"section": "方法", "page": 4, "content": "Dataset-X 包含多模态样本。", "rerank_score": 0.7},
            ],
        ),
        (
            _project_paper("project-1", "related"),
            _paper("paper-b", "Paper B"),
            [
                {"section": "实验设置", "page": 6, "content": "实验采用 Dataset-Y 数据集。", "rerank_score": 0.75},
            ],
        ),
    ]

    chunks = _rank_project_chunks("这些论文使用了哪些数据集", groups, top_k=3)

    assert {chunk["paper_id"] for chunk in chunks} == {"paper-a", "paper-b"}
    assert [chunk["source_id"] for chunk in chunks] == ["S1", "S2", "S3"]
    assert all(chunk["paper_title"] in {"Paper A", "Paper B"} for chunk in chunks)


def test_project_citations_expose_paper_and_pdf_location():
    chunks = _rank_project_chunks(
        "数据集",
        [(
            _project_paper("project-1"),
            _paper("paper-a", "Paper A"),
            [{"section": "实验", "page": 7, "content": "使用 Dataset-X。", "rerank_score": 0.8}],
        )],
        top_k=2,
    )

    citations = build_deterministic_citations("结论来自 Paper A [S1]。", chunks)

    assert citations[0]["paper_id"] == "paper-a"
    assert citations[0]["paper_title"] == "Paper A"
    assert citations[0]["position"] == "PDF 第7页"
