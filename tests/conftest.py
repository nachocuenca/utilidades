from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import get_settings


@pytest.fixture(autouse=True)
def isolated_settings_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    inbox_dir = data_dir / "inbox"
    export_dir = data_dir / "exports"
    database_path = data_dir / "app.db"

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "Utilidades Facturas Test")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("INBOX_DIR", str(inbox_dir))
    monkeypatch.setenv("EXPORT_DIR", str(export_dir))
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("DEFAULT_PARSER", "generic")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sample_texts_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "sample_texts"


@pytest.fixture
def load_sample_text(sample_texts_dir: Path):
    def _loader(file_name: str) -> str:
        return (sample_texts_dir / file_name).read_text(encoding="utf-8")

    return _loader