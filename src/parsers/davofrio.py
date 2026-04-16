from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.ids import normalize_tax_id

DAVOFRIO_MARKERS = (
    "davofrio",
    "oirfovad",
    "www.davofrio.com",
)

INVOICE_NUMBER_PATTERN = re.compile(r"\b(FVC\d{2}-\d{4})\b", re.IGNORECASE)
DATE_AFTER_INVOICE_PATTERN = re.compile(
    r"\bFVC\d{2}-\d{4}\s+(\d{1,2}/\d{1,2}/\d{2,4})\b",
    re.IGNORECASE,
)
SUMMARY_STOP_PATTERN = re.compile(
    r"\b(forma\s+de\s+pago|vencimientos|observaciones|pagado|p.gina)\b",
    re.IGNORECASE,
)
TAX_ID_TOKEN_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9\-/.]{7,15}[A-Z0-9]", re.IGNORECASE)


class DavofrioInvoiceParser(BaseInvoiceParser):
    parser_name = "davofrio"
    priority = 340

    SUPPLIER_NAME = "DAVOFRIO, S.L.U."
    SUPPLIER_TAX_ID = "B54141999"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if any(marker in normalized_text for marker in DAVOFRIO_MARKERS):
            return True

        if self.matches_file_path_hint(file_path, ("davofrio",)) and INVOICE_NUMBER_PATTERN.search(text):
            return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(text, file_path)
        result.nif_proveedor = self.extract_supplier_tax_id(text, lines)
        result.numero_factura = self.extract_davofrio_invoice_number(text, file_path)
        result.fecha_factura = self.extract_davofrio_date(text, file_path)

        subtotal, iva, total = self.extract_davofrio_amounts(text, lines)
        result.subtotal = subtotal
        result.iva = iva
        result.total = total

        return result.finalize()

    def extract_supplier_name(self, text: str, file_path: str | Path) -> str | None:
        normalized_text = text.lower()

        if any(marker in normalized_text for marker in DAVOFRIO_MARKERS):
            return self.SUPPLIER_NAME

        if self.matches_file_path_hint(file_path, ("davofrio",)):
            return self.SUPPLIER_NAME

        return None

    def extract_supplier_tax_id(self, text: str, lines: list[str]) -> str | None:
        customer_tax_id = self.extract_tax_id_from_text(text)

        for index, line in enumerate(lines[:12]):
            context = " ".join(lines[max(0, index - 1) : min(len(lines), index + 2)])
            prefer_reversed = "fic" in context.lower()

            for candidate in self.extract_tax_ids_from_line(line, prefer_reversed=prefer_reversed):
                if candidate == customer_tax_id:
                    continue
                return candidate

        return self.SUPPLIER_TAX_ID

    def extract_tax_ids_from_line(self, line: str, *, prefer_reversed: bool = False) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        variants = (line[::-1], line) if prefer_reversed else (line, line[::-1])

        for variant in variants:
            direct_candidate = normalize_tax_id(variant)
            if direct_candidate and direct_candidate not in seen:
                seen.add(direct_candidate)
                candidates.append(direct_candidate)

            for token in TAX_ID_TOKEN_PATTERN.findall(variant.upper()):
                normalized = normalize_tax_id(token)
                if normalized is None or normalized in seen:
                    continue
                seen.add(normalized)
                candidates.append(normalized)

        return candidates

    def extract_davofrio_invoice_number(self, text: str, file_path: str | Path) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            return self.clean_invoice_number_candidate(match.group(1).upper())

        return self.extract_filename_invoice_number(file_path, [r"(FVC\d{2}-\d{4})"])

    def extract_davofrio_date(self, text: str, file_path: str | Path) -> str | None:
        match = DATE_AFTER_INVOICE_PATTERN.search(text)
        if match:
            candidate = normalize_date(match.group(1))
            if candidate:
                return candidate

        return self.extract_filename_date(file_path) or self.extract_date(text)

    def extract_davofrio_amounts(
        self,
        text: str,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        summary_lines = self.extract_summary_lines(lines)

        if summary_lines:
            base_candidates: list[float] = []
            iva_candidates: list[float] = []
            total_candidates: list[float] = []

            for index, line in enumerate(summary_lines):
                amounts = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if not amounts:
                    continue

                previous_line = summary_lines[index - 1].lower() if index > 0 else ""

                if "%" in line:
                    base_candidates.append(amounts[0])
                    iva_candidates.append(amounts[-1])

                if "retenci" in previous_line or "total" in line.lower():
                    total_candidates.append(amounts[-1])

                if len(amounts) >= 2:
                    base_candidates.append(amounts[0])
                    total_candidates.append(amounts[-1])

            for total_value in reversed(total_candidates):
                for base_value in reversed(base_candidates):
                    for iva_value in reversed(iva_candidates):
                        if abs((base_value + iva_value) - total_value) <= 0.01:
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

    def extract_summary_lines(self, lines: list[str]) -> list[str]:
        if not lines:
            return []

        start_index: int | None = None
        lower_lines = [line.lower() for line in lines]

        for index in range(len(lower_lines) - 1, -1, -1):
            line = lower_lines[index]
            if "base imponible" in line or "subtotal" in line:
                start_index = index
                break

        if start_index is None:
            return []

        summary_lines: list[str] = []
        for line in lines[start_index : start_index + 8]:
            if summary_lines and SUMMARY_STOP_PATTERN.search(line):
                break
            summary_lines.append(line)

        return summary_lines
