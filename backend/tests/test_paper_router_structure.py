from app.main import app


def test_paper_analysis_routes_are_registered_once():
    expected = {
        "/api/v1/papers/{paper_id}/qa",
        "/api/v1/papers/{paper_id}/interpret",
        "/api/v1/papers/{paper_id}/summarize",
        "/api/v1/papers/{paper_id}/summary",
        "/api/v1/papers/{paper_id}/pdf/telemetry",
    }
    paths = [route.path for route in app.routes]
    for path in expected:
        assert paths.count(path) == 1


def test_failed_import_delete_route_is_registered_as_a_task_route():
    routes = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert ("DELETE", "/api/v1/papers/tasks/{task_id}") in routes
