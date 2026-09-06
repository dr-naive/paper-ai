"""One project snapshot and deterministic, pruned goal templates."""
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select
from app.models.paper import Paper, Section
from app.models.project import ResearchProject, ProjectPaper, WritingArtifact
from app.models.document import WritingDocument
from app.models.research import EvidenceItem, MemoryItem
from app.research.task_contracts import (
    GoalInput, ProjectStateSnapshot, PaperState, ArtifactRef, Dependency,
    ExecutionPlan, PlannedTask,
)


class GoalResolver:
    def resolve(self, agent_type, payload, goal):
        if agent_type == 'writing_generate':
            return GoalInput(goal_type='WRITE_SECTION', **{**payload, 'nearby_text': payload.get('nearby_text') or ''})
        return GoalInput.model_validate({**payload, 'instruction': payload.get('instruction') or goal})


class ProjectStateReader:
    def __init__(self, db):
        self.db = db

    async def read(self, project_id, user_id):
        project = await self.db.get(ResearchProject, project_id)
        if project is None or project.user_id != user_id:
            raise LookupError('PROJECT_NOT_FOUND')
        rows = (await self.db.execute(select(ProjectPaper, Paper).join(Paper, Paper.id == ProjectPaper.paper_id)
            .where(ProjectPaper.project_id == project_id, Paper.user_id == user_id))).all()
        from app.rag.knowledge_base import get_knowledge_base
        from app.utils.task_manager import list_tasks
        processing = {t.paper_id: t for t in list_tasks() if t.user_id == user_id}
        assets, papers = [], []
        def ref(kind, identifier, source_paper_id=None):
            return ArtifactRef(artifact_type=kind, artifact_id=str(identifier), project_id=project_id,
                               source_paper_id=source_paper_id)
        for pp, paper in rows:
            sections = (await self.db.execute(select(Section.id).where(Section.paper_id == paper.id).limit(1))).first()
            task = processing.get(paper.id)
            state = task.status.value if task else 'unknown'
            ready = bool(sections and paper.full_text) and state not in {'pending', 'processing', 'failed'}
            ready = ready and await get_knowledge_base().has_paper_index(paper.id)
            papers.append(PaperState(paper_id=paper.id, indexed=ready, processing=state,
                                    card_ready=bool((pp.analysis_card or {}).get('summary'))))
            assets.append(ref('paper', paper.id))
            if papers[-1].card_ready:
                assets.append(ref('paper_card', pp.id))
        ready_ids = {p.paper_id for p in papers if p.indexed}
        from app.research.evidence.service import EvidenceService, EvidenceProvenanceError
        evidence_service = EvidenceService(self.db)
        for evidence in (await self.db.scalars(select(EvidenceItem).where(
                EvidenceItem.project_id == project_id, EvidenceItem.status == 'active'))).all():
            if evidence.paper_id not in ready_ids:
                continue
            try:
                await evidence_service.validate_locator(paper_id=evidence.paper_id, section_id=evidence.section_id,
                    element_id=evidence.element_id, chunk_id=evidence.chunk_id)
                paper = await self.db.get(Paper, evidence.paper_id)
                if evidence.source_fingerprint != await evidence_service.source_fingerprint(paper):
                    continue
            except EvidenceProvenanceError:
                continue
            assets.append(ref('evidence', evidence.id, source_paper_id=evidence.paper_id))
        for doc in (await self.db.scalars(select(WritingDocument).where(WritingDocument.project_id == project_id))).all():
            assets.append(ref('document', doc.id))
        for artifact in (await self.db.scalars(select(WritingArtifact).where(WritingArtifact.project_id == project_id))).all():
            kind = {'section_draft': 'section_draft', 'paper_blueprint': 'blueprint', 'review_report': 'audit'}.get(artifact.artifact_type)
            if kind:
                assets.append(ref(kind, artifact.id))
        for memory_id in (await self.db.scalars(select(MemoryItem.id).where(MemoryItem.project_id == project_id,
                MemoryItem.user_id == user_id, MemoryItem.superseded_by.is_(None)))).all():
            assets.append(ref('memory', memory_id))
        return ProjectStateSnapshot(project_id=project_id, user_id=user_id, captured_at=datetime.utcnow().isoformat(),
                                    papers=papers, assets=assets)


class DependencyResolver:
    def resolve(self, goal, state):
        papers = [p for p in state.papers if not goal.paper_ids or p.paper_id in goal.paper_ids]
        if set(goal.paper_ids) - {p.paper_id for p in papers}:
            raise ValueError('PAPER_NOT_IN_PROJECT')
        selected = {p.paper_id for p in papers}
        available_evidence = [r for r in state.assets if r.artifact_type == 'evidence']
        if goal.evidence_ids:
            evidence = [r for r in available_evidence if r.artifact_id in goal.evidence_ids]
        else:
            # Evidence is a reusable project asset.  When the user does not
            # narrow the paper set, all validated evidence is eligible; when
            # papers are explicitly selected, keep only evidence whose paper
            # is selected.  The snapshot already performed provenance checks.
            evidence_paper_ids = {p.paper_id for p in papers}
            evidence = (available_evidence if not goal.paper_ids else
                        [r for r in available_evidence if self._evidence_paper_id(r) in evidence_paper_ids])
        if goal.evidence_ids and len(evidence) != len(set(goal.evidence_ids)):
            raise ValueError('EVIDENCE_NOT_USABLE')
        # Only explicitly selected evidence can be assumed relevant to this goal.
        deps = []
        if goal.goal_type == 'READ_PAPERS':
            deps.append(Dependency(kind='hard', capability='project_papers', satisfied=bool(papers),
                reason='Reading requires selected owned papers', refs=[r for r in state.assets if r.artifact_type == 'paper' and r.artifact_id in selected]))
        if goal.goal_type == 'WRITE_SECTION':
            document_refs = [r for r in state.assets if r.artifact_type == 'document' and
                             r.artifact_id == goal.document_id]
            deps.extend([
                Dependency(kind='hard', capability='indexed_papers', satisfied=any(p.indexed for p in papers),
                    reason='Writing never starts external discovery implicitly'),
                Dependency(kind='hard', capability='document', satisfied=any(r.artifact_type == 'document' and r.artifact_id == goal.document_id for r in state.assets),
                    refs=document_refs, reason='A current project document is required'),
                Dependency(kind='soft', capability='evidence', satisfied=bool(evidence), refs=evidence,
                    reason='Reuse validated project evidence before building new evidence'),
                Dependency(kind='recommended', capability='blueprint', satisfied=any(r.artifact_type == 'blueprint' for r in state.assets),
                    reason='An outline improves context but does not gate a paragraph'),
            ])
        return deps

    @staticmethod
    def _evidence_paper_id(ref):
        # ProjectStateReader currently exposes the evidence id as the
        # structured reference.  Keep this helper deliberately conservative:
        # absent provenance never makes evidence appear relevant by guesswork.
        return ref.source_paper_id


class PlanBuilder:
    def build(self, execution_id, goal, state):
        deps = DependencyResolver().resolve(goal, state)
        missing = [d for d in deps if d.kind == 'hard' and not d.satisfied]
        tasks, reused = [], [r for d in deps for r in d.refs]
        def add(kind, executor, refs=(), dependencies=(), skill=None, reason='Required by goal'):
            task_id = str(uuid5(NAMESPACE_URL, f'paperai:{execution_id}:{kind}:{len(tasks)}'))
            tasks.append(PlannedTask(task_id=task_id, task_type=kind, executor_type=executor,
                input_refs=list(refs), dependencies=list(dependencies), skill_id=skill, reason=reason))
            return task_id
        # A blocked plan still persists the shortest useful task graph.  This
        # lets a user add the missing asset and resume the same execution;
        # execution state, not a second planning pass, remains authoritative.
        if not missing or goal.goal_type == 'WRITE_SECTION':
            if goal.goal_type == 'READ_PAPERS':
                for paper in state.papers:
                    if goal.paper_ids and paper.paper_id not in goal.paper_ids:
                        continue
                    if paper.card_ready:
                        continue
                    add('READ_PAPER', 'AGENT', [ArtifactRef(artifact_type='paper', artifact_id=paper.paper_id,
                        project_id=state.project_id)], skill='paper_internal',
                        reason='Read current paper' if paper.indexed else 'Complete existing processing, then read current paper')
            elif goal.goal_type == 'WRITE_SECTION':
                evidence = next(d.refs for d in deps if d.capability == 'evidence')
                indexed = [ArtifactRef(artifact_type='paper', artifact_id=p.paper_id,
                                      project_id=state.project_id) for p in state.papers
                            if p.indexed and (not goal.paper_ids or p.paper_id in goal.paper_ids)]
                build = [] if evidence else [add('BUILD_EVIDENCE', 'WORKFLOW', indexed,
                                                 reason='Build traceable evidence from indexed project papers')]
                document = ([ArtifactRef(artifact_type='document', artifact_id=goal.document_id,
                                         project_id=state.project_id)] if goal.document_id else [])
                write = add('WRITE_SECTION', 'WORKFLOW', [*evidence, *document], build,
                            'writing_evidence_generation')
                add('AUDIT_DRAFT', 'DETERMINISTIC', dependencies=[write])
            else:
                discover = add('DISCOVER', 'WORKFLOW')
                add('IMPORT_PAPER', 'WORKFLOW', dependencies=[discover], reason='Import only selected approved sources')
        return ExecutionPlan(goal=goal, tasks=tasks, dependencies=deps, reused_assets=reused,
                             missing_dependencies=missing, snapshot=state)
