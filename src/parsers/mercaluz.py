from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


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
        result.fecha_factura = self.extract_filename_date(file_path) or self.extract_date(text)
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        return result.finalize()

    def extract_mercaluz_invoice_number(self, file_path: str | Path, text: str) -> str | None:
        filename_num = self.extract_filename_invoice_number(
            file_path,
            [
                r"^([ABVF][A-Z]?\d{4}-\d{5}-\d{6})",
                r"^([ABVF][A-Z]?\d{4}-\d{5}-\d+)",
                r"^(FVN\d{4}-\d{5}-\d+)",
                r"^([A-Z]{3}\d{4}-\d{5}-\d{6})",
            ],
        )
        if filename_num:
            return filename_num

        text_patterns = [
            r"(?:factura|numero de factura|no factura|factura no)\s*[:\-#]?\s*([ABVF][A-Z]?\d{4}-\d{5}-\d+)",
            r"factura[:\s]+([ABVF][A-Z]?\d{4}-\d{5}-\d+)",
            r"factura\s+([ABVF][A-Z]?\d{4}-\d{5}-\d+)",
            r"([ABVF][A-Z]?\d{4}-\d{5}-\d+)\s*(?:fecha|no factura|factura)",
        ]
        for pattern in text_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = self.clean_invoice_number_candidate(match.group(1))
                if candidate:
                    return candidate

        return self.extract_invoice_number(text)