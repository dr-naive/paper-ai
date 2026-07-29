from app.main import app


def test_app_metadata():
    assert app.title == "PaperAI"


def test_paper_reading_status_route_is_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/papers/{paper_id}/status" in paths


def test_admin_dashboard_route_is_registered():
    paths = {route.path for route in app.routes}
    assert "/api/admin/dashboard" in paths
