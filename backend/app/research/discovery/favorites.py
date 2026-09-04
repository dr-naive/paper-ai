"""Project-scoped persistence for Literature Discovery favorites."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ResearchProject

from .schemas import DiscoveryFavoriteRequest, DiscoveryFavoriteResponse


DISCOVERY_FAVORITES_KEY = "discovery_favorites"
MAX_DISCOVERY_FAVORITES = 200
SUPPORTED_FAVORITE_SOURCES = {"semantic_scholar", "crossref", "arxiv"}


class FavoriteSourceError(ValueError):
    """Raised when a client tries to persist an unrecognized provider source."""


def favorite_key(source: str, source_paper_id: str) -> str:
    return f"{source.strip().casefold()}:{source_paper_id.strip().casefold()}"


def _records(project: ResearchProject) -> list[dict[str, Any]]:
    preferences = project.preferences if isinstance(project.preferences, dict) else {}
    raw = preferences.get(DISCOVERY_FAVORITES_KEY) or []
    return [dict(item) for item in raw if isinstance(item, dict)]


def favorite_keys(project: ResearchProject) -> set[str]:
    return {
        favorite_key(str(item.get("source") or ""), str(item.get("source_paper_id") or ""))
        for item in _records(project)
        if item.get("source") and item.get("source_paper_id")
    }


def _validate_source(source: str) -> str:
    normalized = source.strip().casefold()
    if normalized not in SUPPORTED_FAVORITE_SOURCES:
        raise FavoriteSourceError(f"不支持收藏来源: {source}")
    return normalized


def _response(record: dict[str, Any]) -> DiscoveryFavoriteResponse:
    return DiscoveryFavoriteResponse.model_validate(record)


async def save_favorite(
    db: AsyncSession,
    project: ResearchProject,
    request: DiscoveryFavoriteRequest,
) -> DiscoveryFavoriteResponse:
    source = _validate_source(request.source)
    source_paper_id = request.source_paper_id.strip()
    key = favorite_key(source, source_paper_id)
    records = _records(project)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    existing = next(
        (item for item in records if favorite_key(str(item.get("source") or ""), str(item.get("source_paper_id") or "")) == key),
        None,
    )
    record = request.model_dump(mode="json")
    record.update(
        {
            "source": source,
            "source_paper_id": source_paper_id,
            "favorite_id": str(existing.get("favorite_id")) if existing else str(uuid4()),
            "saved_at": str(existing.get("saved_at") or now) if existing else now,
            "download_available": bool(request.pdf_url),
            "import_available": source == "arxiv" and bool(request.pdf_url),
        }
    )
    if existing:
        records = [record if item is existing else item for item in records]
    else:
        records.append(record)
    preferences = dict(project.preferences or {})
    preferences[DISCOVERY_FAVORITES_KEY] = records[-MAX_DISCOVERY_FAVORITES:]
    project.preferences = preferences
    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return _response(record)


async def remove_favorite(
    db: AsyncSession,
    project: ResearchProject,
    favorite_id: str,
) -> bool:
    records = _records(project)
    remaining = [item for item in records if str(item.get("favorite_id") or "") != favorite_id]
    if len(remaining) == len(records):
        return False
    preferences = dict(project.preferences or {})
    preferences[DISCOVERY_FAVORITES_KEY] = remaining
    project.preferences = preferences
    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return True


def list_favorites(project: ResearchProject) -> list[DiscoveryFavoriteResponse]:
    result: list[DiscoveryFavoriteResponse] = []
    for record in _records(project):
        try:
            result.append(_response(record))
        except Exception:
            continue
    return result
