from __future__ import annotations

from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


class EdieuropaInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "edieuropa"
    priority = 350
    SUPPLIER_TAX_ID = "B03310091"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        score = 0

        if self.matches_file_path_hint(file_path, ("edieuropa", "edi europa")):
            score += 1

        if "edieuropa" in normalized_text or "edi europa" in normalized_text:
            score += 2

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 2

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        folder_hint = self.get_folder_hint_name(file_path)

        result.nombre_proveedor = folder_hint or "EDIEUROPA"
        result.nif_proveedor = self.SUPPLIER_TAX_ID
        result.numero_factura = self.extract_filename_invoice_number(
            file_path,
            [
                r"factura\s+([0-9A-Z\-]+)",
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
