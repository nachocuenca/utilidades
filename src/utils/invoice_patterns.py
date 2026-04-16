from __future__ import annotations
import re


def extract_last_amount(line: str) -> float | None:
    """Return last monetary amount in a line as float, or None."""
    if not line:
        return None
    m = re.findall(r"([0-9]+[.,][0-9]{2})", line)
    if not m:
        return None
    return float(m[-1].replace(',', '.'))


def normalize_date_ddmmyyyy(value: str) -> str:
    """Normalize date strings like dd/mm/yy or dd/mm/yyyy to YYYY-MM-DD."""
    if not value:
        return value
    m = re.match(r"^(\d{2})/(\d{2})/(\d{2,4})$", value)
    if not m:
        return value
    day, month, year = m.group(1), m.group(2), m.group(3)
    if len(year) == 2:
        year = '20' + year
    return f"{year}-{month}-{day}"


def extract_total_from_lines(text: str) -> float | None:
    """Scan lines containing the word TOTAL (case-insensitive) and return the last
    monetary amount found in the last matching line. Returns None if not found."""
    if not text:
        return None
    # Prefer explicit 'TOTAL FACTURA' lines
    candidates = []
    for line in text.splitlines():
        up = line.upper()
        if 'TOTAL FACTURA' in up:
            amt = extract_last_amount(line)
            # ignore zero amounts from malformed lines
            if amt is not None and amt > 0.0:
                return amt
        # exclude subtotal or card totals
        if 'TOTAL' in up and 'SUBTOTAL' not in up and 'TARJETA' not in up:
            amt = extract_last_amount(line)
            if amt is not None and amt > 0.0:
                candidates.append(amt)
    if candidates:
        return candidates[-1]
    return None
