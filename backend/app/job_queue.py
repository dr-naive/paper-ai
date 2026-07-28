"""Redis-backed reliable queue shared by the API and worker process."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Optional

from app.redis_client import get_async_redis

logger = logging.getLogger(__name__)

QUEUE_KEY = "paperai:jobs:waiting"
PROCESSING_KEY = "paperai:jobs:processing"
DEAD_LETTER_KEY = "paperai:jobs:failed"


@dataclass
class WorkerJob:
    id: str
    type: str
    payload: dict[str, Any]
    attempts: int = 0
    created_at: float = 0.0

    @classmethod
    def create(
        cls,
        job_type: str,
        payload: dict[str, Any],
        job_id: Optional[str] = None,
    ) -> "WorkerJob":
        return cls(
            id=job_id or str(uuid.uuid4()),
            type=job_type,
            payload=payload,
            created_at=time.time(),
        )

    def dumps(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def loads(cls, raw: str) -> "WorkerJob":
        data = json.loads(raw)
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            payload=dict(data.get("payload") or {}),
            attempts=int(data.get("attempts", 0)),
            created_at=float(data.get("created_at", time.time())),
        )


async def enqueue_job(
    job_type: str,
    payload: dict[str, Any],
    *,
    job_id: Optional[str] = None,
) -> WorkerJob:
    job = WorkerJob.create(job_type, payload, job_id)
    await get_async_redis().lpush(QUEUE_KEY, job.dumps())
    logger.info("Worker 任务已入队 job_id=%s type=%s", job.id, job.type)
    return job


async def reserve_job(timeout_seconds: int = 1) -> tuple[WorkerJob, str] | None:
    raw = await get_async_redis().brpoplpush(
        QUEUE_KEY,
        PROCESSING_KEY,
        timeout=timeout_seconds,
    )
    if not raw:
        return None
    return WorkerJob.loads(raw), raw


async def acknowledge_job(raw: str) -> None:
    await get_async_redis().lrem(PROCESSING_KEY, 1, raw)


async def fail_or_retry_job(job: WorkerJob, raw: str, max_attempts: int = 2) -> None:
    client = get_async_redis()
    await client.lrem(PROCESSING_KEY, 1, raw)
    job.attempts += 1
    if job.attempts <= max_attempts:
        await client.lpush(QUEUE_KEY, job.dumps())
        logger.warning(
            "Worker 任务重试 job_id=%s type=%s attempts=%d",
            job.id,
            job.type,
            job.attempts,
        )
    else:
        await client.lpush(DEAD_LETTER_KEY, job.dumps())
        logger.error(
            "Worker 任务进入失败队列 job_id=%s type=%s",
            job.id,
            job.type,
        )


async def recover_processing_jobs() -> int:
    client = get_async_redis()
    recovered = 0
    while True:
        raw = await client.rpoplpush(PROCESSING_KEY, QUEUE_KEY)
        if raw is None:
            break
        recovered += 1
    if recovered:
        logger.warning("回收 %d 个未确认 Worker 任务", recovered)
    return recovered
