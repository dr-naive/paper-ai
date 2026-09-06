"""Request-local capability accounting shared by existing executors/LLM client."""
from contextvars import ContextVar

current_task_id = ContextVar('research_task_id', default=None)
current_task_skill_id = ContextVar('research_task_skill_id', default=None)
current_task_progress = ContextVar('research_task_progress', default=None)
current_model_call_observer = ContextVar('research_model_call_observer', default=None)
current_agent_tool_observer = ContextVar('research_agent_tool_observer', default=None)


async def account(stage, data=None):
    callback = current_task_progress.get()
    if callback is not None:
        await callback(stage, data or {})


async def observe_model_call(stage, data=None):
    """Notify only the active ResearchTask recorder; legacy paths are no-op."""
    callback = current_model_call_observer.get()
    if callback is not None:
        await callback(stage, data or {})


async def observe_agent_tool(stage, data=None):
    """Record Lead Agent tool calls without making tools own persistence."""
    callback = current_agent_tool_observer.get()
    if callback is not None:
        await callback(stage, data or {})
