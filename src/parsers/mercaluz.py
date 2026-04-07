from __future__ import annotations

from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


class MercaluzInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "mercaluz"
    priority = 110

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("mercaluz",)):
            return True

        return "mercaluz" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = super().parse(text, file_path)
        folder_hint = self.get_folder_hint_name(file_path)

        result.parser_usado = self.parser_name
        result.nombre_proveedor = folder_hint or "MERCALUZ"

        if not result.nombre_cliente:
            result.nombre_cliente = result.nombre_proveedor

        return result.finalize()