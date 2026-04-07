from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

AMOUNT_CANDIDATE_PATTERN = re.compile(
    r"(?<!\w)([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?)(?!\w)"
)

DECIMAL_PRECISION = Decimal("0.0001")


def _sanitize_amount_text(value: str) -> str:
    cleaned = value.strip()
    cleaned = cleaned.replace("€", "")
    cleaned = cleaned.replace("EUR", "")
    cleaned = cleaned.replace("eur", "")
    cleaned = cleaned.replace("\u00A0", " ")
    cleaned = re.sub(r"[^\d,.\-\+\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_amount_text(value: str | int | float | Decimal | None) -> str | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, (int, float)):
        decimal_value = Decimal(str(value)).quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP)
        return format(decimal_value, "f")

    cleaned = _sanitize_amount_text(str(value))
    if cleaned == "":
        return None

    sign = ""
    if cleaned.startswith(("+", "-")):
        sign = cleaned[0]
        cleaned = cleaned[1:].strip()

    cleaned = cleaned.replace(" ", "")

    has_comma = "," in cleaned
    has_dot = "." in cleaned

    decimal_separator: str | None = None

    if has_comma and has_dot:
        decimal_separator = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
    elif has_comma:
        last_part = cleaned.split(",")[-1]
        decimal_separator = "," if 1 <= len(last_part) <= 4 else None
    elif has_dot:
        last_part = cleaned.split(".")[-1]
        decimal_separator = "." if 1 <= len(last_part) <= 4 else None

    if decimal_separator is None:
        normalized = re.sub(r"[.,]", "", cleaned)
    else:
        integer_part, decimal_part = cleaned.rsplit(decimal_separator, 1)
        integer_part = re.sub(r"[.,]", "", integer_part)
        decimal_part = re.sub(r"[.,]", "", decimal_part)
        normalized = f"{integer_part}.{decimal_part}"

    normalized = normalized.strip(".")
    if normalized == "":
        return None

    if sign == "-":
        normalized = f"-{normalized}"

    return normalized


def parse_amount(value: str | int | float | Decimal | None) -> float | None:
    normalized = normalize_amount_text(value)
    if normalized is None:
        return None

    try:
        decimal_value = Decimal(normalized).quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None

    return float(decimal_value)


def extract_amount_candidates(text: str, unique: bool = True) -> list[float]:
    candidates: list[float] = []

    for match in AMOUNT_CANDIDATE_PATTERN.finditer(text):
        parsed = parse_amount(match.group(1))
        if parsed is None:
            continue
        candidates.append(parsed)

    if not unique:
        return candidates

    unique_candidates: list[float] = []
    seen: set[float] = set()

    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)

    return unique_candidates


def _to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP)


def _to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP))


def calculate_missing_amounts(
    subtotal: float | None,
    iva: float | None,
    total: float | None,
) -> tuple[float | None, float | None, float | None]:
    subtotal_dec = _to_decimal(subtotal)
    iva_dec = _to_decimal(iva)
    total_dec = _to_decimal(total)

    if subtotal_dec is None and total_dec is not None and iva_dec is not None:
        subtotal_dec = total_dec - iva_dec

    if total_dec is None and subtotal_dec is not None and iva_dec is not None:
        total_dec = subtotal_dec + iva_dec

    if iva_dec is None and subtotal_dec is not None and total_dec is not None:
        iva_dec = total_dec - subtotal_dec

    return _to_float(subtotal_dec), _to_float(iva_dec), _to_float(total_dec)