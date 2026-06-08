from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData


class EndesaInvoiceParser(BaseInvoiceParser):
    parser_name = "endesa"
    priority = 430

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        return "endesa energia" in normalized or "a81948077" in normalized

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        result.nombre_proveedor = "Endesa Energia, S.A. Unipersonal."
        result.nif_proveedor = "A81948077" if "A81948077" in self.extract_exact_tax_ids(text) else self.extract_supplier_tax_id(text)
        result.numero_factura = self._extract_number(text)
        result.fecha_factura = self._extract_date(text)
        result.subtotal, result.iva, result.total = self.extract_summary_amounts(text)
        if result.total is None:
            result.total = self.extract_labeled_amount(text, [r"total\s+factura", r"total\s+a\s+pagar", r"importe\s+factura"], ignore_percent=True)
        return result.finalize()

    def _extract_number(self, text: str) -> str | None:
        match = re.search(r"N[°ºo]?\s*factura:?\s*([A-Z0-9\-/.]+)", text, re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_date(self, text: str) -> str | None:
        match = re.search(r"Fecha\s+emisi[oó]n\s+factura:?\s*([^\n\r]+)", text, re.IGNORECASE)
        if match:
            return self.extract_date(match.group(1))
        return self.extract_date(text)
