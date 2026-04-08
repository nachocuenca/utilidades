from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser

MERCALUZ_INVOICE_NUMBER_PATTERN = re.compile(
    r"\b((?:ABV|FVN|VN)\d{4}-\d{5}-\d{5,6})\b",
    re.IGNORECASE,
)
MERCALUZ_AMOUNT_ONLY_PATTERN = re.compile(
    r"^[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?\s*(?:€|eur)?$",
    re.IGNORECASE,
)
MERCALUZ_TOTAL_NOISE_MARKERS = (
    "pronto pago",
    "descuento",
    "descuentos",
    "dto",
    "financ",
    "vencim",
    "recargo",
)
MERCALUZ_SUMMARY_SCAN_LINES = 60
MERCALUZ_COHERENCE_TOLERANCE = 0.02
MERCALUZ_COMMON_IVA_RATES = {4.0, 10.0, 21.0}
MERCALUZ_FINAL_BLOCK_MAX_WINDOW = 8
MERCALUZ_BASE_LABELS = (
    "base imponible",
    "subtotal",
    "importe sin iva",
    "total ai",
)
MERCALUZ_IVA_LABELS = (
    "cuota iva",
    "importe iva",
    "iva",
    "impuesto",
)


@dataclass(frozen=True, slots=True)
class MercaluzAmountCandidate:
    value: float
    line_index: int
    rank: int
    line: str
    contaminated: bool = False


class MercaluzInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "mercaluz"
    priority = 345
    SUPPLIER_TAX_ID = "A03204864"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        path_text = self.get_path_text(file_path) or ""
        score = 0

        if self.matches_file_path_hint(file_path, ("mercaluz",)):
            score += 1

        if "mercaluz" in normalized_text:
            score += 2

        if "abv" in path_text or "abv" in normalized_text:
            score += 2

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 2

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        folder_hint = self.get_folder_hint_name(file_path)

        result.nombre_proveedor = folder_hint or "MERCALUZ"
        result.nif_proveedor = self.SUPPLIER_TAX_ID

        result.numero_factura = self.extract_mercaluz_invoice_number(file_path, text)
        document_kind = self.detect_mercaluz_document_kind(file_path, text, result.numero_factura)
        is_credit_note = document_kind == "ABV"
        result.tipo_documento = "abono" if is_credit_note else "factura"
        result.fecha_factura = self.extract_filename_date(file_path) or self.extract_date(text)

        subtotal, iva, total = self.extract_mercaluz_amounts(text)
        result.subtotal = self.apply_mercaluz_document_sign(subtotal, is_credit_note)
        result.iva = self.apply_mercaluz_document_sign(iva, is_credit_note)
        result.total = self.apply_mercaluz_document_sign(total, is_credit_note)

        return result.finalize()

    def extract_mercaluz_invoice_number(self, file_path: str | Path, text: str) -> str | None:
        filename_num = self.extract_filename_invoice_number(
            file_path,
            [
                r"^((?:ABV|FVN|VN)\d{4}-\d{5}-\d{5,6})",
                r"^([A-Z]{3}\d{4}-\d{5}-\d{5,6})",
            ],
        )
        if filename_num:
            return filename_num.upper()

        for line in self.extract_lines(text):
            lowered = line.lower()
            if "anulad" in lowered:
                continue

            match = MERCALUZ_INVOICE_NUMBER_PATTERN.search(line)
            if match:
                candidate = self.clean_invoice_number_candidate(match.group(1).upper())
                if candidate:
                    return candidate

        return self.extract_invoice_number(text)

    def detect_mercaluz_document_kind(
        self,
        file_path: str | Path,
        text: str,
        invoice_number: str | None,
    ) -> str:
        stem = Path(file_path).stem.upper()
        invoice_candidate = (invoice_number or "").upper()

        for candidate in (stem, invoice_candidate):
            if candidate.startswith("ABV"):
                return "ABV"
            if candidate.startswith(("FVN", "VN")):
                return "FVN"

        for line in self.extract_lines(text)[:25]:
            lowered = line.lower()
            if "anulad" in lowered:
                continue

            match = MERCALUZ_INVOICE_NUMBER_PATTERN.search(line)
            if not match:
                continue

            prefix = match.group(1).upper()
            if prefix.startswith("ABV"):
                return "ABV"
            if prefix.startswith(("FVN", "VN")):
                return "FVN"

        lowered_text = text.lower()
        if any(
            marker in lowered_text
            for marker in (
                "abono",
                "rectificativa",
                "devolucion",
                "devoluciÃ³n",
            )
        ):
            return "ABV"

        return "FVN"

    def is_mercaluz_credit_note(self, text: str) -> bool:
        lowered_text = text.lower()
        return any(
            marker in lowered_text
            for marker in (
                "abono",
                "rectificativa",
                "devolucion",
                "devolución",
            )
        )

    def extract_mercaluz_amounts(self, text: str) -> tuple[float | None, float | None, float | None]:
        lines = self.extract_lines(text)
        if not lines:
            return None, None, None

        line_offset = max(0, len(lines) - MERCALUZ_SUMMARY_SCAN_LINES)
        summary_lines = lines[line_offset:]

        final_block_triplet = self.extract_mercaluz_final_summary_block(summary_lines, line_offset)
        if final_block_triplet is None and line_offset > 0:
            final_block_triplet = self.extract_mercaluz_final_summary_block(lines, 0)
        if final_block_triplet is not None:
            return final_block_triplet

        base_candidates = self.collect_mercaluz_base_candidates(summary_lines, line_offset)
        iva_candidates = self.collect_mercaluz_iva_candidates(summary_lines, line_offset)
        total_candidates = self.collect_mercaluz_total_candidates(summary_lines, line_offset)

        if not base_candidates and not iva_candidates and not total_candidates:
            base_candidates = self.collect_mercaluz_base_candidates(lines, 0)
            iva_candidates = self.collect_mercaluz_iva_candidates(lines, 0)
            total_candidates = self.collect_mercaluz_total_candidates(lines, 0)

        coherent_triplet = self.select_mercaluz_coherent_triplet(
            base_candidates,
            iva_candidates,
            total_candidates,
        )
        if coherent_triplet is not None:
            return coherent_triplet

        base_candidate = self.pick_best_mercaluz_candidate(base_candidates)
        iva_candidate = self.pick_best_mercaluz_candidate(iva_candidates)
        total_candidate = self.pick_best_mercaluz_candidate(total_candidates, prefer_clean=True)
        if total_candidate is None:
            total_candidate = self.pick_best_mercaluz_candidate(total_candidates)

        base_value = base_candidate.value if base_candidate is not None else None
        iva_value = iva_candidate.value if iva_candidate is not None else None
        total_value = total_candidate.value if total_candidate is not None else None

        if base_value is not None and total_value is not None:
            computed_iva = round(total_value - base_value, 4)
            if iva_value is None:
                iva_value = computed_iva
            elif abs((base_value + iva_value) - total_value) > MERCALUZ_COHERENCE_TOLERANCE:
                if iva_value in MERCALUZ_COMMON_IVA_RATES:
                    iva_value = computed_iva

        if (
            base_value is not None
            and iva_value is not None
            and (
                total_value is None
                or (total_candidate is not None and total_candidate.contaminated)
            )
        ):
            total_value = round(base_value + iva_value, 4)

        if iva_value is not None and total_value is not None and base_value is None:
            base_value = round(total_value - iva_value, 4)

        return base_value, iva_value, total_value

    def extract_mercaluz_final_summary_block(
        self,
        lines: list[str],
        line_offset: int,
    ) -> tuple[float | None, float | None, float | None] | None:
        best_score: int | None = None
        best_triplet: tuple[float, float, float] | None = None

        for relative_start, line in enumerate(lines):
            if not self.is_mercaluz_summary_anchor(line):
                continue

            max_end = min(len(lines), relative_start + MERCALUZ_FINAL_BLOCK_MAX_WINDOW)
            for relative_end in range(relative_start + 1, max_end + 1):
                window_lines = lines[relative_start:relative_end]
                window_text = " ".join(window_lines).lower()
                if not self.window_has_mercaluz_summary_labels(window_text):
                    continue

                amounts: list[float] = []
                for window_line in window_lines:
                    amounts.extend(
                        abs(value)
                        for value in self.extract_amounts_from_fragment(
                            window_line,
                            ignore_percent=False,
                        )
                    )

                if len(amounts) < 3 or len(amounts) > 10:
                    continue

                triplet = self.extract_mercaluz_triplet_from_amount_sequence(amounts)
                if triplet is None:
                    continue

                score = (line_offset + relative_end) * 1000 - (relative_end - relative_start)
                if "total factura" in window_text:
                    score += 600
                elif "importe total" in window_text:
                    score += 500
                elif "total a pagar" in window_text:
                    score += 200
                elif "importe a pagar" in window_text or "neto a pagar" in window_text:
                    score += 120

                if "cuota iva" in window_text or "importe iva" in window_text:
                    score += 250
                if "base imponible" in window_text:
                    score += 150

                if (
                    any(marker in window_text for marker in MERCALUZ_TOTAL_NOISE_MARKERS)
                    and "total factura" not in window_text
                    and "importe total" not in window_text
                ):
                    score -= 400

                if best_score is None or score > best_score:
                    best_score = score
                    best_triplet = triplet

        return best_triplet

    def is_mercaluz_summary_anchor(self, line: str) -> bool:
        lowered = line.lower()
        return (
            any(label in lowered for label in MERCALUZ_BASE_LABELS)
            or any(label in lowered for label in MERCALUZ_IVA_LABELS)
            or "total" in lowered
        )

    def window_has_mercaluz_summary_labels(self, window_text: str) -> bool:
        has_base = any(label in window_text for label in MERCALUZ_BASE_LABELS)
        has_iva = any(label in window_text for label in MERCALUZ_IVA_LABELS)
        has_total = any(
            label in window_text
            for label in (
                "total factura",
                "importe total",
                "total a pagar",
                "importe a pagar",
                "neto a pagar",
            )
        ) or re.search(r"\btotal\b", window_text) is not None
        return has_base and has_iva and has_total

    def extract_mercaluz_triplet_from_amount_sequence(
        self,
        amounts: list[float],
    ) -> tuple[float, float, float] | None:
        best_score: int | None = None
        best_triplet: tuple[float, float, float] | None = None

        for index in range(len(amounts) - 3):
            base_value, rate_value, iva_value, total_value = amounts[index:index + 4]
            if round(rate_value, 2) not in MERCALUZ_COMMON_IVA_RATES:
                continue
            if not self.is_mercaluz_coherent_amount_triplet(base_value, iva_value, total_value):
                continue

            score = 200 - index
            if best_score is None or score > best_score:
                best_score = score
                best_triplet = (base_value, iva_value, total_value)

        for index in range(len(amounts) - 2):
            base_value, iva_value, total_value = amounts[index:index + 3]
            if not self.is_mercaluz_coherent_amount_triplet(base_value, iva_value, total_value):
                continue

            score = 100 - index
            if best_score is None or score > best_score:
                best_score = score
                best_triplet = (base_value, iva_value, total_value)

        return best_triplet

    def is_mercaluz_coherent_amount_triplet(
        self,
        base_value: float,
        iva_value: float,
        total_value: float,
    ) -> bool:
        if min(base_value, iva_value, total_value) < 0:
            return False
        if total_value + MERCALUZ_COHERENCE_TOLERANCE < max(base_value, iva_value):
            return False
        return abs((base_value + iva_value) - total_value) <= MERCALUZ_COHERENCE_TOLERANCE

    def collect_mercaluz_base_candidates(
        self,
        lines: list[str],
        line_offset: int,
    ) -> list[MercaluzAmountCandidate]:
        candidates: list[MercaluzAmountCandidate] = []

        for relative_index, line in enumerate(lines):
            lowered = line.lower()
            rank: int | None = None

            if "base imponible" in lowered:
                rank = 90
            elif "subtotal" in lowered:
                rank = 80
            elif "importe sin iva" in lowered:
                rank = 70
            elif "total ai" in lowered:
                rank = 65

            if rank is None:
                continue

            value, _from_following_line, amount_index = self.extract_amount_near_summary_label(
                lines,
                relative_index,
                ignore_percent=True,
            )
            if value is None or amount_index is None:
                continue

            candidates.append(
                MercaluzAmountCandidate(
                    value=abs(value),
                    line_index=line_offset + amount_index,
                    rank=rank,
                    line=line,
                )
            )

        return candidates

    def collect_mercaluz_iva_candidates(
        self,
        lines: list[str],
        line_offset: int,
    ) -> list[MercaluzAmountCandidate]:
        candidates: list[MercaluzAmountCandidate] = []

        for relative_index, line in enumerate(lines):
            lowered = line.lower()
            compact = re.sub(r"\s+", " ", lowered).strip()
            rank: int | None = None

            if "tipo iva" in lowered or "tasa iva" in lowered:
                continue

            if "cuota iva" in lowered:
                rank = 100
            elif "importe iva" in lowered:
                rank = 95
            elif re.search(r"\bimpuesto\b", lowered):
                rank = 70
            elif re.search(r"\biva\b", lowered):
                rank = 80

            if rank is None:
                continue

            same_line_values = self.extract_amounts_from_fragment(line, ignore_percent=True)
            candidate_entries: list[tuple[float, int, str, bool]] = []

            if same_line_values:
                candidate_entries.append((same_line_values[-1], relative_index, line, False))
            else:
                candidate_entries.extend(
                    self.collect_mercaluz_following_amount_only_candidates(
                        lines,
                        relative_index,
                        ignore_percent=True,
                    )
                )

            if not candidate_entries:
                continue

            for value, amount_index, source_line, from_following_line in candidate_entries:
                normalized_value = abs(value)

                if "cuota iva" not in lowered and "importe iva" not in lowered and "impuesto" not in lowered:
                    if not from_following_line and re.fullmatch(
                        r"iva\s*[:\-]?\s*\(?\d{1,2}(?:[.,]\d{1,2})?\s*%?\)?",
                        compact,
                    ):
                        continue

                    raw_values = self.extract_amounts_from_fragment(line, ignore_percent=False)
                    if (
                        not from_following_line
                        and len(raw_values) == 1
                        and normalized_value in MERCALUZ_COMMON_IVA_RATES
                    ):
                        continue

                candidates.append(
                    MercaluzAmountCandidate(
                        value=normalized_value,
                        line_index=line_offset + amount_index,
                        rank=rank,
                        line=source_line,
                    )
                )

        return candidates

    def collect_mercaluz_total_candidates(
        self,
        lines: list[str],
        line_offset: int,
    ) -> list[MercaluzAmountCandidate]:
        candidates: list[MercaluzAmountCandidate] = []

        for relative_index, line in enumerate(lines):
            lowered = line.lower()
            rank: int | None = None

            if "subtotal" in lowered or "base imponible" in lowered:
                continue

            if "total factura" in lowered:
                rank = 100
            elif "importe total" in lowered:
                rank = 90
            elif "total a pagar" in lowered:
                rank = 80
            elif "importe a pagar" in lowered:
                rank = 70
            elif "neto a pagar" in lowered:
                rank = 65
            elif "total ii" in lowered:
                rank = 60
            elif re.search(r"\btotal\b", lowered):
                rank = 50

            if rank is None:
                continue

            value, _from_following_line, amount_index = self.extract_amount_near_summary_label(
                lines,
                relative_index,
                ignore_percent=False,
            )
            if value is None or amount_index is None:
                continue

            candidates.append(
                MercaluzAmountCandidate(
                    value=abs(value),
                    line_index=line_offset + amount_index,
                    rank=rank,
                    line=line,
                    contaminated=self.is_contaminated_total_candidate(lines, relative_index),
                )
            )

        return candidates

    def extract_amount_near_summary_label(
        self,
        lines: list[str],
        relative_index: int,
        *,
        ignore_percent: bool,
    ) -> tuple[float | None, bool, int | None]:
        line = lines[relative_index]
        line_values = self.extract_amounts_from_fragment(line, ignore_percent=ignore_percent)
        if line_values:
            return abs(line_values[-1]), False, relative_index

        for offset in (1, 2, 3):
            next_index = relative_index + offset
            if next_index >= len(lines):
                break

            next_line = lines[next_index].strip()
            if next_line == "":
                continue

            if re.search(r"[A-Za-z]", next_line) and not MERCALUZ_AMOUNT_ONLY_PATTERN.match(next_line):
                break

            next_values = self.extract_amounts_from_fragment(next_line, ignore_percent=ignore_percent)
            if len(next_values) != 1:
                continue
            if not MERCALUZ_AMOUNT_ONLY_PATTERN.match(next_line):
                continue

            return abs(next_values[0]), True, next_index

        return None, False, None

    def collect_mercaluz_following_amount_only_candidates(
        self,
        lines: list[str],
        relative_index: int,
        *,
        ignore_percent: bool,
    ) -> list[tuple[float, int, str, bool]]:
        candidates: list[tuple[float, int, str, bool]] = []

        for offset in (1, 2, 3):
            next_index = relative_index + offset
            if next_index >= len(lines):
                break

            next_line = lines[next_index].strip()
            if next_line == "":
                continue

            if re.search(r"[A-Za-z]", next_line) and not MERCALUZ_AMOUNT_ONLY_PATTERN.match(next_line):
                break

            if not MERCALUZ_AMOUNT_ONLY_PATTERN.match(next_line):
                break

            next_values = self.extract_amounts_from_fragment(next_line, ignore_percent=ignore_percent)
            if len(next_values) != 1:
                continue

            candidates.append((abs(next_values[0]), next_index, next_line, True))

        return candidates

    def is_contaminated_total_candidate(self, lines: list[str], relative_index: int) -> bool:
        line = lines[relative_index].lower()
        if "total factura" in line or "importe total" in line:
            return False

        if "a pagar" not in line:
            return False

        start = max(0, relative_index - 3)
        end = min(len(lines), relative_index + 4)
        context = " ".join(lines[start:end]).lower()
        return any(marker in context for marker in MERCALUZ_TOTAL_NOISE_MARKERS)

    def select_mercaluz_coherent_triplet(
        self,
        base_candidates: list[MercaluzAmountCandidate],
        iva_candidates: list[MercaluzAmountCandidate],
        total_candidates: list[MercaluzAmountCandidate],
    ) -> tuple[float | None, float | None, float | None] | None:
        best_score: int | None = None
        best_triplet: tuple[float, float, float] | None = None

        # Regla fuerte Mercaluz: si existe un bloque final coherente base + cuota IVA = total,
        # ese bloque manda aunque existan otros "a pagar" o importes de contexto financiero.
        for total_candidate in total_candidates:
            for base_candidate in base_candidates:
                for iva_candidate in iva_candidates:
                    indexes = (
                        base_candidate.line_index,
                        iva_candidate.line_index,
                        total_candidate.line_index,
                    )
                    span = max(indexes) - min(indexes)
                    if span > MERCALUZ_FINAL_BLOCK_MAX_WINDOW:
                        continue

                    difference = abs((base_candidate.value + iva_candidate.value) - total_candidate.value)
                    if difference > MERCALUZ_COHERENCE_TOLERANCE:
                        continue

                    score = (
                        total_candidate.rank * 1000
                        + base_candidate.rank * 100
                        + iva_candidate.rank * 10
                        + total_candidate.line_index
                        - span
                    )
                    if total_candidate.contaminated:
                        score -= 500

                    if best_score is None or score > best_score:
                        best_score = score
                        best_triplet = (
                            base_candidate.value,
                            iva_candidate.value,
                            total_candidate.value,
                        )

        return best_triplet

    def pick_best_mercaluz_candidate(
        self,
        candidates: list[MercaluzAmountCandidate],
        *,
        prefer_clean: bool = False,
    ) -> MercaluzAmountCandidate | None:
        if not candidates:
            return None

        filtered = candidates
        if prefer_clean:
            clean_candidates = [candidate for candidate in candidates if not candidate.contaminated]
            if clean_candidates:
                filtered = clean_candidates

        best_candidate = max(
            filtered,
            key=lambda candidate: (
                0 if candidate.contaminated else 1,
                candidate.rank,
                candidate.line_index,
            ),
        )
        return best_candidate

    def apply_mercaluz_document_sign(self, value: float | None, is_credit_note: bool) -> float | None:
        if value is None:
            return None
        if is_credit_note:
            return -abs(value)
        return abs(value)
