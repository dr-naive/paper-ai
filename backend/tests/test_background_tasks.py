import asyncio

from app.utils.background_tasks import shutdown_background_tasks, spawn_background_task


def test_registered_background_tasks_are_cancelled_on_shutdown():
    async def scenario():
        started = asyncio.Event()

        async def worker():
            started.set()
            await asyncio.sleep(60)

        task = spawn_background_task(worker(), name="test-worker")
        await started.wait()
        await shutdown_background_tasks()
        return task

    task = asyncio.run(scenario())
    assert task.cancelled()
