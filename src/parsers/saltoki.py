from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount

AMOUNT_TOKEN_PATTERN = re.compile(
    r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?"
)

HEADER_ROW_PATTERN = re.compile(
    r"^\s*\d+\s+([0-9]{2}[-/][0-9]{2}[-/][0-9]{4})\s+(\d+)\s+\d+\s*$",
    re.IGNORECASE,
)

INVOICE_NUMBER_PATTERN = re.compile(
    r"(?:n[úu]mero|numero|factura|albar[aá]n)\s*(?:de)?\s*(?:factura)?\s*[:#-]?\s*(\d{3,})",
    re.IGNORECASE,
)

DATE_PATTERN = re.compile(
    r"(?:fecha|fec\.)\s*[:#-]?\s*([0-9]{2}[-/][0-9]{2}[-/][0-9]{4})",
    re.IGNORECASE,
)

EURO_TOTAL_PATTERN = re.compile(
    r"([0-9]+(?:[.,][0-9]+)?)\s*€",
    re.IGNORECASE,
)


class SaltokiInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "saltoki"
    priority = 490

    BENIDORM_SUPPLIER_NAME = "SALTOKI BENIDORM"
    BENIDORM_SUPPLIER_TAX_ID = "B71406607"

    ALICANTE_SUPPLIER_NAME = "SALTOKI ALICANTE"
    ALICANTE_SUPPLIER_TAX_ID = "B71406623"

    DEFAULT_CUSTOMER_NAME = "Daniel Cuenca Moya"
    DEFAULT_CUSTOMER_TAX_ID = "48334490J"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("saltoki",)):
            return True

        return "saltoki" in normalized_text or "saltoki.es" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        lines = self.extract_lines(text)

        branch = self.detect_branch(text, lines, file_path)

        result.nombre_proveedor = self.get_supplier_name(branch)
        result.nif_proveedor = self.get_supplier_tax_id(branch)
        result.nombre_cliente = self.DEFAULT_CUSTOMER_NAME
        result.nif_cliente = self.DEFAULT_CUSTOMER_TAX_ID

        numero_factura, fecha_factura = self.extract_header_data(text, lines, file_path)
        result.numero_factura = numero_factura
        result.fecha_factura = fecha_factura

        subtotal, iva, total = self.extract_totals(lines, text)
        result.subtotal = subtotal
        result.iva = iva
        result.total = total

        return result.finalize()

    def detect_branch(self, text: str, lines: list[str], file_path: str | Path) -> str:
        upper_text = text.upper()
        top_text = "\n".join(lines[:12]).upper()
        path_text = self.get_path_text(file_path)
        folder_hint = (self.get_folder_hint_name(file_path) or "").lower()

        if self.ALICANTE_SUPPLIER_TAX_ID in upper_text:
            return "alicante"
        if self.BENIDORM_SUPPLIER_TAX_ID in upper_text:
            return "benidorm"

        if "SALTOKI ALICANTE" in top_text:
            return "alicante"
        if "SALTOKI BENIDORM" in top_text:
            return "benidorm"

        if "alicante" in path_text or "alicante" in folder_hint:
            return "alicante"
        if "benidorm" in path_text or "benidorm" in folder_hint:
            return "benidorm"

        return "unknown"

    def get_supplier_name(self, branch: str) -> str:
        if branch == "benidorm":
            return self.BENIDORM_SUPPLIER_NAME
        if branch == "alicante":
            return self.ALICANTE_SUPPLIER_NAME
        return "SALTOKI"

    def get_supplier_tax_id(self, branch: str) -> str | None:
        if branch == "benidorm":
            return self.BENIDORM_SUPPLIER_TAX_ID
        if branch == "alicante":
            return self.ALICANTE_SUPPLIER_TAX_ID
        return None

    def extract_header_data(
        self,
        text: str,
        lines: list[str],
        file_path: str | Path,
    ) -> tuple[str | None, str | None]:
        from_filename_number = self.extract_filename_invoice_number(
            file_path,
            [
                r"copia de (\d+)",
                r"factura[ _-]*(\d+)",
                r"^(\d+)",
            ],
        )
        from_filename_date = self.extract_filename_date(
            file_path,
            patterns=[
                r"(20\d{2}[01]\d[0-3]\d)",
                r"([0-3]\d[_\-][01]\d[_\-]20\d{2})",
                r"(20\d{2}[_\-][01]\d[_\-][0-3]\d)",
            ],
        )

        for line in lines:
            match = HEADER_ROW_PATTERN.search(line)
            if not match:
                continue

            fecha = match.group(1)
            numero = self.clean_invoice_number_candidate(match.group(2))
            return numero, fecha

        for line in lines[:20]:
            date_match = DATE_PATTERN.search(line)
            number_match = INVOICE_NUMBER_PATTERN.search(line)

            if date_match or number_match:
                return (
                    self.clean_invoice_number_candidate(number_match.group(1)) if number_match else from_filename_number,
                    date_match.group(1) if date_match else from_filename_date,
                )

        text_date_match = DATE_PATTERN.search(text)
        text_number_match = INVOICE_NUMBER_PATTERN.search(text)

        return (
            self.clean_invoice_number_candidate(text_number_match.group(1)) if text_number_match else from_filename_number,
            text_date_match.group(1) if text_date_match else from_filename_date,
        )

    def extract_totals(
        self,
        lines: list[str],
        text: str,
    ) -> tuple[float | None, float | None, float | None]:
        total = self.extract_total_from_tail(lines, text)
        base, iva = self.extract_base_and_iva_from_tail(lines)

        if base is None and iva is not None and total is not None:
            base = round(total - iva, 2)

        if iva is None and base is not None and total is not None:
            iva = round(total - base, 2)

        if base is None:
            base = self.extract_labeled_amount(text, [r"base\s+imponible", r"subtotal"])

        if iva is None:
            iva = self.extract_labeled_amount(text, [r"i\.?v\.?a\.?", r"cuota\s+iva", r"importe\s+iva"])

        if total is None:
            total = self.extract_labeled_amount(text, [r"total\s+factura", r"importe\s+total", r"\btotal\b"])

        return base, iva, total

    def extract_total_from_tail(self, lines: list[str], text: str) -> float | None:
        for line in reversed(lines[-15:]):
            match = EURO_TOTAL_PATTERN.search(line)
            if not match:
                continue

            value = parse_amount(match.group(1))
            if value is not None:
                return value

        matches = EURO_TOTAL_PATTERN.findall(text)
        if matches:
            value = parse_amount(matches[-1])
            if value is not None:
                return value

        return None

    def extract_base_and_iva_from_tail(self, lines: list[str]) -> tuple[float | None, float | None]:
        tail_lines = lines[-20:]

        for line in reversed(tail_lines):
            if self.looks_like_date_line(line):
                continue

            amounts = self.parse_amounts_from_line(line)
            if not amounts:
                continue

            if len(amounts) == 3 and self.looks_like_vat_rate(amounts[1]):
                return amounts[0], amounts[2]

            if len(amounts) == 2 and self.looks_like_vat_rate(amounts[0]):
                return None, amounts[1]

            if len(amounts) == 3 and self.looks_like_vat_rate(amounts[0]):
                return amounts[2], amounts[1]

        return None, None

    def looks_like_date_line(self, line: str) -> bool:
        normalized = line.strip()
        if normalized == "":
            return False

        return re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b", normalized) is not None

    def looks_like_vat_rate(self, value: float) -> bool:
        return round(value, 2) in {4.00, 10.00, 21.00}

    def parse_amounts_from_line(self, line: str) -> list[float]:
        values: list[float] = []

        for raw_match in AMOUNT_TOKEN_PATTERN.findall(line):
            parsed = parse_amount(raw_match)
            if parsed is None:
                continue
            values.append(parsed)

        return values
