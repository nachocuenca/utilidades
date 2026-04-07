from __future__ import annotations

import re

from src.utils.ids import is_probable_tax_id, normalize_postal_code

LEADING_LABELS_PATTERN = re.compile(
    r"^(cliente|clienta|raz[oó]n social|empresa|nombre|señor|sra|sr|att|a la atenci[oó]n de)\s*[:\-]\s*",
    re.IGNORECASE,
)

TRAILING_NOISE_PATTERN = re.compile(
    r"\b(nif|cif|dni|nie|cp|c\.?p\.?|iban|tel[eé]fono|telefono|email|e-mail)\b.*$",
    re.IGNORECASE,
)

URL_OR_EMAIL_PATTERN = re.compile(r"(https?://|www\.|@)")
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)


def clean_name_candidate(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    if cleaned == "":
        return None

    cleaned = cleaned.replace("\u00A0", " ")
    cleaned = LEADING_LABELS_PATTERN.sub("", cleaned)
    cleaned = TRAILING_NOISE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -,:;|/")

    return cleaned or None


def is_valid_name_candidate(value: str | None) -> bool:
    cleaned = clean_name_candidate(value)
    if cleaned is None:
        return False

    if len(cleaned) < 3:
        return False

    if URL_OR_EMAIL_PATTERN.search(cleaned):
        return False

    if IBAN_PATTERN.search(cleaned):
        return False

    if is_probable_tax_id(cleaned):
        return False

    if normalize_postal_code(cleaned) == cleaned:
        return False

    if not any(character.isalpha() for character in cleaned):
        return False

    digit_count = sum(1 for character in cleaned if character.isdigit())
    if digit_count > 2:
        return False

    compacted = cleaned.replace(" ", "")
    if compacted.isupper() and len(compacted) <= 2:
        return False

    return True


def pick_best_name(candidates: list[str]) -> str | None:
    valid_candidates: list[str] = []

    for candidate in candidates:
        cleaned = clean_name_candidate(candidate)
        if not is_valid_name_candidate(cleaned):
            continue
        valid_candidates.append(cleaned)

    if not valid_candidates:
        return None

    valid_candidates.sort(key=lambda item: (-len(item), item))
    return valid_candidates[0]