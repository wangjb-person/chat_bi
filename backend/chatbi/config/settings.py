"""应用配置：从仓库根目录 .env 加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from chatbi.config.paths import (
    BACKEND_ROOT,
    DEFAULT_CHROMA_DIR,
    DEFAULT_MODEL_CACHE_DIR,
    PROJECT_ROOT,
)


def _env(key: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        raise RuntimeError(f"缺少环境变量 {key}，请在项目根目录 .env 中配置")
    return value


def _resolve_data_path(value: str | None, default: Path) -> str:
    """将相对路径解析为基于 backend 目录的绝对路径。"""
    if not value:
        return str(default.resolve())
    raw = Path(value)
    if raw.is_absolute():
        return str(raw)
    return str((BACKEND_ROOT / raw).resolve())


@dataclass(frozen=True)
class MysqlSettings:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    initial_prompt: str
    persist_directory: str
    embedding_model: str
    model_cache_dir: str
    mysql: MysqlSettings
    flask_port: int
    project_root: Path
    backend_root: Path

    @property
    def templates_dir(self) -> Path:
        return self.backend_root / "templates"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        api_key=_env("OPENAI_API_KEY", required=True),
        base_url=_env(
            "OPENAI_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=_env("LLM_MODEL", "qwen-plus"),
        initial_prompt="你是一位MySQL数据库专家。",
        persist_directory=_resolve_data_path(
            os.getenv("CHROMA_DB_PATH"),
            DEFAULT_CHROMA_DIR,
        ),
        embedding_model=_env(
            "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        ),
        model_cache_dir=_resolve_data_path(
            os.getenv("MODEL_CACHE_DIR"),
            DEFAULT_MODEL_CACHE_DIR,
        ),
        mysql=MysqlSettings(
            host=_env("MYSQL_HOST", "127.0.0.1"),
            port=int(_env("MYSQL_PORT", "3306")),
            user=_env("MYSQL_USER", "root"),
            password=_env("MYSQL_PASSWORD", required=True),
            database=_env("MYSQL_DATABASE", "testDatabase"),
        ),
        flask_port=int(_env("FLASK_PORT", "5000")),
        project_root=PROJECT_ROOT,
        backend_root=BACKEND_ROOT,
    )
