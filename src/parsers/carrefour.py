from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.ids import normalize_postal_code, normalize_tax_id
from src.utils.names import clean_name_candidate, is_valid_name_candidate

SUPPLIER_NAME = "Carrefour S.A."
SUPPLIER_TAX_ID = "A28425270"
BRAND_NAME = "Carrefour"

SUPPLIER_TAX_ID_PATTERN = re.compile(r"(?<![A-Z0-9])A[\s\-./]*28425270(?![A-Z0-9])", re.IGNORECASE)
INVOICE_NUMBER_PATTERN = re.compile(r"\b(?:FACTURA|COD\s+FACTURA)\s*=?\s*(\d{2}A\d{7})\b", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\bFECHA\s+FACTURA\s*=?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", re.IGNORECASE)

SUPPLIER_NAME_MARKERS = (
    "carrefour s a",
    "centros comerciales carrefour s a",
)
BRAND_MARKERS = (
    "carrefour",
    "www carrefour es",
)
STRUCTURAL_MARKERS = (
    "datos facturacion",
    "cod factura",
    "fecha factura",
    "detalle del pedido",
    "total factura",
)
CUSTOMER_BLOCK_START_PATTERN = re.compile(r"^datos\s+facturaci[oó]n$", re.IGNORECASE)
CUSTOMER_BLOCK_END_PATTERN = re.compile(r"^(forma\s+de\s+pago|cod\s+factura|n[uú]m\s+pedido)\b", re.IGNORECASE)
CUSTOMER_NAME_BLOCK_PATTERNS = (
    re.compile(r"\b(calle|av\.?|avenida|benidorm|alicante|alacant|forma\s+de\s+pago|paypal)\b", re.IGNORECASE),
    re.compile(r"\b(factura|pedido|carrefour|www\.|@)\b", re.IGNORECASE),
)


class CarrefourInvoiceParser(BaseInvoiceParser):
    parser_name = "carrefour"
    priority = 480

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
        has_invoice_evidence = (
            INVOICE_NUMBER_PATTERN.search(text) is not None
            and DATE_PATTERN.search(text) is not None
            and "total factura" in normalized_text
        )

        if structural_hits >= 3 and has_invoice_evidence:
            return True

        return (
            self.matches_file_path_hint(file_path, ("carrefour",))
            and structural_hits >= 3
            and INVOICE_NUMBER_PATTERN.search(text) is not None
        )

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = SUPPLIER_NAME
        result.nif_proveedor = self.extract_carrefour_supplier_tax_id(text)
        result.nombre_cliente = self.extract_carrefour_customer_name(lines)
        result.nif_cliente = self.extract_carrefour_customer_tax_id(text)
        result.cp_cliente = self.extract_carrefour_customer_postal_code(lines)
        result.numero_factura = self.extract_carrefour_invoice_number(text)
        result.fecha_factura = self.extract_carrefour_invoice_date(text)
        result.subtotal = self.extract_labeled_amount(text, [r"subtotal\s+sin\s+iva"], ignore_percent=True)
        result.iva = self.extract_labeled_amount(text, [r"total\s+iva", r"\biva\s+\d{1,2}[,.]\d{2}%"], ignore_percent=True)
        result.total = self.extract_labeled_amount(text, [r"total\s+factura"])
        result.metadatos["marca"] = BRAND_NAME

        return result.finalize()

    def extract_carrefour_supplier_tax_id(self, text: str) -> str | None:
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

    def extract_carrefour_customer_tax_id(self, text: str) -> str | None:
        for candidate in self.extract_exact_tax_ids(text):
            if candidate == SUPPLIER_TAX_ID:
                continue
            return candidate

        return None

    def extract_carrefour_customer_name(self, lines: list[str]) -> str | None:
        for line in self._extract_customer_block(lines):
            candidate = clean_name_candidate(line)
            if not self._is_safe_customer_name(candidate):
                continue
            return candidate

        return None

    def extract_carrefour_customer_postal_code(self, lines: list[str]) -> str | None:
        for line in self._extract_customer_block(lines):
            candidate = normalize_postal_code(line)
            if candidate:
                return candidate

        return None

    def extract_carrefour_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            return self.clean_invoice_number_candidate(match.group(1).upper())

        return self.extract_invoice_number(text)

    def extract_carrefour_invoice_date(self, text: str) -> str | None:
        match = DATE_PATTERN.search(text)
        if match:
            candidate = normalize_date(match.group(1))
            if candidate:
                return candidate

        return self.extract_date(text)

    def _extract_customer_block(self, lines: list[str]) -> list[str]:
        start_index: int | None = None
        end_index = len(lines)

        for index, line in enumerate(lines):
            if CUSTOMER_BLOCK_START_PATTERN.search(line.strip()):
                start_index = index + 1
                break

        if start_index is None:
            return []

        for index in range(start_index, len(lines)):
            if CUSTOMER_BLOCK_END_PATTERN.search(lines[index].strip()):
                end_index = index
                break

        return lines[start_index:end_index]

    def _is_safe_customer_name(self, value: str | None) -> bool:
        if value is None:
            return False

        candidate = value.strip()
        if not is_valid_name_candidate(candidate):
            return False

        if self.extract_exact_tax_ids(candidate):
            return False

        if any(character.isdigit() for character in candidate):
            return False

        return not any(pattern.search(candidate) for pattern in CUSTOMER_NAME_BLOCK_PATTERNS)
