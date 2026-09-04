from app.api.research_items import EVIDENCE_TYPES, MEMORY_TYPES
from app.main import app
from app.models.research import EvidenceItem, MemoryItem


def test_research_item_models_match_phase_five_contract():
    memory = set(MemoryItem.__table__.columns.keys())
    evidence = set(EvidenceItem.__table__.columns.keys())
    assert {"project_id", "user_id", "type", "content", "source_type", "source_id", "confidence", "tags", "superseded_by"} <= memory
    assert {"project_id", "paper_id", "section_id", "element_id", "chunk_id", "page_number", "bbox", "evidence_type", "snippet", "normalized_claim"} <= evidence
    assert "decision" in MEMORY_TYPES and "hypothesis" in MEMORY_TYPES
    assert "quote" in EVIDENCE_TYPES and "limitation" in EVIDENCE_TYPES


def test_notes_and_evidence_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/notes" in paths
    assert "/api/v1/projects/{project_id}/notes/{note_id}" in paths
    assert "/api/v1/projects/{project_id}/evidence" in paths
    assert "/api/v1/projects/{project_id}/evidence/{evidence_id}" in paths
    assert "/api/v1/evidence/{evidence_id}" in paths
