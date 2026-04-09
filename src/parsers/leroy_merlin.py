from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.ids import normalize_tax_id

SUPPLIER_NAME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bleroy\s+merlin\s+espa(?:na|\xf1a)\s+s\.?\s*l\.?\s*u\.?\b", re.IGNORECASE),
        "Leroy Merlin Espana S.L.U.",
    ),
    (
        re.compile(r"\bleroy\s+merlin\s+s\.?\s*l\.?\s*u\.?\b", re.IGNORECASE),
        "Leroy Merlin S.L.U.",
    ),
)

SUPPLIER_TAX_ID_PATTERNS = (
    re.compile(r"(?:n\.?\s*i\.?\s*f\.?|c\.?\s*i\.?\s*f\.?)\s*[:.]?\s*(B[-\s]?\d{8})", re.IGNORECASE),
    re.compile(r"\b(B[-\s]?\d{8})\b", re.IGNORECASE),
)

INVOICE_NUMBER_PATTERNS = (
    re.compile(
        r"(?:factura(?:\s+rectificativa)?|n[\xbao\xb0]?\s*factura|n[\xfau]mero\s+de\s+factura)"
        r"\s*[:#-]?\s*([A-Z0-9]+(?:[-/][A-Z0-9]+)+)",
        re.IGNORECASE,
    ),
    re.compile(r"\b([0-9]{3}-[0-9]{4}-[A-Z0-9]+)\b", re.IGNORECASE),
)

DATE_PATTERNS = (
    re.compile(r"fecha\s+de\s+venta\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+factura\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+factura\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+emision\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+emisi[o\xf3]n\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
)

TEXTUAL_DATE_PATTERN = re.compile(
    r",\s*a\s*(\d{1,2})\s+([A-Za-z\xc1\xc9\xcd\xd3\xda\xdc\xd1\xe1\xe9\xed\xf3\xfa\xfc\xf1]+)\s+(\d{4})",
    re.IGNORECASE,
)

CUSTOMER_MARKERS = (
    "numero nif",
    "nif cliente",
    "cliente",
    "adquiriente",
    "destinatario",
    "facturar a",
)

FISCAL_MARKERS = (
    "factura",
    "fecha de venta",
    "fecha factura",
    "fecha de factura",
    "numero de factura",
    "base imponible",
    "cuota iva",
    "importe iva",
    "importe total",
    "total factura",
    "neto a pagar",
)

BASE_LABEL_REGEX = re.compile(
    r"base\s+imponible|subtotal|importe\s+sin\s+iva|total\s+sin\s+iva",
    re.IGNORECASE,
)
IVA_LABEL_REGEX = re.compile(
    r"cuota\s+iva|importe\s+iva|\biva\b",
    re.IGNORECASE,
)
TOTAL_LABEL_REGEX = re.compile(
    r"importe\s+total|total\s+factura|total\s+a\s+pagar|neto\s+a\s+pagar|\btotal\b",
    re.IGNORECASE,
)

BLOCK_LOOKBACK = 7
TAIL_SCAN_LINES = 40
AMOUNT_TOLERANCE = 0.02
SUPPLIER_CONTEXT_HINTS = (
    "leroy merlin",
    "cif",
    "avda",
    "avenida",
    "telf",
    "telefono",
)


class LeroyMerlinInvoiceParser(BaseInvoiceParser):
    parser_name = "leroy_merlin"
    priority = 520

    SUPPLIER_NAME = "Leroy Merlin Espana S.L.U."
    SUPPLIER_SHORT_NAME = "Leroy Merlin S.L.U."
    SUPPLIER_TAX_ID = "B84818442"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        del file_path

        lines = self.extract_lines(text)
        if not lines:
            return False

        normalized_text = self._normalize_lookup_text(text)
        if "leroy merlin" not in normalized_text:
            return False

        supplier_block = self._extract_supplier_block(lines)
        supplier_text = "\n".join(supplier_block)

        has_supplier_name = self._extract_supplier_name_from_block(supplier_block) is not None
        has_supplier_tax_id = self._contains_known_supplier_tax_id(supplier_text) or self._contains_known_supplier_tax_id(text)
        fiscal_hits = sum(1 for marker in FISCAL_MARKERS if marker in normalized_text)
        has_invoice_number = self._extract_invoice_number(text, lines) is not None
        has_date = self._extract_document_date(text, lines) is not None
        has_amounts = self._extract_final_tax_block(lines) is not None
        supporting_hits = sum(1 for flag in (has_invoice_number, has_date, has_amounts) if flag)

        if has_supplier_tax_id and fiscal_hits >= 2 and supporting_hits >= 1:
            return True

        if has_supplier_name and fiscal_hits >= 3 and supporting_hits >= 2:
            return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(lines, text)
        result.nif_proveedor = self.extract_supplier_tax_id(lines, text)
        result.numero_factura = self.extract_leroy_invoice_number(text, lines, file_path)
        result.fecha_factura = self.extract_leroy_date(text, lines, file_path)
        result.cp_cliente = self.extract_leroy_customer_postal_code(lines)

        subtotal, iva, total = self.extract_leroy_amounts(text, lines)
        result.subtotal = subtotal
        result.iva = iva
        result.total = total

        return result.finalize()

    def extract_supplier_name(self, lines: list[str], text: str) -> str | None:
        supplier_block = self._extract_supplier_block(lines)
        supplier_name = self._extract_supplier_name_from_block(supplier_block)
        if supplier_name:
            return supplier_name

        if self._contains_known_supplier_tax_id("\n".join(supplier_block)):
            return self.SUPPLIER_NAME

        if self._contains_known_supplier_tax_id(text):
            return self.SUPPLIER_NAME

        return None

    def extract_supplier_tax_id(self, lines: list[str], text: str) -> str | None:
        supplier_block = self._extract_supplier_block(lines)
        customer_tax_ids = self._extract_customer_tax_ids(lines)

        for line in supplier_block:
            normalized_line = self._normalize_lookup_text(line)
            has_brand_context = "leroy merlin" in normalized_line
            has_tax_label = "cif" in normalized_line or "nif" in normalized_line

            for candidate in self._extract_supplier_tax_id_candidates(line):
                if candidate in customer_tax_ids:
                    continue
                if candidate == self.SUPPLIER_TAX_ID or has_brand_context or has_tax_label:
                    return candidate

        if self._contains_known_supplier_tax_id("\n".join(supplier_block)):
            return self.SUPPLIER_TAX_ID

        if self._contains_known_supplier_tax_id(text):
            return self.SUPPLIER_TAX_ID

        return None

    def extract_leroy_invoice_number(
        self,
        text: str,
        lines: list[str],
        file_path: str | Path,
    ) -> str | None:
        candidate = self._extract_invoice_number(text, lines)
        if candidate:
            return candidate

        return self.extract_filename_invoice_number(
            file_path,
            [
                r"factura[ _-]*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)",
                r"([0-9]{3}-[0-9]{4}-[A-Z0-9]+)",
            ],
        )

    def extract_leroy_date(
        self,
        text: str,
        lines: list[str],
        file_path: str | Path,
    ) -> str | None:
        candidate = self._extract_document_date(text, lines)
        if candidate:
            return candidate

        return self.extract_filename_date(file_path) or self.extract_date(text)

    def extract_leroy_amounts(
        self,
        text: str,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        triplet = self._extract_final_tax_block(lines)
        if triplet is not None:
            return self._apply_credit_triplet(text, triplet)

        summary_triplet = self.extract_summary_amounts(text)
        if summary_triplet != (None, None, None):
            return self._apply_credit_triplet(text, summary_triplet)

        return (
            self._apply_credit_sign(text, self.extract_subtotal(text)),
            self._apply_credit_sign(text, self.extract_iva(text)),
            self._apply_credit_sign(text, self.extract_total(text)),
        )

    def _extract_invoice_number(self, text: str, lines: list[str]) -> str | None:
        header_text = "\n".join(lines[:25])

        for pattern in INVOICE_NUMBER_PATTERNS:
            for fragment in (header_text, text):
                match = pattern.search(fragment)
                if not match:
                    continue

                candidate = self.clean_invoice_number_candidate(match.group(1))
                if candidate:
                    return candidate

        return None

    def _extract_document_date(self, text: str, lines: list[str]) -> str | None:
        header_text = "\n".join(lines[:25])

        for fragment in (header_text, text):
            for pattern in DATE_PATTERNS:
                match = pattern.search(fragment)
                if not match:
                    continue

                candidate = normalize_date(match.group(1))
                if candidate:
                    return candidate

        textual_match = TEXTUAL_DATE_PATTERN.search(header_text)
        if textual_match:
            day_value, month_value, year_value = textual_match.groups()
            candidate = normalize_date(f"{day_value} de {month_value} de {year_value}")
            if candidate:
                return candidate

        return None

    def _extract_final_tax_block(
        self,
        lines: list[str],
    ) -> tuple[float, float, float] | None:
        tail_lines = lines[-TAIL_SCAN_LINES:]
        payment_triplet = self._extract_payment_summary_triplet(tail_lines)
        if payment_triplet is not None:
            return payment_triplet

        for end_index in range(len(tail_lines) - 1, -1, -1):
            window = tail_lines[max(0, end_index - BLOCK_LOOKBACK): end_index + 1]
            if not self._window_has_full_fiscal_context(window):
                continue

            triplet = self._extract_triplet_from_labeled_window(window)
            if triplet is not None:
                return triplet

            triplet = self._extract_triplet_from_header_window(window)
            if triplet is not None:
                return triplet

        return None

    def _extract_payment_summary_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float, float, float] | None:
        for index, line in enumerate(tail_lines):
            normalized_line = self._normalize_lookup_text(line)
            if "modos de pago" not in normalized_line or "total" not in normalized_line:
                continue

            for candidate_line in tail_lines[index + 1 : index + 4]:
                amounts = self.extract_amounts_from_fragment(candidate_line, ignore_percent=True)
                triplet = self._pick_coherent_triplet(amounts)
                if triplet is not None:
                    return triplet

            break

        return None

    def _extract_triplet_from_labeled_window(
        self,
        window_lines: list[str],
    ) -> tuple[float, float, float] | None:
        base_candidate: tuple[int, float] | None = None
        iva_candidate: tuple[int, float] | None = None
        total_candidate: tuple[int, float] | None = None

        for index, line in enumerate(window_lines):
            for label_kind, value in self._extract_labeled_values_from_line(line).items():
                if label_kind == "base":
                    base_candidate = (index, value)
                elif label_kind == "iva":
                    iva_candidate = (index, value)
                elif label_kind == "total":
                    total_candidate = (index, value)

        if base_candidate is None or iva_candidate is None or total_candidate is None:
            return None

        if total_candidate[0] < max(base_candidate[0], iva_candidate[0]):
            return None

        triplet = (base_candidate[1], iva_candidate[1], total_candidate[1])
        return triplet if self._is_coherent_triplet(triplet) else None

    def _extract_triplet_from_header_window(
        self,
        window_lines: list[str],
    ) -> tuple[float, float, float] | None:
        for index, line in enumerate(window_lines):
            label_kinds = self._line_label_kinds(line)
            if len(label_kinds) < 2:
                continue

            amount_pool: list[float] = []
            for candidate_line in window_lines[index : index + 4]:
                amount_pool.extend(self.extract_amounts_from_fragment(candidate_line, ignore_percent=True))

            triplet = self._pick_coherent_triplet(amount_pool)
            if triplet is not None:
                return triplet

        return None

    def _window_has_full_fiscal_context(self, window_lines: list[str]) -> bool:
        kinds: set[str] = set()

        for line in window_lines:
            kinds.update(self._line_label_kinds(line))

        return {"base", "iva", "total"}.issubset(kinds)

    def _line_label_kinds(self, line: str) -> set[str]:
        return {label_kind for label_kind, _, _ in self._iter_line_labels(line)}

    def _extract_labeled_values_from_line(self, line: str) -> dict[str, float]:
        labels = self._iter_line_labels(line)
        if not labels:
            return {}

        values: dict[str, float] = {}

        for index, (label_kind, _, label_end) in enumerate(labels):
            next_start = labels[index + 1][1] if index + 1 < len(labels) else len(line)
            fragment = line[label_end:next_start]
            amounts = self.extract_amounts_from_fragment(fragment, ignore_percent=True)
            if amounts:
                values[label_kind] = amounts[-1]

        return values

    def _iter_line_labels(self, line: str) -> list[tuple[str, int, int]]:
        labels: list[tuple[str, int, int]] = []

        for regex, label_kind in (
            (BASE_LABEL_REGEX, "base"),
            (IVA_LABEL_REGEX, "iva"),
            (TOTAL_LABEL_REGEX, "total"),
        ):
            for match in regex.finditer(line):
                if label_kind == "total" and self._is_non_final_total_label(line, match):
                    continue
                labels.append((label_kind, match.start(), match.end()))

        labels.sort(key=lambda item: item[1])
        return labels

    def _is_non_final_total_label(self, line: str, match: re.Match[str]) -> bool:
        normalized_line = self._normalize_lookup_text(line)
        matched_text = self._normalize_lookup_text(match.group(0))
        suffix = self._normalize_lookup_text(line[match.end() : match.end() + 12])

        if "subtotal" in normalized_line:
            return True

        if matched_text == "total" and suffix.startswith("iva"):
            return True

        return False

    def _pick_coherent_triplet(
        self,
        amounts: list[float],
    ) -> tuple[float, float, float] | None:
        if len(amounts) < 3:
            return None

        for start_index in range(len(amounts) - 3, -1, -1):
            triplet = tuple(amounts[start_index : start_index + 3])
            if self._is_coherent_triplet(triplet):
                return triplet

        return None

    def _is_coherent_triplet(
        self,
        values: tuple[float, float, float],
    ) -> bool:
        base_value, iva_value, total_value = values
        return abs((base_value + iva_value) - total_value) <= AMOUNT_TOLERANCE

    def _extract_supplier_block(self, lines: list[str]) -> list[str]:
        supplier_block: list[str] = []

        for line in lines[:18]:
            normalized_line = self._normalize_lookup_text(line)
            if supplier_block and any(marker in normalized_line for marker in CUSTOMER_MARKERS):
                break
            supplier_block.append(line)

        return supplier_block or lines[:12]

    def _extract_supplier_name_from_block(self, supplier_block: list[str]) -> str | None:
        for line in supplier_block:
            for pattern, normalized_name in SUPPLIER_NAME_PATTERNS:
                if pattern.search(line):
                    return normalized_name

        normalized_block = self._normalize_lookup_text("\n".join(supplier_block))
        if "leroy merlin" not in normalized_block:
            return None

        if "espana" in normalized_block or self._contains_known_supplier_tax_id("\n".join(supplier_block)):
            return self.SUPPLIER_NAME

        if "slu" in normalized_block or "s l u" in normalized_block:
            return self.SUPPLIER_SHORT_NAME

        return None

    def _extract_customer_tax_ids(self, lines: list[str]) -> set[str]:
        customer_tax_ids: set[str] = set()

        for index, line in enumerate(lines):
            normalized_line = self._normalize_lookup_text(line)
            if not any(marker in normalized_line for marker in CUSTOMER_MARKERS):
                continue

            for offset in range(0, 3):
                next_index = index + offset
                if next_index >= len(lines):
                    break
                customer_tax_ids.update(self.extract_exact_tax_ids(lines[next_index]))

        return customer_tax_ids

    def extract_leroy_customer_postal_code(self, lines: list[str]) -> str | None:
        customer_tax_index = self._find_customer_tax_index(lines)
        if customer_tax_index is None:
            return None

        customer_block_start = self._find_interleaved_customer_block_start(lines, customer_tax_index)
        if customer_block_start is None:
            return None

        customer_column_lines = [
            lines[index]
            for index in range(customer_block_start, customer_tax_index, 2)
        ]
        return self.extract_postal_code_from_text("\n".join(customer_column_lines))

    def _find_customer_tax_index(self, lines: list[str]) -> int | None:
        for index, line in enumerate(lines[:25]):
            normalized_line = self._normalize_lookup_text(line)
            if "numero nif" in normalized_line or "nif cliente" in normalized_line:
                return index

        return None

    def _find_interleaved_customer_block_start(
        self,
        lines: list[str],
        customer_tax_index: int,
    ) -> int | None:
        start_index = max(0, customer_tax_index - 12)

        for index in range(start_index, customer_tax_index - 1):
            current_line = lines[index]
            next_line = lines[index + 1]
            if self._looks_like_supplier_context_line(next_line) and not self._looks_like_supplier_context_line(current_line):
                return index

        return None

    def _looks_like_supplier_context_line(self, line: str) -> bool:
        normalized_line = self._normalize_lookup_text(line)
        if normalized_line == "":
            return False

        if any(hint in normalized_line for hint in SUPPLIER_CONTEXT_HINTS):
            return True

        return self._contains_known_supplier_tax_id(line)

    def _extract_supplier_tax_id_candidates(self, fragment: str) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()

        for pattern in SUPPLIER_TAX_ID_PATTERNS:
            for match in pattern.finditer(fragment):
                candidate = normalize_tax_id(match.group(1))
                if candidate is None or candidate in seen:
                    continue
                seen.add(candidate)
                candidates.append(candidate)

        for candidate in self.extract_exact_tax_ids(fragment):
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)

        return candidates

    def _contains_known_supplier_tax_id(self, fragment: str | None) -> bool:
        return self.SUPPLIER_TAX_ID.lower() in self._compact_lookup_text(fragment)

    def _apply_credit_triplet(
        self,
        text: str,
        values: tuple[float | None, float | None, float | None],
    ) -> tuple[float | None, float | None, float | None]:
        return (
            self._apply_credit_sign(text, values[0]),
            self._apply_credit_sign(text, values[1]),
            self._apply_credit_sign(text, values[2]),
        )

    def _normalize_lookup_text(self, value: str | None) -> str:
        if not value:
            return ""

        normalized = unicodedata.normalize("NFKD", value)
        normalized = "".join(character for character in normalized if not unicodedata.combining(character))
        normalized = normalized.lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _compact_lookup_text(self, value: str | None) -> str:
        return self._normalize_lookup_text(value).replace(" ", "")
