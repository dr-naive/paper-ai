import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api import papers as papers_api
from fastapi import HTTPException
from app.utils.task_manager import TaskStatus, create_task, get_task, remove_task, update_task


class FakeDatabase:
    def __init__(self, paper=None):
        self.paper = paper

    async def scalar(self, statement):
        return self.paper


class FakeKnowledgeBase:
    def __init__(self):
        self.deleted_papers = []

    async def delete_paper(self, paper_id):
        self.deleted_papers.append(paper_id)
        return True


def _configure_task_storage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("data/tasks").mkdir(parents=True)


def test_failed_import_retry_requeues_the_persisted_pdf(tmp_path, monkeypatch):
    _configure_task_storage(tmp_path, monkeypatch)
    paper_dir = tmp_path / "papers"
    paper_dir.mkdir()
    monkeypatch.setattr(papers_api.settings, "FILE_STORAGE_PATH", str(paper_dir))
    (paper_dir / "paper-1.pdf").write_bytes(b"%PDF-1.7\n")

    task = create_task("paper-1", "user-1")
    update_task(
        task.task_id,
        status=TaskStatus.FAILED,
        message="处理失败",
        details={"counts": {"original_filename": "failed.pdf"}},
    )
    queued = []

    async def fake_user_id(*args, **kwargs):
        return "user-1"

    async def fake_enqueue(job_type, payload, **kwargs):
        queued.append((job_type, payload, kwargs))

    knowledge_base = FakeKnowledgeBase()
    monkeypatch.setattr(papers_api, "get_current_user_id", fake_user_id)
    monkeypatch.setattr(papers_api, "enqueue_job", fake_enqueue)
    monkeypatch.setattr(papers_api, "get_knowledge_base", lambda: knowledge_base)

    result = asyncio.run(
        papers_api.retry_paper_task(task.task_id, "Bearer token", FakeDatabase())
    )

    assert result["retry_type"] == "import"
    assert queued[0][0] == "paper_process"
    assert queued[0][1]["paper_id"] == "paper-1"
    assert knowledge_base.deleted_papers == ["paper-1"]
    assert get_task(task.task_id).status == TaskStatus.PENDING


def test_failed_media_retry_only_queues_media_enhancement(tmp_path, monkeypatch):
    _configure_task_storage(tmp_path, monkeypatch)
    pdf_path = tmp_path / "paper-2.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")
    task = create_task("paper-2", "user-1")
    update_task(
        task.task_id,
        status=TaskStatus.COMPLETED,
        message="论文可用，但图表增强失败",
        details={"media_status": "failed", "media_error": "old bug"},
    )
    queued = []

    async def fake_user_id(*args, **kwargs):
        return "user-1"

    async def fake_enqueue(job_type, payload, **kwargs):
        queued.append((job_type, payload, kwargs))

    monkeypatch.setattr(papers_api, "get_current_user_id", fake_user_id)
    monkeypatch.setattr(papers_api, "enqueue_job", fake_enqueue)
    paper = SimpleNamespace(id="paper-2", user_id="user-1", pdf_path=str(pdf_path))

    result = asyncio.run(
        papers_api.retry_paper_task(task.task_id, "Bearer token", FakeDatabase(paper))
    )

    assert result["retry_type"] == "media"
    assert queued[0][0] == "paper_media_enhance"
    assert queued[0][1]["media_only"] is True
    retried = get_task(task.task_id)
    assert retried.status == TaskStatus.READY
    assert retried.details["media_status"] == "processing"
    assert "media_error" not in retried.details


def test_failed_import_can_be_deleted_with_its_file_and_persisted_task(tmp_path, monkeypatch):
    _configure_task_storage(tmp_path, monkeypatch)
    paper_dir = tmp_path / "papers"
    paper_dir.mkdir()
    monkeypatch.setattr(papers_api.settings, "FILE_STORAGE_PATH", str(paper_dir))
    pdf_path = paper_dir / "paper-delete.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")

    task = create_task("paper-delete", "user-1")
    update_task(
        task.task_id,
        status=TaskStatus.FAILED,
        message="处理失败",
        details={"counts": {"original_filename": "failed.pdf"}},
    )

    class DeleteDatabase:
        async def scalar(self, _statement):
            return None

        async def commit(self):
            return None

    async def fake_user_id(*args, **kwargs):
        return "user-1"

    knowledge_base = FakeKnowledgeBase()
    monkeypatch.setattr(papers_api, "get_current_user_id", fake_user_id)
    monkeypatch.setattr(papers_api, "get_knowledge_base", lambda: knowledge_base)

    result = asyncio.run(
        papers_api.delete_failed_import_task(task.task_id, "Bearer token", DeleteDatabase())
    )

    assert result["message"] == "失败导入已删除"
    assert knowledge_base.deleted_papers == ["paper-delete"]
    assert not pdf_path.exists()
    assert get_task(task.task_id) is None


def test_processing_import_cannot_be_deleted(tmp_path, monkeypatch):
    _configure_task_storage(tmp_path, monkeypatch)
    task = create_task("paper-processing", "user-1")
    update_task(task.task_id, status=TaskStatus.PROCESSING, message="处理中")

    async def fake_user_id(*args, **kwargs):
        return "user-1"

    monkeypatch.setattr(papers_api, "get_current_user_id", fake_user_id)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            papers_api.delete_failed_import_task(task.task_id, "Bearer token", FakeDatabase())
        )

    assert exc.value.status_code == 409
    assert get_task(task.task_id).status == TaskStatus.PROCESSING
    remove_task(task.task_id)


def test_worker_dispatches_media_retry_through_the_existing_paper_handler(monkeypatch):
    from app import worker
    from app.job_queue import WorkerJob

    handled = []

    async def fake_handler(job):
        handled.append(job.type)

    monkeypatch.setattr(worker, "handle_paper_process", fake_handler)
    asyncio.run(worker.dispatch_job(WorkerJob.create("paper_media_enhance", {"media_only": True})))

    assert handled == ["paper_media_enhance"]
