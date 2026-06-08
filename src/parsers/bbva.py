from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData


class BBVAInvoiceParser(BaseInvoiceParser):
    parser_name = "bbva"
    priority = 420

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        return "bbva factura" in normalized or (
            "total factura" in normalized and "importe neto" in normalized and "cuota correspondiente al vto" in normalized
        )

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        result.nombre_proveedor = "BBVA"
        result.fecha_factura = self._extract_date(text)
        result.subtotal = self.extract_labeled_amount(text, [r"IMPORTE\s+NETO"], ignore_percent=True)
        result.iva = self.extract_labeled_amount(text, [r"I\.?V\.?A\.?\s*21,00%"], ignore_percent=True)
        result.total = self.extract_labeled_amount(text, [r"TOTAL\s+FACTURA"], ignore_percent=True)
        return result.finalize()

    def _extract_date(self, text: str) -> str | None:
        match = re.search(r"Plaza\s+y\s+Fecha:?\s*[A-ZÁÉÍÓÚÑ ]+\s+([0-9]{1,2}-[0-9]{1,2}-[0-9]{2,4})", text, re.IGNORECASE)
        if match:
            return self.extract_date(match.group(1))
        return self.extract_date(text)
