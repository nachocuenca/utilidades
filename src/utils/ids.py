from __future__ import annotations

import re

POSTAL_CODE_PATTERN = re.compile(r"\b(\d{5})\b")
SPANISH_TAX_ID_PATTERN = re.compile(
    r"\b([ABCDEFGHJNPQRSUVWXYZ]?\d{7,8}[A-Z0-9])\b",
    re.IGNORECASE,
)
STRUCTURED_SPANISH_TAX_ID_PATTERN = re.compile(
    r"^(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z]|[KLM]\d{7}[A-Z]|[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J])$",
    re.IGNORECASE,
)
KNOWN_TAX_ID_PREFIXES = (
    "CIF",
    "NIF",
    "DNI",
    "NIE",
    "VAT",
    "TAXID",
    "IDFISCAL",
    "ES",
)


def compact_identifier(value: str | None) -> str | None:
    if value is None:
        return None

    compacted = re.sub(r"[\s\-_/.:]", "", value.strip()).upper()
    return compacted or None


def _iter_tax_id_variants(value: str) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()
    candidate = value

    while candidate and candidate not in seen:
        seen.add(candidate)
        variants.append(candidate)

        next_candidate: str | None = None
        for prefix in KNOWN_TAX_ID_PREFIXES:
            if candidate.startswith(prefix) and len(candidate) > len(prefix):
                next_candidate = candidate[len(prefix):]
                break

        if next_candidate is None:
            break

        candidate = next_candidate

    return variants


def _is_structured_spanish_tax_id(value: str) -> bool:
    return STRUCTURED_SPANISH_TAX_ID_PATTERN.fullmatch(value) is not None


def normalize_tax_id(value: str | None) -> str | None:
    compacted = compact_identifier(value)
    if compacted is None:
        return None

    for candidate in _iter_tax_id_variants(compacted):
        if _is_structured_spanish_tax_id(candidate):
            return candidate

    return None


def is_probable_tax_id(value: str | None) -> bool:
    return normalize_tax_id(value) is not None


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
