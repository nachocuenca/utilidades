from __future__ import annotations
import re
from pathlib import Path
from src.parsers.base import BaseInvoiceParser

class B2MobilityInvoiceParser(BaseInvoiceParser):
    parser_name = "b2mobility"
    priority = 380

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        return "B2Mobility GmbH" in text or "N2765289J" in text

    def parse(self, text: str, file_path: str | Path) -> "ParsedInvoiceData":
        result = self.build_result(text, file_path)
        # Número de factura
        m = re.search(r"NUMERO\s*([0-9A-Za-z]+)", text)
        if m:
            result.numero_factura = m.group(1)
        # Fecha
        iso_date = None
        m = re.search(r"FECHA\s*([0-9]{2}/[0-9]{2}/[0-9]{2,4})", text)
        if m:
            iso_date = self._normalize_b2m_date(m.group(1))
            result.fecha_factura = iso_date
        # Total: busca la línea TOTAL FACTURA y toma el último importe de esa línea
        total = None
        for line in text.splitlines():
            if "TOTAL FACTURA" in line:
                nums = re.findall(r"([0-9]+[.,][0-9]{2})", line)
                if nums:
                    total = float(nums[-1].replace(",", "."))
        if total is not None:
            result.total = total
        else:
            # Fallback: busca importe mayor al final de la última línea con euros
            matches = re.findall(r"([0-9]+[.,][0-9]{2})", text)
            if matches:
                result.total = float(matches[-1].replace(",", "."))
        finalized = result.finalize()
        if iso_date:
            finalized.fecha_factura = iso_date
        return finalized

    def _normalize_b2m_date(self, value: str) -> str:
        m = re.match(r"(\d{2})/(\d{2})/(\d{2,4})", value)
        if m:
            year = m.group(3)
            if len(year) == 2:
                year = "20" + year
            return f"{year}-{m.group(2)}-{m.group(1)}"
        return value
