from __future__ import annotations

import re

POSTAL_CODE_PATTERN = re.compile(r"\b(\d{5})\b")
SPANISH_TAX_ID_PATTERN = re.compile(
    r"\b([ABCDEFGHJNPQRSUVWXYZ]?\d{7,8}[A-Z0-9])\b",
    re.IGNORECASE,
)


def compact_identifier(value: str | None) -> str | None:
    if value is None:
        return None

    compacted = re.sub(r"[\s\-_/.:]", "", value.strip()).upper()
    return compacted or None


def normalize_tax_id(value: str | None) -> str | None:
    compacted = compact_identifier(value)
    if compacted is None:
        return None
    return compacted


def is_probable_tax_id(value: str | None) -> bool:
    normalized = normalize_tax_id(value)
    if normalized is None:
        return False

    if len(normalized) < 6 or len(normalized) > 16:
        return False

    if normalized.isdigit():
        return False

    if normalized.count(" ") > 0:
        return False

    if re.fullmatch(r"\d{8}[A-Z]", normalized):
        return True

    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", normalized):
        return True

    if re.fullmatch(r"[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]", normalized):
        return True

    if re.fullmatch(r"[A-Z0-9]{6,16}", normalized):
        has_digit = any(character.isdigit() for character in normalized)
        has_letter = any(character.isalpha() for character in normalized)
        return has_digit and has_letter

    return False


def extract_tax_ids(text: str) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()

    for raw_match in SPANISH_TAX_ID_PATTERN.findall(text):
        normalized = normalize_tax_id(raw_match)
        if normalized is None or not is_probable_tax_id(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        matches.append(normalized)

    return matches


def normalize_postal_code(value: str | None) -> str | None:
    if value is None:
        return None

    match = POSTAL_CODE_PATTERN.search(value)
    if not match:
        return None

    return match.group(1)


def extract_postal_codes(text: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()

    for match in POSTAL_CODE_PATTERN.finditer(text):
        postal_code = match.group(1)
        if postal_code in seen:
            continue
        seen.add(postal_code)
        results.append(postal_code)

    return results