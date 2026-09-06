"""Trusted task scope for the incumbent Lead loop, not a second agent runtime."""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

ALIASES = {'get_paper_metadata': 'paper.get_metadata', 'list_paper_sections': 'paper.get_outline',
           'search_paper_content': 'paper.search_content'}
TASK_TYPES = {'DISCOVER', 'IMPORT_PAPER', 'READ_PAPER', 'BUILD_EVIDENCE', 'WRITE_SECTION', 'AUDIT_DRAFT'}


@dataclass(frozen=True)
class TaskScope:
    task_id: str
    task_type: str
    project_id: str
    user_id: str
    paper_ids: frozenset[str]
    allowed_tools: frozenset[str]
    max_tool_calls: int
    max_model_calls: int
    checkpoint: Callable[[str, dict[str, Any]], Awaitable[None]]

    def check(self, tool, args, tool_calls):
        if self.task_type not in TASK_TYPES:
            raise PermissionError('TASK_TYPE_FORBIDDEN')
        if ALIASES.get(tool, tool) not in self.allowed_tools:
            raise PermissionError('TASK_TOOL_FORBIDDEN')
        if tool_calls > self.max_tool_calls:
            raise PermissionError('TASK_TOOL_BUDGET_EXCEEDED')
        def inspect(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'paper_id' and item not in self.paper_ids:
                        raise PermissionError('TASK_PAPER_FORBIDDEN')
                    if key == 'project_id' and item != self.project_id:
                        raise PermissionError('TASK_PROJECT_FORBIDDEN')
                    if key == 'user_id' and item != self.user_id:
                        raise PermissionError('TASK_USER_FORBIDDEN')
                    if key in {'evidence_id', 'task_id', 'execution_id'}:
                        raise PermissionError('TASK_RESOURCE_FORBIDDEN')
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)
        inspect(args)
