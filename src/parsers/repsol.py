from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date


AMOUNT_PATTERN = re.compile(r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?")

INVOICE_NUMBER_PATTERNS = (
    re.compile(r"n[º°o]?\s*factura\s*[:#-]?\s*([A-Z0-9/.-]+)", re.IGNORECASE),
    re.compile(r"factura\s*n[º°o]?\s*[:#-]?\s*([A-Z0-9/.-]+)", re.IGNORECASE),
    re.compile(r"\b(\d{6}/\d/\d{2}/\d{6})\b", re.IGNORECASE),
    re.compile(r"\b(TK\d{6,})\b", re.IGNORECASE),
)

DATE_PATTERNS = (
    re.compile(r"fecha\s+factura\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"^fecha\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE | re.MULTILINE),
)

KNOWN_COMPANY_PATTERNS = (
    (re.compile(r"repsol\s+soluciones\s+energ[ée]ticas,?\s*s\.?a\.?", re.IGNORECASE), "Repsol Soluciones Energéticas, S.A."),
    (re.compile(r"repsol\s+comercial\s+de\s+productos\s+petrol[ií]feros,?\s*s\.?a\.?", re.IGNORECASE), "Repsol Comercial de Productos Petrolíferos, S.A."),
    (re.compile(r"repsol\s+petr[óo]leo,?\s*s\.?a\.?", re.IGNORECASE), "Repsol Petróleo, S.A."),
    (re.compile(r"repsol\s+estaci[óo]n\s+servicio", re.IGNORECASE), "Repsol Estación Servicio"),
    (re.compile(r"repsol\s+estacion\s+de\s+servicio", re.IGNORECASE), "Repsol Estación de Servicio"),
)

TAX_ID_PATTERNS = (
    re.compile(r"C\.I\.F\.\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
    re.compile(r"CIF\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
)

BASE_LINE_MARKERS = (
    re.compile(r"importe\s+del\s+producto.*base\s+imponible", re.IGNORECASE),
    re.compile(r"\bbase\s+imponible\b", re.IGNORECASE),
)

IVA_LINE_MARKERS = (
    re.compile(r"\biva\b", re.IGNORECASE),
    re.compile(r"cuota\s+iva", re.IGNORECASE),
)

TOTAL_LINE_MARKERS = (
    re.compile(r"total\s+factura\s+euros", re.IGNORECASE),
    re.compile(r"\btotal\s+factura\b", re.IGNORECASE),
    re.compile(r"^\s*total\s*[:#-]?", re.IGNORECASE),
)


class RepsolInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "repsol"
    priority = 360

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower().replace("&#10;", "\n")

        if "factura simplificada" in normalized_text and any(
            marker in normalized_text
            for marker in ("n° op", "nº op", "no op", "efectivo", "cambio")
        ):
            return False

        score = 0
        if self.matches_file_path_hint(file_path, ("repsol",)):
            score += 1
        if "repsol" in normalized_text:
            score += 2
        if any(
            marker in normalized_text
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
        normalized_text = text.replace("&#10;", "\n")
        result = self.build_result(normalized_text, file_path)

        result.nombre_proveedor = self.extract_repsol_billing_company(normalized_text)
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(normalized_text)
        result.numero_factura = self.extract_repsol_invoice_number(normalized_text)
        result.fecha_factura = self.extract_repsol_date(normalized_text)
        result.subtotal = self.extract_repsol_subtotal(normalized_text)
        result.iva = self.extract_repsol_iva(normalized_text)
        result.total = self.extract_repsol_total(file_path, normalized_text)

        return result.finalize()

    def extract_repsol_billing_company(self, text: str) -> str | None:
        lower_text = text.lower()

        if "emitida en nombre y por cuenta de" in lower_text:
            start = lower_text.find("emitida en nombre y por cuenta de")
            tail = text[start:start + 500]
            for pattern, canonical_name in KNOWN_COMPANY_PATTERNS:
                if pattern.search(tail):
                    return canonical_name

        for pattern, canonical_name in KNOWN_COMPANY_PATTERNS:
            if pattern.search(text):
                return canonical_name

        return "REPSOL"

    def extract_repsol_supplier_tax_id(self, text: str) -> str | None:
        lower_text = text.lower()
        if "emitida en nombre y por cuenta de" in lower_text:
            start = lower_text.find("emitida en nombre y por cuenta de")
            tail = text[start:]
            for pattern in TAX_ID_PATTERNS:
                match = pattern.search(tail)
                if match:
                    return match.group(1).replace("-", "")
            for tax_id in self.extract_exact_tax_ids(tail):
                if tax_id != "48334490J":
                    return tax_id

        company = self.extract_repsol_billing_company(text)
        if company and company != "REPSOL":
            pattern_map = {
                "Repsol Soluciones Energéticas, S.A.": r"repsol\s+soluciones\s+energ[ée]ticas.*?(?:c\.i\.f\.|cif)\s*[:.]?\s*([A-Z]-?\d{8})",
                "Repsol Comercial de Productos Petrolíferos, S.A.": r"repsol\s+comercial\s+de\s+productos\s+petrol[ií]feros.*?(?:c\.i\.f\.|cif)\s*[:.]?\s*([A-Z]-?\d{8})",
                "Repsol Petróleo, S.A.": r"repsol\s+petr[óo]leo.*?(?:c\.i\.f\.|cif)\s*[:.]?\s*([A-Z]-?\d{8})",
                "Repsol Estación Servicio": r"repsol\s+estaci[óo]n\s+servicio.*?(?:c\.i\.f\.|cif)\s*[:.]?\s*([A-Z]-?\d{8})",
                "Repsol Estación de Servicio": r"repsol\s+estacion\s+de\s+servicio.*?(?:c\.i\.f\.|cif)\s*[:.]?\s*([A-Z]-?\d{8})",
            }
            regex_text = pattern_map.get(company)
            if regex_text:
                match = re.search(regex_text, text, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(1).replace("-", "")

        for pattern in TAX_ID_PATTERNS:
            match = pattern.search(text)
            if match:
                tax_id = match.group(1).replace("-", "")
                if tax_id != "48334490J":
                    return tax_id

        for tax_id in self.extract_exact_tax_ids(text):
            if tax_id != "48334490J":
                return tax_id

        return None

    def extract_repsol_invoice_number(self, text: str) -> str | None:
        for pattern in INVOICE_NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                return self.clean_invoice_number_candidate(match.group(1))
        return self.extract_invoice_number(text)

    def extract_repsol_date(self, text: str) -> str | None:
        for pattern in DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                return normalize_date(match.group(1))
        return self.extract_date(text)

    def extract_repsol_subtotal(self, text: str) -> float | None:
        value = self._extract_last_amount_from_matching_line(text, BASE_LINE_MARKERS)
        if value is not None:
            return value
        return self.extract_labeled_amount(
            text,
            [r"importe\s+del\s+producto", r"base\s+imponible", r"subtotal"],
            ignore_percent=True,
        )

    def extract_repsol_iva(self, text: str) -> float | None:
        value = self._extract_last_amount_from_matching_line(text, IVA_LINE_MARKERS)
        if value is not None:
            return value
        return self.extract_labeled_amount(text, [r"cuota\s+iva", r"\biva\b"], ignore_percent=True)

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self._extract_last_amount_from_matching_line(text, TOTAL_LINE_MARKERS)
        if value is not None:
            return value

        stem_match = re.search(r"(\d+(?:,\d{2})?)\s*€", Path(file_path).stem)
        if stem_match:
            return parse_amount(stem_match.group(1))
        return self.extract_total(text)

    def _extract_last_amount_from_matching_line(self, text: str, markers: tuple[re.Pattern[str], ...]) -> float | None:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if not any(marker.search(line) for marker in markers):
                continue

            parsed_values: list[float] = []
            for token in AMOUNT_PATTERN.findall(line):
                parsed = parse_amount(token)
                if parsed is not None:
                    parsed_values.append(parsed)

            if not parsed_values:
                continue

            return parsed_values[-1]

        return None