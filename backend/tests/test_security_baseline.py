import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import papers
from app.api import auth
from app.api import dependencies
from app.api.auth import (
    DEFAULT_ADMIN_USERNAME,
    UserCreate,
    UserPermissionUpdate,
    get_password_hash,
    require_admin,
    verify_password,
)
from app.config import Settings, settings
from app.models.user import User


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


def test_default_admin_password_comes_from_environment():
    configured = Settings(
        DEBUG=True,
        DEFAULT_ADMIN_PASSWORD="test-admin-password",
        _env_file=None,
    )
    assert DEFAULT_ADMIN_USERNAME == "admin"
    assert configured.DEFAULT_ADMIN_PASSWORD == "test-admin-password"


def test_permission_update_only_accepts_known_roles():
    with pytest.raises(ValidationError):
        UserPermissionUpdate(role="owner")


def test_regular_user_cannot_use_admin_dependency():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_admin(SimpleNamespace(role="user")))
    assert exc.value.status_code == 403


def test_current_user_dependency_uses_supplied_database_session(monkeypatch):
    user = SimpleNamespace(id="user-a", is_active=True)

    class Result:
        def scalars(self):
            return self

        def first(self):
            return user

    class Session:
        async def execute(self, _query):
            return Result()

    monkeypatch.setattr(dependencies, "decode_token", lambda _token: {"sub": user.id})
    resolved = asyncio.run(
        dependencies.get_current_user_id("Bearer token", Session())
    )
    assert resolved == user.id


def test_default_admin_bootstrap_is_idempotent(monkeypatch):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with engine.begin() as connection:
            await connection.run_sync(User.__table__.create)
        monkeypatch.setattr(auth, "AsyncSessionLocal", session_factory)
        test_password = "test-admin-password"
        monkeypatch.setattr(settings, "DEFAULT_ADMIN_PASSWORD", test_password)

        await auth.ensure_default_admin()
        await auth.ensure_default_admin()

        async with session_factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(User).where(User.username == "admin")
            )
            admin = await session.scalar(select(User).where(User.username == "admin"))
            assert count == 1
            assert admin is not None
            assert admin.role == "admin"
            assert admin.is_active
            assert verify_password(test_password, admin.password_hash)
        await engine.dispose()

    asyncio.run(run())


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
