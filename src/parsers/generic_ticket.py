from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.names import clean_name_candidate, is_valid_name_candidate, pick_best_name

TICKET_MONTHS = {
    "ene": "enero",
    "feb": "febrero",
    "mar": "marzo",
    "abr": "abril",
    "may": "mayo",
    "jun": "junio",
    "jul": "julio",
    "ago": "agosto",
    "sep": "septiembre",
    "sept": "septiembre",
    "oct": "octubre",
    "nov": "noviembre",
    "dic": "diciembre",
}

STRONG_TICKET_PATTERNS = (
    re.compile(r"factura\s+simplificada", re.IGNORECASE),
    re.compile(r"\bsala-mesa\b", re.IGNORECASE),
    re.compile(r"\bn[ºo]\s*op\.?\b", re.IGNORECASE),
    re.compile(r"\bn[ºo]\s*operaci[oó]n\b", re.IGNORECASE),
    re.compile(r"\bticket\b", re.IGNORECASE),
)

SUPPORT_TICKET_PATTERNS = (
    re.compile(r"\bidentificador\b", re.IGNORECASE),
    re.compile(r"impuestos\s+incluidos", re.IGNORECASE),
    re.compile(r"\befectivo\b", re.IGNORECASE),
    re.compile(r"\bentregado\b", re.IGNORECASE),
    re.compile(r"\bcambio\b", re.IGNORECASE),
)

TOTAL_LINE_PATTERN = re.compile(
    r"\btotal\b[^\n\r:]*[: ]+\d+(?:[.,]\d{2})?",
    re.IGNORECASE,
)

DATE_PATTERN = re.compile(
    r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b",
    re.IGNORECASE,
)


class GenericTicketInvoiceParser(BaseInvoiceParser):
    parser_name = "generic_ticket"
    priority = 200

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        path_text = self.get_path_text(file_path)

        if "/tickets/" in path_text or path_text.endswith("/tickets") or "/ticket/" in path_text:
            return True

        strong_matches = sum(1 for pattern in STRONG_TICKET_PATTERNS if pattern.search(text))
        support_matches = sum(1 for pattern in SUPPORT_TICKET_PATTERNS if pattern.search(text))
        has_total_line = TOTAL_LINE_PATTERN.search(text) is not None
        has_date = DATE_PATTERN.search(text) is not None

        if strong_matches >= 2:
            return True

        if strong_matches >= 1 and support_matches >= 1 and has_total_line:
            return True

        if strong_matches >= 1 and has_total_line and has_date:
            return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(lines, file_path)
        result.nif_proveedor = self.extract_supplier_tax_id(text)
        result.numero_factura = self.extract_ticket_number(text)
        result.fecha_factura = self.extract_ticket_date(text)
        result.subtotal = self.extract_ticket_subtotal(text)
        result.iva = self.extract_ticket_iva(text)
        result.total = self.extract_ticket_total(text)

        return result.finalize()

    def extract_supplier_name(self, lines: list[str], file_path: str | Path) -> str | None:
        ignored_patterns = [
            re.compile(r"factura\s+simplificada", re.IGNORECASE),
            re.compile(r"subtotal", re.IGNORECASE),
            re.compile(r"total", re.IGNORECASE),
            re.compile(r"base", re.IGNORECASE),
            re.compile(r"cuota", re.IGNORECASE),
            re.compile(r"producto", re.IGNORECASE),
            re.compile(r"importe", re.IGNORECASE),
            re.compile(r"entregado", re.IGNORECASE),
            re.compile(r"cambio", re.IGNORECASE),
            re.compile(r"efectivo", re.IGNORECASE),
            re.compile(r"tel[.: ]", re.IGNORECASE),
            re.compile(r"^c/", re.IGNORECASE),
            re.compile(r"avenida", re.IGNORECASE),
            re.compile(r"calle", re.IGNORECASE),
        ]

        candidates: list[str] = []

        for line in lines[:8]:
            cleaned = clean_name_candidate(line)
            if cleaned is None:
                continue

            if any(pattern.search(cleaned) for pattern in ignored_patterns):
                continue

            if is_valid_name_candidate(cleaned):
                candidates.append(cleaned)

        best = pick_best_name(candidates)
        if best:
            return best

        folder_hint = self.get_folder_hint_name(file_path)
        if folder_hint and folder_hint.lower() != "tickets":
            return folder_hint

        return None

    def extract_ticket_number(self, text: str) -> str | None:
        patterns = [
            r"(?:n[ºo]\s*op\.?|n[ºo]\s*operaci[oó]n)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
            r"(?:identificador)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
            r"(?:ticket)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
        ]

        for pattern_text in patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if not match:
                continue

            candidate = match.group(1).strip(" .,:;")
            if candidate:
                return candidate

        return self.extract_invoice_number(text)

    def extract_ticket_date(self, text: str) -> str | None:
        numeric_match = re.search(r"\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b", text)
        if numeric_match:
            candidate = normalize_date(numeric_match.group(1))
            if candidate:
                return candidate

        month_match = re.search(
            r"\b(\d{1,2})\s*(ene|feb|mar|abr|may|jun|jul|ago|sep|sept|oct|nov|dic)\.?\s*(\d{2,4})\b",
            text,
            re.IGNORECASE,
        )
        if month_match:
            day_value, month_abbrev, year_value = month_match.groups()
            month_name = TICKET_MONTHS.get(month_abbrev.lower())
            if month_name:
                candidate = normalize_date(f"{day_value} de {month_name} de {year_value}")
                if candidate:
                    return candidate

        return self.extract_date(text)

    def extract_ticket_subtotal(self, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [
                r"\bbase\b",
                r"subtotal",
                r"base\s+imponible",
            ],
        )
        if value is not None:
            return value

        return self.extract_subtotal(text)

    def extract_ticket_iva(self, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [
                r"\bcuota\b",
                r"\biva\b",
            ],
        )
        if value is not None:
            return value

        return self.extract_iva(text)

    def extract_ticket_total(self, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [
                r"total\s*\(.*?incl.*?\)",
                r"\btotal\b",
            ],
        )
        if value is not None:
            return value

        return self.extract_total(text)
