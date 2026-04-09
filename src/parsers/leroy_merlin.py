from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.ids import normalize_tax_id

SUPPLIER_NAME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bleroy\s+merlin\s+espa(?:na|ña)\s+s\.?\s*l\.?\s*u\.?\b", re.IGNORECASE),
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
        r"(?:factura(?:\s+rectificativa)?|n[ºo°]?\s*factura|n[úu]mero\s+de\s+factura)\s*[:#-]?\s*([A-Z0-9]+(?:[-/][A-Z0-9]+)+)",
        re.IGNORECASE,
    ),
    re.compile(r"\b([0-9]{3}-[0-9]{4}-[A-Z0-9]+)\b", re.IGNORECASE),
)

DATE_PATTERNS = (
    re.compile(r"fecha\s+de\s+venta\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+factura\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+factura\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+emision\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+emisi[oó]n\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
)

TEXTUAL_DATE_PATTERN = re.compile(
    r",\s*a\s*(\d{1,2})\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+(\d{4})",
    re.IGNORECASE,
)

CAN_HANDLE_FISCAL_MARKERS = (
    "factura",
    "fecha de venta",
    "fecha factura",
    "fecha de factura",
    "numero de factura",
    "numero nif",
    "nif cliente",
    "base imponible",
    "cuota iva",
    "importe iva",
    "importe total",
    "total factura",
    "total a pagar",
    "neto a pagar",
)

SUMMARY_BASE_LABELS = (
    "base imponible",
    "subtotal",
    "importe sin iva",
    "total sin iva",
)

SUMMARY_IVA_LABELS = (
    "cuota iva",
    "importe iva",
    "total iva",
    "iva",
)

SUMMARY_TOTAL_LABELS = (
    "importe total",
    "total factura",
    "total a pagar",
    "neto a pagar",
    "total",
)

SUMMARY_HEADER_MARKERS = (
    "base imponible",
    "cuota iva",
    "importe iva",
    "importe total",
    "total factura",
    "total a pagar",
    "neto a pagar",
)

CUSTOMER_SECTION_MARKERS = (
    "numero nif",
    "nif cliente",
    "cliente",
    "adquiriente",
    "destinatario",
    "facturar a",
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

        supplier_zone = self._extract_supplier_zone(lines)
        supplier_name = self._extract_supplier_name_from_lines(supplier_zone)
        has_supplier_tax_id = self._contains_known_supplier_tax_id("\n".join(supplier_zone))
        if not has_supplier_tax_id:
            has_supplier_tax_id = self._contains_known_supplier_tax_id(text)

        fiscal_hits = sum(1 for marker in CAN_HANDLE_FISCAL_MARKERS if marker in normalized_text)
        has_invoice_number = self._extract_invoice_number_from_fragments(text, lines) is not None
        has_date = self._extract_date_from_fragments(text, lines) is not None
        has_coherent_amounts = self._extract_final_amount_triplet(lines[-50:]) is not None
        supporting_hits = sum(1 for flag in (has_invoice_number, has_date, has_coherent_amounts) if flag)

        if has_supplier_tax_id and fiscal_hits >= 2 and supporting_hits >= 1:
            return True

        if supplier_name is not None and fiscal_hits >= 3 and supporting_hits >= 2:
            return True

        brand_hits = normalized_text.count("leroy merlin")
        return brand_hits >= 2 and fiscal_hits >= 4 and has_invoice_number and has_date

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(text, lines)
        result.nif_proveedor = self.extract_supplier_tax_id_from_document(text, lines)
        result.numero_factura = self.extract_leroy_invoice_number(text, lines, file_path)
        result.fecha_factura = self.extract_leroy_date(text, lines, file_path)

        subtotal, iva, total = self.extract_leroy_amounts(text, lines)
        result.subtotal = subtotal
        result.iva = iva
        result.total = total

        return result.finalize()

    def extract_supplier_name(self, text: str, lines: list[str]) -> str | None:
        supplier_zone = self._extract_supplier_zone(lines)
        supplier_name = self._extract_supplier_name_from_lines(supplier_zone)
        if supplier_name:
            return supplier_name

        if self._contains_known_supplier_tax_id("\n".join(supplier_zone)):
            return self.SUPPLIER_NAME

        if self._contains_known_supplier_tax_id(text):
            return self.SUPPLIER_NAME

        return None

    def extract_supplier_tax_id_from_document(self, text: str, lines: list[str]) -> str | None:
        supplier_zone = self._extract_supplier_zone(lines)
        customer_tax_ids = self._extract_customer_tax_ids(lines)

        for index, line in enumerate(supplier_zone):
            nearby_lines = supplier_zone[max(0, index - 1): min(len(supplier_zone), index + 2)]
            nearby_text = "\n".join(nearby_lines)
            normalized_nearby = self._normalize_lookup_text(nearby_text)
            has_brand_context = "leroy merlin" in normalized_nearby
            has_tax_label = any(token in self._normalize_lookup_text(line) for token in ("cif", "nif"))

            for candidate in self._extract_supplier_tax_id_candidates(line):
                if candidate in customer_tax_ids:
                    continue
                if candidate == self.SUPPLIER_TAX_ID or has_brand_context or has_tax_label:
                    return candidate

        zone_text = "\n".join(supplier_zone)
        if self._contains_known_supplier_tax_id(zone_text):
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
        candidate = self._extract_invoice_number_from_fragments(text, lines)
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
        candidate = self._extract_date_from_fragments(text, lines)
        if candidate:
            return candidate

        return self.extract_filename_date(file_path) or self.extract_date("\n".join(lines[:25])) or self.extract_date(text)

    def extract_leroy_amounts(
        self,
        text: str,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        tail_lines = lines[-50:]

        triplet = self._extract_final_amount_triplet(tail_lines)
        if triplet is not None:
            return self._apply_credit_triplet(text, triplet)

        labeled_triplet = self._extract_last_labeled_amounts(tail_lines)
        if labeled_triplet != (None, None, None):
            return self._apply_credit_triplet(text, labeled_triplet)

        summary_triplet = self.extract_summary_amounts(text)
        if summary_triplet != (None, None, None):
            return self._apply_credit_triplet(text, summary_triplet)

        return (
            self._apply_credit_sign(text, self.extract_subtotal(text)),
            self._apply_credit_sign(text, self.extract_iva(text)),
            self._apply_credit_sign(text, self.extract_total(text)),
        )

    def _extract_invoice_number_from_fragments(self, text: str, lines: list[str]) -> str | None:
        header_text = "\n".join(lines[:25])

        for pattern_index, pattern in enumerate(INVOICE_NUMBER_PATTERNS):
            fragments = (header_text, text) if pattern_index == 0 else (header_text,)
            for fragment in fragments:
                match = pattern.search(fragment)
                if not match:
                    continue

                candidate = self.clean_invoice_number_candidate(match.group(1))
                if candidate:
                    return candidate

        return None

    def _extract_date_from_fragments(self, text: str, lines: list[str]) -> str | None:
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

    def _extract_final_amount_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float, float, float] | None:
        for extractor in (
            self._extract_header_driven_summary_triplet,
            self._extract_single_line_summary_triplet,
            self._extract_window_labeled_triplet,
        ):
            triplet = extractor(tail_lines)
            if triplet is not None:
                return triplet

        return None

    def _extract_header_driven_summary_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float, float, float] | None:
        candidate_triplet: tuple[float, float, float] | None = None

        for index, line in enumerate(tail_lines):
            normalized_line = self._normalize_lookup_text(line)
            label_hits = sum(1 for marker in SUMMARY_HEADER_MARKERS if marker in normalized_line)
            if label_hits < 2:
                continue

            inline_triplet = self._pick_coherent_triplet(
                self.extract_amounts_from_fragment(line, ignore_percent=True)
            )
            if inline_triplet is not None:
                candidate_triplet = inline_triplet

            for candidate_line in tail_lines[index + 1 : index + 4]:
                triplet = self._pick_coherent_triplet(
                    self.extract_amounts_from_fragment(candidate_line, ignore_percent=True)
                )
                if triplet is not None:
                    candidate_triplet = triplet
                    break

        return candidate_triplet

    def _extract_single_line_summary_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float, float, float] | None:
        for line in reversed(tail_lines):
            normalized_line = self._normalize_lookup_text(line)
            if self._count_summary_label_hits(normalized_line) < 2:
                continue

            triplet = self._pick_coherent_triplet(
                self.extract_amounts_from_fragment(line, ignore_percent=True)
            )
            if triplet is not None:
                return triplet

        return None

    def _extract_window_labeled_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float, float, float] | None:
        for end_index in range(len(tail_lines) - 1, -1, -1):
            window_lines = tail_lines[max(0, end_index - 5): end_index + 1]
            triplet = self._extract_labeled_triplet_from_window(window_lines)
            if triplet is not None:
                return triplet

        return None

    def _extract_labeled_triplet_from_window(
        self,
        window_lines: list[str],
    ) -> tuple[float, float, float] | None:
        base_candidate = self._find_last_labeled_value(window_lines, SUMMARY_BASE_LABELS)
        iva_candidate = self._find_last_labeled_value(window_lines, SUMMARY_IVA_LABELS)
        total_candidate = self._find_last_total_value(window_lines)

        if base_candidate is None or iva_candidate is None or total_candidate is None:
            return None

        base_index, base_value = base_candidate
        iva_index, iva_value = iva_candidate
        total_index, total_value = total_candidate

        if not (base_index <= iva_index <= total_index):
            return None

        if abs((base_value + iva_value) - total_value) > 0.02:
            return None

        return base_value, iva_value, total_value

    def _extract_last_labeled_amounts(
        self,
        tail_lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        base_candidate = self._find_last_labeled_value(tail_lines, SUMMARY_BASE_LABELS)
        iva_candidate = self._find_last_labeled_value(tail_lines, SUMMARY_IVA_LABELS)
        total_candidate = self._find_last_total_value(tail_lines)

        return (
            base_candidate[1] if base_candidate is not None else None,
            iva_candidate[1] if iva_candidate is not None else None,
            total_candidate[1] if total_candidate is not None else None,
        )

    def _find_last_labeled_value(
        self,
        lines: list[str],
        labels: tuple[str, ...],
    ) -> tuple[int, float] | None:
        for index in range(len(lines) - 1, -1, -1):
            normalized_line = self._normalize_lookup_text(lines[index])
            if not any(label in normalized_line for label in labels):
                continue

            amounts = self.extract_amounts_from_fragment(lines[index], ignore_percent=True)
            if not amounts:
                continue

            return index, amounts[-1]

        return None

    def _find_last_total_value(self, lines: list[str]) -> tuple[int, float] | None:
        for index in range(len(lines) - 1, -1, -1):
            normalized_line = self._normalize_lookup_text(lines[index])
            if not self._has_total_label(normalized_line):
                continue

            amounts = self.extract_amounts_from_fragment(lines[index], ignore_percent=True)
            if not amounts:
                continue

            return index, amounts[-1]

        return None

    def _pick_coherent_triplet(
        self,
        amounts: list[float],
    ) -> tuple[float, float, float] | None:
        if len(amounts) < 3:
            return None

        for start_index in range(len(amounts) - 3, -1, -1):
            base_value, iva_value, total_value = amounts[start_index : start_index + 3]
            if abs((base_value + iva_value) - total_value) <= 0.02:
                return base_value, iva_value, total_value

        return None

    def _extract_supplier_zone(self, lines: list[str]) -> list[str]:
        if not lines:
            return []

        supplier_zone: list[str] = []

        for line in lines[:18]:
            normalized_line = self._normalize_lookup_text(line)
            if supplier_zone and any(marker in normalized_line for marker in CUSTOMER_SECTION_MARKERS):
                break
            supplier_zone.append(line)

        return supplier_zone or lines[:12]

    def _extract_supplier_name_from_lines(self, supplier_zone: list[str]) -> str | None:
        for index, line in enumerate(supplier_zone):
            supplier_name = self._extract_supplier_name_from_line(line)
            if supplier_name:
                return supplier_name

            normalized_line = self._normalize_lookup_text(line)
            if "leroy merlin" not in normalized_line:
                continue

            nearby_lines = supplier_zone[max(0, index - 1): min(len(supplier_zone), index + 2)]
            nearby_text = "\n".join(nearby_lines)
            nearby_normalized = self._normalize_lookup_text(nearby_text)

            if "espana" in nearby_normalized:
                return self.SUPPLIER_NAME

            if "slu" in nearby_normalized or "s l u" in nearby_normalized:
                return self.SUPPLIER_SHORT_NAME

            if self._contains_known_supplier_tax_id(nearby_text):
                return self.SUPPLIER_NAME

        return None

    def _extract_supplier_name_from_line(self, line: str) -> str | None:
        for pattern, normalized_name in SUPPLIER_NAME_PATTERNS:
            if pattern.search(line):
                return normalized_name

        return None

    def _extract_customer_tax_ids(self, lines: list[str]) -> set[str]:
        customer_tax_ids: set[str] = set()

        for index, line in enumerate(lines):
            normalized_line = self._normalize_lookup_text(line)
            if not any(marker in normalized_line for marker in CUSTOMER_SECTION_MARKERS):
                continue

            for offset in range(0, 3):
                next_index = index + offset
                if next_index >= len(lines):
                    break
                customer_tax_ids.update(self.extract_exact_tax_ids(lines[next_index]))

        return customer_tax_ids

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

    def _count_summary_label_hits(self, normalized_line: str) -> int:
        hits = 0
        if any(label in normalized_line for label in SUMMARY_BASE_LABELS):
            hits += 1
        if any(label in normalized_line for label in SUMMARY_IVA_LABELS):
            hits += 1
        if self._has_total_label(normalized_line):
            hits += 1
        return hits

    def _has_total_label(self, normalized_line: str) -> bool:
        if "subtotal" in normalized_line:
            return False
        if "total iva" in normalized_line:
            return False
        return any(label in normalized_line for label in SUMMARY_TOTAL_LABELS)

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
