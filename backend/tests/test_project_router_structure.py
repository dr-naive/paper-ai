from app.main import app


EXPECTED_PROJECT_ROUTES = {
    ("GET", "/api/v1/projects"),
    ("POST", "/api/v1/projects"),
    ("GET", "/api/v1/projects/{project_id}"),
    ("GET", "/api/v1/projects/{project_id}/workflow-status"),
    ("PATCH", "/api/v1/projects/{project_id}"),
    ("DELETE", "/api/v1/projects/{project_id}"),
    ("GET", "/api/v1/projects/{project_id}/papers"),
    ("POST", "/api/v1/projects/{project_id}/papers"),
    ("PATCH", "/api/v1/projects/{project_id}/papers/{paper_id}"),
    ("GET", "/api/v1/projects/{project_id}/papers/{paper_id}/card"),
    ("PATCH", "/api/v1/projects/{project_id}/papers/{paper_id}/card"),
    ("DELETE", "/api/v1/projects/{project_id}/papers/{paper_id}"),
    ("GET", "/api/v1/projects/{project_id}/artifacts"),
    ("POST", "/api/v1/projects/{project_id}/artifacts"),
    ("GET", "/api/v1/projects/{project_id}/artifacts/{artifact_id}"),
    ("PATCH", "/api/v1/projects/{project_id}/artifacts/{artifact_id}"),
    ("DELETE", "/api/v1/projects/{project_id}/artifacts/{artifact_id}"),
    ("GET", "/api/v1/projects/{project_id}/memory"),
    ("PATCH", "/api/v1/projects/{project_id}/memory"),
    ("POST", "/api/v1/projects/{project_id}/memory/note"),
    ("POST", "/api/v1/projects/{project_id}/reading-executions"),
    ("GET", "/api/v1/projects/{project_id}/reading-executions/{task_id}"),
    ("POST", "/api/v1/projects/{project_id}/reading-executions/{task_id}/pause"),
    ("POST", "/api/v1/projects/{project_id}/reading-executions/{task_id}/resume"),
}


def test_all_project_api_routes_are_registered():
    registered = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert EXPECTED_PROJECT_ROUTES <= registered


def test_project_chat_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/chat/sessions" in paths
    assert "/api/v1/chat/sessions/{session_id}/messages" in paths


def test_worker_registers_arxiv_import_handler():
    from pathlib import Path
    source = Path("app/worker.py").read_text(encoding="utf-8")
    assert '"arxiv_import": handle_arxiv_import' in source
