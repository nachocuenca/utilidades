from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date


class SabadellInvoiceParser(BaseInvoiceParser):
    parser_name = "sabadell"
    priority = 470

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        has_supplier = "banco de sabadell" in normalized or "a08000143" in normalized or "sabadell" in normalized
        has_invoice = re.search(r"factura\s+n(?:o|º|°)?", normalized) is not None
        return has_supplier and has_invoice

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        result.nombre_proveedor = "Banco de Sabadell, S.A."
        result.nif_proveedor = "A08000143"

        number_match = re.search(r"Factura\s+n\S?\s*([0-9][0-9\s]+)", text, re.IGNORECASE)
        if number_match:
            result.numero_factura = re.sub(r"\s+", "", number_match.group(1))

        date_match = re.search(r"Sabadell,\s*([^\n\r]+)", text, re.IGNORECASE)
        if date_match:
            result.fecha_factura = normalize_date(date_match.group(1))

        if re.search(r"SUMINISTROS\s+DE\s+OFICINA\s+BENIOFFI\s+S\.?L\.?", text, re.IGNORECASE):
            result.nombre_cliente = "SUMINISTROS DE OFICINA BENIOFFI S.L."
        if re.search(r"\bB53711495\b", text, re.IGNORECASE):
            result.nif_cliente = "B53711495"

        amount = self._extract_exempt_amount(text)
        result.subtotal = amount
        if re.search(r"\bexento\b", text, re.IGNORECASE):
            result.iva = 0.0
        result.total = amount

        return result.finalize()

    def _extract_exempt_amount(self, text: str) -> float | None:
        lines = self.extract_lines(text)
        for index, line in enumerate(lines):
            if not re.search(r"importe.*(?:iva|igic|ipsi)|exento", line, re.IGNORECASE):
                continue
            for next_line in lines[index + 1:index + 4]:
                values = [value for value in self.extract_amounts_from_fragment(next_line, ignore_percent=True) if value >= 0]
                if values:
                    return values[-1]
        return None
