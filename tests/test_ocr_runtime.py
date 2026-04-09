from __future__ import annotations

import os
from pathlib import Path

from src.pdf.ocr import _configure_tessdata_prefix


def test_configure_tessdata_prefix_recovers_from_invalid_env(monkeypatch, tmp_path: Path) -> None:
    tessdata_dir = tmp_path / "Tesseract-OCR" / "tessdata"
    tessdata_dir.mkdir(parents=True)
    (tessdata_dir / "spa.traineddata").write_text("", encoding="utf-8")
    (tessdata_dir / "eng.traineddata").write_text("", encoding="utf-8")

    tesseract_cmd = tessdata_dir.parent / "tesseract.exe"
    tesseract_cmd.write_text("", encoding="utf-8")

    monkeypatch.setenv("TESSDATA_PREFIX", str(tmp_path / "invalid-tessdata"))

    _configure_tessdata_prefix("spa+eng", str(tesseract_cmd))

    assert Path(os.environ["TESSDATA_PREFIX"]).resolve() == tessdata_dir.resolve()
