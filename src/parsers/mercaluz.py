from __future__ import annotations

from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


class MercaluzInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "mercaluz"
    priority = 345
    SUPPLIER_TAX_ID = "A03204864"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        score = 0

        if self.matches_file_path_hint(file_path, ("mercaluz",)):
            score += 1

        if "mercaluz" in normalized_text:
            score += 2

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 2

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        folder_hint = self.get_folder_hint_name(file_path)

        result.nombre_proveedor = folder_hint or "MERCALUZ"
        result.nif_proveedor = self.SUPPLIER_TAX_ID
        result.numero_factura = self.extract_filename_invoice_number(
            file_path,
            [
                r"^([A-Z]{3}\d{4}-\d{5}-\d{6})",
                r"^([A-Z]{3}\d{4}-\d{5}-\d+)",
                r"^(FVN\d{4}-\d{5}-\d+)",
            ],
        ) or self.extract_invoice_number(text)
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
