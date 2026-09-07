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
import time

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
    logger.info("✅ 数据库迁移版本校验完成")
    from app.api.auth import ensure_default_admin
    await ensure_default_admin()
    logger.info("✅ 默认管理员账户已就绪")
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


def _is_pdf_transport_request(request: Request) -> bool:
    path = request.url.path
    return (
        request.method == "GET"
        and path.startswith("/api/v1/papers/")
        and path.endswith("/pdf")
    )


@app.middleware("http")
async def add_pdf_request_timing(request: Request, call_next):
    """Expose and log the server-side portion of PDF request latency.

    The browser reports first-page/render/cache timings separately. This
    middleware covers API/auth/file preparation time and deliberately logs the
    path without query parameters so legacy token query strings are not copied
    into the performance log.
    """
    is_pdf_request = _is_pdf_transport_request(request)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        if is_pdf_request:
            logger.exception("pdf_request_failed path=%s", request.url.path)
        raise

    if is_pdf_request:
        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["Server-Timing"] = f"pdf-app;dur={duration_ms:.1f}"
        logger.info(
            "pdf_request path=%s status=%s range=%s response_bytes=%s app_ms=%.1f",
            request.url.path,
            response.status_code,
            "yes" if request.headers.get("range") else "no",
            response.headers.get("content-length", "-"),
            duration_ms,
        )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Server-Timing"],
)


from app.api.auth import router as auth_router
from app.api.papers import router as papers_router
from app.api.paper_analysis import router as paper_analysis_router
from app.api.chat import router as chat_router
from app.api.admin import router as admin_router
from app.api.projects import router as projects_router
from app.api.executions import router as executions_router
from app.api.research_items import evidence_router, router as research_items_router
from app.api.documents import router as documents_router
from app.api.discovery import router as discovery_router

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
# 项目/写作产物模型:import 后 Base.metadata.create_all 会自动建表
from app.models.project import ResearchProject, ProjectPaper, WritingArtifact
from app.models.execution import AgentExecution, AgentEvent, ToolCall
from app.models.evaluation import EvaluationRun
from app.models.research import MemoryItem, EvidenceItem
from app.models.document import WritingDocument, DocumentRevision

app.include_router(auth_router)
app.include_router(papers_router)
app.include_router(paper_analysis_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(projects_router)
app.include_router(executions_router)
app.include_router(research_items_router)
app.include_router(evidence_router)
app.include_router(documents_router)
app.include_router(discovery_router)


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
