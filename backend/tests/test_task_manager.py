from app.api.papers import _get_paper_media_state, recover_incomplete_paper_tasks
from app.utils.task_manager import TaskStatus, create_task, get_task, list_tasks, update_task


def test_ready_status_round_trips_through_task_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = create_task("paper-1", "user-1")

    update_task(
        task.task_id,
        status=TaskStatus.READY,
        progress=100,
        message="论文已可用，图表继续后台增强",
    )
    loaded = get_task(task.task_id)

    assert loaded is not None
    assert loaded.status == TaskStatus.READY
    assert loaded.progress == 100


def test_paper_media_state_tracks_ready_and_completion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = create_task("paper-2", "user-1")

    update_task(task.task_id, status=TaskStatus.READY, details={"media_status": "processing"})
    assert _get_paper_media_state("paper-2")["media_status"] == "processing"

    update_task(task.task_id, status=TaskStatus.COMPLETED, details={"media_status": "completed"})
    state = _get_paper_media_state("paper-2")
    assert state["media_status"] == "completed"
    assert state["media_message"] == "图表已完成"


def test_paper_without_task_is_treated_as_legacy_complete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert _get_paper_media_state("legacy-paper") == {
        "media_status": "completed",
        "media_message": "图表已完成",
    }


def test_task_writes_are_atomic_and_listable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = create_task("paper-atomic", "user-1")
    update_task(task.task_id, status=TaskStatus.PROCESSING, progress=42)

    assert not (tmp_path / "data/tasks/task_paper-atomic.json.tmp").exists()
    assert [item.task_id for item in list_tasks({TaskStatus.PROCESSING})] == [task.task_id]


def test_ready_task_is_kept_usable_after_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = create_task("paper-ready", "user-1")
    update_task(
        task.task_id,
        status=TaskStatus.READY,
        progress=100,
        details={"media_status": "processing"},
    )

    assert recover_incomplete_paper_tasks() == 0
    recovered = get_task(task.task_id)
    assert recovered.status == TaskStatus.COMPLETED
    assert recovered.details["media_status"] == "interrupted"
    assert "正文可用" in recovered.message
    assert _get_paper_media_state("paper-ready")["media_message"] == "图表增强因服务重启中断"
