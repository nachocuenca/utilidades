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
        r"(?:n[º°o]?\s*factura|n[úu]mero\s+de\s+factura|factura)\s*[:#-]?\s*([A-Z0-9]+(?:[-/][A-Z0-9]+)+)",
        re.IGNORECASE,
    ),
    re.compile(r"\b([0-9]{3}-[0-9]{4}-[A-Z0-9]+)\b", re.IGNORECASE),
)

DATE_PATTERNS = (
    re.compile(r"fecha\s+de\s+venta\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+factura\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+factura\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+emisi[oó]n\s*[:#-]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", re.IGNORECASE),
)

CAN_HANDLE_FISCAL_MARKERS = (
    "factura",
    "fecha de venta",
    "fecha factura",
    "fecha de factura",
    "numero nif",
    "nif cliente",
    "base imponible",
    "cuota iva",
    "importe iva",
    "importe total",
    "total factura",
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
    priority = 480

    SUPPLIER_NAME = "Leroy Merlin Espana S.L.U."
    SUPPLIER_TAX_ID = "B84818442"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = self._normalize_lookup_text(text)
        compact_text = normalized_text.replace(" ", "")

        if "leroy merlin" not in normalized_text:
            return False

        brand_markers = (
            "leroy merlin espana",
            "leroy merlin espan",
            "leroy merlin finestrat",
            "leroy merlin slu",
            "leroy merlin s l u",
        )
        brand_hits = sum(1 for marker in brand_markers if marker in normalized_text)
        fiscal_hits = sum(1 for marker in CAN_HANDLE_FISCAL_MARKERS if marker in normalized_text)
        has_supplier_tax_id = self.SUPPLIER_TAX_ID.lower() in compact_text

        if has_supplier_tax_id and fiscal_hits >= 1:
            return True

        if brand_hits >= 1 and fiscal_hits >= 2:
            return True

        if normalized_text.count("leroy merlin") >= 2 and fiscal_hits >= 2:
            return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(lines)
        result.nif_proveedor = self.extract_supplier_tax_id_from_document(text, lines)
        result.numero_factura = self.extract_leroy_invoice_number(text, lines, file_path)
        result.fecha_factura = self.extract_leroy_date(text, lines, file_path)

        subtotal, iva, total = self.extract_leroy_amounts(text, lines)
        result.subtotal = subtotal
        result.iva = iva
        result.total = total

        return result.finalize()

    def extract_supplier_name(self, lines: list[str]) -> str | None:
        for line in lines[:12]:
            supplier_name = self._extract_supplier_name_from_line(line)
            if supplier_name:
                return supplier_name

        return self.SUPPLIER_NAME

    def extract_supplier_tax_id_from_document(self, text: str, lines: list[str]) -> str | None:
        supplier_zone = self._extract_supplier_zone(lines)
        zone_text = "\n".join(supplier_zone)

        tax_id = self._extract_supplier_tax_id_from_fragment(zone_text)
        if tax_id:
            return tax_id

        for line in supplier_zone:
            tax_id = self._extract_supplier_tax_id_from_fragment(line)
            if tax_id:
                return tax_id

        if self.SUPPLIER_TAX_ID.lower() in self._compact_lookup_text(text):
            return self.SUPPLIER_TAX_ID

        return self.SUPPLIER_TAX_ID

    def extract_leroy_invoice_number(
        self,
        text: str,
        lines: list[str],
        file_path: str | Path,
    ) -> str | None:
        header_text = "\n".join(lines[:20])

        for fragment in (header_text, text):
            for pattern in INVOICE_NUMBER_PATTERNS:
                match = pattern.search(fragment)
                if not match:
                    continue

                candidate = self.clean_invoice_number_candidate(match.group(1))
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
        header_text = "\n".join(lines[:25])

        for fragment in (header_text, text):
            for pattern in DATE_PATTERNS:
                match = pattern.search(fragment)
                if not match:
                    continue

                candidate = normalize_date(match.group(1))
                if candidate:
                    return candidate

        return self.extract_filename_date(file_path) or self.extract_date(header_text) or self.extract_date(text)

    def extract_leroy_amounts(
        self,
        text: str,
        lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        tail_lines = lines[-40:]

        single_line_triplet = self._extract_single_line_summary_triplet(tail_lines)
        if single_line_triplet is not None:
            return self._apply_credit_triplet(text, single_line_triplet)

        header_driven_triplet = self._extract_header_driven_summary_triplet(tail_lines)
        if header_driven_triplet is not None:
            return self._apply_credit_triplet(text, header_driven_triplet)

        labeled_triplet = self._extract_labeled_summary_triplet(tail_lines)
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

    def _extract_single_line_summary_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float, float, float] | None:
        for line in reversed(tail_lines):
            normalized_line = self._normalize_lookup_text(line)
            if not any(marker in normalized_line for marker in ("base", "subtotal", "iva", "total", "importe")):
                continue

            triplet = self._pick_coherent_triplet(
                self.extract_amounts_from_fragment(line, ignore_percent=True)
            )
            if triplet is not None:
                return triplet

        return None

    def _extract_header_driven_summary_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float, float, float] | None:
        for index, line in enumerate(tail_lines):
            normalized_line = self._normalize_lookup_text(line)
            if not any(marker in normalized_line for marker in SUMMARY_HEADER_MARKERS):
                continue

            for candidate_line in tail_lines[index + 1 : index + 5]:
                triplet = self._pick_coherent_triplet(
                    self.extract_amounts_from_fragment(candidate_line, ignore_percent=True)
                )
                if triplet is not None:
                    return triplet

        return None

    def _extract_labeled_summary_triplet(
        self,
        tail_lines: list[str],
    ) -> tuple[float | None, float | None, float | None]:
        base_candidates: list[tuple[int, float]] = []
        iva_candidates: list[tuple[int, float]] = []
        total_candidates: list[tuple[int, float]] = []

        for index, line in enumerate(tail_lines):
            normalized_line = self._normalize_lookup_text(line)
            amounts = self.extract_amounts_from_fragment(line, ignore_percent=True)
            if not amounts:
                continue

            if any(label in normalized_line for label in SUMMARY_BASE_LABELS):
                base_candidates.append((index, amounts[-1]))

            if any(label in normalized_line for label in SUMMARY_IVA_LABELS):
                triplet = self._pick_coherent_triplet(amounts)
                if triplet is not None:
                    return triplet
                iva_candidates.append((index, amounts[-1]))

            if self._has_total_label(normalized_line):
                total_candidates.append((index, amounts[-1]))

        for total_index, total_value in reversed(total_candidates):
            for iva_index, iva_value in reversed(iva_candidates):
                if iva_index > total_index or total_index - iva_index > 4:
                    continue

                for base_index, base_value in reversed(base_candidates):
                    if base_index > iva_index or total_index - base_index > 8:
                        continue

                    if abs((base_value + iva_value) - total_value) <= 0.02:
                        return base_value, iva_value, total_value

        base_value = base_candidates[-1][1] if base_candidates else None
        iva_value = iva_candidates[-1][1] if iva_candidates else None
        total_value = total_candidates[-1][1] if total_candidates else None
        return base_value, iva_value, total_value

    def _pick_coherent_triplet(
        self,
        amounts: list[float],
    ) -> tuple[float, float, float] | None:
        if len(amounts) < 3:
            return None

        windows = [amounts[index:index + 3] for index in range(len(amounts) - 2)]
        for base_value, iva_value, total_value in reversed(windows):
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

    def _extract_supplier_name_from_line(self, line: str) -> str | None:
        for pattern, normalized_name in SUPPLIER_NAME_PATTERNS:
            if pattern.search(line):
                return normalized_name

        normalized_line = self._normalize_lookup_text(line)
        if normalized_line.startswith("leroy merlin"):
            return self.SUPPLIER_NAME

        return None

    def _extract_supplier_tax_id_from_fragment(self, fragment: str) -> str | None:
        for pattern in SUPPLIER_TAX_ID_PATTERNS:
            for match in pattern.finditer(fragment):
                candidate = normalize_tax_id(match.group(1))
                if candidate:
                    return candidate

        if self.SUPPLIER_TAX_ID.lower() in self._compact_lookup_text(fragment):
            return self.SUPPLIER_TAX_ID

        return None

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
