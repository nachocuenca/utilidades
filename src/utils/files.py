from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def ensure_directory(path: str | Path) -> Path:
    resolved_path = Path(path).resolve()
    resolved_path.mkdir(parents=True, exist_ok=True)
    return resolved_path


def is_pdf_file(path: str | Path) -> bool:
    return Path(path).is_file() and Path(path).suffix.lower() == ".pdf"


def list_pdf_files(directory: str | Path, recursive: bool = False) -> list[Path]:
    base_path = Path(directory).resolve()
    if not base_path.exists():
        return []

    pattern = "**/*.pdf" if recursive else "*.pdf"
    files = [path for path in base_path.glob(pattern) if path.is_file()]
    return sorted(files, key=lambda item: item.name.lower())


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", value.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned or "archivo"


def build_export_path(export_dir: str | Path, prefix: str, extension: str) -> Path:
    directory = ensure_directory(export_dir)
    safe_prefix = sanitize_filename(prefix)
    safe_extension = extension.lower().lstrip(".")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return directory / f"{safe_prefix}_{timestamp}.{safe_extension}"