import asyncio

from app.job_queue import (
    PROCESSING_KEY,
    QUEUE_KEY,
    acknowledge_job,
    enqueue_job,
    recover_processing_jobs,
    reserve_job,
)


class FakeRedis:
    def __init__(self):
        self.lists = {}

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    async def brpoplpush(self, source, destination, timeout=0):
        values = self.lists.setdefault(source, [])
        if not values:
            return None
        value = values.pop()
        self.lists.setdefault(destination, []).insert(0, value)
        return value

    async def lrem(self, key, count, value):
        values = self.lists.setdefault(key, [])
        if value not in values:
            return 0
        values.remove(value)
        return 1

    async def rpoplpush(self, source, destination):
        values = self.lists.setdefault(source, [])
        if not values:
            return None
        value = values.pop()
        self.lists.setdefault(destination, []).insert(0, value)
        return value


def test_worker_queue_reserves_and_acknowledges(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr("app.job_queue.get_async_redis", lambda: redis)

    async def run():
        created = await enqueue_job(
            "chat_answer",
            {"question": "测试"},
            job_id="job-1",
        )
        reserved = await reserve_job(timeout_seconds=0)
        assert reserved is not None
        job, raw = reserved
        await acknowledge_job(raw)
        return created, job

    created, reserved = asyncio.run(run())

    assert created.id == "job-1"
    assert reserved.id == "job-1"
    assert reserved.type == "chat_answer"
    assert redis.lists[QUEUE_KEY] == []
    assert redis.lists[PROCESSING_KEY] == []


def test_worker_queue_recovers_unacknowledged_jobs(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr("app.job_queue.get_async_redis", lambda: redis)

    async def run():
        await enqueue_job("paper_process", {"paper_id": "paper-1"}, job_id="job-2")
        reserved = await reserve_job(timeout_seconds=0)
        assert reserved is not None
        return await recover_processing_jobs()

    recovered = asyncio.run(run())

    assert recovered == 1
    assert len(redis.lists[QUEUE_KEY]) == 1
    assert redis.lists[PROCESSING_KEY] == []
