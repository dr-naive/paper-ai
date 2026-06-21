import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import papers
from app.api.auth import UserCreate, get_password_hash, verify_password
from app.config import Settings


def test_production_rejects_short_or_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(DEBUG=False, SECRET_KEY="short", _env_file=None)


def test_registration_enforces_minimum_password_length():
    with pytest.raises(ValidationError):
        UserCreate(username="user", email="u@example.com", password="short")


def test_pbkdf2_password_is_not_truncated_at_72_characters():
    first = "a" * 72 + "first"
    second = "a" * 72 + "second"
    password_hash = get_password_hash(first)
    assert verify_password(first, password_hash)
    assert not verify_password(second, password_hash)


def test_task_status_is_hidden_from_other_users(monkeypatch):
    async def current_user(*_args, **_kwargs):
        return "user-a"

    monkeypatch.setattr(papers, "get_current_user_id", current_user)
    monkeypatch.setattr(
        papers,
        "get_task",
        lambda _task_id: SimpleNamespace(user_id="user-b"),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(papers.get_task_status("task-1", "Bearer token"))
    assert exc.value.status_code == 404
