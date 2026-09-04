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
    assert ALEMBIC_HEAD_REVISION == "0002_execution_runtime"
    assert f"revision: str = '{ALEMBIC_HEAD_REVISION}'" in source
    assert "down_revision: Union[str, None] = '0001_current_schema'" in source
    for table in ("agent_executions", "agent_events", "tool_calls"):
        assert f"op.create_table('{table}'" in source


def test_baseline_has_one_index_per_generated_definition():
    source = REVISION_FILE.read_text(encoding="utf-8")
    assert source.count("op.create_index('idx_writing_artifacts_project_type'") == 1
    assert source.count("op.create_index(op.f('ix_writing_artifacts_artifact_type')") == 1


def test_runtime_database_module_contains_no_compatibility_alter_ddl():
    source = (BACKEND_DIR / "app" / "database.py").read_text(encoding="utf-8")
    assert "ALTER TABLE" not in source.upper()
    assert "verify_schema_revision" in source
