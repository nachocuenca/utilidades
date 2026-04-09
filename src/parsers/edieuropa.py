from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date


INVOICE_LABEL_PATTERN = re.compile(
    "(?:n[\\W_]*(?:\u00ba|\u00b0|o)?|no|num(?:ero)?|n\u00famero)?\\s*(?:de\\s*)?factura\\s*[:#\\-]?\\s*([^\\n\\r]+)",
    re.IGNORECASE,
)
SUMMARY_SCAN_LINES = 40
SUMMARY_MAX_SPAN = 6
SUMMARY_LOOKAHEAD_LINES = 1
FINAL_BLOCK_LOOKAHEAD_LINES = 3
STRICT_TAX_WINDOW_LINES = 4
TEXT_SCAN_LINES = 18
AMOUNT_TOLERANCE = 0.02
RATE_TOLERANCE = 0.06
FINAL_BLOCK_AMOUNT_TOKEN_PATTERN = r"[+-]?(?:\d{1,3}(?:[.]\d{3})+|\d+)(?:[.,]\d{2,4})"
RATE_TOKEN_PATTERN = r"[+-]?(?:\d{1,2}(?:[.,]\d{1,2})?)"
FINAL_BLOCK_ROW_WITH_RATE_PATTERN = re.compile(
    rf"(?P<base>{FINAL_BLOCK_AMOUNT_TOKEN_PATTERN})\s+"
    rf"(?P<rate>{RATE_TOKEN_PATTERN})\s+"
    rf"(?P<iva>{FINAL_BLOCK_AMOUNT_TOKEN_PATTERN})\s+"
    rf"(?P<total>{FINAL_BLOCK_AMOUNT_TOKEN_PATTERN})\s*(?:€|eur)?\s*$",
    re.IGNORECASE,
)
FINAL_BLOCK_ROW_PATTERN = re.compile(
    rf"(?P<base>{FINAL_BLOCK_AMOUNT_TOKEN_PATTERN})\s+"
    rf"(?P<iva>{FINAL_BLOCK_AMOUNT_TOKEN_PATTERN})\s+"
    rf"(?P<total>{FINAL_BLOCK_AMOUNT_TOKEN_PATTERN})\s*(?:€|eur)?\s*$",
    re.IGNORECASE,
)
BASE_LABEL_PATTERN = re.compile(r"base\s+imponible|subtotal", re.IGNORECASE)
IVA_LABEL_PATTERN = re.compile(r"cuota\s+iva|\biva\b", re.IGNORECASE)
TOTAL_LABEL_PATTERN = re.compile(r"total\s+factura|importe\s+total|\btotal\b", re.IGNORECASE)


class EdieuropaInvoiceParser(BaseInvoiceParser):
    parser_name = "edieuropa"
    priority = 350
    SUPPLIER_NAME = "EDIEUROPA MURCIA PUCHADES INVESTMENT,SL"
    SUPPLIER_TAX_ID = "B03310091"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if "sin edieuropa" in normalized_text:
            return False

        path_hint = self.matches_file_path_hint(file_path, ("edieuropa", "edi europa"))
        has_brand = "edieuropa" in normalized_text or "edi europa" in normalized_text
        has_tax_id = self.SUPPLIER_TAX_ID.lower() in normalized_text
        has_company_context = any(
            marker in normalized_text
            for marker in ("electrodom", "maquinas", "m\u00e1quinas", "electrodom\u00e9sticos")
        )

        return has_tax_id or (has_brand and (path_hint or has_company_context))

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.SUPPLIER_TAX_ID
        result.numero_factura = self.extract_edieuropa_invoice_number(text, file_path)
        result.fecha_factura = self.extract_edieuropa_invoice_date(text, file_path)

        result.subtotal, result.iva, result.total = self.extract_edieuropa_amounts(text)

        return result.finalize()

    def extract_edieuropa_amounts(self, text: str) -> tuple[float | None, float | None, float | None]:
        lines = self.extract_lines(text)
        if not lines:
            return None, None, None

        line_offset = max(0, len(lines) - SUMMARY_SCAN_LINES)
        tail_lines = lines[line_offset:]

        final_block_triplet = self._extract_explicit_final_tax_block(tail_lines)
        if final_block_triplet is not None:
            return final_block_triplet

        strict_window_triplet = self._extract_strict_tax_window_triplet(tail_lines)
        if strict_window_triplet is not None:
            return strict_window_triplet

        labeled_triplet = self._extract_labeled_summary_triplet(tail_lines, line_offset)
        if labeled_triplet is not None:
            return labeled_triplet

        return None, None, None

    def extract_edieuropa_invoice_number(self, text: str, file_path: str | Path) -> str | None:
        filename_invoice_number = self._extract_invoice_number_from_filename(file_path)
        if filename_invoice_number:
            return filename_invoice_number

        text_invoice_number = self._extract_invoice_number_from_text(text)
        if text_invoice_number:
            return text_invoice_number

        return None

    def extract_edieuropa_invoice_date(self, text: str, file_path: str | Path) -> str | None:
        header_text = "\n".join(self.extract_lines(text)[:TEXT_SCAN_LINES])

        for label_pattern in (
            r"fecha\s+emisi[oó]n",
            r"fecha\s+de\s+factura",
            r"fecha\s+factura",
            r"\bfecha\b",
        ):
            for match in re.finditer(
                rf"{label_pattern}\s*[:\-]?\s*([^\n\r]+)",
                header_text,
                re.IGNORECASE,
            ):
                candidate = normalize_date(match.group(1))
                if candidate:
                    return candidate

        return self.extract_date(text) or self.extract_filename_date(file_path)

    def _extract_invoice_number_from_filename(self, file_path: str | Path) -> str | None:
        stem = Path(file_path).stem

        candidate = self._match_invoice_number(stem, allow_bare_year=False)
        if candidate:
            return candidate

        if re.search(r"\bfac(?:tura)?\b", stem, re.IGNORECASE):
            candidate = self._match_invoice_number(stem, allow_bare_year=True)
            if candidate:
                return candidate

        normalized_stem = re.sub(r"^[^\dA-Z]*", "", stem, flags=re.IGNORECASE)
        if re.match(r"^\d{4}\s*[-_ ]\s*\d{3,6}(?:\D|$)", normalized_stem):
            return self._match_invoice_number(normalized_stem, allow_bare_year=True)

        return None

    def _extract_invoice_number_from_text(self, text: str) -> str | None:
        for match in INVOICE_LABEL_PATTERN.finditer(text):
            candidate = self._normalize_invoice_number(match.group(1), allow_bare_year=True)
            if candidate:
                return candidate

        for line in self.extract_lines(text)[:TEXT_SCAN_LINES]:
            candidate = self._normalize_invoice_number(
                line,
                allow_bare_year=self._should_allow_bare_year_from_text(line),
            )
            if candidate:
                return candidate

        return None

    def _normalize_invoice_number(self, value: str | None, *, allow_bare_year: bool) -> str | None:
        if not value:
            return None

        cleaned = re.sub(r"\s+", " ", value).strip()
        cleaned = re.sub(
            "^(?:n[\\W_]*(?:\u00ba|\u00b0|o)?|no|num(?:ero)?|n\u00famero)\\s*(?:de\\s*)?(?:factura)?\\s*[:#\\-]?\\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^factura\s*[:#\-]?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" .,:;#/-[]()")
        if cleaned == "":
            return None

        candidate = self._match_invoice_number(cleaned, allow_bare_year=allow_bare_year)
        if candidate and self._is_plausible_invoice_number(candidate):
            return candidate

        return None

    def _should_allow_bare_year_from_text(self, value: str) -> bool:
        if re.search(r"\bfac(?:tura)?\b", value, re.IGNORECASE):
            return True

        cleaned = re.sub(r"\s+", " ", value).strip(" .,:;#/-[]()")
        return re.fullmatch(r"\d{4}\s*[-_ ]\s*\d{3,6}", cleaned) is not None

    def _is_plausible_invoice_number(self, value: str) -> bool:
        return (
            re.fullmatch(r"\d{4}-\d{3,6}", value) is not None
            or re.fullmatch(r"\d{1,4}-A\d{2}-\d{1,6}", value, re.IGNORECASE) is not None
        )

    def _extract_explicit_final_tax_block(self, lines: list[str]) -> tuple[float, float, float] | None:
        for relative_index in range(len(lines) - 1, -1, -1):
            header_line = lines[relative_index]
            if not self._is_explicit_tax_header(header_line):
                continue

            requires_rate = "%" in header_line or re.search(r"\btipo\s+iva\b", header_line, re.IGNORECASE) is not None

            for lookahead in range(1, FINAL_BLOCK_LOOKAHEAD_LINES + 1):
                candidate_index = relative_index + lookahead
                if candidate_index >= len(lines):
                    break

                candidate_line = lines[candidate_index]
                if self._is_explicit_tax_header(candidate_line):
                    break

                triplet = self._parse_explicit_tax_row(candidate_line, requires_rate=requires_rate)
                if triplet is not None:
                    return triplet

        return None

    def _extract_labeled_summary_triplet(
        self,
        lines: list[str],
        line_offset: int,
    ) -> tuple[float, float, float] | None:
        base_candidates = self._collect_labeled_amount_candidates(
            lines,
            line_offset,
            [
                (r"base\s+imponible", 100),
                (r"\bsubtotal\b", 90),
            ],
            ignore_percent=True,
        )
        iva_candidates = self._collect_labeled_amount_candidates(
            lines,
            line_offset,
            [
                (r"cuota\s+iva", 100),
                (r"\biva\b", 80),
            ],
            ignore_percent=True,
        )
        total_candidates = self._collect_labeled_amount_candidates(
            lines,
            line_offset,
            [
                (r"total\s+factura", 100),
                (r"importe\s+total", 90),
                (r"\btotal\b", 60),
            ],
            ignore_percent=False,
        )

        best_score: int | None = None
        best_triplet: tuple[float, float, float] | None = None

        for total_line_index, total_value, total_rank in total_candidates:
            for iva_line_index, iva_value, iva_rank in iva_candidates:
                if iva_line_index > total_line_index:
                    continue

                for base_line_index, base_value, base_rank in base_candidates:
                    if base_line_index > iva_line_index:
                        continue

                    span = total_line_index - base_line_index
                    if span > SUMMARY_MAX_SPAN:
                        continue

                    if not self._is_reliable_tax_triplet(base_value, iva_value, total_value):
                        continue

                    score = (
                        total_rank * 100000
                        + iva_rank * 1000
                        + base_rank
                        + total_line_index
                        - span
                    )
                    if best_score is None or score > best_score:
                        best_score = score
                        best_triplet = (base_value, iva_value, total_value)

        return best_triplet

    def _extract_strict_tax_window_triplet(self, lines: list[str]) -> tuple[float, float, float] | None:
        for end_index in range(len(lines) - 1, -1, -1):
            for window_size in range(1, STRICT_TAX_WINDOW_LINES + 1):
                start_index = end_index - window_size + 1
                if start_index < 0:
                    break

                window_text = " ".join(lines[start_index:end_index + 1]).strip()
                if not self._contains_required_tax_labels(window_text):
                    continue

                requires_rate = "%" in window_text or re.search(r"\btipo\s+iva\b", window_text, re.IGNORECASE) is not None

                explicit_triplet = self._parse_explicit_tax_row(window_text, requires_rate=requires_rate)
                if explicit_triplet is not None:
                    return explicit_triplet

                labeled_triplet = self._parse_labeled_tax_window(window_text)
                if labeled_triplet is not None:
                    return labeled_triplet

        return None

    def _collect_labeled_amount_candidates(
        self,
        lines: list[str],
        line_offset: int,
        label_rules: list[tuple[str, int]],
        *,
        ignore_percent: bool,
    ) -> list[tuple[int, float, int]]:
        candidates: list[tuple[int, float, int]] = []

        for relative_index, line in enumerate(lines):
            label_match = self._match_summary_label(line, label_rules)
            if label_match is None:
                continue

            label_end, rank = label_match
            line_number = line_offset + relative_index
            direct_amount = self._extract_single_reliable_amount(line[label_end:], ignore_percent=ignore_percent)
            if direct_amount is not None:
                candidates.append((line_number, direct_amount, rank + 20))
                continue

            for lookahead in range(1, SUMMARY_LOOKAHEAD_LINES + 1):
                candidate_index = relative_index + lookahead
                if candidate_index >= len(lines):
                    break

                candidate_line = lines[candidate_index]
                if self._has_summary_label(candidate_line):
                    break

                lookahead_amount = self._extract_single_reliable_amount(candidate_line, ignore_percent=ignore_percent)
                if lookahead_amount is None:
                    continue

                candidates.append(
                    (
                        line_offset + candidate_index,
                        lookahead_amount,
                        rank + max(0, 20 - lookahead * 5),
                    )
                )
                break

        return candidates

    def _extract_single_reliable_amount(self, fragment: str, *, ignore_percent: bool) -> float | None:
        values = self.extract_amounts_from_fragment(fragment, ignore_percent=ignore_percent)
        if len(values) != 1:
            return None
        return abs(values[0])

    def _match_summary_label(
        self,
        line: str,
        label_rules: list[tuple[str, int]],
    ) -> tuple[int, int] | None:
        for pattern_text, pattern_rank in label_rules:
            match = re.search(pattern_text, line, re.IGNORECASE)
            if match:
                return match.end(), pattern_rank
        return None

    def _has_summary_label(self, line: str) -> bool:
        return re.search(
            r"base\s+imponible|subtotal|cuota\s+iva|\biva\b|total\s+factura|importe\s+total|\btotal\b",
            line,
            re.IGNORECASE,
        ) is not None

    def _contains_required_tax_labels(self, text: str) -> bool:
        return (
            BASE_LABEL_PATTERN.search(text) is not None
            and IVA_LABEL_PATTERN.search(text) is not None
            and TOTAL_LABEL_PATTERN.search(text) is not None
        )

    def _is_explicit_tax_header(self, line: str) -> bool:
        lowered = line.lower()
        has_base = "base imponible" in lowered or "subtotal" in lowered
        has_iva = "cuota iva" in lowered or re.search(r"\biva\b", lowered) is not None
        has_total = (
            "total factura" in lowered
            or "importe total" in lowered
            or re.search(r"\btotal\b", lowered) is not None
        )
        return has_base and has_iva and has_total

    def _parse_explicit_tax_row(
        self,
        line: str,
        *,
        requires_rate: bool,
    ) -> tuple[float, float, float] | None:
        patterns = [FINAL_BLOCK_ROW_WITH_RATE_PATTERN] if requires_rate else [
            FINAL_BLOCK_ROW_WITH_RATE_PATTERN,
            FINAL_BLOCK_ROW_PATTERN,
        ]

        for pattern in patterns:
            match = pattern.search(line)
            if match is None:
                continue

            base_value = parse_amount(match.group("base"))
            iva_value = parse_amount(match.group("iva"))
            total_value = parse_amount(match.group("total"))
            rate_text = match.groupdict().get("rate")
            rate_value = parse_amount(rate_text) if rate_text is not None else None

            if not self._is_reliable_tax_triplet(base_value, iva_value, total_value, rate=rate_value):
                return None

            return abs(base_value), abs(iva_value), abs(total_value)

        return None

    def _parse_labeled_tax_window(self, text: str) -> tuple[float, float, float] | None:
        compact_window = re.sub(r"\s+", " ", text).strip()
        if compact_window == "":
            return None

        total_matches = list(TOTAL_LABEL_PATTERN.finditer(compact_window))
        iva_matches = list(IVA_LABEL_PATTERN.finditer(compact_window))
        base_matches = list(BASE_LABEL_PATTERN.finditer(compact_window))

        for total_match in reversed(total_matches):
            for iva_match in reversed(iva_matches):
                if iva_match.start() >= total_match.start():
                    continue

                for base_match in reversed(base_matches):
                    if base_match.start() >= iva_match.start():
                        continue

                    triplet = self._parse_labeled_tax_segments(
                        compact_window[base_match.end():iva_match.start()],
                        compact_window[iva_match.end():total_match.start()],
                        compact_window[total_match.end():],
                    )
                    if triplet is not None:
                        return triplet

        return None

    def _parse_labeled_tax_segments(
        self,
        base_segment: str,
        iva_segment: str,
        total_segment: str,
    ) -> tuple[float, float, float] | None:
        base_value = self._extract_single_reliable_amount(base_segment, ignore_percent=True)
        total_value = self._extract_single_reliable_amount(total_segment, ignore_percent=False)
        if base_value is None or total_value is None:
            return None

        iva_resolution = self._resolve_iva_amount_from_segment(
            iva_segment,
            subtotal=base_value,
            total=total_value,
        )
        if iva_resolution is None:
            return None

        iva_value, _ = iva_resolution
        return base_value, iva_value, total_value

    def _resolve_iva_amount_from_segment(
        self,
        segment: str,
        *,
        subtotal: float,
        total: float,
    ) -> tuple[float, float | None] | None:
        values = [abs(value) for value in self.extract_amounts_from_fragment(segment, ignore_percent=False)]
        if not values or len(values) > 2:
            return None

        candidate_options: list[tuple[float, float | None, int]] = []
        if len(values) == 1:
            candidate_options.append((values[0], None, 10))
        else:
            first_value, second_value = values
            if self._looks_like_tax_rate(first_value):
                candidate_options.append((second_value, first_value, 40))
            if self._looks_like_tax_rate(second_value):
                candidate_options.append((first_value, second_value, 30))
            candidate_options.append((second_value, None, 20))
            candidate_options.append((first_value, None, 10))

        best_candidate: tuple[float, float | None] | None = None
        best_score: int | None = None

        for iva_value, rate_value, score in candidate_options:
            if not self._is_reliable_tax_triplet(subtotal, iva_value, total, rate=rate_value):
                continue

            if best_score is None or score > best_score:
                best_candidate = (iva_value, rate_value)
                best_score = score
                continue

            if score == best_score and best_candidate != (iva_value, rate_value):
                return None

        return best_candidate

    def _looks_like_tax_rate(self, value: float) -> bool:
        rate_value = abs(value)
        if rate_value > 30 + RATE_TOLERANCE:
            return False

        return abs((rate_value * 10) - round(rate_value * 10)) <= RATE_TOLERANCE

    def _is_reliable_tax_triplet(
        self,
        subtotal: float | None,
        iva: float | None,
        total: float | None,
        *,
        rate: float | None = None,
    ) -> bool:
        if subtotal is None or iva is None or total is None:
            return False

        subtotal_value = abs(subtotal)
        iva_value = abs(iva)
        total_value = abs(total)

        if abs((subtotal_value + iva_value) - total_value) > AMOUNT_TOLERANCE:
            return False

        if self._is_trivial_tax_triplet(subtotal_value, iva_value, total_value):
            return False

        if total_value + AMOUNT_TOLERANCE < max(subtotal_value, iva_value):
            return False

        if subtotal_value > 0 and iva_value >= subtotal_value - AMOUNT_TOLERANCE:
            return False

        if rate is None:
            return True

        rate_value = abs(rate)
        if rate_value > 100:
            return False

        if rate_value == 0:
            return iva_value <= RATE_TOLERANCE

        expected_iva = subtotal_value * rate_value / 100.0
        return abs(expected_iva - iva_value) <= RATE_TOLERANCE

    def _is_trivial_tax_triplet(self, subtotal: float, iva: float, total: float) -> bool:
        if max(subtotal, iva, total) > 2.0:
            return False

        rounded_values = [abs(value - round(value)) <= AMOUNT_TOLERANCE for value in (subtotal, iva, total)]
        return all(rounded_values)

    def _match_invoice_number(self, value: str, *, allow_bare_year: bool) -> str | None:
        cleaned = re.sub(r"\s+", " ", value).strip()

        fac_match = re.search(
            r"(?<![A-Z0-9])FAC\s*[-_ ]\s*(\d{4})\s*[-_ ]\s*(\d{3,6})(?![A-Z0-9])",
            cleaned,
            re.IGNORECASE,
        )
        if fac_match:
            return f"{fac_match.group(1)}-{fac_match.group(2)}"

        structured_match = re.search(
            r"(?<![A-Z0-9])(\d{1,4})\s*[-_ ]\s*(A\d{2})\s*[-_ ]\s*(\d{1,6})(?![A-Z0-9])",
            cleaned,
            re.IGNORECASE,
        )
        if structured_match:
            return (
                f"{structured_match.group(1)}-"
                f"{structured_match.group(2).upper()}-"
                f"{structured_match.group(3)}"
            )

        if allow_bare_year:
            bare_year_match = re.search(
                r"(?<![A-Z0-9])(\d{4})\s*[-_ ]\s*(\d{3,6})(?![A-Z0-9])",
                cleaned,
            )
            if bare_year_match:
                return f"{bare_year_match.group(1)}-{bare_year_match.group(2)}"

        return None
