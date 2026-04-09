from __future__ import annotations

from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


class EseaformsInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "eseaforms"
    priority = 355
    SUPPLIER_NAME = "CANAL TONIGHT, SOCIEDAD LIMITADA"
    SUPPLIER_TAX_ID = "B76080407"

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        score = 0

        if self.matches_file_path_hint(file_path, ("eseaforms",)):
            score += 1

        if "eseaforms" in normalized_text:
            score += 2

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 2

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.SUPPLIER_NAME
        result.nif_proveedor = self.SUPPLIER_TAX_ID
        result.numero_factura = self.extract_filename_invoice_number(
            file_path,
            [
                r"^(I\d+)",
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
