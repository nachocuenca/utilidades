from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount
from src.utils.names import clean_name_candidate


class ObramatInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "obramat"
    priority = 500

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("obramat", "bricoman")):
            return True

        return "obramat" in normalized_text or "bricoman" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = "OBRAMAT"
        result.nif_proveedor = "B84406289"
        result.nombre_cliente = self.extract_obramat_customer_name(text)
        result.nif_cliente = self.extract_obramat_customer_tax_id(text)
        result.numero_factura = self.extract_obramat_invoice_number(file_path, text)
        result.fecha_factura = self.extract_obramat_date(file_path, text)

        subtotal, iva, total = self.extract_obramat_tax_breakdown(text)
        result.subtotal = subtotal if subtotal is not None else self.extract_subtotal(text)
        result.iva = iva if iva is not None else self.extract_iva(text)
        result.total = total if total is not None else self.extract_total(text)

        return result.finalize()

    def extract_obramat_customer_name(self, text: str) -> str | None:
        match = re.search(r"^\s*SR\s+([A-ZÁÉÍÓÚÑ][^\n\r]+)$", text, re.IGNORECASE | re.MULTILINE)
        if match:
            return clean_name_candidate(match.group(1))

        lines = self.extract_lines(text)
        for index, line in enumerate(lines):
            if line.strip().upper().startswith("SR "):
                candidate = line.strip()[3:].strip()
                cleaned = clean_name_candidate(candidate)
                if cleaned:
                    return cleaned

                if index + 1 < len(lines):
                    cleaned = clean_name_candidate(lines[index + 1])
                    if cleaned:
                        return cleaned

        return None

    def extract_obramat_customer_tax_id(self, text: str) -> str | None:
        match = re.search(r"Numero\s+NIF\s*:\s*([A-Z0-9]+)", text, re.IGNORECASE)
        if match:
            return match.group(1)

        exact_candidates = self.extract_exact_tax_ids(text)
        for candidate in exact_candidates:
            if candidate != "B84406289":
                return candidate

        return None

    def extract_obramat_invoice_number(self, file_path: str | Path, text: str) -> str | None:
        from_filename = self.extract_filename_invoice_number(
            file_path,
            [
                r"factura\s*([A-Z0-9][A-Z0-9/_-]+)",
            ],
        )
        if from_filename:
            return self.clean_invoice_number_candidate(from_filename.replace("_", "/"))

        match = re.search(r"\bFACTURA\s+([A-Z0-9][A-Z0-9/_-]+)\b", text, re.IGNORECASE)
        if match:
            return self.clean_invoice_number_candidate(match.group(1).replace("_", "/"))

        return None

    def extract_obramat_date(self, file_path: str | Path, text: str) -> str | None:
        match = re.search(r"Fecha\s+de\s+venta\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
        if match:
            return match.group(1)

        return self.extract_filename_date(file_path) or self.extract_date(text)

    def extract_obramat_tax_breakdown(self, text: str) -> tuple[float | None, float | None, float | None]:
        match = re.search(
            r"IVA\s+\d{1,2}(?:[.,]\d{2})?%\s+([0-9.,]+)\s+([0-9.,]+)\s+([0-9.,]+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return (
                parse_amount(match.group(1)),
                parse_amount(match.group(2)),
                parse_amount(match.group(3)),
            )

        return (None, None, None)