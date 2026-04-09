from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.dates import normalize_date

INVOICE_NUMBER_PATTERN = re.compile(
    r"(?:\bno\s+factura\b|\bfactura\s+n[º°o]?\b)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/.\-]+)",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"fecha\s+registro\s*[:#-]?\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
    re.IGNORECASE,
)


class FempaInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "fempa"
    priority = 340

    SUPPLIER_NAME = "Federación de Empresarios del Metal de la provincia de Alicante"
    SUPPLIER_TAX_ID = "G03096963"
    SUPPLIER_MARKERS = (
        "fed. empresarios del metal",
        "de la provincia de alicante",
        "fempa@fempa.es",
        "www.fempa.es",
    )
    EXEMPT_MARKERS = (
        "iva exento",
        "art.20 uno 12",
        "art.20 tres",
    )
    NON_FISCAL_MARKERS = (
        "adeudo recibido",
        "titular de la domiciliacion",
        "titular de la domiciliación",
        "entidad emisora",
    )

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        normalized_text = text.lower()
        if any(marker in normalized_text for marker in self.NON_FISCAL_MARKERS):
            return False

        if not self.looks_like_invoice_document(text):
            return False

        if not any(marker in normalized_text for marker in self.EXEMPT_MARKERS):
            return False

        score = 0

        if self.matches_file_path_hint(file_path, ("fempa",)):
            score += 1

        if any(marker in normalized_text for marker in self.SUPPLIER_MARKERS):
            score += 3

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 2

        if "no factura" in normalized_text:
            score += 1

        if "base imponible" in normalized_text and "total factura" in normalized_text:
            score += 1

        return score >= 5

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.extract_fempa_supplier_tax_id(text)
        result.nif_cliente = self.extract_tax_id_from_text(text)
        result.numero_factura = self.extract_fempa_invoice_number(text)
        result.fecha_factura = self.extract_fempa_date(text)

        total = self.extract_fempa_total(text)
        subtotal = self.extract_fempa_subtotal(text)

        if subtotal is None:
            subtotal = total

        if total is None:
            total = subtotal

        result.subtotal = subtotal
        result.iva = 0.0
        result.total = total

        return result.finalize()

    def extract_fempa_supplier_tax_id(self, text: str) -> str | None:
        for candidate in self.extract_exact_tax_ids(text):
            if candidate == self.SUPPLIER_TAX_ID:
                return candidate

        if self.SUPPLIER_TAX_ID.lower() in text.lower():
            return self.SUPPLIER_TAX_ID

        return None

    def extract_fempa_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            candidate = self.clean_invoice_number_candidate(match.group(1))
            if candidate:
                return candidate

        return self.extract_invoice_number(text)

    def extract_fempa_date(self, text: str) -> str | None:
        match = DATE_PATTERN.search(text)
        if match:
            candidate = normalize_date(match.group(1))
            if candidate:
                return candidate

        return self.extract_date(text)

    def extract_fempa_total(self, text: str) -> float | None:
        for line in reversed(self.extract_lines(text)):
            if "total factura" not in line.lower():
                continue

            values = self.extract_amounts_from_fragment(line, ignore_percent=True)
            if values:
                return values[-1]

        return self.extract_labeled_amount(
            text,
            [r"total\s+factura"],
            ignore_percent=True,
        )

    def extract_fempa_subtotal(self, text: str) -> float | None:
        lines = self.extract_lines(text)

        for index, line in enumerate(lines):
            if "base imponible" not in line.lower():
                continue

            for candidate_line in lines[index:index + 3]:
                values = self.extract_amounts_from_fragment(candidate_line, ignore_percent=True)
                if values:
                    return values[0]

        value = self.extract_labeled_amount(
            text,
            [r"base\s+imponible"],
            ignore_percent=True,
        )
        if value is not None:
            return value

        total = self.extract_fempa_total(text)
        if total is not None and any(marker in text.lower() for marker in self.EXEMPT_MARKERS):
            return total

        return None
