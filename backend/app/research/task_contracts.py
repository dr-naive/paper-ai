"""Typed business-task contracts; independent of queues, ORM and model reasoning."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

TaskType = Literal['DISCOVER', 'IMPORT_PAPER', 'READ_PAPER', 'BUILD_EVIDENCE', 'WRITE_SECTION', 'AUDIT_DRAFT']
ExecutorType = Literal['AGENT', 'DETERMINISTIC', 'WORKFLOW']
GoalType = Literal['READ_PAPERS', 'WRITE_SECTION', 'DISCOVER_AND_IMPORT']
Status = Literal['pending', 'queued', 'running', 'waiting_user', 'retrying', 'completed', 'partial', 'blocked', 'failed', 'cancelled', 'paused']

# Paused is retained for historical execution compatibility. No terminal state
# is implicitly reopened by a duplicate delivery.  Tasks and executions use the
# same vocabulary, but keep separate maps so the lifecycle owner is explicit.
TASK_TRANSITIONS = {
    'pending': {'queued', 'blocked', 'cancelled', 'completed'},
    'queued': {'running', 'paused', 'cancelled', 'blocked', 'failed'},
    'running': {'queued', 'completed', 'partial', 'blocked', 'waiting_user', 'retrying', 'failed', 'cancelled', 'paused'},
    'retrying': {'queued', 'running', 'failed', 'partial', 'cancelled', 'paused'},
    'waiting_user': {'queued', 'cancelled'},
    'blocked': {'queued', 'cancelled'},
    'paused': {'queued', 'cancelled'},
    'completed': set(), 'partial': set(), 'failed': set(), 'cancelled': set(),
}
# AgentExecution is the durable goal lifecycle.  It deliberately does not
# allow a terminal execution to be reopened by a stale queue message.
EXECUTION_TRANSITIONS = {
    **TASK_TRANSITIONS,
    'pending': {'queued', 'blocked', 'cancelled'},
}
TRANSITIONS = TASK_TRANSITIONS
TERMINAL = {'completed', 'partial', 'failed', 'cancelled'}


def transition(item: Any, target: str) -> None:
    if target == item.status:
        return
    if target not in TRANSITIONS.get(item.status, set()):
        raise ValueError(f'ILLEGAL_STATE_TRANSITION:{item.status}->{target}')
    item.status = target
    item.updated_at = datetime.utcnow()
    if target == 'running' and not item.started_at:
        item.started_at = item.updated_at
    if target in TERMINAL:
        item.completed_at = item.updated_at


def transition_execution(item: Any, target: str) -> None:
    """Apply a legal ResearchExecution transition.

    API, orchestrator and worker code call this single transition helper for
    the execution row.  ResearchTask continues to use ``transition`` above.
    """
    if target == item.status:
        return
    if target not in EXECUTION_TRANSITIONS.get(item.status, set()):
        raise ValueError(f'ILLEGAL_EXECUTION_STATE_TRANSITION:{item.status}->{target}')
    item.status = target
    item.updated_at = datetime.utcnow()
    if target == 'running' and not item.started_at:
        item.started_at = item.updated_at
    if target in TERMINAL:
        item.completed_at = item.updated_at


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ArtifactRef(Contract):
    artifact_type: Literal['paper', 'paper_card', 'evidence', 'writing_context', 'section_draft', 'audit', 'discovery_results', 'blueprint', 'document', 'memory']
    artifact_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=36)
    source_task_id: str | None = None
    source_paper_id: str | None = None


class TaskError(Contract):
    code: str
    message: str
    retryable: bool = False


class TaskResult(Contract):
    task_id: str
    status: Literal['completed', 'partial', 'blocked', 'waiting_user', 'failed', 'cancelled']
    output_refs: list[ArtifactRef] = Field(default_factory=list)
    completion: dict[str, bool] = Field(default_factory=dict)
    metrics: dict[str, int | float] = Field(default_factory=dict)
    error: TaskError | None = None
    waiting: dict[str, Any] | None = None


class GoalInput(Contract):
    goal_type: GoalType
    paper_ids: list[str] = Field(default_factory=list, max_length=50)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    document_id: str | None = None
    base_revision_id: str | None = None
    instruction: str = Field(default='', max_length=20000)
    section_path: list[str] = Field(default_factory=list, max_length=20)
    nearby_text: str = Field(default='', max_length=12000)
    citation_style: Literal['apa', 'ieee', 'gbt7714'] = 'apa'
    search: dict[str, Any] | None = None
    require_import_confirmation: bool = True


class PaperState(Contract):
    paper_id: str
    indexed: bool
    processing: str
    card_ready: bool = False


class ProjectStateSnapshot(Contract):
    project_id: str
    user_id: str
    captured_at: str
    papers: list[PaperState] = Field(default_factory=list)
    assets: list[ArtifactRef] = Field(default_factory=list)


class Dependency(Contract):
    kind: Literal['hard', 'soft', 'recommended']
    capability: str
    satisfied: bool
    refs: list[ArtifactRef] = Field(default_factory=list)
    reason: str


class PlannedTask(Contract):
    task_id: str
    task_type: TaskType
    executor_type: ExecutorType
    skill_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    input_refs: list[ArtifactRef] = Field(default_factory=list)
    reason: str


class ExecutionPlan(Contract):
    plan_version: int = 1
    goal: GoalInput
    tasks: list[PlannedTask]
    dependencies: list[Dependency]
    reused_assets: list[ArtifactRef]
    missing_dependencies: list[Dependency]
    snapshot: ProjectStateSnapshot
    reason: str = 'Goal required capabilities - reusable project assets + missing hard dependencies'
