"""FastAPI 主入口模块"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
from app.config import settings
from app.database import init_db, close_db
from app.redis_client import close_redis, get_async_redis, initialize_redis, redis_health
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_allowed_origin(origin: str) -> bool:
    if not origin:
        return False
    if origin in settings.CORS_ORIGINS:
        return True
    # 允许 localhost/127.0.0.1 任意端口
    if re.match(r'^http://localhost:\d+$', origin):
        return True
    if re.match(r'^http://127\.0\.0\.1:\d+$', origin):
        return True
    # 允许局域网 IP 访问（部署后其他电脑访问）
    if re.match(r'^http://\d+\.\d+\.\d+\.\d+:\d+$', origin):
        return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    logger.info("✅ 数据库初始化完成")
    await initialize_redis()
    yield
    from app.utils.background_tasks import shutdown_background_tasks
    await shutdown_background_tasks()
    await close_redis()
    await close_db()
    logger.info("👋 应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="智能论文精读 AI Agent 系统",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


from app.api.auth import router as auth_router
from app.api.papers import router as papers_router
from app.api.paper_analysis import router as paper_analysis_router
from app.api.chat import router as chat_router

# 导入所有模型，确保 SQLAlchemy 能发现它们
from app.models.user import User
from app.models.paper import (
    DocumentElement,
    Folder,
    Image,
    Note,
    Paper,
    QAPair,
    Section,
    Table,
    TableCell,
    TableStructure,
)
from app.models.chat import ChatSession, ChatMessage, SummaryCache, InterpretCache

app.include_router(auth_router)
app.include_router(papers_router)
app.include_router(paper_analysis_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "智能论文精读 AI Agent 系统"
    }


@app.get("/health")
async def health_check():
    redis_ok = await redis_health()
    worker_ok = False
    if redis_ok:
        try:
            worker_ok = bool(await get_async_redis().exists("paperai:worker:heartbeat"))
        except Exception:
            worker_ok = False
    return {
        "status": "healthy",
        "database": "healthy",
        "redis": "healthy" if redis_ok else "degraded",
        "worker": "healthy" if worker_ok else "degraded",
    }
