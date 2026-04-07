from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from config.settings import get_settings
from src.pdf.ocr import OcrUnavailableError, has_meaningful_text, ocr_pdf_text
from src.pdf.text_cleaner import normalize_pdf_text


@dataclass(slots=True, frozen=True)
class PdfReadResult:
    file_path: Path
    text: str
    page_count: int
    extractor: str


def _read_with_pdfplumber(pdf_path: Path) -> tuple[str, int]:
    pages_text: list[str] = []

    with pdfplumber.open(pdf_path) as pdf_document:
        page_count = len(pdf_document.pages)

        for page in pdf_document.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)

    return "\n\n".join(pages_text), page_count


def _read_with_pypdf(pdf_path: Path) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    pages_text: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages_text.append(page_text)

    return "\n\n".join(pages_text), len(reader.pages)


def _pick_best_text_candidate(candidates: list[PdfReadResult]) -> PdfReadResult | None:
    if not candidates:
        return None

    ordered = sorted(
        candidates,
        key=lambda item: len(item.text or ""),
        reverse=True,
    )
    return ordered[0]


def read_pdf_text(pdf_path: str | Path, use_ocr_fallback: bool | None = None) -> PdfReadResult:
    path = Path(pdf_path).resolve()
    settings = get_settings()

    if not path.exists():
        raise FileNotFoundError(f"No existe el PDF: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"El archivo no es un PDF: {path}")

    candidates: list[PdfReadResult] = []
    errors: list[Exception] = []

    try:
        raw_text, page_count = _read_with_pdfplumber(path)
        cleaned_text = normalize_pdf_text(raw_text)
        result = PdfReadResult(
            file_path=path,
            text=cleaned_text,
            page_count=page_count,
            extractor="pdfplumber",
        )
        candidates.append(result)

        if has_meaningful_text(cleaned_text, settings.ocr_min_text_length):
            return result
    except Exception as error:
        errors.append(error)

    try:
        raw_text, page_count = _read_with_pypdf(path)
        cleaned_text = normalize_pdf_text(raw_text)
        result = PdfReadResult(
            file_path=path,
            text=cleaned_text,
            page_count=page_count,
            extractor="pypdf",
        )
        candidates.append(result)

        if has_meaningful_text(cleaned_text, settings.ocr_min_text_length):
            return result
    except Exception as error:
        errors.append(error)

    should_use_ocr = settings.ocr_enabled if use_ocr_fallback is None else use_ocr_fallback

    if should_use_ocr:
        try:
            ocr_result = ocr_pdf_text(
                pdf_path=path,
                language=settings.ocr_language,
                dpi=settings.ocr_render_dpi,
                tesseract_cmd=settings.ocr_tesseract_cmd,
            )
            return PdfReadResult(
                file_path=ocr_result.file_path,
                text=ocr_result.text,
                page_count=ocr_result.page_count,
                extractor="ocr",
            )
        except OcrUnavailableError as error:
            best_candidate = _pick_best_text_candidate(candidates)
            if best_candidate is not None and best_candidate.text:
                return best_candidate
            raise RuntimeError(
                f"No se pudo leer el PDF con extractores normales ni OCR: {path}"
            ) from error

    best_candidate = _pick_best_text_candidate(candidates)
    if best_candidate is not None:
        return best_candidate

    if errors:
        raise RuntimeError(f"No se pudo leer el PDF: {path}") from errors[-1]

    raise RuntimeError(f"No se pudo leer el PDF: {path}")


def read_pdf_text_only(pdf_path: str | Path) -> str:
    return read_pdf_text(pdf_path).text