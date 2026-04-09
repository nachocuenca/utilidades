from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date

SUPPLIER_NAME_PATTERN = re.compile(
    r"W(?:U|\u00dc)RTH\s+ESPA(?:N|\u00d1)A,\s*S\.A\.",
    re.IGNORECASE,
)
SUPPLIER_TAX_ID_PATTERN = re.compile(r"\bNIF:\s*(A\d{8})\b", re.IGNORECASE)
INVOICE_NUMBER_PATTERN = re.compile(
    r"(?im)^\s*No\s+factura\s+([A-Z0-9][A-Z0-9/-]*)\b",
)
DATE_PATTERN = re.compile(
    r"(?im)^\s*Fecha\s+([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})\b",
)
SUMMARY_LINE_PATTERN = re.compile(
    r"^\s*"
    r"(?P<portes>[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?)\s+"
    r"(?P<subtotal>[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?)\s+"
    r"\d{1,2}(?:[.,]\d{2})?%\s+"
    r"(?P<iva>[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?)\s+"
    r"(?P<total>[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?)\s*$",
    re.IGNORECASE,
)


class WurthInvoiceParser(BaseInvoiceParser):
    parser_name = "wurth"
    priority = 340

    SUPPLIER_TAX_ID = "A08472276"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        normalized_text = self._normalize_for_match(text)

        supplier_hits = 0
        if self.matches_file_path_hint(file_path, ("wurth", "wuerth")):
            supplier_hits += 1
        if "wurth espana" in normalized_text:
            supplier_hits += 2
        if "wurth.es" in normalized_text:
            supplier_hits += 1
        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            supplier_hits += 2

        layout_hits = 0
        if "no factura" in normalized_text and "no cliente" in normalized_text:
            layout_hits += 1
        if "su interlocutor de la red de ventas" in normalized_text:
            layout_hits += 1
        if self.has_summary_header(normalized_text):
            layout_hits += 1

        return supplier_hits >= 2 and layout_hits >= 1

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        lines = self.extract_lines(text)

        result.nombre_proveedor = self.extract_wurth_supplier_name(text)
        result.nif_proveedor = self.extract_wurth_supplier_tax_id(text, lines)
        result.numero_factura = self.extract_wurth_invoice_number(text, file_path)
        result.fecha_factura = self.extract_wurth_invoice_date(text, file_path)
        result.subtotal, result.iva, result.total = self.extract_wurth_amounts(lines)

        return result.finalize()

    def extract_wurth_supplier_name(self, text: str) -> str | None:
        matches = list(SUPPLIER_NAME_PATTERN.finditer(text))
        if not matches:
            return None
        return matches[-1].group(0).strip()

    def extract_wurth_supplier_tax_id(self, text: str, lines: list[str]) -> str | None:
        for index in range(len(lines) - 1, -1, -1):
            if not SUPPLIER_NAME_PATTERN.search(lines[index]):
                continue

            supplier_block = " ".join(lines[index:index + 6])
            match = SUPPLIER_TAX_ID_PATTERN.search(supplier_block)
            if match:
                return match.group(1).upper()

        for line in reversed(lines[-10:]):
            match = SUPPLIER_TAX_ID_PATTERN.search(line)
            if not match:
                continue

            candidate = match.group(1).upper()
            if candidate == self.SUPPLIER_TAX_ID:
                return candidate

        for candidate in self.extract_exact_tax_ids(text):
            if candidate == self.SUPPLIER_TAX_ID:
                return candidate

        return None

    def extract_wurth_invoice_number(self, text: str, file_path: str | Path) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            candidate = self.clean_invoice_number_candidate(match.group(1))
            if candidate:
                return candidate

        return self.extract_filename_invoice_number(
            file_path,
            [
                r"wuerth[_\-\s]?factura[_\-\s]?(\d{8,12})",
                r"factura[_\-\s]?(\d{8,12})",
            ],
        )

    def extract_wurth_invoice_date(self, text: str, file_path: str | Path) -> str | None:
        match = DATE_PATTERN.search(text)
        if match:
            candidate = normalize_date(match.group(1))
            if candidate:
                return candidate

        return self.extract_filename_date(file_path)

    def extract_wurth_amounts(
        self,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        for index, line in enumerate(lines):
            if not self.has_summary_header(self._normalize_for_match(line)):
                continue

            for next_line in lines[index + 1:index + 4]:
                triplet = self.extract_summary_triplet_from_line(next_line)
                if triplet is not None:
                    return triplet

        tail_start = max(0, len(lines) - 12)
        for index in range(len(lines) - 1, tail_start - 1, -1):
            if not self.has_summary_context(lines, index):
                continue

            triplet = self.extract_summary_triplet_from_line(lines[index])
            if triplet is not None:
                return triplet

        return None, None, None

    def extract_summary_triplet_from_line(
        self,
        line: str,
    ) -> tuple[float, float, float] | None:
        match = SUMMARY_LINE_PATTERN.search(line)
        if match:
            subtotal = parse_amount(match.group("subtotal"))
            iva = parse_amount(match.group("iva"))
            total = parse_amount(match.group("total"))
            if self.is_coherent_triplet(subtotal, iva, total):
                return subtotal, iva, total

        values = self.extract_amounts_from_fragment(line, ignore_percent=True)
        return self.pick_last_coherent_triplet(values)

    def pick_last_coherent_triplet(
        self,
        values: list[float],
    ) -> tuple[float, float, float] | None:
        if len(values) < 3:
            return None

        for start_index in range(len(values) - 3, -1, -1):
            subtotal, iva, total = values[start_index:start_index + 3]
            if self.is_coherent_triplet(subtotal, iva, total):
                return subtotal, iva, total

        return None

    def is_coherent_triplet(
        self,
        subtotal: float | None,
        iva: float | None,
        total: float | None,
    ) -> bool:
        if subtotal is None or iva is None or total is None:
            return False
        return abs((subtotal + iva) - total) <= 0.02

    def has_summary_context(self, lines: list[str], index: int) -> bool:
        start_index = max(0, index - 2)
        context = " ".join(lines[start_index:index + 1])
        return self.has_summary_header(self._normalize_for_match(context))

    def has_summary_header(self, normalized_text: str) -> bool:
        return (
            "portes eur" in normalized_text
            and "valor neto eur" in normalized_text
            and "importe total eur" in normalized_text
            and (
                "impte. iva eur" in normalized_text
                or "impte iva eur" in normalized_text
            )
        )

    def _normalize_for_match(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        return re.sub(r"\s+", " ", without_accents).strip().lower()
