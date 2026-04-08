from __future__ import annotations

import re
from pathlib import Path
from typing import List

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
    re.compile(r"\b(n[ºo]\s*ticket|ticket n[ºo])\b", re.IGNORECASE),
)

SUPPORT_TICKET_PATTERNS = (
    re.compile(r"\bidentificador\b", re.IGNORECASE),
    re.compile(r"impuestos\s+incluidos", re.IGNORECASE),
    re.compile(r"\befectivo\b", re.IGNORECASE),
    re.compile(r"\bentregado\b", re.IGNORECASE),
    re.compile(r"\bcambio\b", re.IGNORECASE),
    re.compile(r"\bpagado\b", re.IGNORECASE | re.MULTILINE),
)

# Fixed TOTAL_LINE_PATTERN para capturar "TOTAL 100.00" y "TOTAL: 54,20"
TOTAL_LINE_PATTERN = re.compile(
    r"(?i)(?:total|TOTAL)\s*[:\.\s]*(\d+[.,]\d{2})",
    re.MULTILINE,
)

DATE_PATTERN = re.compile(r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b")

NIF_PATTERN = re.compile(r"\b([0-9A-Z]{8,9}[A-Z])\b")

OCR_BASURA_PATTERNS = [
    re.compile(r"^\s*[A-Z\s\./]{1,8}\s*$"),  # Líneas upper cortas
    re.compile(r"^[.A-Z\s]+F\.I\.N[.A-Z\s]*$", re.I),
    re.compile(r"ajoh|OILOF|otnemucod", re.I),
]

def is_ocr_basura(line: str) -> bool:
    """Detecta líneas típicas de OCR malo en tickets."""
    line_upper = line.strip().upper()
    if len(line_upper) < 4 or len(line.strip()) < 3:
        return True
    for pattern in OCR_BASURA_PATTERNS:
        if pattern.search(line):
            return True
    vowels = sum(1 for c in line.lower() if c in 'aeiouáéíóú')
    if len(line) < 8 and vowels == 0:
        return True
    return False


class GenericTicketInvoiceParser(BaseInvoiceParser):
    parser_name = "generic_ticket"
    priority = 60

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        path_text = self.get_path_text(file_path)

        # Path tickets fuerza
        if any(ticket_path in path_text for ticket_path in ["/tickets/", "/ticket/"]):
            return True

        lines = self.extract_lines(text)
        line_count = len(lines)

        # Docs muy largos nunca tickets
        if line_count > 60:
            return False

        # Contar matches
        strong_matches = sum(1 for pattern in STRONG_TICKET_PATTERNS if pattern.search(text))
        support_matches = sum(1 for pattern in SUPPORT_TICKET_PATTERNS if pattern.search(text))
        has_total = bool(TOTAL_LINE_PATTERN.search(text))
        has_date = bool(DATE_PATTERN.search(text))

        # ESTRICto: al menos 1 STRONG + 1 SUPPORT + total + fecha OR 2 STRONG
        if not ((strong_matches >= 2) or (strong_matches >= 1 and support_matches >= 1 and has_total and has_date)):
            return False

        # Rechazar si muchos NIF (docs fiscales)
        nif_count = len(NIF_PATTERN.findall(text))
        if nif_count > 3:
            return False

        # Rechazar si muchos líneas OCR basura en top
        basura_top = sum(1 for line in lines[:10] if is_ocr_basura(line))
        if basura_top > 3:
            return False

        return True

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        supplier = self.extract_supplier_name(lines, file_path)
        if not supplier:
            result.nombre_proveedor = None
            return result.finalize()

        result.nombre_proveedor = supplier
        result.nif_proveedor = self.extract_supplier_tax_id_improved(text, lines)
        result.numero_factura = self.extract_ticket_number(text)
        result.fecha_factura = self.extract_ticket_date_improved(text)
        result.total = self.extract_ticket_total_improved(text, lines)

        if result.total is None:
            result.nombre_proveedor = None
            return result.finalize()

        # Opcionales
        result.subtotal = self.extract_ticket_subtotal(text)
        result.iva = self.extract_ticket_iva(text)

        return result.finalize()

    def extract_supplier_name(self, lines: List[str], file_path: str | Path) -> str | None:
        ignored_patterns = [
            re.compile(r"(?i)(factura\s+simplificada|subtotal|total|base|cuota|producto|importe|entregado|cambio|efectivo|tel[.:]|avenida|calle)"),
            re.compile(r"(?i)(c/|c\.|poblacion|provincia)"),
            re.compile(r"(?i)(informacion\s+adicional|referencia|cumplimiento|normativa)"),
            re.compile(r"(?i)(nif\s+cliente|cliente)"),
        ]

        candidates = []

        for i, line in enumerate(lines[:10]):  # Top 10
            if is_ocr_basura(line):
                continue

            cleaned = clean_name_candidate(line)
            if not cleaned:
                continue

            if any(pattern.search(cleaned) for pattern in ignored_patterns):
                continue

            # Fixed: permitir REPSOL aunque upper
            if len(cleaned) >= 4 and (is_valid_name_candidate(cleaned) or 'REPSOL' in cleaned.upper()):
                candidates.append(cleaned)

        best = pick_best_name(candidates)
        if best:
            return best

        # Solo si no hay nada, folder hint (no forzar)
        folder_hint = self.get_folder_hint_name(file_path)
        if folder_hint and len(folder_hint) > 4 and not is_ocr_basura(folder_hint):
            return folder_hint

        return None

    def extract_supplier_tax_id_improved(self, text: str, lines: List[str]) -> str | None:
        """NIF cerca del proveedor, no cliente."""
        # Buscar NIF en top 20 líneas después del proveedor implícito
        nif_candidates = []
        for i, line in enumerate(lines[:25]):
            nifs = NIF_PATTERN.findall(line)
            for nif in nifs:
                # Ignorar cerca de "cliente"
                if i > 0 and "cliente" in lines[i-1].lower():
                    continue
                nif_candidates.append((i, nif))

        if nif_candidates:
            # Tomar el primer NIF válido (más arriba)
            return nif_candidates[0][1]

        return self.extract_supplier_tax_id(text)  # Fallback

    def extract_ticket_date_improved(self, text: str) -> str | None:
        # Priorizar cerca de "fecha"
        fecha_sections = re.split(r"(?i)fecha", text, flags=re.I)[1:3]  # Primer "fecha"
        if fecha_sections:
            local_match = DATE_PATTERN.search(fecha_sections[0])
            if local_match:
                candidate = normalize_date(local_match.group(1))
                if candidate:
                    return candidate

        return self.extract_ticket_date(text)

    def extract_ticket_total_improved(self, text: str, lines: List[str]) -> float | None:
        # Priorizar últimas líneas con TOTAL
        for line in reversed(lines[-10:]):  # Últimas 10
            match = TOTAL_LINE_PATTERN.search(line)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except ValueError:
                    pass

        # Fallback global
        match = TOTAL_LINE_PATTERN.search(text)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                pass

        return self.extract_ticket_total(text)

    # Mantiene los métodos originales como fallback
    def extract_ticket_number(self, text: str) -> str | None:
        patterns = [
            r"(?:n[ºo]\s*op\.?|n[ºo]\s*operaci[oó]n)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
            r"(?:identificador)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
            r"(?:ticket)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
        ]

        for pattern_text in patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if match:
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

