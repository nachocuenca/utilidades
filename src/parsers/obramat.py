from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount

AMOUNT_TOKEN_PATTERN = re.compile(
    r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?"
)

SUPPLIER_TAX_ID_PATTERN = re.compile(
    r"\bC\.?I\.?F\.?\s*[: ]\s*(B[-\s]?\d{8})\b",
    re.IGNORECASE,
)

CUSTOMER_TAX_ID_PATTERN = re.compile(
    r"Numero\s+NIF\s*:\s*([A-Z0-9][A-Z0-9\-\s]+)",
    re.IGNORECASE,
)

SALE_DATE_PATTERN = re.compile(
    r"Fecha\s+de\s+venta\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
    re.IGNORECASE,
)

STANDARD_INVOICE_NUMBER_PATTERN = re.compile(
    r"\bFACTURA(?:\s+RECTIFICATIVA)?\s*[:#-]?\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)\b",
    re.IGNORECASE,
)

ALTERNATIVE_INVOICE_NUMBER_PATTERN = re.compile(
    r"\bFACTURA(?:\s+RECTIFICATIVA)?\s*[:#-]?\s*(F\d{4}-\d{3}-\d{2}[_/-][A-Z0-9]+)\b",
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

        if any(token in path_text for token in ("obramat", "bricoman")):
            return True

        score = 0

        if any(token in normalized_text for token in ("bricoman", "obramat", "bricolaje bricoman")):
            score += 3

        if "avda. pais valencia" in normalized_text or "avda pais valencia" in normalized_text:
            score += 2

        if "fecha de venta" in normalized_text:
            score += 1

        if "ticket de caja" in normalized_text:
            score += 1

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
        normalized_text = re.sub(r"\s+", " ", text).upper()
        if all(token in normalized_text for token in ("DANIEL", "CUENCA", "MOYA")):
            return self.DEFAULT_CUSTOMER_NAME
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
            return self.clean_invoice_number_candidate(text_match.group(1))

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
            return self.clean_invoice_number_candidate(from_filename)

        return None

    def extract_obramat_date(self, file_path: str | Path, text: str) -> str | None:
        match = SALE_DATE_PATTERN.search(text)
        if match:
            return match.group(1)

        return self.extract_filename_date(file_path) or self.extract_date(text)

    def extract_obramat_tax_breakdown(self, text: str) -> tuple[float | None, float | None, float | None]:
        for block in self._get_breakdown_candidate_blocks(text):
            for line in reversed(block):
                triplet = self._extract_breakdown_triplet_from_line(line)
                if triplet is not None:
                    return triplet

        return (None, None, None)

    def extract_obramat_subtotal_fallback(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"base\s+imponible",
                r"total\.\s*si",
            ],
        )

    def extract_obramat_iva_fallback(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"cuota\s+iva",
                r"importe\s+iva",
                r"total\s+iva/igic/ipsi",
            ],
        )

    def extract_obramat_total_fallback(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"total\s+tti",
                r"importe\s+tti",
                r"total\s+factura",
            ],
        )

    def _get_breakdown_candidate_blocks(self, text: str) -> list[list[str]]:
        lines = self.extract_lines(text)
        lower_lines = [line.lower() for line in lines]

        heading_markers = (
            "tasa iva/igic/ipsi",
            "total iva/igic/ipsi",
            "total tti",
        )

        blocks: list[list[str]] = []

        for index in range(len(lines) - 1, -1, -1):
            if any(marker in lower_lines[index] for marker in heading_markers):
                blocks.append(lines[index : index + 8])

        if lines:
            blocks.append(lines[max(0, len(lines) - 20) :])

        return blocks

    def _extract_breakdown_triplet_from_line(
        self,
        line: str,
    ) -> tuple[float | None, float | None, float | None] | None:
        normalized_line = re.sub(r"\s+", " ", line).strip()
        lowered = normalized_line.lower()

        ignored_markers = (
            "modos de pagos",
            "efectivo",
            "cambio",
            "tarj",
            "ticket de caja",
            "precio unidad",
            "importe tti",
            "designacion",
            "referencia articulo",
        )
        if any(marker in lowered for marker in ignored_markers):
            return None

        raw_amounts = AMOUNT_TOKEN_PATTERN.findall(normalized_line)
        if len(raw_amounts) < 3:
            return None

        candidate_amounts = raw_amounts[-3:]
        parsed_values = [parse_amount(value) for value in candidate_amounts]
        if any(value is None for value in parsed_values):
            return None

        subtotal = parsed_values[0]
        iva = parsed_values[1]
        total = parsed_values[2]

        if subtotal is None or iva is None or total is None:
            return None

        if round(subtotal + iva - total, 2) != 0:
            return None

        return subtotal, iva, total