from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData


class LcmAguaInvoiceParser(BaseInvoiceParser):
    parser_name = "lcm_agua"
    priority = 400

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        return "lcm agua" in normalized or "b05499983" in normalized

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        result.nombre_proveedor = "LCM Agua, S.L."
        result.nif_proveedor = "B05499983"
        result.numero_factura = self._extract_number(text)
        result.fecha_factura = self._extract_date(text)
        result.subtotal = self._extract_summary_value(text, "base")
        result.iva = self._extract_summary_value(text, "iva")
        result.total = self._extract_total(text)
        return result.finalize()

    def _extract_number(self, text: str) -> str | None:
        match = re.search(r"FACTURA\s+No:.*?\n\s*([0-9]{4,})", text, re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else None

    def _extract_date(self, text: str) -> str | None:
        match = re.search(r"FACTURA\s+No:.*?FECHA:.*?\n\s*[0-9]{4,}\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})", text, re.IGNORECASE | re.DOTALL)
        if match:
            return self.extract_date(match.group(1))
        match = re.search(r"FECHA:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})", text, re.IGNORECASE)
        return self.extract_date(match.group(1)) if match else self.extract_date(text)

    def _extract_summary_value(self, text: str, field: str) -> float | None:
        lines = self.extract_lines(text)
        for index, line in enumerate(lines):
            lowered = line.lower()
            if field == "base" and "base" in lowered and "i.v.a" in lowered:
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if not values and index + 1 < len(lines):
                    values = self.extract_amounts_from_fragment(lines[index + 1], ignore_percent=True)
                if values:
                    return values[0]
            if field == "iva" and re.search(r"\b10,0\b", line):
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if len(values) >= 3:
                    return values[2]
            if field == "iva" and "i.v.a" in lowered and index + 1 < len(lines):
                values = self.extract_amounts_from_fragment(lines[index + 1], ignore_percent=True)
                if len(values) >= 4:
                    return values[3]
        return None

    def _extract_total(self, text: str) -> float | None:
        for line in self.extract_lines(text):
            if "€" in line or "eur" in line.lower():
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if values:
                    return values[-1]
        return None
