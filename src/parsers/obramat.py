from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date

AMOUNT_TOKEN_PATTERN = re.compile(
    r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?"
)

SUPPLIER_TAX_ID_PATTERN = re.compile(
    r"\bC\.?I\.?F\.?\s*[: ]\s*(B[-\s]?\d{8})\b",
    re.IGNORECASE,
)

CUSTOMER_TAX_ID_PATTERN = re.compile(
    r"(?:Numero\s+NIF|NIF)\s*:\s*([A-Z0-9][A-Z0-9\-\s]+)",
    re.IGNORECASE,
)

SALE_DATE_PATTERN = re.compile(
    r"Fecha\s+de\s+venta\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
    re.IGNORECASE,
)

RETURN_DATE_PATTERN = re.compile(
    r"Fecha\s+de\s+devoluci[oó]n\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
    re.IGNORECASE,
)

F0018_TEXTUAL_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+(\d{4})\b"
)

STANDARD_INVOICE_NUMBER_PATTERN = re.compile(
    r"\bFACTURA(?:\s+RECTIFICATIVA)?\s*[:#-]?\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)\b",
    re.IGNORECASE,
)

ALTERNATIVE_INVOICE_NUMBER_PATTERN = re.compile(
    r"\bFACTURA(?:\s+RECTIFICATIVA)?\s*[:#-]?\s*(F\d{4}-\d{3}-\d{2}[_/-][A-Z0-9]+)\b",
    re.IGNORECASE,
)

RECTIFICATIVE_BREAKDOWN_WITH_IVA_PATTERN = re.compile(
    r"(?:^|[\n\r])\s*IVA\s+\d{1,2}(?:[.,]\d{2})?%\s+([+-]?\d+(?:[.,]\d+)?)\s+([+-]?\d+(?:[.,]\d+)?)\s+([+-]?\d+(?:[.,]\d+)?)\s*(?:$|[\n\r])",
    re.IGNORECASE,
)

RECTIFICATIVE_BREAKDOWN_WITHOUT_IVA_PATTERN = re.compile(
    r"(?:^|[\n\r])\s*\d{1,2}(?:[.,]\d{2})?\s+([+-]?\d+(?:[.,]\d+)?)\s+([+-]?\d+(?:[.,]\d+)?)\s+([+-]?\d+(?:[.,]\d+)?)\s*(?:$|[\n\r])",
    re.IGNORECASE,
)


class ObramatInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "obramat"
    priority = 500

    SUPPLIER_NAME = "BRICOLAJE BRICOMAN, S.L.U."
    SUPPLIER_TAX_ID = "B84406289"
    DEFAULT_CUSTOMER_NAME = "Daniel Cuenca Moya"
    DEFAULT_CUSTOMER_TAX_ID = "48334490J"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        path_text = self.get_path_text(file_path)

        if self._looks_like_leroy_merlin(normalized_text, path_text):
            return False

        score = 0

        if self.matches_file_path_hint(file_path, ("obramat", "bricoman")):
            score += 1

        if any(token in normalized_text for token in ("bricoman", "obramat", "bricolaje bricoman")):
            score += 3

        if "obramat finestrat" in normalized_text:
            score += 2

        if "avda. pais valencia" in normalized_text or "avda pais valencia" in normalized_text:
            score += 2

        if "avinguda país valencià" in normalized_text or "avinguda pais valencia" in normalized_text:
            score += 2

        if "fecha de venta" in normalized_text or "fecha de devolucion" in normalized_text:
            score += 1

        if "ticket de caja" in normalized_text:
            score += 1

        if "desglose totales" in normalized_text:
            score += 2

        if "tasa iva/igic/ipsi" in normalized_text:
            score += 1

        if "ejemplar cliente" in normalized_text:
            score += 1

        return score >= 3

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.extract_obramat_supplier_tax_id(text)

        result.nombre_cliente = self.extract_obramat_customer_name(text)
        result.nif_cliente = self.extract_obramat_customer_tax_id(text)

        result.numero_factura = self.extract_obramat_invoice_number(file_path, text)
        result.fecha_factura = self.extract_obramat_date(file_path, text)

        subtotal, iva, total = self.extract_obramat_tax_breakdown(text)
        result.subtotal = subtotal if subtotal is not None else self.extract_obramat_subtotal_fallback(text)
        result.iva = iva if iva is not None else self.extract_obramat_iva_fallback(text)
        result.total = total if total is not None else self.extract_obramat_total_fallback(text)

        return result.finalize()

    def _looks_like_leroy_merlin(self, normalized_text: str, path_text: str) -> bool:
        leroy_markers = (
            "leroy merlin",
            "leroy merlin espana",
            "leroy merlin españa",
            "leroy merlin finestrat",
            "b84818442",
        )
        combined = f"{normalized_text}\n{path_text}"
        return any(marker in combined for marker in leroy_markers)

    def extract_obramat_supplier_tax_id(self, text: str) -> str:
        match = SUPPLIER_TAX_ID_PATTERN.search(text)
        if match:
            return match.group(1)

        exact_candidates = self.extract_exact_tax_ids(text)
        for candidate in exact_candidates:
            if candidate == self.SUPPLIER_TAX_ID:
                return candidate

        return self.SUPPLIER_TAX_ID

    def extract_obramat_customer_name(self, text: str) -> str:
        return self.DEFAULT_CUSTOMER_NAME

    def extract_obramat_customer_tax_id(self, text: str) -> str:
        match = CUSTOMER_TAX_ID_PATTERN.search(text)
        if match:
            candidate = re.sub(r"\s+", "", match.group(1)).strip().upper()
            if candidate == self.DEFAULT_CUSTOMER_TAX_ID:
                return candidate

        exact_candidates = self.extract_exact_tax_ids(text)
        for candidate in exact_candidates:
            if candidate == self.DEFAULT_CUSTOMER_TAX_ID:
                return candidate

        return self.DEFAULT_CUSTOMER_TAX_ID

    def extract_obramat_invoice_number(self, file_path: str | Path, text: str) -> str | None:
        text_match = STANDARD_INVOICE_NUMBER_PATTERN.search(text)
        if text_match:
            return self.clean_invoice_number_candidate(text_match.group(1))

        text_match = ALTERNATIVE_INVOICE_NUMBER_PATTERN.search(text)
        if text_match:
            return self.clean_invoice_number_candidate(text_match.group(1).replace("_", "/"))

        from_filename = self.extract_filename_invoice_number(
            file_path,
            [
                r"factura\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)",
                r"factura\s*(F\d{4}-\d{3}-\d{2}[_/-][A-Z0-9]+)",
                r"n[º°o]?\s*factura\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)",
                r"n[º°o]?\s*factura\s*(F\d{4}-\d{3}-\d{2}[_/-][A-Z0-9]+)",
                r"([0-9]{3}-[0-9]{4}-R?[A-Z0-9]+)",
                r"(F\d{4}-\d{3}-\d{2}[_/-][A-Z0-9]+)",
            ],
        )
        if from_filename:
            return self.clean_invoice_number_candidate(from_filename.replace("_", "/"))

        return None

    def extract_obramat_date(self, file_path: str | Path, text: str) -> str | None:
        match = RETURN_DATE_PATTERN.search(text)
        if match:
            return match.group(1)

        match = SALE_DATE_PATTERN.search(text)
        if match:
            return match.group(1)

        if self.is_f0018_layout(text):
            f0018_date = self.extract_f0018_date(text)
            if f0018_date:
                return f0018_date

        top_text = "\n".join(self.extract_lines(text)[:8])
        top_date = normalize_date(top_text)
        if top_date:
            return top_date

        return self.extract_filename_date(file_path) or self.extract_date(text)

    def extract_f0018_date(self, text: str) -> str | None:
        lines = self.extract_lines(text)

        for line in lines[:6]:
            match = F0018_TEXTUAL_DATE_PATTERN.search(line)
            if not match:
                continue

            day, month, year = match.groups()
            normalized = normalize_date(f"{day} de {month} de {year}")
            if normalized:
                return normalized

        return None

    def extract_obramat_tax_breakdown(self, text: str) -> tuple[float | None, float | None, float | None]:
        if self.is_rectificative_layout(text):
            triplet = self.extract_rectificative_tax_breakdown(text)
            if triplet is not None:
                return triplet

        if self.is_f0018_layout(text):
            triplet = self.extract_f0018_tax_breakdown(text)
            if triplet is not None:
                return triplet

        triplet = self.extract_classic_tax_breakdown(text)
        if triplet is not None:
            return triplet

        return (None, None, None)

    def is_rectificative_layout(self, text: str) -> bool:
        return "factura rectificativa" in text.lower()

    def is_f0018_layout(self, text: str) -> bool:
        normalized_text = text.lower()
        return (
            "factura f0018-" in normalized_text
            or "desglose totales" in normalized_text
            or "factura emitida por 018" in normalized_text
        )

    def extract_rectificative_tax_breakdown(self, text: str) -> tuple[float | None, float | None, float | None] | None:
        match = RECTIFICATIVE_BREAKDOWN_WITH_IVA_PATTERN.search(text)
        if match:
            return (
                parse_amount(match.group(1)),
                parse_amount(match.group(2)),
                parse_amount(match.group(3)),
            )

        match = RECTIFICATIVE_BREAKDOWN_WITHOUT_IVA_PATTERN.search(text)
        if match:
            return (
                parse_amount(match.group(1)),
                parse_amount(match.group(2)),
                parse_amount(match.group(3)),
            )

        lines = self.extract_lines(text)
        for line in reversed(lines):
            normalized_line = re.sub(r"\s+", " ", line).strip()
            if normalized_line == "":
                continue

            if "modos de pagos" in normalized_line.lower():
                continue

            amounts = self._parse_amounts_from_line(normalized_line)
            if len(amounts) >= 4:
                triplet = self._extract_triplet_from_amounts(amounts[1:], prefer_tail=False)
                if triplet is not None:
                    return triplet

            if len(amounts) >= 3:
                triplet = self._extract_triplet_from_amounts(amounts, prefer_tail=True)
                if triplet is not None:
                    return triplet

        return None

    def extract_f0018_tax_breakdown(self, text: str) -> tuple[float | None, float | None, float | None] | None:
        lines = self.extract_lines(text)

        for index, line in enumerate(lines):
            if "DESGLOSE TOTALES" not in line.upper():
                continue

            candidate_lines = lines[index + 1 : index + 10]
            for candidate_line in candidate_lines:
                upper_line = candidate_line.upper()

                if "TOTAL BI" in upper_line or "TOTAL IVA" in upper_line:
                    continue

                if "IVA" not in upper_line and "EUR" not in upper_line:
                    continue

                triplet = self._extract_triplet_from_amounts(
                    self._parse_amounts_from_line(candidate_line),
                    prefer_tail=True,
                )
                if triplet is not None:
                    return triplet

        return None

    def extract_classic_tax_breakdown(self, text: str) -> tuple[float | None, float | None, float | None] | None:
        lines = self.extract_lines(text)

        for line in reversed(lines):
            upper_line = line.upper()

            if "DESGLOSE TOTALES" in upper_line or "MODOS DE PAGOS" in upper_line:
                continue

            amounts = self._parse_amounts_from_line(line)
            if len(amounts) < 3:
                continue

            triplet = self._extract_triplet_from_amounts(amounts, prefer_tail=True)
            if triplet is not None:
                return triplet

        return None

    def _extract_triplet_from_amounts(
        self,
        amounts: list[float],
        prefer_tail: bool,
    ) -> tuple[float | None, float | None, float | None] | None:
        if len(amounts) < 3:
            return None

        candidate_amounts = amounts[-3:] if prefer_tail else amounts[:3]
        subtotal, iva, total = candidate_amounts

        if subtotal is None or iva is None or total is None:
            return None

        if round(subtotal + iva, 2) != round(total, 2):
            return None

        return subtotal, iva, total

    def _parse_amounts_from_line(self, line: str) -> list[float]:
        parsed_values: list[float] = []
        for raw_amount in AMOUNT_TOKEN_PATTERN.findall(line):
            parsed = parse_amount(raw_amount)
            if parsed is None:
                continue
            parsed_values.append(parsed)
        return parsed_values

    def extract_obramat_subtotal_fallback(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"base\s+imponible",
                r"total\s+bi",
                r"subtotal",
            ],
        )

    def extract_obramat_iva_fallback(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"cuota\s+iva",
                r"importe\s+iva",
                r"total\s+iva",
            ],
        )

    def extract_obramat_total_fallback(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"total\s+factura",
                r"importe\s+total",
                r"total\s*eur",
            ],
        )