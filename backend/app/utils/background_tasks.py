"""Small in-process task registry with visible failures and clean shutdown."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)
_running_tasks: set[asyncio.Task] = set()


def spawn_background_task(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _running_tasks.add(task)

    def completed(done: asyncio.Task) -> None:
        _running_tasks.discard(done)
        if done.cancelled():
            logger.info("后台任务已取消: %s", done.get_name())
            return
        error = done.exception()
        if error is not None:
            logger.exception(
                "后台任务异常退出: %s",
                done.get_name(),
                exc_info=(type(error), error, error.__traceback__),
            )

    task.add_done_callback(completed)
    return task


async def shutdown_background_tasks() -> None:
    tasks = list(_running_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
