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


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise ValueError(f"Valor booleano no valido para {name}: {raw_value}")


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
    ocr_enabled: bool
    ocr_language: str
    ocr_render_dpi: int
    ocr_min_text_length: int
    ocr_tesseract_cmd: str
    force_default_customer_for_facturas: bool
    default_customer_name: str
    default_customer_tax_id: str
    default_customer_postal_code: str
    openai_api_key: str
    openai_model: str
    openai_fallback_enabled: bool
    openai_fallback_min_confidence: float
    openai_timeout: int


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
        ocr_enabled=_get_bool_env("OCR_ENABLED", False),
        ocr_language=_get_env("OCR_LANGUAGE", "spa+eng"),
        ocr_render_dpi=_get_int_env("OCR_RENDER_DPI", 200),
        ocr_min_text_length=_get_int_env("OCR_MIN_TEXT_LENGTH", 30),
        ocr_tesseract_cmd=_get_env("OCR_TESSERACT_CMD", ""),
        force_default_customer_for_facturas=_get_bool_env(
            "FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS",
            False,
        ),
        default_customer_name=_get_env("DEFAULT_CUSTOMER_NAME", ""),
        default_customer_tax_id=_get_env("DEFAULT_CUSTOMER_TAX_ID", ""),
        default_customer_postal_code=_get_env("DEFAULT_CUSTOMER_POSTAL_CODE", ""),
        openai_api_key=_get_env("OPENAI_API_KEY", ""),
        openai_model=_get_env("OPENAI_MODEL", "gpt-4o"),
        openai_fallback_enabled=_get_bool_env("OPENAI_FALLBACK_ENABLED", False),
        openai_fallback_min_confidence=float(_get_env("OPENAI_FALLBACK_MIN_CONFIDENCE", "0.7")),
        openai_timeout=_get_int_env("OPENAI_TIMEOUT", 40),
    )

    ensure_runtime_directories(settings)
    return settings
