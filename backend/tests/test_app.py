from app.main import app


def test_app_metadata():
    assert app.title == "PaperAI"
