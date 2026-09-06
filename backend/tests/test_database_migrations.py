from pathlib import Path

from app.infrastructure.db.migrations import ALEMBIC_HEAD_REVISION


BACKEND_DIR = Path(__file__).resolve().parents[1]
REVISION_FILE = (
    BACKEND_DIR
    / "alembic"
    / "versions"
    / "0001_current_schema_baseline_current_schema.py"
)


def test_alembic_baseline_revision_is_fixed():
    source = REVISION_FILE.read_text(encoding="utf-8")
    assert "revision: str = '0001_current_schema'" in source
    assert "Base.metadata.create_all" not in source
    assert "op.create_table('users'" in source
    assert "op.create_table('research_projects'" in source
    assert "op.create_table('writing_artifacts'" in source


def test_runtime_head_points_to_execution_runtime_revision():
    revision = BACKEND_DIR / "alembic" / "versions" / "0002_execution_runtime_add_execution_runtime.py"
    source = revision.read_text(encoding="utf-8")
    assert "revision: str = '0002_execution_runtime'" in source
    assert "down_revision: Union[str, None] = '0001_current_schema'" in source
    for table in ("agent_executions", "agent_events", "tool_calls"):
        assert f"op.create_table('{table}'" in source


def test_runtime_head_points_to_research_items_revision():
    revision = BACKEND_DIR / "alembic" / "versions" / "0003_research_items_add_research_notes_and_evidence.py"
    source = revision.read_text(encoding="utf-8")
    assert "revision: str = '0003_research_items'" in source
    assert "down_revision: Union[str, None] = '0002_execution_runtime'" in source
    assert "op.create_table('memory_items'" in source
    assert "op.create_table('evidence_items'" in source


def test_runtime_head_points_to_writing_documents_revision():
    revision = BACKEND_DIR / "alembic" / "versions" / "0004_writing_documents_add_revisioned_writing_documents.py"
    source = revision.read_text(encoding="utf-8")
    assert "revision: str = '0004_writing_documents'" in source
    assert "down_revision: Union[str, None] = '0003_research_items'" in source
    assert "op.create_table('writing_documents'" in source
    assert "op.create_table('document_revisions'" in source


def test_runtime_head_points_to_evidence_verification_revision():
    revision = BACKEND_DIR / "alembic" / "versions" / "0005_evidence_verification_add_evidence_lifecycle.py"
    source = revision.read_text(encoding="utf-8")
    assert 'revision: str = "0005_evidence_verification"' in source
    assert 'down_revision: Union[str, None] = "0004_writing_documents"' in source
    for column in ("source_type", "status", "source_fingerprint", "verification_status", "verification_reason", "verification_model", "verification_version", "updated_at"):
        assert f'"{column}"' in source
    assert "idx_evidence_items_project_status" in source


def test_runtime_head_points_to_execution_io_revision():
    revision = BACKEND_DIR / "alembic" / "versions" / "0006_execution_io_add_execution_input_and_result.py"
    source = revision.read_text(encoding="utf-8")
    assert ALEMBIC_HEAD_REVISION == "0008_agent_runtime_observability"
    assert 'revision: str = "0006_execution_io"' in source
    assert 'down_revision: Union[str, None] = "0005_evidence_verification"' in source
    assert '"input_payload"' in source
    assert '"result_payload"' in source


def test_agent_runtime_observability_migration_is_additive():
    revision = BACKEND_DIR / "alembic" / "versions" / "0008_agent_runtime_observability.py"
    source = revision.read_text(encoding="utf-8")
    assert 'revision: str = "0008_agent_runtime_observability"' in source
    assert 'down_revision: Union[str, None] = "0007_research_tasks"' in source
    assert 'op.add_column("tool_calls"' in source
    assert '"task_id"' in source and '"skill_id"' in source
    assert 'op.create_table(' in source and '"model_calls"' in source
    assert 'ondelete="SET NULL"' in source


def test_schema_check_loads_every_current_model_family():
    source = (BACKEND_DIR / "scripts" / "check_schema_revision.py").read_text()
    for module in ("chat", "document", "execution", "paper", "project", "research", "user"):
        assert f"import app.models.{module}" in source


def test_baseline_has_one_index_per_generated_definition():
    source = REVISION_FILE.read_text(encoding="utf-8")
    assert source.count("op.create_index('idx_writing_artifacts_project_type'") == 1
    assert source.count("op.create_index(op.f('ix_writing_artifacts_artifact_type')") == 1


def test_runtime_database_module_contains_no_compatibility_alter_ddl():
    source = (BACKEND_DIR / "app" / "database.py").read_text(encoding="utf-8")
    assert "ALTER TABLE" not in source.upper()
    assert "verify_schema_revision" in source
