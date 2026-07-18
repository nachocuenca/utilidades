from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.ids import normalize_postal_code
from src.utils.names import clean_name_candidate

INVOICE_NUMBER_PATTERN = re.compile(r"\b(05032-\d{6})\b", re.IGNORECASE)
DATE_PATTERN = re.compile(r"fecha\s*[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})", re.IGNORECASE)
HEADER_LINE_PATTERN = re.compile(
    r"(?:factura|ifactura|leactura|teactura)\s+(05032-\d{6})\s+fecha\s*[:\-]?\s*"
    r"(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\s+(.+)$",
    re.IGNORECASE,
)


class CementosBenidormInvoiceParser(BaseInvoiceParser):
    parser_name = "cementos_benidorm"
    priority = 345

    SUPPLIER_NAME = "Cementos Benidorm, S.A."
    SUPPLIER_TAX_ID = "A03072816"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        normalized_text = self._normalize_for_match(text)
        raw_lower = text.lower()
        score = 0

        if self.matches_file_path_hint(file_path, ("cementos benidorm", "cb mat", "cb-mat")):
            score += 1

        if "cementos benidorm" in normalized_text:
            score += 3

        if "materiales siempre cerca by cementos benidorm" in normalized_text:
            score += 2

        if any(marker in raw_lower for marker in ("cb mat", "cb-mat.com", "www.cb-mat.com")):
            score += 2

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 3

        if INVOICE_NUMBER_PATTERN.search(text):
            score += 1

        if self._has_cementos_tax_layout(text):
            score += 2

        return score >= 4

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.extract_cementos_supplier_tax_id(text)
        result.nombre_cliente = self.extract_cementos_customer_name(lines)
        result.cp_cliente = self.extract_cementos_customer_postal_code(lines)
        result.numero_factura = self.extract_cementos_invoice_number(text)
        result.fecha_factura = self.extract_cementos_invoice_date(text)
        result.subtotal, result.iva, result.total = self.extract_cementos_tax_breakdown(lines)

        return result.finalize()

    def extract_cementos_supplier_tax_id(self, text: str) -> str:
        for candidate in self.extract_exact_tax_ids(text):
            if candidate == self.SUPPLIER_TAX_ID:
                return candidate

        return self.SUPPLIER_TAX_ID

    def extract_cementos_customer_name(self, lines: list[str]) -> str | None:
        for line in lines[:8]:
            match = HEADER_LINE_PATTERN.search(line)
            if not match:
                continue

            candidate = self._normalize_customer_name(match.group(3))
            if candidate:
                return candidate

        return None

    def extract_cementos_customer_postal_code(self, lines: list[str]) -> str | None:
        header_index = self._find_header_index(lines)
        if header_index is None:
            return None

        for line in lines[header_index + 1 : header_index + 6]:
            if self._is_customer_block_stop(line):
                break

            candidate = normalize_postal_code(line)
            if candidate:
                return candidate

        return None

    def extract_cementos_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if not match:
            return None
        return self.clean_invoice_number_candidate(match.group(1))

    def extract_cementos_invoice_date(self, text: str) -> str | None:
        match = DATE_PATTERN.search(text)
        if not match:
            return None
        return normalize_date(match.group(1))

    def extract_cementos_tax_breakdown(
        self,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        for index in range(len(lines) - 1, -1, -1):
            if not self._is_cementos_tax_header(lines[index]):
                continue

            for candidate_line in lines[index + 1 : min(len(lines), index + 5)]:
                triplet = self._pick_last_coherent_triplet(
                    self.extract_amounts_from_fragment(candidate_line, ignore_percent=False)
                )
                if triplet is not None:
                    return triplet

        for line in reversed(lines[-8:]):
            triplet = self._pick_last_coherent_triplet(
                self.extract_amounts_from_fragment(line, ignore_percent=False)
            )
            if triplet is not None:
                return triplet

        return None, None, None

    def _find_header_index(self, lines: list[str]) -> int | None:
        for index, line in enumerate(lines[:8]):
            if HEADER_LINE_PATTERN.search(line):
                return index
        return None

    def _has_cementos_tax_layout(self, text: str) -> bool:
        normalized_text = self._normalize_for_match(text)
        return (
            "base imp" in normalized_text
            and "imp iva" in normalized_text
            and "total" in normalized_text
            and "imp bruto" in normalized_text
        )

    def _is_cementos_tax_header(self, line: str) -> bool:
        normalized_line = self._normalize_for_match(line)
        return (
            "base imp" in normalized_line
            and "imp iva" in normalized_line
            and "total" in normalized_line
        )

    def _is_customer_block_stop(self, line: str) -> bool:
        normalized_line = self._normalize_for_match(line)
        return any(
            marker in normalized_line
            for marker in (
                "forma de pago",
                "banco",
                "codigo",
                "c digo",
                "albaran",
                "tfno",
            )
        )

    def _normalize_customer_name(self, value: str) -> str | None:
        cleaned = clean_name_candidate(value)
        if not cleaned:
            return None

        candidate = re.sub(r"\s+", " ", cleaned).strip(" ,;-")
        if "," in candidate:
            parts = [part.strip() for part in candidate.split(",") if part.strip()]
            if len(parts) >= 2:
                candidate = f"{' '.join(parts[1:])} {parts[0]}"

        candidate = re.sub(r"\s+", " ", candidate).strip()
        if candidate == "":
            return None

        return candidate.title()

    def _normalize_for_match(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
        without_punctuation = re.sub(r"[^a-zA-Z0-9]+", " ", without_accents)
        return re.sub(r"\s+", " ", without_punctuation).strip().lower()

    def _pick_last_coherent_triplet(
        self,
        values: list[float],
    ) -> tuple[float, float, float] | None:
        if len(values) < 3:
            return None

        amounts = [abs(value) for value in values]

        for total_index in range(len(amounts) - 1, 1, -1):
            total_value = amounts[total_index]

            for iva_index in range(total_index - 1, 0, -1):
                iva_value = amounts[iva_index]
                if iva_value >= total_value:
                    continue

                for base_index in range(iva_index - 1, -1, -1):
                    base_value = amounts[base_index]
                    if base_value <= 0 or base_value >= total_value:
                        continue

                    if abs((base_value + iva_value) - total_value) <= 0.02:
                        return base_value, iva_value, total_value

        return None
