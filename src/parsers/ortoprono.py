from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.ids import normalize_postal_code, normalize_tax_id

SUPPLIER_NAME = "Organizacion de Servicios Ortopedicos Totales, S.L.U."
SUPPLIER_TAX_ID = "B46264305"
BRAND_NAME = "ORTOPRONO"

SUPPLIER_TAX_ID_PATTERN = re.compile(r"(?<![A-Z0-9])B[\s\-./]*46264305(?![A-Z0-9])", re.IGNORECASE)
INVOICE_NUMBER_PATTERN = re.compile(r"\b(FA-\d{6,})\b", re.IGNORECASE)
DATE_AFTER_INVOICE_PATTERN = re.compile(
    r"\bFA-\d{6,}\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    re.IGNORECASE,
)

SUPPLIER_NAME_MARKERS = (
    "organizacion de servicios ortopedicos totales",
    "organización de servicios ortopédicos totales",
)
BRAND_MARKERS = (
    "ortoprono",
    "www.ortoprono.es",
    "ortoprono@ortoprono.es",
)
STRUCTURAL_MARKERS = (
    "ortopedia tecnica",
    "ortopedia técnica",
    "avenida limones",
    "felix pizcueta",
    "félix pizcueta",
)
CUSTOMER_NAME_BLOCK_PATTERNS = (
    re.compile(r"\b(calle|avenida|avda\.?|c/|fax|tel[eefono]*|telefono|factura|alicante|benidorm)\b", re.IGNORECASE),
    re.compile(r"\b(c[oó]digo|codigo|ortoprono|ortopedia|www\.|@)\b", re.IGNORECASE),
)


class OrtopronoInvoiceParser(BaseInvoiceParser):
    parser_name = "ortoprono"
    priority = 365

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        if SUPPLIER_TAX_ID_PATTERN.search(text):
            return True

        if self._can_handle_by_supplier(
            text,
            supplier_name=SUPPLIER_NAME,
            supplier_tax_id=SUPPLIER_TAX_ID,
            file_path=file_path,
        ):
            return True

        normalized_text = self._normalize_lookup_text(text)
        has_brand = any(marker in normalized_text for marker in BRAND_MARKERS)
        if not has_brand:
            return False

        structural_hits = sum(1 for marker in STRUCTURAL_MARKERS if marker in normalized_text)
        has_invoice_evidence = "factura" in normalized_text and (
            INVOICE_NUMBER_PATTERN.search(text) is not None or self.extract_date(text) is not None
        )

        if structural_hits >= 1 and has_invoice_evidence:
            return True

        return (
            self.matches_file_path_hint(file_path, ("ortoprono",))
            and INVOICE_NUMBER_PATTERN.search(text) is not None
            and "factura" in normalized_text
        )

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = SUPPLIER_NAME
        result.nif_proveedor = self.extract_ortoprono_supplier_tax_id(text)
        result.nombre_cliente = self.extract_ortoprono_customer_name(lines)
        result.nif_cliente = self.extract_ortoprono_customer_tax_id(text)
        result.cp_cliente = self.extract_ortoprono_customer_postal_code(lines)
        result.numero_factura = self.extract_ortoprono_invoice_number(text)
        result.fecha_factura = self.extract_ortoprono_date(text)
        result.subtotal, result.iva, result.total = self.extract_ortoprono_amounts(text, lines)

        return result.finalize()

    def extract_ortoprono_supplier_tax_id(self, text: str) -> str | None:
        for candidate in self.extract_exact_tax_ids(text):
            if candidate == SUPPLIER_TAX_ID:
                return candidate

        match = SUPPLIER_TAX_ID_PATTERN.search(text)
        if match:
            return normalize_tax_id(match.group(0))

        normalized_text = self._normalize_lookup_text(text)
        if any(marker in normalized_text for marker in SUPPLIER_NAME_MARKERS):
            return SUPPLIER_TAX_ID

        return None

    def extract_ortoprono_customer_tax_id(self, text: str) -> str | None:
        for candidate in self.extract_exact_tax_ids(text):
            if candidate == SUPPLIER_TAX_ID:
                continue
            return candidate

        return None

    def extract_ortoprono_customer_name(self, lines: list[str]) -> str | None:
        tax_line_index = self.find_ortoprono_customer_tax_line_index(lines)
        search_limit = tax_line_index if tax_line_index is not None else min(len(lines), 12)

        for index in range(search_limit - 1, -1, -1):
            candidate = lines[index].strip()
            if self.is_safe_ortoprono_customer_name(candidate):
                if candidate.isupper():
                    return candidate.title()
                return candidate

        return None

    def extract_ortoprono_customer_postal_code(self, lines: list[str]) -> str | None:
        name_index = self.find_ortoprono_customer_name_line_index(lines)
        tax_line_index = self.find_ortoprono_customer_tax_line_index(lines)

        if name_index is None or tax_line_index is None:
            return None

        for line in lines[name_index + 1 : tax_line_index]:
            candidate = normalize_postal_code(line)
            if candidate:
                return candidate

        return None

    def find_ortoprono_customer_tax_line_index(self, lines: list[str]) -> int | None:
        for index, line in enumerate(lines):
            customer_ids = [
                candidate
                for candidate in self.extract_exact_tax_ids(line)
                if candidate != SUPPLIER_TAX_ID
            ]
            if customer_ids:
                return index

        return None

    def find_ortoprono_customer_name_line_index(self, lines: list[str]) -> int | None:
        tax_line_index = self.find_ortoprono_customer_tax_line_index(lines)
        search_limit = tax_line_index if tax_line_index is not None else min(len(lines), 12)

        for index in range(search_limit - 1, -1, -1):
            if self.is_safe_ortoprono_customer_name(lines[index]):
                return index

        return None

    def is_safe_ortoprono_customer_name(self, value: str | None) -> bool:
        if value is None:
            return False

        candidate = value.strip()
        if candidate == "":
            return False

        if any(character.isdigit() for character in candidate):
            return False

        if len(candidate.split()) < 2:
            return False

        if self.extract_exact_tax_ids(candidate):
            return False

        return not any(pattern.search(candidate) for pattern in CUSTOMER_NAME_BLOCK_PATTERNS)

    def extract_ortoprono_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            return self.clean_invoice_number_candidate(match.group(1).upper())

        return self.extract_invoice_number(text)

    def extract_ortoprono_date(self, text: str) -> str | None:
        match = DATE_AFTER_INVOICE_PATTERN.search(text)
        if match:
            candidate = normalize_date(match.group(1))
            if candidate:
                return candidate

        return self.extract_date(text)

    def extract_ortoprono_amounts(
        self,
        text: str,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        for index, line in enumerate(lines):
            if "iva" not in line.lower():
                continue

            values = self.extract_amounts_from_fragment(line, ignore_percent=False)
            if len(values) < 2:
                continue

            base_value = values[-2]
            iva_value = values[-1]
            total_value = self.extract_total_after_tax_line(lines, index, base_value, iva_value)

            return (
                self._apply_credit_sign(text, base_value),
                self._apply_credit_sign(text, iva_value),
                self._apply_credit_sign(text, total_value),
            )

        return (
            self.extract_subtotal(text),
            self.extract_iva(text),
            self.extract_total(text),
        )

    def extract_total_after_tax_line(
        self,
        lines: list[str],
        tax_line_index: int,
        base_value: float,
        iva_value: float,
    ) -> float | None:
        expected_total = round(base_value + iva_value, 2)

        for line in lines[tax_line_index + 1 : tax_line_index + 5]:
            values = self.extract_amounts_from_fragment(line, ignore_percent=True)
            for value in values:
                if abs(value - expected_total) <= 0.02:
                    return value

        return None
