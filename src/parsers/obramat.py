from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount

AMOUNT_PATTERN = r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?"
BREAKDOWN_ROW_PATTERN = re.compile(
    rf"(?:^|[\n\r])\s*(?:IVA\s*)?\d{{1,2}}(?:[.,]\d{{2}})?%?\s+({AMOUNT_PATTERN})\s+({AMOUNT_PATTERN})\s+({AMOUNT_PATTERN})\s*(?:$|[\n\r])",
    re.IGNORECASE | re.MULTILINE,
)
INVOICE_NUMBER_TEXT_PATTERNS = (
    re.compile(
        r"\bFACTURA(?:\s+RECTIFICATIVA)?\s*[:#-]?\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bN[º°O]?\s*FACTURA\s*[:#-]?\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)\b",
        re.IGNORECASE,
    ),
)
SUPPLIER_TAX_ID_PATTERN = re.compile(
    r"\bC\.?I\.?F\.?\s*[: ]\s*(B[-\s]?\d{8})\b",
    re.IGNORECASE,
)
CUSTOMER_NAME_PATTERN = re.compile(
    r"^\s*SR\s+([A-ZÁÉÍÓÚÜÑ][^\n\r]+)$",
    re.IGNORECASE | re.MULTILINE,
)
CUSTOMER_TAX_ID_PATTERN = re.compile(
    r"Numero\s+NIF\s*:\s*([A-Z0-9][A-Z0-9\- ]+)",
    re.IGNORECASE,
)
SALE_DATE_PATTERN = re.compile(
    r"Fecha\s+de\s+venta\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
    re.IGNORECASE,
)


class ObramatInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "obramat"
    priority = 500

    SUPPLIER_NAME = "BRICOLAJE BRICOMAN, S.L.U."
    SUPPLIER_TAX_ID = "B-84406289"
    DEFAULT_CUSTOMER_NAME = "Daniel Cuenca Moya"
    DEFAULT_CUSTOMER_TAX_ID = "48334490J"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        path_text = self.get_path_text(file_path)

        if any(token in path_text for token in ("obramat", "bricoman")):
            return True

        score = 0

        if any(token in normalized_text for token in ("obramat", "bricoman", "bricolaje bricoman")):
            score += 2

        if "ticket de caja" in normalized_text:
            score += 1

        if "fecha de venta" in normalized_text:
            score += 1

        if "tasa iva/igic/ipsi" in normalized_text:
            score += 1

        if "avda. pais valencia" in normalized_text or "avda pais valencia" in normalized_text:
            score += 1

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_obramat_supplier_name(text)
        result.nif_proveedor = self.extract_obramat_supplier_tax_id(text)

        result.nombre_cliente = self.extract_obramat_customer_name(text)
        result.nif_cliente = self.extract_obramat_customer_tax_id(text)

        result.numero_factura = self.extract_obramat_invoice_number(file_path, text)
        result.fecha_factura = self.extract_obramat_date(file_path, text)

        subtotal, iva, total = self.extract_obramat_tax_breakdown(text)
        result.subtotal = subtotal if subtotal is not None else self.extract_subtotal(text)
        result.iva = iva if iva is not None else self.extract_iva(text)
        result.total = total if total is not None else self.extract_total(text)

        return result.finalize()

    def extract_obramat_supplier_name(self, text: str) -> str:
        if "bricoman" in text.lower() or "obramat" in text.lower():
            return self.SUPPLIER_NAME

        return self.SUPPLIER_NAME

    def extract_obramat_supplier_tax_id(self, text: str) -> str:
        match = SUPPLIER_TAX_ID_PATTERN.search(text)
        if match:
            return match.group(1)

        exact_candidates = self.extract_exact_tax_ids(text)
        for candidate in exact_candidates:
            if candidate.startswith("B84406289"):
                return candidate

        return self.SUPPLIER_TAX_ID

    def extract_obramat_customer_name(self, text: str) -> str:
        match = CUSTOMER_NAME_PATTERN.search(text)
        if match:
            candidate = re.sub(r"\s+", " ", match.group(1)).strip()
            normalized = candidate.upper()
            if all(token in normalized for token in ("DANIEL", "CUENCA", "MOYA")):
                return self.DEFAULT_CUSTOMER_NAME
            return candidate.title()

        lines = self.extract_lines(text)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.upper().startswith("SR "):
                continue

            candidate = stripped[3:].strip()
            normalized = re.sub(r"\s+", " ", candidate).upper()
            if all(token in normalized for token in ("DANIEL", "CUENCA", "MOYA")):
                return self.DEFAULT_CUSTOMER_NAME

            if candidate:
                return candidate.title()

            if index + 1 < len(lines):
                fallback = lines[index + 1].strip()
                normalized_fallback = re.sub(r"\s+", " ", fallback).upper()
                if all(token in normalized_fallback for token in ("DANIEL", "CUENCA", "MOYA")):
                    return self.DEFAULT_CUSTOMER_NAME
                if fallback:
                    return fallback.title()

        return self.DEFAULT_CUSTOMER_NAME

    def extract_obramat_customer_tax_id(self, text: str) -> str:
        match = CUSTOMER_TAX_ID_PATTERN.search(text)
        if match:
            candidate = re.sub(r"\s+", "", match.group(1)).strip()
            if candidate.upper().startswith("48334490J"):
                return self.DEFAULT_CUSTOMER_TAX_ID
            return candidate

        exact_candidates = self.extract_exact_tax_ids(text)
        for candidate in exact_candidates:
            if candidate == "48334490J":
                return candidate

        return self.DEFAULT_CUSTOMER_TAX_ID

    def extract_obramat_invoice_number(self, file_path: str | Path, text: str) -> str | None:
        from_filename = self.extract_filename_invoice_number(
            file_path,
            [
                r"factura\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)",
                r"n[º°o]?\s*factura\s*([0-9]{3}-[0-9]{4}-[A-Z0-9]+)",
                r"([0-9]{3}-[0-9]{4}-[A-Z0-9]+)",
            ],
        )
        if from_filename:
            return self.clean_invoice_number_candidate(from_filename)

        for pattern in INVOICE_NUMBER_TEXT_PATTERNS:
            match = pattern.search(text)
            if match:
                return self.clean_invoice_number_candidate(match.group(1))

        return None

    def extract_obramat_date(self, file_path: str | Path, text: str) -> str | None:
        match = SALE_DATE_PATTERN.search(text)
        if match:
            return match.group(1)

        return self.extract_filename_date(file_path) or self.extract_date(text)

    def extract_obramat_tax_breakdown(self, text: str) -> tuple[float | None, float | None, float | None]:
        candidate_sections = self._build_tax_sections(text)

        for section in candidate_sections:
            matches = list(BREAKDOWN_ROW_PATTERN.finditer(section))
            if not matches:
                continue

            last_match = matches[-1]
            subtotal = parse_amount(last_match.group(1))
            iva = parse_amount(last_match.group(2))
            total = parse_amount(last_match.group(3))

            if subtotal is None and iva is None and total is None:
                continue

            return subtotal, iva, total

        return (None, None, None)

    def _build_tax_sections(self, text: str) -> list[str]:
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        sections: list[str] = []

        heading_patterns = [
            r"Tasa\s+IVA/IGIC/IPSI",
            r"Total\s+IVA/IGIC/IPSI",
            r"Total\s+TTI\s*\(EUR\)",
        ]

        for heading_pattern in heading_patterns:
            matches = list(re.finditer(heading_pattern, normalized_text, re.IGNORECASE))
            if not matches:
                continue

            start = matches[-1].start()
            sections.append(normalized_text[start:])

        lines = self.extract_lines(normalized_text)
        bottom_lines = "\n".join(lines[-12:]) if lines else normalized_text
        sections.append(bottom_lines)
        sections.append(normalized_text)

        return sections