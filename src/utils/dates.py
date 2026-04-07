from __future__ import annotations

import re
from datetime import date

NUMERIC_DATE_PATTERN = re.compile(r"\b(\d{1,4})[\/\-.](\d{1,2})[\/\-.](\d{1,4})\b")
TEXTUAL_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-záéíóúüñ]+)\s+de\s+(\d{2,4})\b",
    re.IGNORECASE,
)

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _normalize_year(year_value: int) -> int:
    if year_value >= 100:
        return year_value
    if year_value <= 49:
        return 2000 + year_value
    return 1900 + year_value


def _safe_format_date(day: int, month: int, year: int) -> str | None:
    try:
        parsed = date(year, month, day)
    except ValueError:
        return None
    return parsed.strftime("%d-%m-%Y")


def normalize_date(value: str | None) -> str | None:
    if value is None:
        return None

    raw_value = value.strip()
    if raw_value == "":
        return None

    numeric_match = NUMERIC_DATE_PATTERN.search(raw_value)
    if numeric_match:
        first, second, third = numeric_match.groups()

        if len(first) == 4:
            year = _normalize_year(int(first))
            month = int(second)
            day = int(third)
        else:
            day = int(first)
            month = int(second)
            year = _normalize_year(int(third))

        return _safe_format_date(day, month, year)

    textual_match = TEXTUAL_DATE_PATTERN.search(raw_value)
    if textual_match:
        day_text, month_text, year_text = textual_match.groups()
        month = SPANISH_MONTHS.get(month_text.lower())
        if month is None:
            return None

        day = int(day_text)
        year = _normalize_year(int(year_text))
        return _safe_format_date(day, month, year)

    return None


def extract_date_candidates(text: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()

    for match in NUMERIC_DATE_PATTERN.finditer(text):
        normalized = normalize_date(match.group(0))
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)

    for match in TEXTUAL_DATE_PATTERN.finditer(text):
        normalized = normalize_date(match.group(0))
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)

    return results