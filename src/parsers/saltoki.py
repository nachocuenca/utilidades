from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount

SALTOKI_AMOUNT_PATTERN = r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?"

AMOUNT_TOKEN_PATTERN = re.compile(rf"[+-]?{SALTOKI_AMOUNT_PATTERN}")
SALTOKI_SUMMARY_LINE_PATTERN = re.compile(
    rf"^\s*({SALTOKI_AMOUNT_PATTERN})\s+({SALTOKI_AMOUNT_PATTERN})\s+({SALTOKI_AMOUNT_PATTERN})\s+({SALTOKI_AMOUNT_PATTERN})\s*$"
)
SALTOKI_SUMMARY_NUMERIC_TOKEN_PATTERN = re.compile(SALTOKI_AMOUNT_PATTERN)

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

EURO_TOTAL_PATTERN = re.compile(rf"({SALTOKI_AMOUNT_PATTERN})\s*€", re.IGNORECASE)


class SaltokiInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "saltoki"
    priority = 490

    BENIDORM_SUPPLIER_NAME = "SALTOKI BENIDORM, S.L."
    BENIDORM_SUPPLIER_TAX_ID = "B71406607"

    ALICANTE_SUPPLIER_NAME = "SALTOKI ALICANTE, S.L."
    ALICANTE_SUPPLIER_TAX_ID = "B71406623"

    DEFAULT_CUSTOMER_NAME = "Daniel Cuenca Moya"
    DEFAULT_CUSTOMER_TAX_ID = "48334490J"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        score = 0

        if self.matches_file_path_hint(file_path, ("saltoki",)):
            score += 1

        if "saltoki" in normalized_text:
            score += 2

        if "saltoki.es" in normalized_text:
            score += 1

        if any(marker in normalized_text for marker in ("saltoki alicante", "saltoki benidorm")):
            score += 1

        if any(marker in normalized_text for marker in (self.ALICANTE_SUPPLIER_TAX_ID.lower(), self.BENIDORM_SUPPLIER_TAX_ID.lower())):
            score += 2

        return score >= 2

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

        for line in lines[:30]:
            match = HEADER_ROW_PATTERN.search(line)
            if match:
                fecha = match.group(1)
                numero = self.clean_invoice_number_candidate(match.group(2))
                return numero, fecha

        for line in lines[:20]:
            date_match = DATE_PATTERN.search(line)
            number_match = INVOICE_NUMBER_PATTERN.search(line)
            if date_match and number_match:
                return (
                    self.clean_invoice_number_candidate(number_match.group(1)),
                    date_match.group(1),
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
        summary_base, summary_iva, summary_total = self.extract_summary_block_amounts(lines, text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            return summary_base, summary_iva, summary_total

        summary_line_base, summary_line_iva, summary_line_total = self.extract_summary_line_amounts(lines, text)
        if summary_line_base is not None and summary_line_iva is not None and summary_line_total is not None:
            return summary_line_base, summary_line_iva, summary_line_total

        total = self.extract_total_from_tail(lines, text)
        base, iva = self.extract_base_and_iva_from_tail(lines, total_hint=total)

        if base is None and iva is not None and total is not None:
            base = round(total - iva, 2)

        if iva is None and base is not None and total is not None:
            iva = round(total - base, 2)

        return base, iva, total

    def normalize_summary_candidate_line(self, raw_line: str) -> str:
        line = re.sub(r"\s+", " ", raw_line.strip()).strip()
        if not line:
            return ""

        line = re.sub(r"\b(\d)\s+(\d)\s*,\s*(\d)\s*(\d)\b", r"\1\2.\3\4", line)
        line = re.sub(r"(\d+)\s*,\s*0\s*0", r"\1.00", line)
        line = re.sub(r"(\d+)\s*,\s*0\s+(\d)", r"\1.0\2", line)
        line = re.sub(r"(\d+)\s+,\s+(\d+)", r"\1.\2", line)

        line = re.sub(r"\s*([.,])\s*", r"\1", line)
        line = re.sub(r"(\d)\s+([.,])", r"\1\2", line)
        line = re.sub(r"([.,])\s+(\d)", r"\1\2", line)

        return line

    def extract_amount_tokens_with_joined_pairs(self, line: str) -> list[float]:
        raw_tokens = SALTOKI_SUMMARY_NUMERIC_TOKEN_PATTERN.findall(line)
        values: list[float] = []

        i = 0
        while i < len(raw_tokens):
            token = raw_tokens[i]
            parsed = parse_amount(token)

            if parsed is not None and parsed.is_integer() and 1 <= parsed <= 99 and i + 1 < len(raw_tokens):
                next_token = raw_tokens[i + 1]
                next_parsed = parse_amount(next_token)
                if next_parsed is not None and next_parsed.is_integer() and 0 <= next_parsed <= 99:
                    merged = f"{int(parsed)}.{int(next_parsed):02d}"
                    merged_parsed = parse_amount(merged)
                    if merged_parsed is not None:
                        values.append(merged_parsed)
                        i += 2
                        continue

            if parsed is not None:
                values.append(parsed)
            i += 1

        return values

    def extract_summary_block_amounts(
        self,
        lines: list[str],
        text: str,
    ) -> tuple[float | None, float | None, float | None]:
        tail_lines = lines[-20:]
        full_lines = text.splitlines()
        tail_text_lines = full_lines[-30:]

        candidates = tail_lines + tail_text_lines

        for raw_line in reversed(candidates):
            if len(raw_line.strip()) < 10:
                continue

            line = self.normalize_summary_candidate_line(raw_line)
            if not line or len(line) < 10:
                continue

            match = SALTOKI_SUMMARY_LINE_PATTERN.match(line)
            if match:
                base = parse_amount(match.group(1))
                rate = parse_amount(match.group(2))
                iva = parse_amount(match.group(3))
                total = parse_amount(match.group(4))
                if all(v is not None for v in [base, iva, total]):
                    if rate and round(rate, 2) in {4.0, 10.0, 21.0}:
                        if abs(base + iva - total) <= 0.05:
                            return base, iva, total

            tokens = self.extract_amount_tokens_with_joined_pairs(line)
            if len(tokens) >= 4:
                for i in range(len(tokens) - 4, -1, -1):
                    base_c = tokens[i]
                    rate_c = tokens[i + 1]
                    iva_c = tokens[i + 2]
                    total_c = tokens[i + 3]
                    if round(rate_c, 2) in {4.0, 10.0, 21.0} and abs(base_c + iva_c - total_c) <= 0.05:
                        return base_c, iva_c, total_c

        return None, None, None

    def extract_summary_line_amounts(
        self,
        lines: list[str],
        text: str,
    ) -> tuple[float | None, float | None, float | None]:
        target_indexes = [
            index for index, line in enumerate(lines)
            if "base imponible" in line.lower() and "total" in line.lower()
        ]

        candidate_lines: list[str] = []
        for index in target_indexes:
            window = lines[index + 1 : index + 8]
            candidate_lines.extend(window)

        if "BASE IMPONIBLE" in text.upper():
            raw_lines = text.splitlines()
            for index, line in enumerate(raw_lines):
                if "BASE IMPONIBLE" in line.upper() and "TOTAL" in line.upper():
                    candidate_lines.extend(raw_lines[index + 1 : index + 8])

        for raw_line in reversed(candidate_lines):
            line = self.normalize_summary_candidate_line(raw_line)
            if not line:
                continue

            match = SALTOKI_SUMMARY_LINE_PATTERN.match(line)
            if match:
                base = parse_amount(match.group(1))
                rate = parse_amount(match.group(2))
                iva = parse_amount(match.group(3))
                total = parse_amount(match.group(4))

                if base is not None and iva is not None and total is not None:
                    if rate is not None and round(rate, 2) in {4.00, 10.00, 21.00}:
                        if abs((base + iva) - total) <= 0.03:
                            return base, iva, total

            token_values = self.extract_amount_tokens_with_joined_pairs(line)

            if len(token_values) < 4:
                continue

            for index in range(len(token_values) - 4, -1, -1):
                base = token_values[index]
                rate = token_values[index + 1]
                iva = token_values[index + 2]
                total = token_values[index + 3]

                if round(rate, 2) not in {4.00, 10.00, 21.00}:
                    continue

                if abs((base + iva) - total) <= 0.03:
                    return base, iva, total

        return None, None, None

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

    def extract_base_and_iva_from_tail(
        self,
        lines: list[str],
        total_hint: float | None = None,
    ) -> tuple[float | None, float | None]:
        tail_lines = lines[-28:]

        for line in reversed(tail_lines):
            if self.looks_like_date_line(line):
                continue

            amounts = self.parse_amounts_from_line(line)
            if len(amounts) < 2:
                continue

            if len(amounts) == 3 and self.looks_like_vat_rate(amounts[1]):
                return amounts[0], amounts[2]

            if len(amounts) == 2 and self.looks_like_vat_rate(amounts[0]):
                return None, amounts[1]

            if len(amounts) == 3 and self.looks_like_vat_rate(amounts[0]):
                return amounts[2], amounts[1]

            rates = [value for value in amounts if self.looks_like_vat_rate(value)]
            if not rates:
                continue

            for rate in rates:
                rate_index = amounts.index(rate)
                numeric_candidates = [
                    value
                    for index, value in enumerate(amounts)
                    if index != rate_index and value > 0
                ]
                if len(numeric_candidates) < 2:
                    continue

                numeric_candidates_sorted = sorted(numeric_candidates)
                for left_index in range(len(numeric_candidates_sorted)):
                    for right_index in range(left_index + 1, len(numeric_candidates_sorted)):
                        first = numeric_candidates_sorted[left_index]
                        second = numeric_candidates_sorted[right_index]
                        base_candidate, iva_candidate = sorted((first, second), reverse=True)

                        if total_hint is not None:
                            if abs((base_candidate + iva_candidate) - total_hint) <= 0.03:
                                return base_candidate, iva_candidate

                        if rate > 0 and abs((base_candidate * rate / 100.0) - iva_candidate) <= 0.06:
                            return base_candidate, iva_candidate

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
