from app.main import app


def test_paper_analysis_routes_are_registered_once():
    expected = {
        "/api/v1/papers/{paper_id}/qa",
        "/api/v1/papers/{paper_id}/interpret",
        "/api/v1/papers/{paper_id}/summarize",
        "/api/v1/papers/{paper_id}/summary",
    }
    paths = [route.path for route in app.routes]
    for path in expected:
        assert paths.count(path) == 1
