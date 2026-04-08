from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date


BILLING_COMPANY_PATTERNS = (
    re.compile(r"emitida\s+en\s+nombre\s+y\s+por\s+cuenta\s+de\s+([^\n]+)", re.IGNORECASE),
    re.compile(r"^(REPSOL\s+COMERCIAL\s+DE\s+PRODUCTOS\s+PETROL[IÍ]FEROS\s+S\.?A\.?)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(REPSOL\s+PETR[ÓO]LEO\s+S\.?A\.?)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(REPSOL\s+SOLUCIONES\s+ENERG[ÉE]TICAS,?\s+S\.?A\.?)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(REPSOL\s+ESTACI[ÓO]N\s+SERVICIO)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(REPSOL\s+ESTACION\s+DE\s+SERVICIO)$", re.IGNORECASE | re.MULTILINE),
)

BILLING_TAX_ID_PATTERNS = (
    re.compile(r"C\.I\.F\.\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
    re.compile(r"CIF\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
)

INVOICE_NUMBER_PATTERNS = (
    re.compile(r"N[º°o]?\s*Factura\s*[:#-]?\s*([A-Z0-9/.-]+)", re.IGNORECASE),
    re.compile(r"FACTURA\s*N[º°o]?\s*[:#-]?\s*([A-Z0-9/.-]+)", re.IGNORECASE),
    re.compile(r"\b(\d{6}/\d/\d{2}/\d{6})\b", re.IGNORECASE),
    re.compile(r"\b(TK\d{6,})\b", re.IGNORECASE),
)

DATE_LABEL_PATTERNS = (
    re.compile(r"fecha\s+factura\s*[:#-]?\s*(\d{1,2}[/.\\-]\d{1,2}[/.\\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"^fecha\s*[:#-]?\s*(\d{1,2}[/.\\-]\d{1,2}[/.\\-]\d{2,4})", re.IGNORECASE | re.MULTILINE),
)

BASE_PATTERNS = (
    re.compile(r"importe\s+del\s+producto\s*\(\s*base\s+imponible\s*\)\s*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE),
    re.compile(r"base\s+imponible(?:\s+\d+(?:[.,]\d+)?%)?\s*[:\s€]+([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE),
)

IVA_PATTERNS = (
    re.compile(r"iva\s+\d+[.,]\d+%\s+de\s+[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?\s*€?\s*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE),
    re.compile(r"cuota\s+iva(?:\s+\d+(?:[.,]\d+)?%)?\s*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE),
    re.compile(r"iva\s+\d+(?:[.,]\d+)?%\s*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE),
)

TOTAL_PATTERNS = (
    re.compile(r"total\s+factura\s+euros[^\d\n]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE),
    re.compile(r"total\s+factura\s*[:#-]?\s*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE),
    re.compile(r"^total\s*[:#-]?\s*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)", re.IGNORECASE | re.MULTILINE),
)


class RepsolInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "repsol"
    priority = 360

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if "factura simplificada" in normalized_text and any(
            marker in normalized_text for marker in ("n° op", "nº op", "no op", "efectivo", "cambio")
        ):
            return False

        score = 0
        if self.matches_file_path_hint(file_path, ("repsol",)):
            score += 1
        if "repsol" in normalized_text:
            score += 2
        if any(marker in normalized_text for marker in (
            "base imponible", "cuota iva", "total factura", "emitida en nombre y por cuenta de"
        )):
            score += 1

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_repsol_billing_company(text)
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(text)
        result.numero_factura = self.extract_repsol_invoice_number(text)
        result.fecha_factura = self.extract_repsol_date(text)
        result.subtotal = self.extract_repsol_subtotal(text)
        result.iva = self.extract_repsol_iva(text)
        result.total = self.extract_repsol_total(file_path, text)

        return result.finalize()

    def extract_repsol_billing_company(self, text: str) -> str | None:
        normalized_text = text.replace("&#10;", "\n")
        for pattern in BILLING_COMPANY_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                return self._normalize_company_name(value)
        return "REPSOL"

    def _normalize_company_name(self, value: str) -> str:
        cleaned = " ".join(value.replace("&#10;", " ").split())
        cleaned = cleaned.rstrip(". ")
        normalized_map = {
            "REPSOL SOLUCIONES ENERGÉTICAS, S.A": "Repsol Soluciones Energéticas, S.A.",
            "REPSOL SOLUCIONES ENERGETICAS, S.A": "Repsol Soluciones Energéticas, S.A.",
            "REPSOL COMERCIAL DE PRODUCTOS PETROLÍFEROS S.A": "Repsol Comercial de Productos Petrolíferos, S.A.",
            "REPSOL COMERCIAL DE PRODUCTOS PETROLIFEROS S.A": "Repsol Comercial de Productos Petrolíferos, S.A.",
            "REPSOL PETRÓLEO S.A": "Repsol Petróleo, S.A.",
            "REPSOL PETROLEO S.A": "Repsol Petróleo, S.A.",
            "REPSOL ESTACIÓN SERVICIO": "Repsol Estación Servicio",
            "REPSOL ESTACION DE SERVICIO": "Repsol Estación de Servicio",
        }
        key = cleaned.upper().replace("S.A.", "S.A").strip()
        return normalized_map.get(key, cleaned)

    def extract_repsol_supplier_tax_id(self, text: str) -> str | None:
        normalized_text = text.replace("&#10;", "\n")

        if "emitida en nombre y por cuenta de" in normalized_text.lower():
            start = normalized_text.lower().find("emitida en nombre y por cuenta de")
            tail_original = normalized_text[start:]
            for pattern in BILLING_TAX_ID_PATTERNS:
                match = pattern.search(tail_original)
                if match:
                    return match.group(1).replace("-", "")
            for tax_id in self.extract_exact_tax_ids(tail_original):
                if tax_id != "48334490J":
                    return tax_id

        for pattern in BILLING_TAX_ID_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                tax_id = match.group(1).replace("-", "")
                if tax_id != "48334490J":
                    return tax_id

        for tax_id in self.extract_exact_tax_ids(normalized_text):
            if tax_id != "48334490J":
                return tax_id

        return None

    def extract_repsol_invoice_number(self, text: str) -> str | None:
        normalized_text = text.replace("&#10;", "\n")
        for pattern in INVOICE_NUMBER_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                return self.clean_invoice_number_candidate(match.group(1))
        return self.extract_invoice_number(normalized_text)

    def extract_repsol_date(self, text: str) -> str | None:
        normalized_text = text.replace("&#10;", "\n")
        for pattern in DATE_LABEL_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                return normalize_date(match.group(1))
        return self.extract_date(normalized_text)

    def extract_repsol_subtotal(self, text: str) -> float | None:
        normalized_text = text.replace("&#10;", "\n")
        for pattern in BASE_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                return parse_amount(match.group(1))
        return self.extract_labeled_amount(normalized_text, [r"base\s+imponible", r"subtotal"])

    def extract_repsol_iva(self, text: str) -> float | None:
        normalized_text = text.replace("&#10;", "\n")
        for pattern in IVA_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                return parse_amount(match.group(1))
        return self.extract_labeled_amount(normalized_text, [r"cuota\s+iva", r"\biva\b"])

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        normalized_text = text.replace("&#10;", "\n")
        for pattern in TOTAL_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                return parse_amount(match.group(1))

        match = re.search(r"(\d+(?:,\d{2})?)\s*€", Path(file_path).stem)
        if match:
            return parse_amount(match.group(1))
        return self.extract_total(normalized_text)
