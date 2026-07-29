"""Administrator-only system observability API."""

from collections import defaultdict
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.config import BACKEND_DIR
from app.database import get_db
from app.models.chat import AnswerTrace, ChatMessage, ChatSession
from app.models.paper import Paper
from app.models.user import User
from app.redis_client import get_async_redis, redis_health

router = APIRouter(prefix="/api/admin", tags=["admin"])
REPORTS_DIR = BACKEND_DIR / "evals" / "reports"


async def _count(db: AsyncSession, model, *conditions) -> int:
    query = select(func.count()).select_from(model)
    if conditions:
        query = query.where(*conditions)
    return int(await db.scalar(query) or 0)


def _estimate_answer_tokens(text: str | None) -> int:
    """Match the answer workflow's network-free token estimate for old messages."""
    if not text:
        return 0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_words = re.findall(r"[A-Za-z0-9_]+", text)
    punctuation = re.findall(r"[^\w\s\u4e00-\u9fff]", text)
    latin_tokens = sum(max(1, math.ceil(len(word) / 4)) for word in latin_words)
    return chinese + latin_tokens + math.ceil(len(punctuation) / 2)


def _load_latest_report(pattern: str) -> dict[str, Any] | None:
    reports: list[tuple[str, Path, dict[str, Any]]] = []
    for path in REPORTS_DIR.glob(pattern):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            reports.append((str(payload.get("generated_at") or ""), path, payload))
        except (OSError, ValueError, TypeError):
            continue
    if not reports:
        return None
    generated_at, path, payload = max(reports, key=lambda item: item[0])
    return {
        "name": path.stem,
        "generated_at": generated_at or None,
        "summary": payload.get("summary") or {},
    }


@router.get("/dashboard")
async def admin_dashboard(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=6)
    today = datetime(now.year, now.month, now.day)

    users_total = await _count(db, User)
    users_active = await _count(db, User, User.is_active.is_(True))
    users_admin = await _count(db, User, User.role == "admin")
    users_new_7d = await _count(db, User, User.created_at >= seven_days_ago)
    papers_total = await _count(db, Paper)
    papers_7d = await _count(db, Paper, Paper.uploaded_at >= seven_days_ago)
    sessions_total = await _count(db, ChatSession)
    messages_total = await _count(db, ChatMessage)
    messages_today = await _count(db, ChatMessage, ChatMessage.created_at >= today)

    trace_totals = (
        await db.execute(
            select(
                func.count(AnswerTrace.id),
                func.coalesce(func.sum(AnswerTrace.thinking_tokens), 0),
                func.coalesce(func.sum(AnswerTrace.answer_tokens), 0),
                func.avg(AnswerTrace.total_ms),
                func.avg(AnswerTrace.first_token_ms),
                func.avg(AnswerTrace.retrieval_ms),
                func.coalesce(func.sum(AnswerTrace.citation_count), 0),
            )
        )
    ).one()
    successful_traces = await _count(
        db, AnswerTrace, AnswerTrace.status == "completed"
    )
    trace_count = int(trace_totals[0] or 0)

    paper_dates = (
        await db.scalars(
            select(Paper.uploaded_at).where(Paper.uploaded_at >= seven_days_ago)
        )
    ).all()
    message_rows = (
        await db.execute(
            select(ChatMessage.created_at, ChatMessage.answer).where(
                ChatMessage.created_at >= seven_days_ago
            )
        )
    ).all()
    all_answer_texts = (await db.scalars(select(ChatMessage.answer))).all()
    estimated_answer_tokens = sum(
        _estimate_answer_tokens(answer) for answer in all_answer_texts
    )
    trace_rows = (
        await db.execute(
            select(
                AnswerTrace.recorded_at,
                AnswerTrace.thinking_tokens,
                AnswerTrace.answer_tokens,
            ).where(AnswerTrace.recorded_at >= seven_days_ago)
        )
    ).all()
    trend: dict[str, dict[str, int]] = defaultdict(
        lambda: {"papers": 0, "questions": 0, "tokens": 0}
    )
    for offset in range(7):
        trend[(seven_days_ago + timedelta(days=offset)).date().isoformat()]
    for value in paper_dates:
        trend[value.date().isoformat()]["papers"] += 1
    for created_at, answer in message_rows:
        day = created_at.date().isoformat()
        trend[day]["questions"] += 1
        trend[day]["tokens"] += _estimate_answer_tokens(answer)
    for recorded_at, thinking_tokens, _answer_tokens in trace_rows:
        trend[recorded_at.date().isoformat()]["tokens"] += int(thinking_tokens or 0)

    recent_users = (
        await db.scalars(select(User).order_by(User.created_at.desc()).limit(5))
    ).all()
    recent_papers = (
        await db.execute(
            select(Paper, User.username)
            .join(User, User.id == Paper.user_id)
            .order_by(Paper.uploaded_at.desc())
            .limit(5)
        )
    ).all()

    redis_ok = await redis_health()
    worker_ok = False
    if redis_ok:
        try:
            worker_ok = bool(
                await get_async_redis().exists("paperai:worker:heartbeat")
            )
        except Exception:
            worker_ok = False

    return {
        "generated_at": now.isoformat(),
        "system": {
            "database": "healthy",
            "redis": "healthy" if redis_ok else "degraded",
            "worker": "healthy" if worker_ok else "degraded",
        },
        "users": {
            "total": users_total,
            "active": users_active,
            "admins": users_admin,
            "disabled": users_total - users_active,
            "new_7d": users_new_7d,
        },
        "usage": {
            "papers_total": papers_total,
            "papers_7d": papers_7d,
            "sessions_total": sessions_total,
            "questions_total": messages_total,
            "questions_today": messages_today,
        },
        "ai": {
            "answer_runs": trace_count,
            "successful_runs": successful_traces,
            "success_rate": (
                round(successful_traces / trace_count, 4) if trace_count else None
            ),
            "thinking_tokens": int(trace_totals[1] or 0),
            "answer_tokens": estimated_answer_tokens,
            "total_tokens": int((trace_totals[1] or 0) + estimated_answer_tokens),
            "avg_total_ms": round(float(trace_totals[3]), 2)
            if trace_totals[3] is not None
            else None,
            "avg_first_token_ms": round(float(trace_totals[4]), 2)
            if trace_totals[4] is not None
            else None,
            "avg_retrieval_ms": round(float(trace_totals[5]), 2)
            if trace_totals[5] is not None
            else None,
            "citations_total": int(trace_totals[6] or 0),
            "token_count_type": "estimated",
        },
        "trend": [
            {"date": date, **values}
            for date, values in sorted(trend.items())
        ],
        "evaluations": {
            "retrieval": _load_latest_report("retrieval_*.json"),
            "e2e": _load_latest_report("e2e_*scored*.json"),
        },
        "recent": {
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat(),
                }
                for user in recent_users
            ],
            "papers": [
                {
                    "id": paper.id,
                    "title": paper.title,
                    "username": username,
                    "uploaded_at": paper.uploaded_at.isoformat(),
                }
                for paper, username in recent_papers
            ],
        },
    }
