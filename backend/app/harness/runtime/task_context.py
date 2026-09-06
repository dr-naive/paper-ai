"""Request-local capability accounting shared by existing executors/LLM client."""
from contextvars import ContextVar

current_task_id = ContextVar('research_task_id', default=None)
current_task_progress = ContextVar('research_task_progress', default=None)


async def account(stage, data=None):
    callback = current_task_progress.get()
    if callback is not None:
        await callback(stage, data or {})
