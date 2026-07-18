from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil

from src.pdf.text_cleaner import normalize_pdf_text

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except ImportError:
    pytesseract = None

    class TesseractNotFoundError(RuntimeError):
        pass


@dataclass(slots=True, frozen=True)
class OcrReadResult:
    file_path: Path
    text: str
    page_count: int
    language: str


class OcrUnavailableError(RuntimeError):
    pass


def has_meaningful_text(text: str | None, min_text_length: int = 30) -> bool:
    if text is None:
        return False

    normalized = normalize_pdf_text(text)
    if normalized == "":
        return False

    condensed = re.sub(r"\s+", "", normalized)
    alnum_count = sum(1 for character in condensed if character.isalnum())
    return alnum_count >= min_text_length


def _ensure_ocr_dependencies() -> None:
    if pdfium is None:
        raise OcrUnavailableError("Falta la dependencia pypdfium2 para renderizar PDF a imagen.")
    if pytesseract is None:
        raise OcrUnavailableError("Falta la dependencia pytesseract para ejecutar OCR.")


def _configure_tesseract_cmd(tesseract_cmd: str | None = None) -> None:
    if pytesseract is None:
        return

    if tesseract_cmd and tesseract_cmd.strip():
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd.strip()


def _split_language_codes(language: str) -> list[str]:
    codes = [code.strip() for code in (language or "").split("+") if code.strip()]
    return codes or ["eng"]


def _has_required_traineddata(tessdata_dir: Path, language: str) -> bool:
    if not tessdata_dir.exists() or not tessdata_dir.is_dir():
        return False

    return any((tessdata_dir / f"{code}.traineddata").exists() for code in _split_language_codes(language))


def _iter_tessdata_candidates(tesseract_cmd: str | None = None) -> list[Path]:
    raw_candidates: list[Path] = []

    env_tessdata = os.environ.get("TESSDATA_PREFIX", "").strip()
    if env_tessdata:
        raw_candidates.append(Path(env_tessdata))

    command_candidates = [
        tesseract_cmd,
        getattr(pytesseract.pytesseract, "tesseract_cmd", "") if pytesseract is not None else "",
    ]

    for command in command_candidates:
        if not command or not str(command).strip():
            continue

        resolved_command = Path(str(command).strip())
        if not resolved_command.is_absolute():
            resolved_from_path = shutil.which(str(command).strip())
            if resolved_from_path:
                resolved_command = Path(resolved_from_path)

        raw_candidates.append(resolved_command.parent / "tessdata")

    raw_candidates.extend(
        [
            Path(r"C:\Program Files\Tesseract-OCR\tessdata"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tessdata"),
        ]
    )

    candidates: list[Path] = []
    seen: set[str] = set()

    for candidate in raw_candidates:
        candidate_str = str(candidate.resolve(strict=False)).lower()
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        candidates.append(candidate)

    return candidates


def _configure_tessdata_prefix(language: str, tesseract_cmd: str | None = None) -> None:
    for candidate in _iter_tessdata_candidates(tesseract_cmd):
        if not _has_required_traineddata(candidate, language):
            continue

        os.environ["TESSDATA_PREFIX"] = str(candidate)
        return


def ocr_pdf_text(
    pdf_path: str | Path,
    language: str = "spa+eng",
    dpi: int = 200,
    tesseract_cmd: str | None = None,
) -> OcrReadResult:
    _ensure_ocr_dependencies()
    _configure_tesseract_cmd(tesseract_cmd)
    _configure_tessdata_prefix(language, tesseract_cmd)

    path = Path(pdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"No existe el PDF: {path}")

    scale = max(dpi, 72) / 72.0
    page_texts: list[str] = []

    try:
        document = pdfium.PdfDocument(str(path))
    except Exception as error:
        raise OcrUnavailableError(f"No se pudo abrir el PDF para OCR: {path}") from error

    page_count = len(document)

    try:
        for page_index in range(page_count):
            page = document[page_index]
            bitmap = None

            try:
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                extracted_text = pytesseract.image_to_string(image, lang=language)
                page_texts.append(extracted_text or "")
            except TesseractNotFoundError as error:
                raise OcrUnavailableError(
                    "Tesseract no esta instalado o no se encuentra en el sistema."
                ) from error
            except Exception as error:
                raise OcrUnavailableError(
                    f"Fallo el OCR en la pagina {page_index + 1} de {path.name}"
                ) from error
            finally:
                if bitmap is not None and hasattr(bitmap, "close"):
                    bitmap.close()
                if hasattr(page, "close"):
                    page.close()
    finally:
        if hasattr(document, "close"):
            document.close()

    cleaned_text = normalize_pdf_text("\n\n".join(page_texts))
    return OcrReadResult(
        file_path=path,
        text=cleaned_text,
        page_count=page_count,
        language=language,
    )
