"""Database connection, session management, and schema readiness checks."""
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings
from typing import AsyncGenerator
import os

settings = get_settings()

if "sqlite" in settings.DATABASE_URL:
    database_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    database_dir = os.path.dirname(database_path)
    if database_dir:
        os.makedirs(database_dir, exist_ok=True)
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
else:
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class DatabaseSchemaError(RuntimeError):
    """Raised when the database has not been migrated to the required revision."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def verify_schema_revision():
    """Validate schema revision; runtime startup never performs production DDL."""
    if engine.dialect.name == "sqlite" and settings.ALLOW_DEV_SCHEMA_CREATE:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
            if not tables:
                await conn.run_sync(Base.metadata.create_all)
                return

    async with engine.connect() as conn:
        has_version_table = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table("alembic_version")
        )
        if not has_version_table:
            raise DatabaseSchemaError(
                "数据库尚未建立 Alembic 版本。请先执行 `cd backend && alembic upgrade head`；"
                "已有数据库必须先完成 schema preflight，再执行 alembic stamp。"
            )
        current_revision = await conn.scalar(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        )

    from app.infrastructure.db.migrations import ALEMBIC_HEAD_REVISION

    if current_revision != ALEMBIC_HEAD_REVISION:
        raise DatabaseSchemaError(
            f"数据库版本 {current_revision or 'unknown'} 与应用要求的 "
            f"{ALEMBIC_HEAD_REVISION} 不一致，请执行 Alembic migration。"
        )


async def init_db():
    """Backward-compatible startup entrypoint for schema readiness."""
    await verify_schema_revision()


async def close_db():
    await engine.dispose()
