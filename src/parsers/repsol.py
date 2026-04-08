from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date
from src.utils.ids import normalize_tax_id

AMOUNT_PATTERN = re.compile(r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?")
INVOICE_NUMBER_PATTERNS = (
    re.compile(r"n[º°o]?\s*factura\s*[:#-]?\s*([A-Z0-9/.\-]+)", re.IGNORECASE),
    re.compile(r"factura\s*n[º°o]?\s*[:#-]?\s*([A-Z0-9/.\-]+)", re.IGNORECASE),
    re.compile(r"\b(\d{6}/\d/\d{2}/\d{6})\b", re.IGNORECASE),
    re.compile(r"\b(TK\d{6,})\b", re.IGNORECASE),
)
DATE_PATTERNS = (
    re.compile(r"fecha\s+factura\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"fecha\s+de\s+factura\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"^fecha\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})", re.IGNORECASE | re.MULTILINE),
)

KNOWN_REPSOL_COMPANIES: tuple[tuple[str, str, str], ...] = (
    (
        "repsol soluciones energeticas",
        "Repsol Soluciones Energéticas, S.A.",
        "A80298839",
    ),
    (
        "repsol comercial de productos petroliferos",
        "Repsol Comercial de Productos Petrolíferos, S.A.",
        "B28920839",
    ),
    (
        "repsol petroleo",
        "Repsol Petróleo, S.A.",
        "B28049929",
    ),
)

EMITTED_IN_NAME_OF_PATTERN = re.compile(
    r"emitida\s+en\s+nombre\s+y\s+por\s+cuenta\s+de",
    re.IGNORECASE,
)
EMITTED_IN_NAME_OF_COMPACT = "emitidaennombreyporcuentade"

TAX_ID_PATTERNS = (
    re.compile(r"C\.?I\.?F\.?\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
    re.compile(r"\bCIF\b\s*[:.]?\s*([A-Z]-?\d{8})", re.IGNORECASE),
)

SIMPLIFIED_TICKET_MARKERS = (
    "factura simplificada",
    "n° op",
    "nº op",
    "no op",
    "efectivo",
    "cambio",
)

CUSTOMER_TAX_ID_MARKERS = (
    "adquiriente",
    "datos fiscales adquiriente",
    "cliente",
    "titular",
    "destinatario",
)


class RepsolInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "repsol"
    priority = 360

    COMPANY_CIF_MAP = {
        company_name: tax_id
        for _needle, company_name, tax_id in KNOWN_REPSOL_COMPANIES
    }

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = self._normalize_text(text)
        lowered = self._strip_accents(normalized_text).lower()

        if "factura simplificada" in lowered and any(marker in lowered for marker in SIMPLIFIED_TICKET_MARKERS):
            return False

        score = 0

        if self.matches_file_path_hint(file_path, ("repsol",)):
            score += 1

        if "repsol" in lowered or self._match_known_repsol_company(normalized_text) is not None:
            score += 2

        if any(
            marker in lowered
            for marker in (
                "base imponible",
                "cuota iva",
                "total factura",
                "emitida en nombre y por cuenta de",
                "repsol comercial",
                "repsol petr",
                "repsol soluciones energ",
                "e.s./a.s. lugar suministro",
                "datos del suministro",
                "importe del producto",
            )
        ):
            score += 1

        if "datos del suministro" in lowered and "importe del producto" in lowered:
            score += 1

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        normalized_text = self._normalize_text(text)
        result = self.build_result(normalized_text, file_path)

        billing_company = self.extract_repsol_billing_company(normalized_text)
        tax_triplet = self.extract_repsol_tax_breakdown(normalized_text)

        result.nombre_proveedor = billing_company
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(normalized_text, billing_company)
        result.numero_factura = self.extract_repsol_invoice_number(normalized_text)
        result.fecha_factura = self.extract_repsol_date(normalized_text)
        result.subtotal = tax_triplet[0]
        result.iva = tax_triplet[1]
        result.total = tax_triplet[2] if tax_triplet[2] is not None else self.extract_repsol_total(file_path, normalized_text)

        if result.subtotal is None:
            result.subtotal = self.extract_repsol_subtotal(normalized_text)

        if result.iva is None:
            result.iva = self.extract_repsol_iva(normalized_text)

        if result.total is None:
            result.total = self.extract_repsol_total(file_path, normalized_text)

        return result.finalize()

    def _normalize_text(self, text: str) -> str:
        text = self._repair_common_mojibake(html.unescape(text or ""))
        return text.replace("&#10;", "\n").replace("\r\n", "\n").replace("\r", "\n")

    def _strip_accents(self, value: str) -> str:
        return "".join(
            char for char in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(char)
        )

    def _repair_common_mojibake(self, value: str) -> str:
        if not value or not any(marker in value for marker in ("Ã", "Â", "â")):
            return value

        try:
            repaired = value.encode("cp1252").decode("utf-8")
        except UnicodeError:
            return value

        if repaired.count("\ufffd") > value.count("\ufffd"):
            return value

        return repaired

    def _normalize_repsol_lookup_text(self, value: str) -> str:
        normalized = self._repair_common_mojibake(html.unescape(value or ""))
        normalized = self._strip_accents(normalized).lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _compact_repsol_lookup_text(self, value: str) -> str:
        return self._normalize_repsol_lookup_text(value).replace(" ", "")

    def _extract_emitted_billing_fragment(self, text: str) -> str | None:
        repaired_text = self._repair_common_mojibake(text)
        ascii_text = self._strip_accents(repaired_text)
        match = EMITTED_IN_NAME_OF_PATTERN.search(ascii_text)
        if match:
            start = match.start()
            end = min(len(repaired_text), start + 800)
            return repaired_text[start:end]

        compact_text = self._compact_repsol_lookup_text(repaired_text)
        compact_start = compact_text.find(EMITTED_IN_NAME_OF_COMPACT)
        if compact_start < 0:
            return None

        compact_fragment = compact_text[compact_start: compact_start + 800]
        return compact_fragment

    def _match_known_repsol_company(self, text: str) -> tuple[str, str] | None:
        lookup_text = self._normalize_repsol_lookup_text(text)
        compact_text = lookup_text.replace(" ", "")
        if not compact_text:
            return None

        best_match: tuple[int, str, str] | None = None

        for needle, company_name, tax_id in KNOWN_REPSOL_COMPANIES:
            compact_needle = needle.replace(" ", "")
            positions = [pos for pos in (lookup_text.find(needle), compact_text.find(compact_needle)) if pos >= 0]
            if not positions:
                continue

            position = min(positions)

            if best_match is None or position < best_match[0]:
                best_match = (position, company_name, tax_id)

        if best_match is None:
            return None

        return best_match[1], best_match[2]

    def _resolve_repsol_billing_company(self, text: str) -> tuple[str, str] | None:
        emitted_fragment = self._extract_emitted_billing_fragment(text)
        if emitted_fragment:
            emitted_match = self._match_known_repsol_company(emitted_fragment)
            if emitted_match is not None:
                return emitted_match

        return self._match_known_repsol_company(text)

    def _collect_repsol_customer_tax_ids(self, text: str) -> set[str]:
        customer_tax_ids = {"48334490J"}
        lines = self.extract_lines(text)

        for index, line in enumerate(lines):
            normalized_line = self._normalize_repsol_lookup_text(line)
            if not any(marker in normalized_line for marker in CUSTOMER_TAX_ID_MARKERS):
                continue

            fragment = "\n".join(lines[index:index + 4])
            customer_tax_ids.update(self.extract_exact_tax_ids(fragment))

            for pattern in TAX_ID_PATTERNS:
                for match in pattern.finditer(fragment):
                    candidate = normalize_tax_id(match.group(1))
                    if candidate:
                        customer_tax_ids.add(candidate)

        return customer_tax_ids

    def _extract_valid_repsol_tax_id(
        self,
        text: str | None,
        *,
        rejected_tax_ids: set[str],
    ) -> str | None:
        if not text:
            return None

        for pattern in TAX_ID_PATTERNS:
            for match in pattern.finditer(text):
                candidate = normalize_tax_id(match.group(1))
                if candidate and candidate not in rejected_tax_ids:
                    return candidate

        for tax_id in self.extract_exact_tax_ids(text):
            normalized_tax_id = normalize_tax_id(tax_id)
            if normalized_tax_id and normalized_tax_id not in rejected_tax_ids:
                return normalized_tax_id

        return None

    def extract_repsol_billing_company(self, text: str) -> str | None:
        billing_company = self._resolve_repsol_billing_company(text)
        if billing_company is not None:
            return billing_company[0]

        ascii_text = self._normalize_repsol_lookup_text(text)

        if "repsol estacion de servicio" in ascii_text:
            return "Repsol Estación de Servicio"

        if "repsol estacion servicio" in ascii_text:
            return "Repsol Estación Servicio"

        return "REPSOL"

    def extract_repsol_supplier_tax_id(self, text: str, company_name: str | None) -> str | None:
        if company_name in self.COMPANY_CIF_MAP:
            return self.COMPANY_CIF_MAP[company_name]

        resolved_company = self._resolve_repsol_billing_company(text)
        if resolved_company is not None:
            return resolved_company[1]

        rejected_tax_ids = self._collect_repsol_customer_tax_ids(text)

        emitted_candidate = self._extract_valid_repsol_tax_id(
            self._extract_emitted_billing_fragment(text),
            rejected_tax_ids=rejected_tax_ids,
        )
        if emitted_candidate is not None:
            return emitted_candidate

        direct_candidate = self._extract_valid_repsol_tax_id(
            text,
            rejected_tax_ids=rejected_tax_ids,
        )
        if direct_candidate is not None:
            return direct_candidate

        return None

    def extract_repsol_invoice_number(self, text: str) -> str | None:
        for pattern in INVOICE_NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                candidate = self.clean_invoice_number_candidate(match.group(1))
                if candidate:
                    return candidate

        return self.extract_invoice_number(text)

    def extract_repsol_date(self, text: str) -> str | None:
        for pattern in DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                candidate = normalize_date(match.group(1))
                if candidate:
                    return candidate

        return self.extract_date(text)

    def extract_repsol_tax_breakdown(
        self,
        text: str,
    ) -> tuple[float | None, float | None, float | None]:
        tail_lines = self.extract_lines(text)[-40:]

        base_candidates = self._extract_tail_amount_candidates(
            tail_lines,
            ("BASE IMPONIBLE", "IMPORTE DEL PRODUCTO"),
        )
        iva_candidates = self._extract_tail_amount_candidates(
            tail_lines,
            ("CUOTA IVA", "IVA "),
        )
        total_candidates = self._extract_tail_amount_candidates(
            tail_lines,
            ("TOTAL FACTURA EUROS", "TOTAL FACTURA"),
        )

        coherent_tail = self._pick_repsol_coherent_tail_breakdown(
            base_candidates,
            iva_candidates,
            total_candidates,
        )
        if coherent_tail is not None:
            return coherent_tail

        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            if abs((summary_base + summary_iva) - summary_total) <= 0.02:
                return summary_base, summary_iva, summary_total

        base = base_candidates[-1][1] if base_candidates else None
        iva = iva_candidates[-1][1] if iva_candidates else None
        total = total_candidates[-1][1] if total_candidates else None
        return base, iva, total

    def extract_repsol_subtotal(self, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [r"importe\s+del\s+producto", r"base\s+imponible", r"subtotal"],
            ignore_percent=True,
        )
        if value is not None:
            return value

        return self.extract_subtotal(text)

    def extract_repsol_iva(self, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [r"cuota\s+iva", r"\biva\b"],
            ignore_percent=True,
        )
        if value is not None:
            return value

        return self.extract_iva(text)

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self.extract_labeled_amount(
            text,
            [r"total\s+factura\s+euros", r"total\s+factura", r"\btotal\b"],
            ignore_percent=False,
        )
        if value is not None:
            return value

        stem_match = re.search(r"(\d+(?:,\d{2})?)\s*(?:€|â‚¬)", Path(file_path).stem)
        if stem_match:
            parsed = parse_amount(stem_match.group(1))
            if parsed is not None:
                return parsed

        return self.extract_total(text)

    def _extract_tail_amount_candidates(
        self,
        tail_lines: list[str],
        markers: tuple[str, ...],
    ) -> list[tuple[int, float]]:
        normalized_markers = tuple(self._strip_accents(marker).upper() for marker in markers)
        candidates: list[tuple[int, float]] = []

        for index, raw_line in enumerate(tail_lines):
            line = raw_line.strip()
            if not line:
                continue

            upper_line = self._strip_accents(line).upper()
            if not any(marker in upper_line for marker in normalized_markers):
                continue

            values: list[float] = []
            for token in AMOUNT_PATTERN.findall(line):
                parsed = parse_amount(token)
                if parsed is not None:
                    values.append(parsed)

            if values:
                candidates.append((index, values[-1]))

        return candidates

    def _pick_repsol_coherent_tail_breakdown(
        self,
        base_candidates: list[tuple[int, float]],
        iva_candidates: list[tuple[int, float]],
        total_candidates: list[tuple[int, float]],
    ) -> tuple[float, float, float] | None:
        for total_index, total_value in reversed(total_candidates):
            for iva_index, iva_value in reversed(iva_candidates):
                if iva_index > total_index:
                    continue

                for base_index, base_value in reversed(base_candidates):
                    if base_index > iva_index:
                        continue

                    if total_index - base_index > 6:
                        continue

                    if abs((base_value + iva_value) - total_value) <= 0.02:
                        return base_value, iva_value, total_value

        return None
