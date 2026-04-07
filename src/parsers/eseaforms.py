from __future__ import annotations

from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


class EseaformsInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "eseaforms"
    priority = 355

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("eseaforms",)):
            return True

        return "eseaforms" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = "ESEAFORMS"
        result.nif_proveedor = "B76080407"
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