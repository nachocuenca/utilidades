from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser

LEGAL_QUALITY_SUMMARY_SCAN_LINES = 18
LEGAL_QUALITY_COHERENCE_TOLERANCE = 0.02

INVOICE_NUMBER_PATTERN = re.compile(
    r"(?im)^\s*(?:no\s+factura|n[º°o]?\s*factura|factura\s+n[º°o]?)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/\-.]+)\s*$",
)
DATE_PATTERN = re.compile(
    r"\bfecha\s*[:\-]?\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LegalQualityAmountCandidate:
    value: float
    line_index: int
    rank: int


class LegalQualityInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "legal_quality"
    priority = 420

    SUPPLIER_NAME = "LEGAL QUALITY CONSULTING ABOGADOS, SL"
    SUPPLIER_TAX_ID = "B65850711"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        if not self.looks_like_invoice_document(text):
            return False

        normalized_text = text.lower()
        score = 0

        if self.matches_file_path_hint(file_path, ("legal quality", "legal_quality", "lqcabogados")):
            score += 1

        if "legal quality consulting abogados" in normalized_text:
            score += 3

        if "lqcabogados.es" in normalized_text:
            score += 2

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 2

        if "picapedrers" in normalized_text and "vilanova" in normalized_text:
            score += 1

        return score >= 4

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.extract_supplier_tax_id(text)
        result.numero_factura = self.extract_invoice_number(text)
        result.fecha_factura = self.extract_date(text)
        result.subtotal, result.iva, result.total = self.extract_legal_quality_amounts(text)

        return result.finalize()

    def extract_supplier_tax_id(self, text: str) -> str | None:
        for candidate in self.extract_exact_tax_ids(text):
            if candidate == self.SUPPLIER_TAX_ID:
                return candidate

        match = re.search(r"\bcif[-:\s]*([A-Z]\d{8})\b", text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        return self.SUPPLIER_TAX_ID

    def extract_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            candidate = self.clean_invoice_number_candidate(match.group(1))
            if candidate:
                return candidate

        return super().extract_invoice_number(text)

    def extract_date(self, text: str) -> str | None:
        match = DATE_PATTERN.search(text)
        if match:
            return match.group(1)

        return super().extract_date(text)

    def extract_legal_quality_amounts(self, text: str) -> tuple[float | None, float | None, float | None]:
        lines = self.extract_lines(text)
        if not lines:
            return None, None, None

        line_offset = max(0, len(lines) - LEGAL_QUALITY_SUMMARY_SCAN_LINES)
        summary_lines = lines[line_offset:]

        base_candidates = self.collect_base_candidates(summary_lines, line_offset)
        iva_candidates = self.collect_iva_candidates(summary_lines, line_offset)
        total_candidates = self.collect_total_candidates(summary_lines, line_offset)

        if not base_candidates and not iva_candidates and not total_candidates:
            base_candidates = self.collect_base_candidates(lines, 0)
            iva_candidates = self.collect_iva_candidates(lines, 0)
            total_candidates = self.collect_total_candidates(lines, 0)

        coherent_triplet = self.select_coherent_triplet(
            base_candidates,
            iva_candidates,
            total_candidates,
        )
        if coherent_triplet is not None:
            return coherent_triplet

        return (
            self.pick_best_candidate(base_candidates),
            self.pick_best_candidate(iva_candidates),
            self.pick_best_candidate(total_candidates),
        )

    def collect_base_candidates(
        self,
        lines: list[str],
        line_offset: int,
    ) -> list[LegalQualityAmountCandidate]:
        return self.collect_candidates(
            lines,
            line_offset,
            (
                (r"\bbase\s+imponible\b", 100),
            ),
            ignore_percent=True,
        )

    def collect_iva_candidates(
        self,
        lines: list[str],
        line_offset: int,
    ) -> list[LegalQualityAmountCandidate]:
        return self.collect_candidates(
            lines,
            line_offset,
            (
                (r"\bcuota\s+iva\b", 110),
                (r"\bimporte\s+iva\b", 100),
            ),
            ignore_percent=True,
        )

    def collect_total_candidates(
        self,
        lines: list[str],
        line_offset: int,
    ) -> list[LegalQualityAmountCandidate]:
        return self.collect_candidates(
            lines,
            line_offset,
            (
                (r"\btotal\s+factura\b", 110),
                (r"\bimporte\s+total\b", 100),
                (r"\btotal\b", 90),
            ),
            ignore_percent=False,
        )

    def collect_candidates(
        self,
        lines: list[str],
        line_offset: int,
        label_patterns: tuple[tuple[str, int], ...],
        *,
        ignore_percent: bool,
    ) -> list[LegalQualityAmountCandidate]:
        candidates: list[LegalQualityAmountCandidate] = []

        for relative_index, line in enumerate(lines):
            for label_pattern, rank in label_patterns:
                value = self.extract_amount_after_label(line, label_pattern, ignore_percent=ignore_percent)
                if value is None:
                    continue

                candidates.append(
                    LegalQualityAmountCandidate(
                        value=value,
                        line_index=line_offset + relative_index,
                        rank=rank,
                    )
                )
                break

        return candidates

    def extract_amount_after_label(
        self,
        line: str,
        label_pattern: str,
        *,
        ignore_percent: bool,
    ) -> float | None:
        match = re.search(
            rf"{label_pattern}\s*[:\-]?\s*(.*)",
            line,
            re.IGNORECASE,
        )
        if not match:
            return None

        fragment = match.group(1).strip()
        if fragment == "":
            return None

        values = self.extract_amounts_from_fragment(fragment, ignore_percent=ignore_percent)
        if not values:
            return None

        return values[-1]

    def select_coherent_triplet(
        self,
        base_candidates: list[LegalQualityAmountCandidate],
        iva_candidates: list[LegalQualityAmountCandidate],
        total_candidates: list[LegalQualityAmountCandidate],
    ) -> tuple[float | None, float | None, float | None] | None:
        best_score: int | None = None
        best_triplet: tuple[float, float, float] | None = None

        for total_candidate in total_candidates:
            for iva_candidate in iva_candidates:
                for base_candidate in base_candidates:
                    indexes = (
                        base_candidate.line_index,
                        iva_candidate.line_index,
                        total_candidate.line_index,
                    )
                    span = max(indexes) - min(indexes)
                    if span > 5:
                        continue

                    difference = abs((base_candidate.value + iva_candidate.value) - total_candidate.value)
                    if difference > LEGAL_QUALITY_COHERENCE_TOLERANCE:
                        continue

                    score = (
                        total_candidate.rank * 1000
                        + iva_candidate.rank * 100
                        + base_candidate.rank * 10
                        + total_candidate.line_index
                        - span
                    )

                    if best_score is None or score > best_score:
                        best_score = score
                        best_triplet = (
                            base_candidate.value,
                            iva_candidate.value,
                            total_candidate.value,
                        )

        return best_triplet

    def pick_best_candidate(self, candidates: list[LegalQualityAmountCandidate]) -> float | None:
        if not candidates:
            return None

        best_candidate = max(
            candidates,
            key=lambda candidate: (candidate.rank, candidate.line_index),
        )
        return best_candidate.value
