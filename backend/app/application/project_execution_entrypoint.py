"""Single entrypoint boundary for project goals and instant interactions.

Project-level Reading/Writing requests enter the durable GoalExecution path.
Short independent paper interactions keep their existing Agent/Workflow path.
This module only classifies/adapts the entrypoint; it does not implement a
second execution runtime or any research capability.
"""
from __future__ import annotations

from typing import Literal

from app.application.research_orchestrator import ResearchOrchestrator

ProjectEntryKind = Literal["goal", "instant"]

PROJECT_GOAL_AGENT_TYPES = frozenset({"research_goal", "writing_generate"})
INSTANT_INTERACTION_KINDS = frozenset({
    "paper_chat",
    "paper_summary",
    "paper_interpretation",
    "paper_section_explanation",
    "writing_selection_proposal",
})


def classify_project_entry(agent_type: str, *, interaction_kind: str | None = None) -> ProjectEntryKind:
    """Return the one lifecycle allowed for a project-facing request."""
    if agent_type in PROJECT_GOAL_AGENT_TYPES:
        return "goal"
    if interaction_kind in INSTANT_INTERACTION_KINDS:
        return "instant"
    raise ValueError("UNSUPPORTED_PROJECT_ENTRY")


def classify_instant_interaction(interaction_kind: str) -> Literal["instant"]:
    """Make an explicitly short interaction stay outside GoalExecution."""
    if interaction_kind not in INSTANT_INTERACTION_KINDS:
        raise ValueError("UNSUPPORTED_INSTANT_INTERACTION")
    return "instant"


def is_project_goal_execution(execution) -> bool:
    """Recognize current and historical project GoalExecution rows."""
    return bool(getattr(execution, "plan_version", 0)) or getattr(execution, "agent_type", "") in PROJECT_GOAL_AGENT_TYPES


async def initialize_project_goal(db, execution):
    """Route a compatible project execution into the existing orchestrator."""
    if classify_project_entry(str(execution.agent_type)) != "goal":
        raise ValueError("UNSUPPORTED_PROJECT_ENTRY")
    await ResearchOrchestrator(db).initialize(execution)
    return execution
