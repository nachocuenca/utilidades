from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.dates import normalize_date

INVOICE_NUMBER_PATTERN = re.compile(
    r"(?im)^\s*factura\s+([A-Z0-9][A-Z0-9/\-.]+)\s*$",
)
DATE_PATTERN = re.compile(r"\b([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})\b")


class VersotelInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "versotel"
    priority = 360

    # Runtime case lives under /ZENNIO/, but the fiscal issuer in the document
    # is Versotel and Zennio only appears as brand/web/email context.
    SUPPLIER_NAME = "VERSOTEL PRODUCTO ELECTRÓNICO S.L."
    SUPPLIER_TAX_ID = "B86314903"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        normalized_text = self._normalize_for_match(text)
        score = 0

        if self.matches_file_path_hint(file_path, ("zennio", "versotel")):
            score += 1

        if "versotel producto electronico" in normalized_text:
            score += 4

        if "zennio.com" in normalized_text:
            score += 2

        if "zenniospain.com" in normalized_text:
            score += 1

        if "b86314903" in normalized_text or "esb86314903" in normalized_text:
            score += 4

        subtotal, iva, total = self.extract_versotel_amounts(text)
        has_summary = subtotal is not None and iva is not None and total is not None
        has_invoice_number = self.extract_versotel_invoice_number(text) is not None
        has_date = self.extract_versotel_invoice_date(text) is not None

        return score >= 5 and has_summary and has_invoice_number and has_date

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.extract_versotel_supplier_tax_id(text)
        result.numero_factura = self.extract_versotel_invoice_number(text)
        result.fecha_factura = self.extract_versotel_invoice_date(text)
        result.subtotal, result.iva, result.total = self.extract_versotel_amounts(text)

        return result.finalize()

    def extract_versotel_supplier_tax_id(self, text: str) -> str | None:
        for candidate in self.extract_exact_tax_ids(text):
            if candidate == self.SUPPLIER_TAX_ID:
                return candidate

        if "versotel producto electronico" in self._normalize_for_match(text):
            return self.SUPPLIER_TAX_ID

        return None

    def extract_versotel_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            candidate = self.clean_invoice_number_candidate(match.group(1))
            if candidate:
                return candidate

        return super().extract_invoice_number(text)

    def extract_versotel_invoice_date(self, text: str) -> str | None:
        lines = self.extract_lines(text)

        for index, line in enumerate(lines):
            normalized_line = self._normalize_for_match(line)
            if "fecha" not in normalized_line or "vencimiento" not in normalized_line:
                continue

            if index + 1 >= len(lines):
                continue

            match = DATE_PATTERN.search(lines[index + 1])
            if not match:
                continue

            candidate = normalize_date(match.group(1))
            if candidate:
                return candidate

        return super().extract_date(text)

    def extract_versotel_amounts(
        self,
        text: str,
    ) -> tuple[float | None, float | None, float | None]:
        lines = self.extract_lines(text)
        tail_lines = lines[-18:]

        subtotal = self._extract_last_summary_amount(tail_lines, "subtotal")
        iva = self._extract_last_summary_amount(tail_lines, "iva")
        total = self._extract_last_summary_amount(tail_lines, "total")

        if subtotal is not None and iva is not None and total is not None:
            if abs((subtotal + iva) - total) <= 0.02:
                return subtotal, iva, total

        return None, None, None

    def _extract_last_summary_amount(self, lines: list[str], label: str) -> float | None:
        for line in reversed(lines):
            normalized_line = self._normalize_for_match(line)

            if label == "subtotal" and not normalized_line.startswith("subtotal"):
                continue

            if label == "iva" and not re.match(r"^iva\b", normalized_line):
                continue

            if label == "total" and not re.match(r"^total\b", normalized_line):
                continue

            values = self.extract_amounts_from_fragment(line, ignore_percent=False)
            if values:
                return values[-1]

        return None

    def _normalize_for_match(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        return re.sub(r"\s+", " ", without_accents).strip().lower()
