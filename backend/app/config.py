"""应用程序配置模块"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from functools import lru_cache
from typing import Any, Optional, List
from pathlib import Path

# 【修正路径计算】根据你的实际文件位置重新计算
CURRENT_DIR = Path(__file__).resolve().parent       # .../backend/app
BACKEND_DIR = CURRENT_DIR.parent                    # .../backend
PROJECT_ROOT = BACKEND_DIR.parent                   # .../myAgent (根目录)

# 优先找 backend 目录下的 .env，如果没有，就找项目根目录的
ENV_FILE_PATH = BACKEND_DIR / ".env" if (BACKEND_DIR / ".env").exists() else PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    """应用配置类"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    APP_NAME: str = "PaperAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    DATABASE_URL: str = "postgresql+asyncpg://postgres:paperai-local@localhost:5432/paperai"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ANSWER_TASK_TTL_SECONDS: int = 24 * 60 * 60
    REDIS_UPLOAD_TASK_TTL_SECONDS: int = 7 * 24 * 60 * 60
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_RETRIES: int = 2
    VISION_MODEL: str = "qwen-vl-max"
    VISION_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VECTOR_STORE_PATH: str = "./data/vectorstore"
    FILE_STORAGE_PATH: str = "./data/papers"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False
        return bool(value)

    @model_validator(mode="after")
    def validate_security_defaults(self):
        insecure_secret = "your-super-secret-key-change-in-production"
        if not self.DEBUG and (
            self.SECRET_KEY == insecure_secret or len(self.SECRET_KEY) < 32
        ):
            raise ValueError("生产模式必须设置至少 32 字符的 SECRET_KEY")
        if self.LLM_TIMEOUT_SECONDS <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS 必须大于 0")
        if not 0 <= self.LLM_MAX_RETRIES <= 5:
            raise ValueError("LLM_MAX_RETRIES 必须在 0 到 5 之间")
        if self.REDIS_ANSWER_TASK_TTL_SECONDS < 60:
            raise ValueError("REDIS_ANSWER_TASK_TTL_SECONDS 不能小于 60")
        if self.REDIS_UPLOAD_TASK_TTL_SECONDS < 60:
            raise ValueError("REDIS_UPLOAD_TASK_TTL_SECONDS 不能小于 60")
        return self

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()


def mask_secret(value: Optional[str]) -> str:
    if not value:
        return "未设置"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"

# 【解决缓冲问题】加上 flush=True，强制立刻写入日志文件！
print("="*50, flush=True)
print(f"🔥 [Config] 当前 config.py 绝对路径: {Path(__file__).resolve()}", flush=True)
print(f"🔥 [Config] 尝试加载 .env 绝对路径: {ENV_FILE_PATH}", flush=True)
print(f"🔥 [Config] 该文件是否存在: {ENV_FILE_PATH.exists()}", flush=True)
print(f"🔥 [Config] 读取到的 LLM_PROVIDER: {settings.LLM_PROVIDER}", flush=True)
print(f"🔥 [Config] 读取到的 OPENAI_BASE_URL: {settings.OPENAI_BASE_URL}", flush=True)
print("="*50, flush=True)
