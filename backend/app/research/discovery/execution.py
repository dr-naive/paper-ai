"""Short-lived Redis state for user-visible Literature Discovery progress."""
from __future__ import annotations

from typing import Any

from app.redis_client import get_json, set_json


DISCOVERY_EXECUTION_PREFIX = "paperai:discovery-execution:"
DISCOVERY_EXECUTION_TTL_SECONDS = 24 * 60 * 60


def execution_key(execution_id: str) -> str:
    return f"{DISCOVERY_EXECUTION_PREFIX}{execution_id}"


async def save_execution_state(execution_id: str, state: dict[str, Any]) -> bool:
    return await set_json(execution_key(execution_id), state, DISCOVERY_EXECUTION_TTL_SECONDS)


async def load_execution_state(execution_id: str) -> dict[str, Any] | None:
    value = await get_json(execution_key(execution_id))
    return value if isinstance(value, dict) else None
