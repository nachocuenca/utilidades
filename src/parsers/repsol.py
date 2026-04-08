from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date

AMOUNT_PATTERN = re.compile(r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?")
INVOICE_NUMBER_PATTERNS = (
    re.compile(r"n[º°o]?\s*factura\s*[:#-]?\s*([A-Z0-9/.\-]+)", re.IGNORECASE),
    re.compile(r"factura\s*n[º°o]?\s*[:#-]?\s*([A-Z0-9/.\-]+)", re.IGNORECASE),
    re.compile(r"\b(\d{6}/\d/\d{2}/\d{6})\b", re.IGNORECASE),
    re.compile(r"\b(TK\d{6,})\b", re.IGNORECASE),
)
DATE_PATTERNS = (
    re.compile(r"fecha\s+factura\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+factura\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"^fecha\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE | re.MULTILINE),
)

BILLING_COMPANY_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"repsol\s+soluciones\s+energet", re.IGNORECASE),
        "Repsol Soluciones Energéticas, S.A.",
        "A80298839",
    ),
    (
        re.compile(r"repsol\s+comercial\s+de\s+productos\s+petrol", re.IGNORECASE),
        "Repsol Comercial de Productos Petrolíferos, S.A.",
        "B28920839",
    ),
    (
        re.compile(r"repsol\s+petr[oó]leo", re.IGNORECASE),
        "Repsol Petróleo, S.A.",
        "B28049929",
    ),
)

TAX_ID_PATTERNS = (
    re.compile(r"C\.?I\.?F\.?\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
    re.compile(r"\bCIF\b\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
)

SIMPLIFIED_TICKET_MARKERS = (
    "factura simplificada",
    "n° op",
    "nº op",
    "no op",
    "efectivo",
    "cambio",
)


class RepsolInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "repsol"
    priority = 360

    COMPANY_CIF_MAP = {
        "Repsol Soluciones Energéticas, S.A.": "A80298839",
        "Repsol Comercial de Productos Petrolíferos, S.A.": "B28920839",
        "Repsol Petróleo, S.A.": "B28049929",
    }

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = self._normalize_text(text)
        lowered = normalized_text.lower()

        if "factura simplificada" in lowered and any(marker in lowered for marker in SIMPLIFIED_TICKET_MARKERS):
            return False

        score = 0

        if self.matches_file_path_hint(file_path, ("repsol",)):
            score += 1

        if "repsol" in lowered:
            score += 2

        if any(
            marker in lowered
            for marker in (
                "base imponible",
                "cuota iva",
                "total factura",
                "emitida en nombre y por cuenta de",
                "repsol comercial",
                "repsol petr",
                "repsol soluciones energ",
            )
        ):
            score += 1

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        normalized_text = self._normalize_text(text)
        result = self.build_result(normalized_text, file_path)

        billing_company = self.extract_repsol_billing_company(normalized_text)
        tax_triplet = self.extract_repsol_tax_breakdown(normalized_text)

        result.nombre_proveedor = billing_company
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(normalized_text, billing_company)
        result.numero_factura = self.extract_repsol_invoice_number(normalized_text)
        result.fecha_factura = self.extract_repsol_date(normalized_text)
        result.subtotal = tax_triplet[0]
        result.iva = tax_triplet[1]
        result.total = tax_triplet[2] if tax_triplet[2] is not None else self.extract_repsol_total(file_path, normalized_text)

        if result.subtotal is None:
            result.subtotal = self.extract_repsol_subtotal(normalized_text)

        if result.iva is None:
            result.iva = self.extract_repsol_iva(normalized_text)

        if result.total is None:
            result.total = self.extract_repsol_total(file_path, normalized_text)

        return result.finalize()

    def _normalize_text(self, text: str) -> str:
        text = html.unescape(text or "")
        return text.replace("&#10;", "\n").replace("\r\n", "\n").replace("\r", "\n")

    def _strip_accents(self, value: str) -> str:
        return "".join(
            char for char in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(char)
        )

    def extract_repsol_billing_company(self, text: str) -> str | None:
        lowered = text.lower()
        ascii_text = self._strip_accents(text).lower()

        if "emitida en nombre y por cuenta de" in lowered:
            start = lowered.find("emitida en nombre y por cuenta de")
            tail = text[start : start + 1500]
            for pattern, company_name, _tax_id in BILLING_COMPANY_PATTERNS:
                if pattern.search(tail):
                    return company_name

        for pattern, company_name, _tax_id in BILLING_COMPANY_PATTERNS:
            if pattern.search(text):
                return company_name

        if "repsol estacion de servicio" in ascii_text:
            return "Repsol Estación de Servicio"

        if "repsol estacion servicio" in ascii_text:
            return "Repsol Estación Servicio"

        return "REPSOL"

    def extract_repsol_supplier_tax_id(self, text: str, company_name: str | None) -> str | None:
        if company_name in self.COMPANY_CIF_MAP:
            return self.COMPANY_CIF_MAP[company_name]

        lowered = text.lower()

        if "emitida en nombre y por cuenta de" in lowered:
            start = lowered.find("emitida en nombre y por cuenta de")
            tail = text[start : start + 1500]

            for pattern in TAX_ID_PATTERNS:
                match = pattern.search(tail)
                if match:
                    candidate = match.group(1).replace("-", "").upper()
                    if candidate != "48334490J":
                        return candidate

            for tax_id in self.extract_exact_tax_ids(tail):
                if tax_id != "48334490J":
                    return tax_id

        for pattern in TAX_ID_PATTERNS:
            match = pattern.search(text)
            if match:
                candidate = match.group(1).replace("-", "").upper()
                if candidate != "48334490J":
                    return candidate

        for tax_id in self.extract_exact_tax_ids(text):
            if tax_id != "48334490J":
                return tax_id

        return None

    def extract_repsol_invoice_number(self, text: str) -> str | None:
        for pattern in INVOICE_NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                candidate = self.clean_invoice_number_candidate(match.group(1))
                if candidate:
                    return candidate

        return self.extract_invoice_number(text)

    def extract_repsol_date(self, text: str) -> str | None:
        for pattern in DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                candidate = normalize_date(match.group(1))
                if candidate:
                    return candidate

        return self.extract_date(text)

    def extract_repsol_tax_breakdown(
        self,
        text: str,
    ) -> tuple[float | None, float | None, float | None]:
        tail_lines = self.extract_lines(text)[-25:]

        base = self._extract_tail_amount_from_markers(
            tail_lines,
            ("BASE IMPONIBLE", "IMPORTE DEL PRODUCTO"),
        )
        iva = self._extract_tail_amount_from_markers(
            tail_lines,
            ("CUOTA IVA", "IVA "),
        )
        total = self._extract_tail_amount_from_markers(
            tail_lines,
            ("TOTAL FACTURA EUROS", "TOTAL FACTURA"),
        )

        if base is not None and iva is not None and total is not None:
            if abs((base + iva) - total) <= 0.02:
                return base, iva, total

        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            if abs((summary_base + summary_iva) - summary_total) <= 0.02:
                return summary_base, summary_iva, summary_total

        return base, iva, total

    def extract_repsol_subtotal(self, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [r"importe\s+del\s+producto", r"base\s+imponible", r"subtotal"],
            ignore_percent=True,
        )
        if value is not None:
            return value

        return self.extract_subtotal(text)

    def extract_repsol_iva(self, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [r"cuota\s+iva", r"\biva\b"],
            ignore_percent=True,
        )
        if value is not None:
            return value

        return self.extract_iva(text)

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [r"total\s+factura\s+euros", r"total\s+factura", r"\btotal\b"],
            ignore_percent=False,
        )
        if value is not None:
            return value

        stem_match = re.search(r"(\d+(?:,\d{2})?)\s*€", Path(file_path).stem)
        if stem_match:
            parsed = parse_amount(stem_match.group(1))
            if parsed is not None:
                return parsed

        return self.extract_total(text)

    def _extract_tail_amount_from_markers(
        self,
        tail_lines: list[str],
        markers: tuple[str, ...],
    ) -> float | None:
        for raw_line in reversed(tail_lines):
            line = raw_line.strip()
            if not line:
                continue

            upper_line = self._strip_accents(line).upper()
            if not any(self._strip_accents(marker).upper() in upper_line for marker in markers):
                continue

            values: list[float] = []
            for token in AMOUNT_PATTERN.findall(line):
                parsed = parse_amount(token)
                if parsed is not None:
                    values.append(parsed)

            if values:
                return values[-1]

        return None