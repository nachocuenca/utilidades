from __future__ import annotations

from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


class SaltokiInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "saltoki"
    priority = 390

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("saltoki",)):
            return True

        return "saltoki" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        folder_hint = self.get_folder_hint_name(file_path) or "SALTOKI"

        result.nombre_proveedor = folder_hint
        result.nif_proveedor = self.get_supplier_tax_id_from_folder(folder_hint) or self.extract_supplier_tax_id(text)
        result.numero_factura = self.extract_filename_invoice_number(
            file_path,
            [
                r"^copia de (\d+)",
                r"^(\d+)",
            ],
        ) or self.extract_saltoki_invoice_number(text)
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

    def get_supplier_tax_id_from_folder(self, folder_hint: str | None) -> str | None:
        if not folder_hint:
            return None

        normalized = folder_hint.lower()
        if "benidorm" in normalized:
            return "B71406607"
        if "alicante" in normalized:
            return "B71406623"
        return None

    def extract_saltoki_invoice_number(self, text: str) -> str | None:
        value = self.extract_invoice_number(text)
        if value and value.lower() not in {"contiene", "hoja", "fecha"}:
            return value
        return None