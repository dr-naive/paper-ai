"""Bounded one-call LLM generator for Paper Profile content."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.application.project_service import project_profile_dict
from app.config import settings
from app.llm.client import get_llm_client
from app.models.paper import Paper, Section
from app.models.project import ResearchProject

from .paper_profile import PaperProfileContent

PROFILE_INPUT_MAX_CHARS = 18_000
PROFILE_SECTION_MAX_CHARS = 2_500
PROFILE_MAX_SECTIONS = 8

_SECTION_PRIORITIES = (
    ("introduction", "intro", "引言", "背景"),
    ("method", "methodology", "approach", "方法", "模型"),
    ("result", "experiment", "evaluation", "结果", "实验", "评估"),
    ("conclusion", "discussion", "结论", "讨论", "limitation", "局限"),
)


@dataclass(frozen=True, slots=True)
class PaperProfileSource:
    metadata: str
    sections: str


def _select_sections(sections: list[Section]) -> list[Section]:
    ordered = sorted(sections, key=lambda item: int(item.order_index or 0))
    selected: list[Section] = []
    for keywords in _SECTION_PRIORITIES:
        match = next(
            (
                section
                for section in ordered
                if section not in selected
                and any(keyword in str(section.section_title or "").casefold() for keyword in keywords)
            ),
            None,
        )
        if match is not None:
            selected.append(match)
    for section in [*ordered[:2], *ordered[-2:]]:
        if section not in selected:
            selected.append(section)
        if len(selected) >= PROFILE_MAX_SECTIONS:
            break
    return selected[:PROFILE_MAX_SECTIONS]


def build_profile_source(paper: Paper, sections: list[Section]) -> PaperProfileSource:
    metadata = "\n".join(
        [
            f"Title: {str(paper.title or '')[:1000]}",
            f"Authors: {str(paper.authors or '')[:1000]}",
            f"Abstract: {str(paper.abstract or '')[:6000]}",
            f"Keywords: {', '.join(str(item) for item in (paper.keywords or [])[:30])}",
        ]
    )
    parts: list[str] = []
    used = len(metadata)
    for section in _select_sections(sections):
        content = str(section.content or "").strip()[:PROFILE_SECTION_MAX_CHARS]
        block = f"## {str(section.section_title or '')[:300]}\n{content}"
        remaining = PROFILE_INPUT_MAX_CHARS - used
        if remaining <= 0:
            break
        parts.append(block[:remaining])
        used += len(parts[-1])
    if not parts and paper.full_text:
        remaining = max(0, PROFILE_INPUT_MAX_CHARS - used)
        parts.append(f"## Parsed text excerpt\n{str(paper.full_text)[:remaining]}")
    sections_text = "\n\n".join(parts)
    sections_text = sections_text[:max(0, PROFILE_INPUT_MAX_CHARS - len(metadata))]
    return PaperProfileSource(metadata=metadata, sections=sections_text)


def _response_text(response: Any) -> str:
    text = str(response.generations[0][0].text or "").strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif text.startswith("```"):
        text = text.split("```", 1)[1].rsplit("```", 1)[0]
    return text.strip()


class PaperProfileGenerator:
    """Generate a selection profile, not citation evidence or a full summary."""

    def __init__(self, llm_client: Any | None = None):
        self.llm_client = llm_client or get_llm_client()

    @property
    def source_model(self) -> str:
        if settings.LLM_PROVIDER == "qwen":
            return str(settings.OPENAI_MODEL or "qwen")
        return str(settings.DEEPSEEK_MODEL or settings.LLM_PROVIDER)

    async def generate(
        self,
        project: ResearchProject,
        paper: Paper,
        sections: list[Section],
    ) -> PaperProfileContent:
        source = build_profile_source(paper, sections)
        project_profile = project_profile_dict(project)
        prompt = f"""
Create a compact structured Paper Profile for candidate-paper selection in a research writing system.

Rules:
- Use only explicit information in PAPER SOURCE. Do not infer missing facts.
- Missing values must be an empty string or empty array.
- Keep observed main_results separate from authors' conclusions.
- Do not invent DOI, datasets, samples, metrics, methods, or limitations.
- project_relevance may compare the paper with PROJECT PROFILE, but must not claim unsupported facts.
- Return one JSON object with exactly these keys:
  topic, research_questions, research_subjects, methods, datasets_or_samples,
  main_results, conclusions, contributions, limitations, keywords, project_relevance.
- All fields except topic and project_relevance are arrays of short strings.

PROJECT PROFILE:
{json.dumps(project_profile, ensure_ascii=False, default=str)}

PAPER SOURCE:
{source.metadata}

{source.sections}
""".strip()
        response = await self.llm_client.agenerate([prompt], json_mode=True, enable_thinking=False)
        data = json.loads(_response_text(response))
        return PaperProfileContent.model_validate(data)
