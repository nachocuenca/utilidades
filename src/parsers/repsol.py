from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount


class RepsolInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "repsol"
    priority = 360

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("repsol",)):
            return True

        return "repsol" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = "REPSOL"
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(text)
        result.numero_factura = self.extract_repsol_invoice_number(text)
        result.fecha_factura = self.extract_filename_date(
            file_path,
            patterns=[
                r"([0-3]\d[_\-][01]\d[_\-]20\d{2})",
            ],
        ) or self.extract_date(text)
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_labeled_amount(
            text,
            [
                r"cuota\s+iva",
                r"importe\s+iva",
            ],
        )
        result.total = self.extract_repsol_total(file_path, text)

        return result.finalize()

    def extract_repsol_supplier_tax_id(self, text: str) -> str | None:
        candidates = self.extract_exact_tax_ids("\n".join(self.extract_lines(text)[:10]))
        for candidate in candidates:
            if candidate != "48334490J":
                return candidate
        return None

    def extract_repsol_invoice_number(self, text: str) -> str | None:
        match = re.search(r"\b\d{6}/\d/\d{2}/\d{6}\b", text)
        if match:
            return self.clean_invoice_number_candidate(match.group(0))
        return self.extract_invoice_number(text)

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self.extract_total(text)
        if value is not None:
            return value

        match = re.search(r"(\d+(?:,\d{2})?)\s*€", Path(file_path).stem)
        if match:
            return parse_amount(match.group(1))

        return None