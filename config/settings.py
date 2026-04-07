from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return int(raw_value.strip())


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_name: str
    project_root: Path
    data_dir: Path
    inbox_dir: Path
    export_dir: Path
    database_path: Path
    default_parser: str
    streamlit_server_address: str
    streamlit_server_port: int


def ensure_runtime_directories(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_environment()

    settings = Settings(
        app_env=_get_env("APP_ENV", "local"),
        app_name=_get_env("APP_NAME", "Utilidades Facturas"),
        project_root=PROJECT_ROOT,
        data_dir=_resolve_path(_get_env("DATA_DIR", "data")),
        inbox_dir=_resolve_path(_get_env("INBOX_DIR", "data/inbox")),
        export_dir=_resolve_path(_get_env("EXPORT_DIR", "data/exports")),
        database_path=_resolve_path(_get_env("DATABASE_PATH", "data/app.db")),
        default_parser=_get_env("DEFAULT_PARSER", "generic"),
        streamlit_server_address=_get_env("STREAMLIT_SERVER_ADDRESS", "127.0.0.1"),
        streamlit_server_port=_get_int_env("STREAMLIT_SERVER_PORT", 8501),
    )

    ensure_runtime_directories(settings)
    return settings