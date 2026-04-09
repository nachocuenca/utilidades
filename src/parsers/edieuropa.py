from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.amounts import parse_amount


INVOICE_LABEL_PATTERN = re.compile(
    "(?:n[\\W_]*(?:\u00ba|\u00b0|o)?|no|num(?:ero)?|n\u00famero)?\\s*(?:de\\s*)?factura\\s*[:#\\-]?\\s*([^\\n\\r]+)",
    re.IGNORECASE,
)
TAIL_WINDOW_LINES = 30
SUMMARY_SCAN_LINES = 40
SUMMARY_MAX_SPAN = 6
TEXT_SCAN_LINES = 18
AMOUNT_TOLERANCE = 0.02


class EdieuropaInvoiceParser(BaseInvoiceParser):
    parser_name = "edieuropa"
    priority = 350
    SUPPLIER_TAX_ID = "B03310091"

    SUMMARY_PATTERNS = {
        "base": [
            r"base\s+imponible[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"subtotal(?:\s+art[^\d\n\r]*)?[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
        "iva": [
            r"iva\s*\d*%?[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"cuota\s+iva[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
        "total": [
            r"total\s+factura[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"total[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
    }

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

        result.nombre_proveedor = "EDIEUROPA"
        result.nif_proveedor = self.SUPPLIER_TAX_ID
        result.numero_factura = self.extract_edieuropa_invoice_number(text, file_path)
        result.fecha_factura = self.extract_date(text) or self.extract_filename_date(file_path)

        subtotal, iva, total = self.extract_edieuropa_amounts(text)
        result.subtotal = subtotal if subtotal is not None else self.extract_subtotal(text)
        result.iva = iva if iva is not None else self.extract_iva(text)
        result.total = total if total is not None else self.extract_total(text)

        return result.finalize()

    def extract_edieuropa_amounts(self, text: str) -> tuple[float | None, float | None, float | None]:
        lines = self.extract_lines(text)
        if not lines:
            return None, None, None

        line_offset = max(0, len(lines) - SUMMARY_SCAN_LINES)
        tail_lines = lines[line_offset:]

        final_block_triplet = self._extract_final_summary_triplet(tail_lines, line_offset)
        if final_block_triplet is not None:
            return final_block_triplet

        tail_text = "\n".join(lines[-TAIL_WINDOW_LINES:])
        base_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS["base"])
        iva_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS["iva"])
        total_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS["total"])

        if base_match and iva_match and total_match:
            base_val = self._parse_amount_match(base_match)
            iva_val = self._parse_amount_match(iva_match)
            total_val = self._parse_amount_match(total_match)
            if (
                base_val is not None
                and iva_val is not None
                and total_val is not None
                and abs((base_val + iva_val) - total_val) <= AMOUNT_TOLERANCE
            ):
                return base_val, iva_val, total_val

        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if (
            summary_base is not None
            and summary_iva is not None
            and summary_total is not None
            and abs((summary_base + summary_iva) - summary_total) <= AMOUNT_TOLERANCE
        ):
            return summary_base, summary_iva, summary_total

        return None, None, None

    def extract_edieuropa_invoice_number(self, text: str, file_path: str | Path) -> str | None:
        filename_invoice_number = self._extract_invoice_number_from_filename(file_path)
        if filename_invoice_number:
            return filename_invoice_number

        text_invoice_number = self._extract_invoice_number_from_text(text)
        if text_invoice_number:
            return text_invoice_number

        return None

    def _extract_amount(self, text: str, patterns: list[str]) -> re.Match[str] | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match
        return None

    def _parse_amount_match(self, match: re.Match[str] | None) -> float | None:
        if not match:
            return None
        return parse_amount(match.group(1))

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

    def _extract_final_summary_triplet(
        self,
        lines: list[str],
        line_offset: int,
    ) -> tuple[float, float, float] | None:
        base_candidates = self._collect_amount_candidates(
            lines,
            line_offset,
            [
                (r"base\s+imponible", 100),
                (r"\bsubtotal\b", 90),
            ],
            ignore_percent=True,
        )
        iva_candidates = self._collect_amount_candidates(
            lines,
            line_offset,
            [
                (r"cuota\s+iva", 100),
                (r"\biva\b", 80),
            ],
            ignore_percent=True,
        )
        total_candidates = self._collect_amount_candidates(
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

        for total_index, total_value, total_rank in total_candidates:
            for iva_index, iva_value, iva_rank in iva_candidates:
                if iva_index > total_index:
                    continue

                for base_index, base_value, base_rank in base_candidates:
                    if base_index > iva_index:
                        continue

                    span = total_index - base_index
                    if span > SUMMARY_MAX_SPAN:
                        continue

                    if abs((base_value + iva_value) - total_value) > AMOUNT_TOLERANCE:
                        continue

                    score = (
                        total_rank * 10000
                        + iva_rank * 100
                        + base_rank
                        + total_index
                        - span
                    )
                    if best_score is None or score > best_score:
                        best_score = score
                        best_triplet = (base_value, iva_value, total_value)

        return best_triplet

    def _collect_amount_candidates(
        self,
        lines: list[str],
        line_offset: int,
        label_rules: list[tuple[str, int]],
        *,
        ignore_percent: bool,
    ) -> list[tuple[int, float, int]]:
        candidates: list[tuple[int, float, int]] = []

        for relative_index, line in enumerate(lines):
            rank: int | None = None
            for pattern_text, pattern_rank in label_rules:
                if re.search(pattern_text, line, re.IGNORECASE):
                    rank = pattern_rank
                    break

            if rank is None:
                continue

            values = self.extract_amounts_from_fragment(line, ignore_percent=ignore_percent)
            if not values:
                continue

            candidates.append((line_offset + relative_index, abs(values[-1]), rank))

        return candidates

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
