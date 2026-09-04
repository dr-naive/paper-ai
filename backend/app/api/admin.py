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


# ==================== 链路追踪:列表 + 详情 ====================

@router.get("/traces")
async def list_traces(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,          # completed / failed
    user_id: str | None = None,
    min_total_ms: float | None = None,  # 只看慢请求,如 min_total_ms=5000
    max_age_days: int = 7,
):
    """链路追踪列表:最近 N 天的 AnswerTrace,支持按状态/用户/耗时筛选。

    带分位数统计(P50/P90/P95 first_token_ms + total_ms),免看日志即可发现长尾问题。
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=max(1, max_age_days))

    where = [AnswerTrace.recorded_at >= cutoff]
    if status:
        where.append(AnswerTrace.status == status)
    if user_id:
        where.append(AnswerTrace.user_id == user_id)
    if min_total_ms:
        where.append(AnswerTrace.total_ms >= min_total_ms)

    total = (await db.execute(
        select(func.count()).select_from(AnswerTrace).where(*where)
    )).scalar() or 0

    rows = (await db.execute(
        select(
            AnswerTrace.trace_id,
            AnswerTrace.task_id,
            AnswerTrace.user_id,
            AnswerTrace.session_id,
            AnswerTrace.status,
            AnswerTrace.total_ms,
            AnswerTrace.first_token_ms,
            AnswerTrace.retrieval_ms,
            AnswerTrace.thinking_tokens,
            AnswerTrace.answer_tokens,
            AnswerTrace.model_calls,
            AnswerTrace.retry_count,
            AnswerTrace.citation_count,
            AnswerTrace.recorded_at,
            User.username,
        )
        .join(User, User.id == AnswerTrace.user_id, isouter=True)
        .where(*where)
        .order_by(AnswerTrace.recorded_at.desc())
        .limit(min(max(1, page_size), 100))
        .offset(max(0, (page - 1) * page_size))
    )).all()

    # 分位数统计(同一个 where 条件下的全量数据)
    percentile_cols = (
        select(
            AnswerTrace.first_token_ms,
            AnswerTrace.total_ms,
        )
        .where(*where)
        .order_by(AnswerTrace.recorded_at.asc())
    )
    percentile_rows = [(r.first_token_ms, r.total_ms) for r in (await db.execute(percentile_cols)).all()]

    def _pct(values: list[float], p: float) -> float | None:
        vals = sorted(v for v in values if v is not None)
        if not vals:
            return None
        idx = min(len(vals) - 1, int(round((len(vals) - 1) * p)))
        return round(float(vals[idx]), 2)

    first_tokens = [ft for ft, _ in percentile_rows]
    totals = [t for _, t in percentile_rows]

    items = []
    for row in rows:
        items.append({
            "trace_id": row.trace_id,
            "task_id": row.task_id,
            "user_id": row.user_id,
            "username": row.username,
            "session_id": row.session_id,
            "status": row.status,
            "total_ms": row.total_ms and round(float(row.total_ms), 2),
            "first_token_ms": row.first_token_ms and round(float(row.first_token_ms), 2),
            "retrieval_ms": row.retrieval_ms and round(float(row.retrieval_ms), 2),
            "thinking_tokens": int(row.thinking_tokens or 0),
            "answer_tokens": int(row.answer_tokens or 0),
            "model_calls": int(row.model_calls or 0),
            "retry_count": int(row.retry_count or 0),
            "citation_count": int(row.citation_count or 0),
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        })

    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": items,
        "stats": {
            "count": len(percentile_rows),
            "first_token_ms": {
                "p50": _pct(first_tokens, 0.5),
                "p90": _pct(first_tokens, 0.9),
                "p95": _pct(first_tokens, 0.95),
            },
            "total_ms": {
                "p50": _pct(totals, 0.5),
                "p90": _pct(totals, 0.9),
                "p95": _pct(totals, 0.95),
            },
        },
    }


@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """单条 trace 详情:DB AnswerTrace + Redis agent_trace(含 tool_calls 明细)。

    失败时带 failure_stage + 失败原因,免看日志即可定位问题。
    """
    from app.redis_utils import get_json
    from app.worker import ANSWER_TRACE_PREFIX

    row = (await db.execute(
        select(
            AnswerTrace,
            User.username,
        )
        .join(User, User.id == AnswerTrace.user_id, isouter=True)
        .where(AnswerTrace.trace_id == trace_id)
    )).one_or_none()
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="trace 不存在")

    trace, username = row

    # 从 Redis 取 agent_trace(含 tool_calls 明细 + intent_analysis + fast_path)
    redis_payload = await get_json(f"{ANSWER_TRACE_PREFIX}{trace_id}")

    # 会话 + 问题/回答内容(调试失败时最需要)
    session_title = None
    question = None
    answer = None
    if trace.session_id:
        msg_row = (await db.execute(
            select(ChatSession.title, ChatMessage.question, ChatMessage.answer)
            .join(ChatMessage, ChatMessage.session_id == ChatSession.id, isouter=True)
            .where(ChatSession.id == trace.session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )).one_or_none()
        if msg_row:
            session_title, question, answer = msg_row

    def _fmt(val, digits=2):
        return None if val is None else round(float(val), digits)

    return {
        # AnswerTrace 字段
        "trace_id": trace.trace_id,
        "task_id": trace.task_id,
        "user": {"id": trace.user_id, "username": username},
        "session": {"id": trace.session_id, "title": session_title},
        "status": trace.status,
        "total_ms": _fmt(trace.total_ms),
        "first_token_ms": _fmt(trace.first_token_ms),
        "retrieval_ms": _fmt(trace.retrieval_ms),
        "thinking_tokens": int(trace.thinking_tokens or 0),
        "answer_tokens": int(trace.answer_tokens or 0),
        "citation_count": int(trace.citation_count or 0),
        "model_calls": int(trace.model_calls or 0),
        "retry_count": int(trace.retry_count or 0),
        "used_second_pass": bool(trace.used_second_pass),
        "recorded_at": trace.recorded_at.isoformat() if trace.recorded_at else None,
        # 对话内容
        "question": question,
        "answer": answer and (answer[:4000] + ("…" if len(answer) > 4000 else "")),
        # Redis 里的 agent_trace 明细
        "retrieval_query": redis_payload.get("retrieval_query") if redis_payload else None,
        "retrieval_top_k": redis_payload.get("retrieval_top_k") if redis_payload else None,
        "intent": redis_payload.get("intent") if redis_payload else None,
        "iterations": redis_payload.get("iterations") if redis_payload else None,
        "tool_calls": redis_payload.get("tool_calls") if redis_payload else None,
        "intent_analysis": redis_payload.get("intent_analysis") if redis_payload else None,
        "fast_path": redis_payload.get("fast_path") if redis_payload else None,
        "failure_stage": redis_payload.get("failure_stage") if redis_payload else None,
        "worker_retry_count": redis_payload.get("worker_retry_count") if redis_payload else None,
    }
