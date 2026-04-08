from __future__ import annotations

import html
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
TAX_ID_PATTERNS = (
    re.compile(r"C\.I\.F\.\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
    re.compile(r"CIF\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
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
        normalized_text = self._normalize_text(text).lower()

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
        normalized_text = self._normalize_text(text)
        result = self.build_result(normalized_text, file_path)

        result.nombre_proveedor = self.extract_repsol_billing_company(normalized_text)
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(normalized_text, result.nombre_proveedor)
        result.numero_factura = self.extract_repsol_invoice_number(normalized_text)
        result.fecha_factura = self.extract_repsol_date(normalized_text)
        result.subtotal = self.extract_repsol_subtotal(normalized_text)
        result.iva = self.extract_repsol_iva(normalized_text)
        result.total = self.extract_repsol_total(file_path, normalized_text)

        return result.finalize()

    def _normalize_text(self, text: str) -> str:
        text = html.unescape(text)
        return text.replace("&#10;", "\n").replace("\r\n", "\n").replace("\r", "\n")

    def extract_repsol_billing_company(self, text: str) -> str | None:
        upper = text.upper()

        if "EMITIDA EN NOMBRE Y POR CUENTA DE" in upper:
            tail = upper.split("EMITIDA EN NOMBRE Y POR CUENTA DE", 1)[1]
            if "REPSOL SOLUCIONES ENERG" in tail:
                return "Repsol Soluciones Energéticas, S.A."
            if "REPSOL COMERCIAL DE PRODUCTOS PETROL" in tail:
                return "Repsol Comercial de Productos Petrolíferos, S.A."
            if "REPSOL PETR" in tail:
                return "Repsol Petróleo, S.A."

        if "REPSOL COMERCIAL DE PRODUCTOS PETROL" in upper:
            return "Repsol Comercial de Productos Petrolíferos, S.A."

        if "REPSOL PETR" in upper:
            return "Repsol Petróleo, S.A."

        if "REPSOL SOLUCIONES ENERG" in upper:
            return "Repsol Soluciones Energéticas, S.A."

        if "REPSOL ESTACIÓN SERVICIO" in upper or "REPSOL ESTACION SERVICIO" in upper:
            return "Repsol Estación Servicio"

        if "REPSOL ESTACION DE SERVICIO" in upper:
            return "Repsol Estación de Servicio"

        return "REPSOL"

    def extract_repsol_supplier_tax_id(self, text: str, company_name: str | None) -> str | None:
        lower = text.lower()

        if "emitida en nombre y por cuenta de" in lower:
            start = lower.find("emitida en nombre y por cuenta de")
            tail = text[start:]
            for pattern in TAX_ID_PATTERNS:
                match = pattern.search(tail)
                if match:
                    return match.group(1).replace("-", "")
            for tax_id in self.extract_exact_tax_ids(tail):
                if tax_id != "48334490J":
                    return tax_id

        if company_name in self.COMPANY_CIF_MAP:
            expected = self.COMPANY_CIF_MAP[company_name]
            if expected in text.replace("-", ""):
                return expected

        for pattern in TAX_ID_PATTERNS:
            match = pattern.search(text)
            if match:
                candidate = match.group(1).replace("-", "")
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
                return self.clean_invoice_number_candidate(match.group(1))
        return self.extract_invoice_number(text)

    def extract_repsol_date(self, text: str) -> str | None:
        for pattern in DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                return normalize_date(match.group(1))
        return self.extract_date(text)

    def extract_repsol_subtotal(self, text: str) -> float | None:
        value = self._extract_last_amount_from_line(text, ("IMPORTE DEL PRODUCTO", "BASE IMPONIBLE"))
        if value is not None:
            return value

        value = self.extract_labeled_amount(
            text,
            [r"importe\s+del\s+producto", r"base\s+imponible", r"subtotal"],
            ignore_percent=True,
        )
        return value

    def extract_repsol_iva(self, text: str) -> float | None:
        value = self._extract_last_amount_from_line(text, ("IVA ", "CUOTA IVA"))
        if value is not None:
            return value

        value = self.extract_labeled_amount(
            text,
            [r"cuota\s+iva", r"\biva\b"],
            ignore_percent=True,
        )
        return value

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self._extract_last_amount_from_line(text, ("TOTAL FACTURA EUROS", "TOTAL FACTURA", "TOTAL"))
        if value is not None:
            return value

        stem_match = re.search(r"(\d+(?:,\d{2})?)\s*€", Path(file_path).stem)
        if stem_match:
            return parse_amount(stem_match.group(1))

        return self.extract_total(text)

    def _extract_last_amount_from_line(self, text: str, markers: tuple[str, ...]) -> float | None:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            upper_line = line.upper()
            if not any(marker in upper_line for marker in markers):
                continue

            values: list[float] = []
            for token in AMOUNT_PATTERN.findall(line):
                parsed = parse_amount(token)
                if parsed is not None:
                    values.append(parsed)

            if values:
                return values[-1]

        return None