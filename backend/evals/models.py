from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


TASK_TYPES = {
    "metadata",
    "fact",
    "method",
    "concept",
    "experiment",
    "table",
    "comparison",
    "cross_section",
    "multi_turn",
    "unanswerable",
    "adversarial",
}


DIFFICULTIES = {"easy", "medium", "hard"}
SPLITS = {"dev", "test"}
ANNOTATION_STATUSES = {"draft", "silver", "verified"}
SOURCE_TYPES = {"text", "table", "figure", "metadata"}


@dataclass(frozen=True)
class Evidence:
    source_type: str
    quote: str = ""
    page: int | None = None
    section: str = ""
    table_number: int | None = None
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        return cls(
            source_type=str(data.get("source_type", "text")),
            quote=str(data.get("quote", "")).strip(),
            page=int(data["page"]) if data.get("page") is not None else None,
            section=str(data.get("section", "")).strip(),
            table_number=(
                int(data["table_number"])
                if data.get("table_number") is not None
                else None
            ),
            note=str(data.get("note", "")).strip(),
        )


@dataclass(frozen=True)
class EvalCase:
    id: str
    paper_id: str
    paper_title: str
    question: str
    task_type: str
    difficulty: str
    split: str
    answerable: bool
    must_abstain: bool
    reference_answer: str
    reference_claims: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    expected_tables: tuple[int, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    annotation_status: str = "draft"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        return cls(
            id=str(data.get("id", "")).strip(),
            paper_id=str(data.get("paper_id", "")).strip(),
            paper_title=str(data.get("paper_title", "")).strip(),
            question=str(data.get("question", "")).strip(),
            task_type=str(data.get("task_type", "")).strip(),
            difficulty=str(data.get("difficulty", "")).strip(),
            split=str(data.get("split", "dev")).strip(),
            answerable=bool(data.get("answerable", True)),
            must_abstain=bool(data.get("must_abstain", False)),
            reference_answer=str(data.get("reference_answer", "")).strip(),
            reference_claims=tuple(
                str(item).strip()
                for item in data.get("reference_claims", [])
                if str(item).strip()
            ),
            evidence=tuple(
                Evidence.from_dict(item) for item in data.get("evidence", [])
            ),
            expected_tables=tuple(int(item) for item in data.get("expected_tables", [])),
            tags=tuple(str(item).strip() for item in data.get("tags", []) if str(item).strip()),
            annotation_status=str(data.get("annotation_status", "draft")).strip(),
        )


def validate_case(case: EvalCase) -> list[str]:
    errors: list[str] = []
    if not case.id:
        errors.append("id 不能为空")
    if not case.paper_id:
        errors.append("paper_id 不能为空")
    if not case.paper_title:
        errors.append("paper_title 不能为空")
    if not case.question:
        errors.append("question 不能为空")
    if case.task_type not in TASK_TYPES:
        errors.append(f"task_type 必须是 {sorted(TASK_TYPES)} 之一")
    if case.difficulty not in DIFFICULTIES:
        errors.append(f"difficulty 必须是 {sorted(DIFFICULTIES)} 之一")
    if case.split not in SPLITS:
        errors.append(f"split 必须是 {sorted(SPLITS)} 之一")
    if case.annotation_status not in ANNOTATION_STATUSES:
        errors.append(f"annotation_status 必须是 {sorted(ANNOTATION_STATUSES)} 之一")
    if case.answerable == case.must_abstain:
        errors.append("answerable 与 must_abstain 必须互为相反值")
    if case.answerable and not case.reference_answer:
        errors.append("可回答问题必须填写 reference_answer")
    if case.answerable and case.task_type != "metadata" and not case.reference_claims:
        errors.append("可回答的非元数据问题必须至少填写一条 reference_claims")
    if case.answerable and case.task_type != "metadata" and not case.evidence:
        errors.append("可回答的非元数据问题必须至少填写一条 evidence")
    if not case.answerable and case.evidence:
        errors.append("不可回答问题不应填写 evidence")

    for index, evidence in enumerate(case.evidence, 1):
        prefix = f"evidence[{index}]"
        if evidence.source_type not in SOURCE_TYPES:
            errors.append(f"{prefix}.source_type 必须是 {sorted(SOURCE_TYPES)} 之一")
        if evidence.source_type in {"text", "table", "figure"} and len(evidence.quote) < 20:
            errors.append(f"{prefix}.quote 至少需要 20 个字符，避免证据过于模糊")
        if evidence.page is not None and evidence.page < 1:
            errors.append(f"{prefix}.page 必须大于等于 1")
        if evidence.source_type == "table" and evidence.table_number is None:
            errors.append(f"{prefix}.table_number 不能为空")
    return errors


def load_jsonl(path: str | Path) -> list[EvalCase]:
    dataset_path = Path(path)
    cases: list[EvalCase] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{dataset_path}:{line_number} JSON 无效: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError(f"{dataset_path}:{line_number} 每行必须是 JSON 对象")
            cases.append(EvalCase.from_dict(data))
    return cases


def validate_dataset(cases: Iterable[EvalCase]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, case in enumerate(cases, 1):
        if case.id in seen_ids:
            errors.append(f"第 {index} 条: id {case.id!r} 重复")
        seen_ids.add(case.id)
        errors.extend(f"{case.id or f'第 {index} 条'}: {error}" for error in validate_case(case))
    return errors
