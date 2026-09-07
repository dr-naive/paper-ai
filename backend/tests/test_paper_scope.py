import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.api import papers as papers_api
from app.services.paper_upload import PaperUploadResult
from app.utils.task_manager import get_task, remove_task


class UploadDatabase:
    async def scalar(self, _statement):
        return SimpleNamespace(id="project-1", user_id="user-1")


class RedisLock:
    def __init__(self):
        self.keys = []

    async def set(self, *args, **kwargs):
        self.keys.append(args[0])
        return True


def test_project_upload_carries_scope_through_the_existing_queue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("data/tasks").mkdir(parents=True)
    storage = tmp_path / "papers"
    storage.mkdir()
    monkeypatch.setattr(papers_api.settings, "FILE_STORAGE_PATH", str(storage))

    async def fake_user_id(*args, **kwargs):
        return "user-1"

    async def fake_receive(**kwargs):
        return PaperUploadResult(
            paper_id=kwargs["paper_id"],
            file_path=str(storage / f"{kwargs['paper_id']}.pdf"),
            file_size=10,
            file_sha256="scope-test-hash",
            timings={},
        )

    queued = []

    async def fake_enqueue(job_type, payload, **kwargs):
        queued.append((job_type, payload, kwargs))

    redis_lock = RedisLock()
    monkeypatch.setattr(papers_api, "get_current_user_id", fake_user_id)
    monkeypatch.setattr(papers_api.paper_upload_service, "receive", fake_receive)
    monkeypatch.setattr(papers_api, "get_async_redis", lambda: redis_lock)
    monkeypatch.setattr(papers_api, "enqueue_job", fake_enqueue)

    result = asyncio.run(papers_api.upload_paper(
        file=SimpleNamespace(filename="project.pdf"),
        project_id="project-1",
        authorization="Bearer token",
        db=UploadDatabase(),
    ))

    assert result["paper_id"]
    assert queued[0][0] == "paper_process"
    assert queued[0][1]["project_only"] is True
    assert queued[0][1]["initial_counts"]["project_id"] == "project-1"
    assert queued[0][1]["initial_counts"]["project_only"] is True
    assert "project-1" in redis_lock.keys[0]
    assert get_task(f"task_{result['paper_id']}").details["counts"]["project_only"] is True
    remove_task(f"task_{result['paper_id']}")


def test_standalone_paper_query_has_a_project_scope_boundary(monkeypatch):
    statement_holder = {}

    class Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class Database:
        async def execute(self, statement):
            statement_holder["value"] = statement
            return Result()

    async def fake_user_id(*args, **kwargs):
        return "user-1"

    monkeypatch.setattr(papers_api, "get_current_user_id", fake_user_id)
    monkeypatch.setattr(papers_api, "list_tasks", lambda *_args, **_kwargs: [])

    asyncio.run(papers_api.get_papers(
        skip=0,
        limit=10,
        authorization="Bearer token",
        db=Database(),
    ))

    assert "is_project_only" in str(statement_holder["value"])
