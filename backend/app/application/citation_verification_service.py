"""Deterministic citation integrity and lexical eligibility checks."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.citation_semantic_verifier import (
    CITATION_VERIFIER_VERSION,
    SemanticCitationVerifier,
    SemanticSupportDecision,
)
from app.models.paper import DocumentElement, Paper, Section
from app.models.project import ProjectPaper, ResearchProject
from app.models.research import EvidenceItem
from app.research.context.paper_profile import paper_source_fingerprint


class CitationVerificationAccessError(LookupError):
    """The project is absent or not owned by the caller."""


class CitationMapping(BaseModel):
    """Structured citation identity supplied by a writing proposal or document."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str = Field(default="", max_length=100)
    paper_id: str = Field(default="", max_length=36)
    evidence_id: str = Field(default="", max_length=36)
    claim_text: str = Field(default="", max_length=20_000)


class CitationIntegrityResult(BaseModel):
    """Deterministic result; a pass is still unverified until Block 5B."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str = ""
    paper_id: str = ""
    evidence_id: str = ""
    status: Literal["passed", "unsupported"]
    verification_status: Literal["unverified", "unsupported"]
    code: str
    reason: str
    evidence_snippet: str = ""


class CitationIntegrityBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    results: list[CitationIntegrityResult]
    passed: bool


class CitationVerificationResult(BaseModel):
    """Claim-specific semantic result after all deterministic gates pass."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str = ""
    paper_id: str = ""
    evidence_id: str = ""
    status: Literal["verified", "weak", "unsupported"]
    code: str
    reason: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    claim_text: str = ""
    original_claim: str = ""
    adjusted_claim: str | None = None
    adjustment_applied: bool = False
    evidence_snippet: str = ""


class CitationVerificationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    results: list[CitationVerificationResult]
    passed: bool
    verified_count: int
    weak_count: int
    unsupported_count: int


def evidence_supports_claim(claim: str, evidence: EvidenceItem) -> bool:
    """Existing conservative lexical gate; passing never means semantic verification."""
    source = f"{evidence.normalized_claim or ''} {evidence.snippet or ''}".lower()
    claim_words = {
        word
        for word in re.findall(r"[a-z0-9]+", claim.lower())
        if len(word) > 3 and word not in {"have", "with", "from", "that", "this", "were", "been"}
    }
    source_words = set(re.findall(r"[a-z0-9]+", source))
    latin_supported = len(claim_words & source_words) >= min(2, max(1, len(claim_words)))
    claim_han = set(re.findall(r"[\u4e00-\u9fff]", claim))
    source_han = set(re.findall(r"[\u4e00-\u9fff]", source))
    han_supported = len(claim_han & source_han) >= min(4, max(1, len(claim_han)))
    return latin_supported or han_supported


class CitationVerificationService:
    """Apply non-bypassable ownership, provenance, stale and lexical gates."""

    def __init__(self, db: AsyncSession, semantic_verifier: Any | None = None):
        self.db = db
        self.semantic_verifier = semantic_verifier
        self._fingerprints: dict[str, str] = {}

    def _get_semantic_verifier(self) -> Any:
        if self.semantic_verifier is None:
            self.semantic_verifier = SemanticCitationVerifier()
        return self.semantic_verifier

    async def _owned_project(self, project_id: str, user_id: str) -> ResearchProject:
        project = await self.db.get(ResearchProject, project_id)
        if project is None or project.user_id != user_id:
            raise CitationVerificationAccessError(project_id)
        return project

    async def _fingerprint(self, paper: Paper) -> str:
        paper_id = str(paper.id)
        if paper_id not in self._fingerprints:
            sections = list(
                (
                    await self.db.execute(
                        select(Section)
                        .where(Section.paper_id == paper_id)
                        .order_by(Section.order_index)
                    )
                ).scalars().all()
            )
            self._fingerprints[paper_id] = paper_source_fingerprint(paper, sections)
        return self._fingerprints[paper_id]

    async def _provenance_failure(self, evidence: EvidenceItem, paper: Paper) -> tuple[str, str, str] | None:
        if not str(evidence.chunk_id or "").strip():
            return "invalid", "invalid_chunk", "Evidence 缺少可追溯 chunk 标识。"

        has_locator = False
        if evidence.section_id:
            has_locator = True
            section = await self.db.get(Section, evidence.section_id)
            if section is None:
                return "stale", "source_missing", "Evidence 来源 section 已不存在。"
            if str(section.paper_id) != str(paper.id):
                return "invalid", "section_paper_mismatch", "Evidence section 不属于引用论文。"
        if evidence.element_id:
            has_locator = True
            element = await self.db.get(DocumentElement, evidence.element_id)
            if element is None:
                return "stale", "source_missing", "Evidence 来源 document element 已不存在。"
            if str(element.paper_id) != str(paper.id):
                return "invalid", "element_paper_mismatch", "Evidence document element 不属于引用论文。"
            if evidence.section_id and str(element.section_id or "") != str(evidence.section_id):
                return "invalid", "locator_mismatch", "Evidence section 与 document element 不一致。"
        if not has_locator:
            return "invalid", "invalid_chunk", "Evidence chunk 无法解析到持久化来源位置。"

        if evidence.source_fingerprint:
            current = await self._fingerprint(paper)
            if current != evidence.source_fingerprint:
                return "stale", "source_changed", "论文解析来源已变化，Evidence 需要重新检索。"
        return None

    @staticmethod
    def _unsupported(mapping: CitationMapping, code: str, reason: str, evidence: EvidenceItem | None = None) -> CitationIntegrityResult:
        return CitationIntegrityResult(
            citation_key=mapping.citation_key,
            paper_id=mapping.paper_id,
            evidence_id=mapping.evidence_id,
            status="unsupported",
            verification_status="unsupported",
            code=code,
            reason=reason,
            evidence_snippet=str(evidence.snippet or "")[:2_000] if evidence else "",
        )

    async def verify_integrity(
        self,
        *,
        project_id: str,
        user_id: str,
        citations: list[CitationMapping],
    ) -> CitationIntegrityBatch:
        project = await self._owned_project(project_id, user_id)
        evidence_ids = {item.evidence_id for item in citations if item.evidence_id}
        evidence_rows = []
        if evidence_ids:
            evidence_rows = list(
                (
                    await self.db.execute(
                        select(EvidenceItem).where(
                            EvidenceItem.id.in_(evidence_ids),
                            EvidenceItem.project_id == project.id,
                        )
                    )
                ).scalars().all()
            )
        evidence_by_id = {str(item.id): item for item in evidence_rows}

        paper_ids = {item.paper_id for item in citations if item.paper_id}
        memberships: set[str] = set()
        if paper_ids:
            memberships = {
                str(value)
                for value in (
                    await self.db.execute(
                        select(ProjectPaper.paper_id).where(
                            ProjectPaper.project_id == project.id,
                            ProjectPaper.paper_id.in_(paper_ids),
                        )
                    )
                ).scalars().all()
            }

        results: list[CitationIntegrityResult] = []
        changed = False
        for mapping in citations:
            if not mapping.paper_id:
                results.append(self._unsupported(mapping, "missing_paper", "Citation 缺少 paper_id。"))
                continue
            if not mapping.evidence_id:
                results.append(self._unsupported(mapping, "missing_evidence", "Citation 缺少 evidence_id。"))
                continue
            evidence = evidence_by_id.get(mapping.evidence_id)
            if evidence is None:
                results.append(self._unsupported(mapping, "missing_evidence", "Evidence 不存在或不属于当前 Project。"))
                continue
            if mapping.paper_id not in memberships:
                if str(evidence.paper_id) == mapping.paper_id:
                    evidence.status = "stale"
                    evidence.verification_status = "unsupported"
                    evidence.verification_reason = "paper_not_in_project"
                    evidence.updated_at = datetime.utcnow()
                results.append(self._unsupported(mapping, "paper_not_in_project", "引用论文不属于当前 Project。", evidence))
                changed = True
                continue
            paper = await self.db.get(Paper, mapping.paper_id)
            if paper is None or paper.user_id != project.user_id:
                evidence.status = "stale"
                evidence.verification_status = "unsupported"
                evidence.verification_reason = "paper_not_found"
                evidence.updated_at = datetime.utcnow()
                changed = True
                results.append(self._unsupported(mapping, "paper_not_found", "引用论文不存在或不可访问。", evidence))
                continue
            if str(evidence.paper_id) != mapping.paper_id:
                results.append(self._unsupported(mapping, "paper_mismatch", "Citation 与 Evidence 的 paper_id 不一致。", evidence))
                continue
            if evidence.status in {"stale", "invalid"}:
                evidence.verification_status = "unsupported"
                evidence.verification_reason = f"evidence_{evidence.status}"
                evidence.updated_at = datetime.utcnow()
                changed = True
                results.append(self._unsupported(mapping, f"evidence_{evidence.status}", "Evidence 已失效，需要重新检索。", evidence))
                continue

            provenance_failure = await self._provenance_failure(evidence, paper)
            if provenance_failure:
                state, code, reason = provenance_failure
                evidence.status = state
                evidence.verification_status = "unsupported"
                evidence.verification_reason = code
                evidence.updated_at = datetime.utcnow()
                changed = True
                results.append(self._unsupported(mapping, code, reason, evidence))
                continue
            if mapping.claim_text and not evidence_supports_claim(mapping.claim_text, evidence):
                evidence.verification_status = "unsupported"
                evidence.verification_reason = "lexical_mismatch"
                evidence.updated_at = datetime.utcnow()
                changed = True
                results.append(self._unsupported(mapping, "lexical_mismatch", "主张与 Evidence 缺少基本词汇对应。", evidence))
                continue

            evidence.verification_status = "unverified"
            evidence.verification_reason = None
            evidence.updated_at = datetime.utcnow()
            changed = True
            results.append(
                CitationIntegrityResult(
                    citation_key=mapping.citation_key,
                    paper_id=mapping.paper_id,
                    evidence_id=mapping.evidence_id,
                    status="passed",
                    verification_status="unverified",
                    code="deterministic_passed",
                    reason="确定性完整性与 lexical gate 已通过；仍需语义验证。",
                    evidence_snippet=str(evidence.snippet or "")[:2_000],
                )
            )
        if changed:
            await self.db.commit()
        return CitationIntegrityBatch(
            project_id=project_id,
            results=results,
            passed=bool(results) and all(item.status == "passed" for item in results),
        )

    @staticmethod
    def _semantic_error(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return "verifier_timeout", "语义引用验证超时，当前引用不能标记为已验证。"
        if isinstance(exc, (json.JSONDecodeError, ValidationError, IndexError, KeyError, TypeError)):
            return "verifier_invalid_response", "语义引用验证返回了无效的结构化结果。"
        message = str(exc).casefold()
        if any(token in message for token in ("401", "403", "api key", "authentication")):
            return "verifier_auth_error", "语义引用验证服务鉴权失败。"
        if any(token in message for token in ("429", "rate limit", "rate_limit")):
            return "verifier_rate_limited", "语义引用验证服务当前受到限流。"
        return "verifier_unavailable", "语义引用验证服务当前不可用。"

    async def _semantic_decision(
        self,
        *,
        claim: str,
        evidence: EvidenceItem,
        paper: Paper,
    ) -> tuple[SemanticSupportDecision | None, str | None, str | None]:
        try:
            decision = await self._get_semantic_verifier().verify(
                claim=claim,
                evidence=evidence,
                paper=paper,
            )
            return decision, None, None
        except Exception as exc:
            code, reason = self._semantic_error(exc)
            return None, code, reason

    def _persist_semantic_status(
        self,
        evidence: EvidenceItem,
        *,
        status: Literal["verified", "weak", "unsupported"],
        reason: str,
    ) -> None:
        verifier = self.semantic_verifier
        evidence.verification_status = status
        evidence.verification_reason = reason[:10_000]
        evidence.verification_model = str(getattr(verifier, "source_model", "unknown"))[:200]
        evidence.verification_version = CITATION_VERIFIER_VERSION
        evidence.updated_at = datetime.utcnow()

    @staticmethod
    def _verification_result(
        mapping: CitationMapping,
        integrity: CitationIntegrityResult,
        *,
        status: Literal["verified", "weak", "unsupported"],
        code: str,
        reason: str,
        confidence: float | None = None,
        claim_text: str | None = None,
        adjusted_claim: str | None = None,
        adjustment_applied: bool = False,
    ) -> CitationVerificationResult:
        return CitationVerificationResult(
            citation_key=mapping.citation_key,
            paper_id=mapping.paper_id,
            evidence_id=mapping.evidence_id,
            status=status,
            code=code,
            reason=reason,
            confidence=confidence,
            claim_text=claim_text if claim_text is not None else mapping.claim_text,
            original_claim=mapping.claim_text,
            adjusted_claim=adjusted_claim,
            adjustment_applied=adjustment_applied,
            evidence_snippet=integrity.evidence_snippet,
        )

    async def verify_citations(
        self,
        *,
        project_id: str,
        user_id: str,
        citations: list[CitationMapping],
        allow_claim_adjustment: bool = False,
    ) -> CitationVerificationBatch:
        """Run fixed deterministic gates, then verify only eligible citations semantically."""
        integrity_batch = await self.verify_integrity(
            project_id=project_id,
            user_id=user_id,
            citations=citations,
        )
        results: list[CitationVerificationResult] = []
        changed = False
        for mapping, integrity in zip(citations, integrity_batch.results, strict=True):
            if integrity.status != "passed":
                results.append(
                    self._verification_result(
                        mapping,
                        integrity,
                        status="unsupported",
                        code=integrity.code,
                        reason=integrity.reason,
                    )
                )
                continue

            evidence = await self.db.get(EvidenceItem, mapping.evidence_id)
            paper = await self.db.get(Paper, mapping.paper_id)
            if evidence is None or paper is None:
                results.append(
                    self._verification_result(
                        mapping,
                        integrity,
                        status="unsupported",
                        code="source_missing_after_integrity",
                        reason="引用来源在语义验证前已不可用。",
                    )
                )
                continue

            decision, error_code, error_reason = await self._semantic_decision(
                claim=mapping.claim_text,
                evidence=evidence,
                paper=paper,
            )
            if decision is None:
                reason = str(error_reason or "语义引用验证失败。")
                self._persist_semantic_status(evidence, status="unsupported", reason=reason)
                changed = True
                results.append(
                    self._verification_result(
                        mapping,
                        integrity,
                        status="unsupported",
                        code=str(error_code or "verifier_unavailable"),
                        reason=reason,
                    )
                )
                continue

            if (
                decision.status == "weak"
                and allow_claim_adjustment
                and decision.suggested_claim
                and decision.suggested_claim != mapping.claim_text.strip()
            ):
                adjusted = decision.suggested_claim
                adjusted_decision, adjusted_error, adjusted_error_reason = await self._semantic_decision(
                    claim=adjusted,
                    evidence=evidence,
                    paper=paper,
                )
                if adjusted_decision is not None and adjusted_decision.status == "verified":
                    self._persist_semantic_status(
                        evidence,
                        status="verified",
                        reason=adjusted_decision.reason,
                    )
                    changed = True
                    results.append(
                        self._verification_result(
                            mapping,
                            integrity,
                            status="verified",
                            code="claim_adjusted_and_verified",
                            reason=adjusted_decision.reason,
                            confidence=adjusted_decision.confidence,
                            claim_text=adjusted,
                            adjusted_claim=adjusted,
                            adjustment_applied=True,
                        )
                    )
                    continue
                adjustment_reason = (
                    adjusted_decision.reason
                    if adjusted_decision is not None
                    else str(adjusted_error_reason or adjusted_error or "adjustment verification failed")
                )
                decision = decision.model_copy(
                    update={"reason": f"{decision.reason} 保守改写未通过复验：{adjustment_reason}"}
                )

            code = {
                "verified": "semantic_verified",
                "weak": "semantic_weak",
                "unsupported": "semantic_unsupported",
            }[decision.status]
            self._persist_semantic_status(
                evidence,
                status=decision.status,
                reason=decision.reason,
            )
            changed = True
            results.append(
                self._verification_result(
                    mapping,
                    integrity,
                    status=decision.status,
                    code=code,
                    reason=decision.reason,
                    confidence=decision.confidence,
                    adjusted_claim=decision.suggested_claim if decision.status == "weak" else None,
                )
            )

        if changed:
            await self.db.commit()
        verified_count = sum(item.status == "verified" for item in results)
        weak_count = sum(item.status == "weak" for item in results)
        unsupported_count = sum(item.status == "unsupported" for item in results)
        return CitationVerificationBatch(
            project_id=project_id,
            results=results,
            passed=bool(results) and verified_count == len(results),
            verified_count=verified_count,
            weak_count=weak_count,
            unsupported_count=unsupported_count,
        )


__all__ = [
    "CitationIntegrityBatch",
    "CitationIntegrityResult",
    "CitationMapping",
    "CitationVerificationAccessError",
    "CitationVerificationBatch",
    "CitationVerificationResult",
    "CitationVerificationService",
    "evidence_supports_claim",
]
