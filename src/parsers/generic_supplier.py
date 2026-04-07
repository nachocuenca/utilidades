from __future__ import annotations

from pathlib import Path
import re

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData


class GenericSupplierInvoiceParser(BaseInvoiceParser):
    parser_name = "generic_supplier"
    priority = 20

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        path_hint = self.get_folder_hint_name(file_path)
        normalized_text = text.lower()

        if path_hint and path_hint.lower() not in {"inbox", "data"}:
            if any(token in normalized_text for token in ("factura", "base imponible", "iva", "total")):
                return True

        supplier_markers = (
            "proveedor",
            "emisor",
            "razón social",
            "razon social",
            "base imponible",
        )
        return any(marker in normalized_text for marker in supplier_markers)

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(lines, file_path)
        result.nif_proveedor = self.extract_supplier_tax_id(text)
        result.numero_factura = self.extract_invoice_number(text)
        result.fecha_factura = self.extract_date(text)
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        if result.nombre_cliente is None and result.nombre_proveedor:
            result.nombre_cliente = result.nombre_proveedor

        if result.nif_cliente is None and result.nif_proveedor:
            result.nif_cliente = result.nif_proveedor

        return result.finalize()

    def extract_supplier_name(self, lines: list[str], file_path: str | Path) -> str | None:
        provider = self.extract_name_near_labels(
            lines,
            [
                r"^proveedor\b",
                r"^emisor\b",
                r"^empresa\b",
                r"^raz[oó]n social\b",
                r"^datos del proveedor\b",
                r"^datos del emisor\b",
            ],
            max_distance=3,
        )

        if provider:
            return provider

        top_provider = self.extract_provider_from_top(lines, top_n=8)
        if top_provider:
            return top_provider

        folder_hint = self.get_folder_hint_name(file_path)
        if folder_hint:
            return folder_hint

        return None