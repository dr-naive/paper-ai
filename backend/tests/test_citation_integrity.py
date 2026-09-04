from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.citation_semantic_verifier import (
    CITATION_VERIFIER_VERSION,
    SemanticCitationVerifier,
    SemanticSupportDecision,
)
from app.application.citation_verification_service import (
    CitationMapping,
    CitationVerificationAccessError,
    CitationVerificationService,
)
from app.main import app as _application  # noqa: F401 - register ORM relationship targets
from app.models.paper import DocumentElement, Paper, Section
from app.models.project import ProjectPaper, ResearchProject
from app.models.research import EvidenceItem
from app.models.user import User
from app.research.context.paper_profile import paper_source_fingerprint


@asynccontextmanager
async def _citation_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        ResearchProject.__table__,
        Paper.__table__,
        ProjectPaper.__table__,
        Section.__table__,
        DocumentElement.__table__,
        EvidenceItem.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_connection: User.metadata.create_all(sync_connection, tables=tables))
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        user = User(id="user-1", username="citation", email="citation@example.com", password_hash="hash")
        project = ResearchProject(
            id="project-1",
            user_id=user.id,
            title="Citation Project",
            research_topic="Evidence integrity",
            memory={},
            preferences={},
        )
        papers = [
            Paper(id="paper-a", user_id=user.id, title="Paper A", authors="Ada", updated_at=datetime(2026, 8, 24)),
            Paper(id="paper-b", user_id=user.id, title="Paper B", authors="Lin", updated_at=datetime(2026, 8, 24)),
        ]
        memberships = [
            ProjectPaper(id="membership-a", project_id=project.id, paper_id="paper-a"),
            ProjectPaper(id="membership-b", project_id=project.id, paper_id="paper-b"),
        ]
        section = Section(
            id="section-a",
            paper_id="paper-a",
            section_title="Results",
            order_index=1,
            start_page=3,
            content="The intervention improved student autonomy and self-regulated learning.",
            created_at=datetime(2026, 8, 24),
        )
        session.add_all([user, project, *papers, *memberships, section])
        await session.commit()
        fingerprint = paper_source_fingerprint(papers[0], [section])
        evidence = EvidenceItem(
            id="evidence-a",
            project_id=project.id,
            paper_id="paper-a",
            section_id=section.id,
            chunk_id="chunk:section-a:bm25-0",
            page_number=3,
            evidence_type="result",
            snippet=section.content,
            normalized_claim="The intervention improved student autonomy.",
            source_title=papers[0].title,
            source_authors=["Ada"],
            source_type="retrieval_generated",
            status="active",
            source_fingerprint=fingerprint,
            verification_status="unverified",
            created_by="retrieval",
        )
        session.add(evidence)
        await session.commit()
        yield session, project, papers, evidence
    await engine.dispose()


def _mapping(**values) -> CitationMapping:
    payload = {
        "citation_key": "ref-a",
        "paper_id": "paper-a",
        "evidence_id": "evidence-a",
        "claim_text": "The intervention improved student autonomy.",
    }
    payload.update(values)
    return CitationMapping(**payload)


class FakeSemanticVerifier:
    source_model = "test-semantic-model"

    def __init__(self, *decisions):
        self.decisions = list(decisions)
        self.calls: list[str] = []

    async def verify(self, *, claim, evidence, paper):
        self.calls.append(claim)
        outcome = self.decisions.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _decision(status: str, reason: str = "contract result", **values) -> SemanticSupportDecision:
    return SemanticSupportDecision(status=status, reason=reason, **values)


@pytest.mark.asyncio
async def test_valid_mapping_passes_integrity_but_remains_semantically_unverified():
    async with _citation_db() as (db, project, _papers, evidence):
        batch = await CitationVerificationService(db).verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        await db.refresh(evidence)

        assert batch.passed
        assert batch.results[0].code == "deterministic_passed"
        assert batch.results[0].verification_status == "unverified"
        assert evidence.verification_status == "unverified"


@pytest.mark.asyncio
async def test_wrong_project_missing_evidence_and_wrong_paper_are_rejected():
    async with _citation_db() as (db, project, _papers, _evidence):
        service = CitationVerificationService(db)
        with pytest.raises(CitationVerificationAccessError):
            await service.verify_integrity(
                project_id=project.id,
                user_id="other-user",
                citations=[_mapping()],
            )

        missing = await service.verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping(evidence_id="missing")],
        )
        mismatch = await service.verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping(paper_id="paper-b")],
        )

        assert missing.results[0].code == "missing_evidence"
        assert mismatch.results[0].code == "paper_mismatch"
        assert not missing.passed and not mismatch.passed


@pytest.mark.asyncio
async def test_stale_removed_and_changed_sources_are_rejected_and_persisted():
    async with _citation_db() as (db, project, _papers, evidence):
        evidence.status = "stale"
        await db.commit()
        stale = await CitationVerificationService(db).verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        assert stale.results[0].code == "evidence_stale"

        evidence.status = "active"
        evidence.source_fingerprint = "b" * 64
        await db.commit()
        changed = await CitationVerificationService(db).verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        await db.refresh(evidence)
        assert changed.results[0].code == "source_changed"
        assert evidence.status == "stale"

        evidence.status = "active"
        evidence.source_fingerprint = None
        await db.execute(delete(ProjectPaper).where(ProjectPaper.id == "membership-a"))
        await db.commit()
        removed = await CitationVerificationService(db).verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        await db.refresh(evidence)
        assert removed.results[0].code == "paper_not_in_project"
        assert evidence.status == "stale"
        assert evidence.verification_status == "unsupported"
        assert evidence.verification_reason == "paper_not_in_project"


@pytest.mark.asyncio
async def test_invalid_chunk_and_lexical_mismatch_are_unsupported():
    async with _citation_db() as (db, project, _papers, evidence):
        evidence.section_id = None
        evidence.element_id = None
        evidence.source_fingerprint = None
        await db.commit()
        invalid = await CitationVerificationService(db).verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        assert invalid.results[0].code == "invalid_chunk"

        evidence.status = "active"
        evidence.section_id = "section-a"
        await db.commit()
        lexical = await CitationVerificationService(db).verify_integrity(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping(claim_text="Marine biodiversity increased across tropical reefs.")],
        )
        refreshed = await db.scalar(select(EvidenceItem).where(EvidenceItem.id == evidence.id))
        assert lexical.results[0].code == "lexical_mismatch"
        assert refreshed.verification_status == "unsupported"


@pytest.mark.asyncio
async def test_semantic_verified_result_is_persisted_with_model_provenance():
    async with _citation_db() as (db, project, _papers, evidence):
        verifier = FakeSemanticVerifier(_decision("verified", confidence=0.93))
        batch = await CitationVerificationService(db, verifier).verify_citations(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        await db.refresh(evidence)

        assert batch.passed
        assert batch.verified_count == 1
        assert batch.results[0].status == "verified"
        assert batch.results[0].code == "semantic_verified"
        assert verifier.calls == [_mapping().claim_text]
        assert evidence.verification_status == "verified"
        assert evidence.verification_model == verifier.source_model
        assert evidence.verification_version == CITATION_VERIFIER_VERSION


@pytest.mark.asyncio
async def test_semantic_weak_and_unsupported_are_never_reported_as_verified():
    async with _citation_db() as (db, project, _papers, evidence):
        weak_verifier = FakeSemanticVerifier(
            _decision(
                "weak",
                "Only an association is reported.",
                confidence=0.71,
                suggested_claim="Use is positively associated with learning performance.",
            )
        )
        weak = await CitationVerificationService(db, weak_verifier).verify_citations(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        assert weak.results[0].status == "weak"
        assert weak.results[0].adjusted_claim
        assert not weak.passed

        unsupported_verifier = FakeSemanticVerifier(
            _decision("unsupported", "The evidence does not make this claim.", confidence=0.95)
        )
        unsupported = await CitationVerificationService(db, unsupported_verifier).verify_citations(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
        )
        await db.refresh(evidence)
        assert unsupported.results[0].status == "unsupported"
        assert unsupported.results[0].code == "semantic_unsupported"
        assert unsupported.unsupported_count == 1
        assert evidence.verification_status == "unsupported"


@pytest.mark.asyncio
async def test_deterministic_failure_never_calls_semantic_verifier():
    async with _citation_db() as (db, project, _papers, _evidence):
        verifier = FakeSemanticVerifier(_decision("verified"))
        batch = await CitationVerificationService(db, verifier).verify_citations(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping(evidence_id="missing")],
        )

        assert batch.results[0].code == "missing_evidence"
        assert batch.results[0].status == "unsupported"
        assert verifier.calls == []


@pytest.mark.asyncio
async def test_correlation_causation_prompt_requires_conservative_classification():
    response = SimpleNamespace(
        generations=[[SimpleNamespace(text=(
            '{"status":"weak","reason":"Association does not establish causation",'
            '"confidence":0.88,"suggested_claim":"Use was associated with performance."}'
        ))]]
    )

    class RecordingLLM:
        def __init__(self):
            self.prompts = None

        async def agenerate(self, prompts, **kwargs):
            self.prompts = prompts
            assert kwargs == {"json_mode": True, "enable_thinking": False}
            return response

    async with _citation_db() as (_db, _project, papers, evidence):
        llm = RecordingLLM()
        decision = await SemanticCitationVerifier(llm, timeout_seconds=1).verify(
            claim="AI use causes higher learning performance.",
            evidence=evidence,
            paper=papers[0],
        )

        assert decision.status == "weak"
        assert "Correlation or association does not verify causation" in llm.prompts[0]
        assert "project-1" not in llm.prompts[0]


@pytest.mark.asyncio
async def test_weak_claim_adjustment_is_reverified_once_and_returned_explicitly():
    async with _citation_db() as (db, project, _papers, evidence):
        adjusted = "The intervention was associated with improved student autonomy."
        verifier = FakeSemanticVerifier(
            _decision("weak", "The original claim is too strong.", suggested_claim=adjusted),
            _decision("verified", "The qualified association is directly supported.", confidence=0.9),
        )
        batch = await CitationVerificationService(db, verifier).verify_citations(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
            allow_claim_adjustment=True,
        )
        await db.refresh(evidence)

        result = batch.results[0]
        assert verifier.calls == [_mapping().claim_text, adjusted]
        assert result.status == "verified"
        assert result.adjustment_applied is True
        assert result.original_claim == _mapping().claim_text
        assert result.claim_text == adjusted
        assert evidence.verification_status == "verified"


@pytest.mark.asyncio
async def test_verifier_timeout_is_explicitly_unsupported_and_not_retried():
    async with _citation_db() as (db, project, _papers, evidence):
        verifier = FakeSemanticVerifier(TimeoutError("provider timed out"))
        batch = await CitationVerificationService(db, verifier).verify_citations(
            project_id=project.id,
            user_id=project.user_id,
            citations=[_mapping()],
            allow_claim_adjustment=True,
        )
        await db.refresh(evidence)

        assert verifier.calls == [_mapping().claim_text]
        assert batch.results[0].status == "unsupported"
        assert batch.results[0].code == "verifier_timeout"
        assert batch.results[0].confidence is None
        assert evidence.verification_status == "unsupported"


@pytest.mark.asyncio
async def test_semantic_verifier_enforces_its_own_outer_timeout():
    class SlowLLM:
        async def agenerate(self, _prompts, **_kwargs):
            await asyncio.sleep(1)

    async with _citation_db() as (_db, _project, papers, evidence):
        with pytest.raises(asyncio.TimeoutError):
            await SemanticCitationVerifier(SlowLLM(), timeout_seconds=0.01).verify(
                claim=_mapping().claim_text,
                evidence=evidence,
                paper=papers[0],
            )
