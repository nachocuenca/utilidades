from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


class ObramatInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "obramat"
    priority = 400

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("obramat", "bricoman")):
            return True

        return "obramat" in normalized_text or "bricoman" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = "OBRAMAT"
        result.nif_proveedor = "B84406289"
        result.numero_factura = self.extract_obramat_invoice_number(file_path, text)
        result.fecha_factura = self.extract_filename_date(file_path) or self.extract_date(text)
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_labeled_amount(
            text,
            [
                r"cuota\s+iva",
                r"importe\s+iva",
            ],
        )
        result.total = self.extract_total(text)

        return result.finalize()

    def extract_obramat_invoice_number(self, file_path: str | Path, text: str) -> str | None:
        from_filename = self.extract_filename_invoice_number(
            file_path,
            [
                r"factura\s*([A-Z0-9_/\-]+)",
            ],
        )
        if from_filename:
            normalized = from_filename.replace("_", "/")
            return self.clean_invoice_number_candidate(normalized)

        match = re.search(r"\b(F\d{4}-\d{3}-\d{2}[\/_-]\d+|\d{3}-\d{4}-[A-Z]?\d+)\b", text, re.IGNORECASE)
        if match:
            return self.clean_invoice_number_candidate(match.group(1).replace("_", "/"))

        return None