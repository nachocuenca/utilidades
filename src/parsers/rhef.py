from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.ids import normalize_postal_code
from src.utils.names import clean_name_candidate

INVOICE_NUMBER_PATTERN = re.compile(r"\b(BFAC/\d{6})\b", re.IGNORECASE)
DATE_PATTERN = re.compile(r"fecha\s+factura\s*[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})", re.IGNORECASE)


class RhefInvoiceParser(BaseInvoiceParser):
    parser_name = "rhef"
    priority = 340

    SUPPLIER_NAME = "Francisco Amador Garcia"
    SUPPLIER_TAX_ID = "48321093W"
    COMMERCIAL_NAME = "Recambios Rhef"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        normalized_text = self._normalize_for_match(text)
        score = 0

        if self.matches_file_path_hint(file_path, ("rhef", "recambios rhef")):
            score += 1

        if "francisco amador garcia" in normalized_text:
            score += 3

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 3

        if "recambiosrhef gmail com" in normalized_text or "recambios rhef" in normalized_text:
            score += 2

        if self._has_rhef_layout(text):
            score += 2

        if INVOICE_NUMBER_PATTERN.search(text):
            score += 1

        return score >= 4

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.SUPPLIER_TAX_ID
        result.nombre_cliente = self.extract_rhef_customer_name(lines)
        result.cp_cliente = self.extract_rhef_customer_postal_code(lines)
        result.numero_factura = self.extract_rhef_invoice_number(text)
        result.fecha_factura = self.extract_rhef_invoice_date(text)
        result.subtotal, result.iva, result.total = self.extract_rhef_tax_breakdown(lines)
        result.metadatos["nombre_comercial"] = self.COMMERCIAL_NAME

        return result.finalize()

    def extract_rhef_customer_name(self, lines: list[str]) -> str | None:
        customer_block = self._extract_customer_block(lines)

        for line in customer_block:
            cleaned = clean_name_candidate(line)
            if not cleaned:
                continue

            if re.search(r"\bcif\b", cleaned, re.IGNORECASE):
                continue

            if re.search(r"\d", cleaned):
                continue

            return cleaned.title()

        return None

    def extract_rhef_customer_postal_code(self, lines: list[str]) -> str | None:
        customer_block = self._extract_customer_block(lines)

        for line in customer_block:
            candidate = normalize_postal_code(line)
            if candidate:
                return candidate

        return None

    def extract_rhef_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if not match:
            return None
        return self.clean_invoice_number_candidate(match.group(1))

    def extract_rhef_invoice_date(self, text: str) -> str | None:
        match = DATE_PATTERN.search(text)
        if not match:
            return None
        return normalize_date(match.group(1))

    def extract_rhef_tax_breakdown(
        self,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        base_value, iva_value = self._extract_rhef_base_and_iva(lines)
        total_value = self._extract_rhef_total(lines)

        if (
            base_value is not None
            and iva_value is not None
            and total_value is not None
            and abs((base_value + iva_value) - total_value) <= 0.02
        ):
            return base_value, iva_value, total_value

        return None, None, total_value

    def _extract_customer_block(self, lines: list[str]) -> list[str]:
        start_index: int | None = None
        end_index = len(lines)

        for index, line in enumerate(lines):
            if "n cliente" in self._normalize_for_match(line):
                start_index = index + 1
                break

        if start_index is None:
            return []

        for index in range(start_index, len(lines)):
            if "n de factura" in self._normalize_for_match(lines[index]):
                end_index = index
                break

        return lines[start_index:end_index]

    def _extract_rhef_base_and_iva(self, lines: list[str]) -> tuple[float | None, float | None]:
        for index, line in enumerate(lines):
            normalized_line = self._normalize_for_match(line)
            if "base imponible" not in normalized_line or "iva" not in normalized_line:
                continue

            for candidate_line in lines[index + 1 : min(len(lines), index + 4)]:
                values = [abs(value) for value in self.extract_amounts_from_fragment(candidate_line, ignore_percent=False)]
                if len(values) >= 3:
                    return values[-2], values[-1]
                if len(values) >= 2:
                    return values[-2], values[-1]

        return None, None

    def _extract_rhef_total(self, lines: list[str]) -> float | None:
        for index, line in enumerate(lines):
            normalized_line = self._normalize_for_match(line)
            if "total factura" not in normalized_line:
                continue

            direct_values = self.extract_amounts_from_fragment(line, ignore_percent=True)
            if direct_values:
                return abs(direct_values[-1])

            for candidate_line in lines[index + 1 : min(len(lines), index + 4)]:
                values = self.extract_amounts_from_fragment(candidate_line, ignore_percent=True)
                if values:
                    return abs(values[-1])

        return None

    def _has_rhef_layout(self, text: str) -> bool:
        normalized_text = self._normalize_for_match(text)
        return all(
            marker in normalized_text
            for marker in (
                "n cliente",
                "n de factura",
                "fecha factura",
                "base imponible",
                "total factura",
            )
        )

    def _normalize_for_match(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
        without_punctuation = re.sub(r"[^a-zA-Z0-9]+", " ", without_accents)
        return re.sub(r"\s+", " ", without_punctuation).strip().lower()
