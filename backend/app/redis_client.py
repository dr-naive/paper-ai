"""Shared Redis clients and small resilient storage helpers."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis
import redis.asyncio as async_redis

from app.config import settings

logger = logging.getLogger(__name__)

_async_client: Optional[async_redis.Redis] = None
_sync_client: Optional[redis.Redis] = None


def get_async_redis() -> async_redis.Redis:
    global _async_client
    if _async_client is None:
        _async_client = async_redis.Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
            health_check_interval=30,
        )
    return _async_client


def get_sync_redis() -> redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=1,
            health_check_interval=30,
        )
    return _sync_client


async def initialize_redis() -> bool:
    try:
        await get_async_redis().ping()
        logger.info("✅ Redis 连接成功")
        return True
    except Exception:
        logger.exception("Redis 连接失败，将使用本地降级存储")
        return False


async def close_redis() -> None:
    global _async_client, _sync_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None


async def redis_health() -> bool:
    try:
        return bool(await get_async_redis().ping())
    except Exception:
        return False


async def set_json(key: str, value: Any, ttl_seconds: int) -> bool:
    try:
        await get_async_redis().set(
            key,
            json.dumps(value, ensure_ascii=False),
            ex=ttl_seconds,
        )
        return True
    except Exception:
        logger.warning("Redis 写入失败 key=%s", key, exc_info=True)
        return False


async def get_json(key: str) -> Any:
    try:
        raw = await get_async_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        logger.warning("Redis 读取失败 key=%s", key, exc_info=True)
        return None

