"""Adapters over incumbent reading, retrieval, writing and import capabilities."""
from __future__ import annotations
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select
from app.models.paper import Paper, Section
from app.models.project import ProjectPaper, WritingArtifact, ResearchProject
from app.models.research import EvidenceItem
from app.research.task_contracts import TaskResult, TaskError, ArtifactRef, GoalInput
from app.application.research_planning import ProjectStateReader
from app.research.context.schemas import WritingRetrievalContext, EvidenceCandidateContext, ProjectProfileContext
from app.research.context.manager import ProjectContextManager, project_profile_dict
from app.research.evidence.service import EvidenceService
from app.harness.runtime.skill_runtime import SkillRuntime
from app.harness.runtime.standard_tools import build_standard_tool_runtime
from app.application.writing_service import WritingService, WritingGenerateRequest, WritingGenerationProposal
from app.application.execution_service import validate_writing_completion


class TaskExecutors:
    def __init__(self, db, execution, task, progress):
        self.db, self.execution, self.task, self.progress = db, execution, task, progress
        self.goal = GoalInput.model_validate(execution.plan['goal'])

    def ref(self, kind, identifier, *, source_paper_id=None):
        return ArtifactRef(artifact_type=kind, artifact_id=identifier, project_id=self.execution.project_id,
                           source_task_id=self.task.task_id, source_paper_id=source_paper_id)

    def result(self, refs, **completion):
        return TaskResult(task_id=self.task.task_id, status='completed', output_refs=refs, completion=completion)

    def blocked(self, code):
        return TaskResult(task_id=self.task.task_id, status='blocked', error=TaskError(code=code, message=code))

    async def artifact(self, kind, content):
        identifier = str(uuid5(NAMESPACE_URL, f'{self.task.task_id}:{kind}'))
        item = await self.db.get(WritingArtifact, identifier)
        if item is None:
            item = WritingArtifact(id=identifier, project_id=self.execution.project_id, author_id=self.execution.user_id,
                artifact_type=kind, title=self.execution.goal[:400], content=content, status='ready',
                meta={'source_task_id': self.task.task_id})
            self.db.add(item)
            await self.db.commit()
        return item

    async def existing_artifact(self, kind):
        return await self.db.get(WritingArtifact, str(uuid5(NAMESPACE_URL, f'{self.task.task_id}:{kind}')))

    async def execute(self):
        expected = {'READ_PAPER': 'AGENT', 'DISCOVER': 'WORKFLOW', 'IMPORT_PAPER': 'WORKFLOW',
                    'BUILD_EVIDENCE': 'WORKFLOW', 'WRITE_SECTION': 'WORKFLOW', 'AUDIT_DRAFT': 'DETERMINISTIC'}
        if self.task.executor_type != expected[self.task.task_type]:
            raise ValueError('EXECUTOR_TYPE_MISMATCH')
        skill = None
        if self.task.skill_id:
            skill = SkillRuntime(Path(__file__).parents[1] / 'harness/skills',
                                 build_standard_tool_runtime().specs()).load(self.task.skill_id)
            if skill.supported_task_types and self.task.task_type not in skill.supported_task_types:
                raise ValueError('SKILL_TASK_FORBIDDEN')
            input_types = {ref.get('artifact_type') for ref in self.task.input_refs or []}
            missing = set(skill.required_inputs) - input_types
            if missing:
                raise ValueError(f'SKILL_INPUTS_MISSING:{sorted(missing)}')
        await self.progress('boundary', {})
        result = await getattr(self, self.task.task_type.lower())()
        if skill and result.status == 'completed' and skill.produced_artifacts:
            produced = {ref.artifact_type for ref in result.output_refs}
            if not produced.intersection(skill.produced_artifacts):
                raise ValueError('SKILL_OUTPUTS_MISSING')
        return result

    async def read_paper(self):
        from app.worker import handle_paper_process
        from app.job_queue import WorkerJob
        from app.harness.agents.lead_agent import run_lead_agent
        from app.harness.runtime.task_scope import TaskScope
        paper_id = next(r['artifact_id'] for r in self.task.input_refs if r['artifact_type'] == 'paper')
        snapshot = await ProjectStateReader(self.db).read(self.execution.project_id, self.execution.user_id)
        state = next((p for p in snapshot.papers if p.paper_id == paper_id), None)
        if state is None:
            return self.blocked('PAPER_NOT_IN_PROJECT')
        paper = await self.db.get(Paper, paper_id)
        if not state.indexed:
            if state.processing in {'pending', 'processing'}:
                # The incumbent paper worker already owns the parse/index
                # operation.  Let the queue retry this business task instead
                # of replaying a second paper-processing side effect.
                raise RuntimeError('PAPER_PROCESSING_INCOMPLETE')
            if not paper.pdf_path:
                return self.blocked('PAPER_PROCESSING_SOURCE_MISSING')
            await handle_paper_process(WorkerJob.create('paper_process', {
                'paper_id': paper_id, 'user_id': self.execution.user_id, 'file_path': paper.pdf_path}))
            snapshot = await ProjectStateReader(self.db).read(self.execution.project_id, self.execution.user_id)
            if not next(p.indexed for p in snapshot.papers if p.paper_id == paper_id):
                raise RuntimeError('PAPER_PROCESSING_INCOMPLETE')
        pp = await self.db.scalar(select(ProjectPaper).where(ProjectPaper.project_id == self.execution.project_id,
                                                            ProjectPaper.paper_id == paper_id))
        if (pp.analysis_card or {}).get('summary'):
            return self.result([self.ref('paper_card', pp.id, source_paper_id=paper_id)], paper_card_saved=True)
        skill_runtime = SkillRuntime(Path(__file__).parents[1] / 'harness/skills', build_standard_tool_runtime().specs())
        skill = await skill_runtime.activate(self.execution, self.task.skill_id, db=self.db)
        if self.task.task_type not in skill.supported_task_types:
            raise ValueError('SKILL_TASK_FORBIDDEN')
        scope = TaskScope(task_id=self.task.task_id, task_type=self.task.task_type,
            project_id=self.execution.project_id, user_id=self.execution.user_id,
            paper_ids=frozenset([paper_id]), allowed_tools=frozenset(skill.allowed_tools),
            max_tool_calls=min(skill.max_tool_calls, self.execution.max_tool_calls),
            max_model_calls=min(skill.max_model_calls, self.execution.max_model_calls), checkpoint=self.progress)
        answer = await run_lead_agent(db=self.db, paper_id=paper_id, user_id=self.execution.user_id,
            project_id=self.execution.project_id, skill_names=['paper_internal'], enable_critique=False,
            request_id=self.task.task_id, task_scope=scope,
            question=f'只精读当前论文：{self.goal.instruction}。先检索全文证据，概括核心贡献、方法、实验与局限；保留来源标识。')
        if not answer.success or not answer.chunks:
            raise RuntimeError('READING_EVIDENCE_INCOMPLETE')
        pp.analysis_card = {**(pp.analysis_card or {}), 'summary': answer.answer,
                            'source_task_id': self.task.task_id, 'sources': answer.chunks}
        await self.db.commit()
        return self.result([self.ref('paper_card', pp.id, source_paper_id=paper_id)], paper_card_saved=True, sources_present=True)

    async def build_evidence(self):
        cached = await self.existing_artifact('writing_context')
        if cached:
            return self.result([self.ref('writing_context', cached.id)], evidence_ready=True)
        snapshot = await ProjectStateReader(self.db).read(self.execution.project_id, self.execution.user_id)
        allowed = [p.paper_id for p in snapshot.papers if p.indexed and (not self.goal.paper_ids or p.paper_id in self.goal.paper_ids)]
        if not allowed:
            return self.blocked('NO_INDEXED_PAPERS')
        # Profile enrichment uses the existing service; it is not a second reading task.
        from app.research.context.paper_profile import PaperProfileService, paper_source_fingerprint, read_paper_profile
        rows = (await self.db.execute(select(ProjectPaper, Paper).join(Paper, Paper.id == ProjectPaper.paper_id)
            .where(ProjectPaper.project_id == self.execution.project_id, Paper.user_id == self.execution.user_id))).all()
        for pp, paper in rows:
            if paper.id not in allowed:
                continue
            profile = read_paper_profile(pp.analysis_card)
            if profile and profile.status in {'ready', 'stale'}:
                continue
            sections = list((await self.db.scalars(select(Section).where(Section.paper_id == paper.id).order_by(Section.order_index))).all())
            if sections:
                await PaperProfileService(self.db).run_generation(project_id=self.execution.project_id,
                    paper_id=paper.id, expected_fingerprint=paper_source_fingerprint(paper, sections))
        try:
            context = await ProjectContextManager(self.db).build_writing_context(project_id=self.execution.project_id,
                user_id=self.execution.user_id, instruction=self.goal.instruction, document_id=self.goal.document_id,
                current_section_path=self.goal.section_path, nearby_text=self.goal.nearby_text, allowed_paper_ids=allowed)
        except Exception as exc:
            from app.application.writing_service import NoImportedPapersError, NoRelevantPapersError, NoSupportingEvidenceError
            if isinstance(exc, (NoImportedPapersError, NoRelevantPapersError, NoSupportingEvidenceError)):
                return self.blocked(getattr(exc, 'code', 'NO_SUPPORTING_EVIDENCE'))
            raise
        if context.status != 'ready' or not context.evidence:
            return self.blocked('NO_SUPPORTING_EVIDENCE')
        refs = []
        for candidate in context.evidence:
            evidence = await EvidenceService(self.db).persist_used(candidate=candidate, user_id=self.execution.user_id,
                                                                  normalized_claim='')
            refs.append(self.ref('evidence', evidence.id, source_paper_id=evidence.paper_id))
        artifact = await self.artifact('writing_context', context.model_dump(mode='json'))
        return self.result([self.ref('writing_context', artifact.id), *refs], evidence_ready=True)

    async def writing_context(self):
        context_ref = next((r for r in self.task.input_refs if r['artifact_type'] == 'writing_context'), None)
        if context_ref:
            artifact = await self.db.get(WritingArtifact, context_ref['artifact_id'])
            if artifact is None or artifact.project_id != self.execution.project_id:
                raise ValueError('CONTEXT_NOT_IN_PROJECT')
            context = WritingRetrievalContext.model_validate(artifact.content)
        else:
            project = await self.db.get(ResearchProject, self.execution.project_id)
            evidence = []
            for ref in self.task.input_refs:
                if ref['artifact_type'] != 'evidence':
                    continue
                item = await self.db.get(EvidenceItem, ref['artifact_id'])
                if item is None or item.project_id != self.execution.project_id or item.status != 'active':
                    raise ValueError('EVIDENCE_NOT_USABLE')
                evidence.append(EvidenceCandidateContext(project_id=item.project_id, paper_id=item.paper_id,
                    chunk_id=item.chunk_id or f'section:{item.section_id}', section_id=item.section_id,
                    element_id=item.element_id, snippet=item.snippet[:2000], paper_title=item.source_title,
                    paper_authors=', '.join(item.source_authors or []), page_number=item.page_number, bbox=item.bbox))
            context = WritingRetrievalContext(status='ready', project_profile=ProjectProfileContext.model_validate(project_profile_dict(project)),
                instruction=self.goal.instruction, document_id=self.goal.document_id, evidence=evidence,
                current_section_path=self.goal.section_path, nearby_text=self.goal.nearby_text)
        # Revalidate sources at use time; snapshot membership alone is insufficient.
        service = EvidenceService(self.db)
        for candidate in context.evidence:
            await service._owned_source(project_id=candidate.project_id, paper_id=candidate.paper_id, user_id=self.execution.user_id)
            await service.validate_locator(paper_id=candidate.paper_id, section_id=candidate.section_id,
                                           element_id=candidate.element_id, chunk_id=candidate.chunk_id)
        return context

    async def write_section(self):
        cached = await self.existing_artifact('section_draft')
        if cached:
            return self.result([self.ref('section_draft', cached.id)], proposal_saved=True)
        context = await self.writing_context()
        request = WritingGenerateRequest.model_validate({k: getattr(self.goal, k) for k in WritingGenerateRequest.model_fields})
        runtime = SkillRuntime(Path(__file__).parents[1] / 'harness/skills', build_standard_tool_runtime().specs())
        await runtime.activate(self.execution, 'writing_evidence_generation', db=self.db)
        proposal = await WritingService(self.db).generate_paragraph(project_id=self.execution.project_id,
            user_id=self.execution.user_id, request=request, prepared_context=context, on_progress=self.progress)
        artifact = await self.artifact('section_draft', proposal.model_dump(mode='json'))
        self.execution.result_payload = {'proposal': proposal.model_dump(mode='json')}
        await self.db.commit()
        return self.result([self.ref('section_draft', artifact.id)], proposal_saved=True)

    async def audit_draft(self):
        ref = next(r for r in self.task.input_refs if r['artifact_type'] == 'section_draft')
        artifact = await self.db.get(WritingArtifact, ref['artifact_id'])
        if artifact is None or artifact.project_id != self.execution.project_id:
            raise ValueError('DRAFT_NOT_IN_PROJECT')
        proposal = WritingGenerationProposal.model_validate(artifact.content)
        runtime = SkillRuntime(Path(__file__).parents[1] / 'harness/skills', build_standard_tool_runtime().specs())
        review = proposal.review
        checks = [len([p for p in proposal.content.split('\n\n') if p.strip()]) == 1,
            bool(proposal.citations) and all(c.evidence_id and c.paper_id for c in proposal.citations),
            bool(review and review.status in {'passed', 'repaired'} and review.repair_count <= 1),
            all(c.status != 'unsupported' for c in proposal.citations)]
        skill = runtime.load('writing_evidence_generation')
        report = runtime.evaluate_completion(skill.id, metadata={'document_id': proposal.document_id,
            'proposal_id': proposal.proposal_id, 'citation_count': len(proposal.citations),
            'reviewer_status': review.status if review else None, 'repair_count': review.repair_count if review else None,
            'completion_contract_ready': all(checks)}, criterion_results=dict(zip(skill.completion.criteria, [*checks, all(checks)]))).model_dump(mode='json')
        # The same final gate as legacy writing, with the same input document ID.
        self.execution.active_skill = skill.id
        from app.application.citation_verification_service import CitationVerificationService, CitationMapping
        integrity = await CitationVerificationService(self.db).verify_integrity(
            project_id=self.execution.project_id, user_id=self.execution.user_id,
            citations=[CitationMapping(citation_key=c.citation_key, paper_id=c.paper_id,
                evidence_id=c.evidence_id, claim_text=c.claim_text) for c in proposal.citations])
        if not integrity.passed:
            return self.blocked('CITATION_INTEGRITY_FAILED')
        completion = validate_writing_completion(self.execution, proposal, report)
        audit = await self.artifact('review_report', completion)
        self.execution.result_payload = {'proposal': proposal.model_dump(mode='json'), 'skill_completion': report, 'completion': completion}
        await self.db.commit()
        return self.result([self.ref('audit', audit.id)], citation_integrity=True, completion_gate=True)

    async def discover(self):
        from app.research.discovery.schemas import LiteratureSearchRequest
        from app.research.discovery.workflow import LiteratureDiscoveryWorkflow, build_default_providers
        cached = await self.existing_artifact('discovery_results')
        if not cached:
            request = LiteratureSearchRequest.model_validate({'project_id': self.execution.project_id,
                **(self.goal.search or {'intent': {'topic': self.goal.instruction}})})
            primary, fallback = build_default_providers()
            result = await LiteratureDiscoveryWorkflow(primary_provider=primary, fallback_providers=fallback).run(request)
            cached = await self.artifact('discovery_results', result.model_dump(mode='json'))
        return self.result([self.ref('discovery_results', cached.id)], normalized_results=True)

    async def import_paper(self):
        from app.research.discovery.schemas import DiscoveryImportRequest
        from app.services.remote_paper_import import normalize_arxiv_id
        from app.worker import handle_arxiv_import
        from app.job_queue import WorkerJob
        ref = next(r for r in self.task.input_refs if r['artifact_type'] == 'discovery_results')
        artifact = await self.db.get(WritingArtifact, ref['artifact_id'])
        if artifact is None or artifact.project_id != self.execution.project_id:
            raise ValueError('DISCOVERY_NOT_IN_PROJECT')
        options = artifact.content['papers']
        selected = (self.task.blocker_reason or {}).get('selected_result_ids')
        if self.goal.require_import_confirmation and selected is None:
            return TaskResult(task_id=self.task.task_id, status='waiting_user', waiting={
                'prompt': '请选择需要导入的论文', 'schema': {'selected_result_ids': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}},
                'options': [{'result_id': p['result_id'], 'title': p['title'], 'import_available': p.get('import_available', False)} for p in options]})
        papers = [p for p in options if p.get('import_available') and (selected is None or p['result_id'] in selected)]
        if not papers:
            return self.blocked('NO_IMPORTABLE_SELECTED_PAPERS')
        refs = []
        for result in papers:
            await self.progress('boundary', {})
            # Validation preserves approved arXiv source/locator policy.
            request = DiscoveryImportRequest(source=result['source'], source_paper_id=result['source_paper_id'], result_id=result['result_id'])
            arxiv_id = normalize_arxiv_id(request.source_paper_id)
            source_url = f'https://arxiv.org/abs/{arxiv_id}'
            paper = await self.db.scalar(select(Paper).where(Paper.user_id == self.execution.user_id, Paper.source_url == source_url))
            paper_id = paper.id if paper else str(uuid5(NAMESPACE_URL, f'paperai:{self.execution.user_id}:arxiv:{arxiv_id}'))
            if paper is None:
                await handle_arxiv_import(WorkerJob.create('arxiv_import', {'project_id': self.execution.project_id,
                    'user_id': self.execution.user_id, 'paper_id': paper_id, 'arxiv_id': arxiv_id, 'source_url': source_url}, job_id=self.task.task_id))
                paper = await self.db.get(Paper, paper_id)
                if paper is None:
                    return TaskResult(task_id=self.task.task_id, status='failed', output_refs=refs,
                        error=TaskError(code='IMPORT_FAILED', message='论文导入未完成', retryable=True))
            membership = await self.db.scalar(select(ProjectPaper).where(ProjectPaper.project_id == self.execution.project_id, ProjectPaper.paper_id == paper_id))
            if membership is None:
                self.db.add(ProjectPaper(project_id=self.execution.project_id, paper_id=paper_id))
                await self.db.commit()
            refs.append(self.ref('paper', paper_id))
        return self.result(refs, selected_papers_imported=True)
