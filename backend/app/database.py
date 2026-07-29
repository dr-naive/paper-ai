"""数据库连接和会话管理模块"""
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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all does not add columns to an existing table. Keep this small
        # compatibility migration here until the project adopts Alembic.
        columns = await conn.run_sync(
            lambda sync_conn: {
                column["name"] for column in inspect(sync_conn).get_columns("users")
            }
        )
        if "role" not in columns:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN role "
                    "VARCHAR(20) NOT NULL DEFAULT 'user'"
                )
            )
    print("✅ 数据库表创建完成")


async def close_db():
    await engine.dispose()
    print("👋 数据库连接已关闭")
