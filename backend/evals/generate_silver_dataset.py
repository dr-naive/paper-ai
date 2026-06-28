from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import fitz

from evals.metrics.retrieval import normalize_text
from evals.models import EvalCase, validate_case


ALLOWED_GENERATED_TASKS = {
    "fact",
    "method",
    "concept",
    "experiment",
    "table",
    "comparison",
    "cross_section",
}


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("papers", []))


def load_paper(connection: sqlite3.Connection, paper_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT id, title, authors, abstract, pdf_path FROM papers WHERE id = ?",
        (paper_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"数据库中不存在论文 {paper_id}")
    sections = connection.execute(
        "SELECT section_title, start_page FROM sections WHERE paper_id = ? ORDER BY order_index",
        (paper_id,),
    ).fetchall()
    tables = connection.execute(
        "SELECT table_number, page_number, caption, markdown_content FROM tables "
        "WHERE paper_id = ? ORDER BY table_number",
        (paper_id,),
    ).fetchall()
    return {
        "id": row[0],
        "title": row[1],
        "authors": row[2] or "",
        "abstract": row[3] or "",
        "pdf_path": row[4],
        "sections": [
            {"section": section, "start_page": int(page or 1)}
            for section, page in sections
        ],
        "tables": [
            {
                "table_number": int(number) if number is not None else None,
                "page": int(page) if page is not None else None,
                "caption": caption or "",
                "content": content or "",
            }
            for number, page, caption, content in tables
        ],
    }


def extract_pages(pdf_path: Path) -> dict[int, str]:
    document = fitz.open(pdf_path)
    try:
        return {
            index + 1: document[index].get_text("text").strip()
            for index in range(document.page_count)
        }
    finally:
        document.close()


def choose_pages(pages: dict[int, str], paper: dict[str, Any], limit: int = 8) -> list[int]:
    page_count = len(pages)
    candidates = {1, page_count}
    candidates.update(
        section["start_page"]
        for section in paper["sections"]
        if 1 <= section["start_page"] <= page_count
    )
    candidates.update(
        table["page"]
        for table in paper["tables"]
        if table["page"] is not None and 1 <= table["page"] <= page_count
    )
    if page_count > 2:
        candidates.update({2, max(1, page_count // 2), max(1, page_count - 1)})

    ordered = sorted(candidates)
    if len(ordered) <= limit:
        return ordered
    # 在首尾、章节起点和表格页过多时均匀抽样，避免只保留论文前半部分。
    indices = {
        round(index * (len(ordered) - 1) / (limit - 1))
        for index in range(limit)
    }
    return [ordered[index] for index in sorted(indices)]


def section_for_page(paper: dict[str, Any], page: int) -> str:
    current = "全文"
    for section in paper["sections"]:
        if section["start_page"] <= page:
            current = section["section"]
        else:
            break
    return current


def build_context(paper: dict[str, Any], pages: dict[int, str], selected_pages: list[int]) -> str:
    parts = []
    for page in selected_pages:
        text = pages.get(page, "")[:3200]
        parts.append(
            f"[PAGE {page}] [SECTION {section_for_page(paper, page)}]\n{text}"
        )
    if paper["tables"]:
        table_parts = []
        for table in paper["tables"][:8]:
            table_parts.append(
                f"[TABLE {table['table_number']}] [PAGE {table['page']}] "
                f"{table['caption']}\n{table['content'][:1800]}"
            )
        parts.append("\n\n".join(table_parts))
    return "\n\n=====\n\n".join(parts)


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
    return json.loads(cleaned)


def find_quote_page(quote: str, pages: dict[int, str], claimed_page: int | None) -> int | None:
    normalized_quote = normalize_text(quote)
    if len(normalized_quote) < 20:
        return None
    ordered_pages = list(pages)
    if claimed_page in pages:
        ordered_pages.remove(claimed_page)
        ordered_pages.insert(0, claimed_page)
    for page in ordered_pages:
        if normalized_quote in normalize_text(pages[page]):
            return page
    return None


def to_eval_case(
    raw: dict[str, Any],
    paper: dict[str, Any],
    pages: dict[int, str],
    alias: str,
    split: str,
    index: int,
) -> EvalCase:
    evidence_rows = []
    all_quotes_verified = True
    expected_tables: list[int] = []
    for raw_evidence in raw.get("evidence", []):
        quote = str(raw_evidence.get("quote", "")).strip()
        claimed_page = raw_evidence.get("page")
        claimed_page = int(claimed_page) if claimed_page is not None else None
        verified_page = find_quote_page(quote, pages, claimed_page)
        if verified_page is None:
            all_quotes_verified = False
            verified_page = claimed_page
        table_number = raw_evidence.get("table_number")
        table_number = int(table_number) if table_number not in (None, "") else None
        if table_number is not None:
            expected_tables.append(table_number)
        evidence_rows.append({
            "source_type": "table" if table_number is not None else "text",
            "page": verified_page,
            "section": section_for_page(paper, verified_page or 1),
            "table_number": table_number,
            "quote": quote,
            "note": "自动生成并通过 PDF 原文存在性检查" if verified_page else "需要人工修订原文",
        })

    task_type = str(raw.get("task_type", "fact"))
    if task_type not in ALLOWED_GENERATED_TASKS:
        task_type = "fact"
    case = EvalCase.from_dict({
        "id": f"{alias}_q{index:03d}",
        "paper_id": paper["id"],
        "paper_title": paper["title"],
        "question": raw.get("question", ""),
        "task_type": task_type,
        "difficulty": raw.get("difficulty", "medium"),
        "split": split,
        "answerable": True,
        "must_abstain": False,
        "reference_answer": raw.get("reference_answer", ""),
        "reference_claims": raw.get("reference_claims", []),
        "evidence": evidence_rows,
        "expected_tables": sorted(set(expected_tables)),
        "tags": raw.get("tags", []),
        "annotation_status": "silver" if evidence_rows and all_quotes_verified else "draft",
    })
    return case


def to_unanswerable_eval_case(
    raw: dict[str, Any],
    paper: dict[str, Any],
    alias: str,
    split: str,
    index: int,
) -> EvalCase:
    return EvalCase.from_dict({
        "id": f"{alias}_q{index:03d}",
        "paper_id": paper["id"],
        "paper_title": paper["title"],
        "question": raw.get("question", ""),
        "task_type": "unanswerable",
        "difficulty": raw.get("difficulty", "medium"),
        "split": split,
        "answerable": False,
        "must_abstain": True,
        "reference_answer": raw.get("reference_answer", "论文未报告该信息。"),
        "reference_claims": [],
        "evidence": [],
        "expected_tables": [],
        "tags": sorted(set(["abstention", *raw.get("tags", [])])),
        # Absence is hard to prove automatically, so these require human review.
        "annotation_status": "draft",
    })


async def call_llm_json(prompt: str, timeout_seconds: int, retries: int) -> dict[str, Any]:
    from app.llm.client import get_llm_client

    response = None
    for attempt in range(1, retries + 2):
        try:
            response = await asyncio.wait_for(
                get_llm_client().agenerate(
                    [prompt],
                    json_mode=True,
                    enable_thinking=False,
                ),
                timeout=timeout_seconds,
            )
            break
        except (TimeoutError, asyncio.TimeoutError):
            if attempt > retries:
                raise RuntimeError(f"模型调用超过 {timeout_seconds} 秒，已重试 {retries} 次")
            print(f"  模型调用超时，重试 {attempt}/{retries}...", flush=True)
    if response is None:
        raise RuntimeError("模型没有返回响应")
    return parse_json_response(response.generations[0][0].text)


async def generate_for_paper(
    paper: dict[str, Any],
    pages: dict[int, str],
    count: int,
    timeout_seconds: int,
    retries: int,
) -> list[dict[str, Any]]:
    selected_pages = choose_pages(pages, paper)
    context = build_context(paper, pages, selected_pages)
    prompt = f"""
你正在为论文问答 RAG 系统建立离线评测集。请只根据给定论文内容生成 {count} 个可回答问题。

论文标题：{paper['title']}
作者：{paper['authors']}

要求：
1. 问题覆盖事实、方法、概念、实验、表格、比较或跨章节综合，避免全部是概述题。
2. reference_answer 只能陈述给定内容可以直接支持的事实。
3. reference_claims 将答案拆成独立、可判真的原子事实，数值分别拆开。
4. 每条 evidence.quote 必须从对应 PAGE 原文逐字连续复制 30～180 个字符，禁止改写或使用省略号。
5. evidence.page 使用 PAGE 后的数字。表格证据填写 table_number，否则为 null。
6. 不生成“论文未提到什么”的问题，不生成作者、标题等元数据问题。
7. 难度只能为 easy、medium、hard；task_type 只能为 fact、method、concept、experiment、table、comparison、cross_section。

返回严格 JSON：
{{
  "questions": [
    {{
      "question": "...",
      "task_type": "experiment",
      "difficulty": "medium",
      "reference_answer": "...",
      "reference_claims": ["..."],
      "evidence": [
        {{"page": 3, "quote": "逐字原文", "table_number": null}}
      ],
      "tags": ["ablation"]
    }}
  ]
}}

论文内容：
{context}
"""
    data = await call_llm_json(prompt, timeout_seconds, retries)
    return list(data.get("questions", []))[:count]


async def generate_unanswerable_for_paper(
    paper: dict[str, Any],
    pages: dict[int, str],
    count: int,
    timeout_seconds: int,
    retries: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []

    selected_pages = choose_pages(pages, paper)
    context = build_context(paper, pages, selected_pages)
    prompt = f"""
你正在为论文问答 RAG 系统建立拒答评测集。请根据给定论文内容生成 {count} 个不可回答问题。

论文标题：{paper['title']}
作者：{paper['authors']}

要求：
1. 问题必须看起来像真实用户会问的问题，并且与论文主题相关。
2. 问题的答案不能从给定论文内容中直接得到，系统正确行为应是拒答或说明论文未报告。
3. 不要生成荒谬问题，不要生成作者、标题等元数据问题。
4. 避免问“论文没有提到什么”这种显式否定题；要问具体缺失信息，例如未报告的数据集、部署延迟、消融设置、成本、超参数或外部实验。
5. reference_answer 必须明确指出论文未报告/未说明该信息。
6. reference_claims、evidence、expected_tables 必须为空数组。
7. 难度只能为 easy、medium、hard；task_type 必须为 unanswerable。

返回严格 JSON：
{{
  "questions": [
    {{
      "question": "...",
      "task_type": "unanswerable",
      "difficulty": "medium",
      "reference_answer": "论文未报告...",
      "reference_claims": [],
      "evidence": [],
      "expected_tables": [],
      "tags": ["abstention"]
    }}
  ]
}}

论文内容：
{context}
"""
    data = await call_llm_json(prompt, timeout_seconds, retries)
    return list(data.get("questions", []))[:count]


def case_to_dict(case: EvalCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "paper_id": case.paper_id,
        "paper_title": case.paper_title,
        "question": case.question,
        "task_type": case.task_type,
        "difficulty": case.difficulty,
        "split": case.split,
        "answerable": case.answerable,
        "must_abstain": case.must_abstain,
        "reference_answer": case.reference_answer,
        "reference_claims": list(case.reference_claims),
        "evidence": [
            {
                "source_type": evidence.source_type,
                "page": evidence.page,
                "section": evidence.section,
                "table_number": evidence.table_number,
                "quote": evidence.quote,
                "note": evidence.note,
            }
            for evidence in case.evidence
        ],
        "expected_tables": list(case.expected_tables),
        "tags": list(case.tags),
        "annotation_status": case.annotation_status,
    }


async def run(args) -> list[EvalCase]:
    manifest = load_manifest(Path(args.manifest))
    connection = sqlite3.connect(f"file:{Path(args.database).resolve()}?mode=ro", uri=True)
    cases: list[EvalCase] = []
    try:
        for paper_entry in manifest:
            paper = load_paper(connection, paper_entry["paper_id"])
            pdf_path = Path(paper["pdf_path"])
            if not pdf_path.is_absolute():
                pdf_path = Path.cwd() / pdf_path
            pages = extract_pages(pdf_path)
            print(f"生成 {paper_entry['alias']}：{paper['title']}（{len(pages)} 页）")
            raw_questions = await generate_for_paper(
                paper,
                pages,
                args.questions_per_paper,
                args.timeout_seconds,
                args.retries,
            )
            raw_unanswerable = await generate_unanswerable_for_paper(
                paper,
                pages,
                args.unanswerable_per_paper,
                args.timeout_seconds,
                args.retries,
            )
            for index, raw in enumerate(raw_questions, 1):
                case = to_eval_case(
                    raw,
                    paper,
                    pages,
                    paper_entry["alias"],
                    paper_entry["split"],
                    index,
                )
                errors = validate_case(case)
                if errors:
                    print(f"  跳过 {case.id}：{'；'.join(errors)}")
                    continue
                cases.append(case)
            for offset, raw in enumerate(raw_unanswerable, len(raw_questions) + 1):
                case = to_unanswerable_eval_case(
                    raw,
                    paper,
                    paper_entry["alias"],
                    paper_entry["split"],
                    offset,
                )
                errors = validate_case(case)
                if errors:
                    print(f"  跳过 {case.id}：{'；'.join(errors)}")
                    continue
                cases.append(case)
            silver = sum(case.annotation_status == "silver" for case in cases if case.paper_id == paper["id"])
            unanswerable = sum(
                case.must_abstain for case in cases if case.paper_id == paper["id"]
            )
            total = sum(case.paper_id == paper["id"] for case in cases)
            print(f"  保留 {total} 条，其中 Silver {silver} 条，不可回答 {unanswerable} 条")
    finally:
        connection.close()
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="使用当前 LLM 生成 Silver 评测候选")
    parser.add_argument("--manifest", default="evals/datasets/pilot_manifest.json")
    parser.add_argument("--database", default="paperai.db")
    parser.add_argument("--questions-per-paper", type=int, default=6)
    parser.add_argument("--unanswerable-per-paper", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--output", default="evals/datasets/paperqa_v1.jsonl")
    args = parser.parse_args()
    if not 2 <= args.questions_per_paper <= 10:
        parser.error("--questions-per-paper 必须在 2 到 10 之间")
    if not 0 <= args.unanswerable_per_paper <= 5:
        parser.error("--unanswerable-per-paper 必须在 0 到 5 之间")

    cases = asyncio.run(run(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(case_to_dict(case), ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    print(f"完成：{len(cases)} 条候选已写入 {output}")
    return 0 if cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
