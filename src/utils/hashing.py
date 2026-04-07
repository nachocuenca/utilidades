from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: str | Path, chunk_size: int = 65536) -> str:
    file_path = Path(path).resolve()
    digest = hashlib.sha256()

    with file_path.open("rb") as file_handler:
        while True:
            chunk = file_handler.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_hash(value: str, length: int = 12) -> str:
    if length <= 0:
        raise ValueError("length debe ser mayor que cero")
    return value[:length]