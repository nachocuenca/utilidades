from __future__ import annotations
import re
from pathlib import Path
from src.parsers.base import BaseInvoiceParser

class RpgCarvinInvoiceParser(BaseInvoiceParser):
    parser_name = "rpg_carvin"
    priority = 360

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        return "RPG CARVIN, S.L." in text or "B53984076" in text

    def parse(self, text: str, file_path: str | Path) -> "ParsedInvoiceData":
        result = self.build_result(text, file_path)
        # Número de factura
        m = re.search(r"No Factura\s*[:]?\s*([0-9]+)", text)
        if m:
            result.numero_factura = m.group(1)
        # Fecha
        iso_date = None
        m = re.search(r"Fecha\s*[:]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text)
        if m:
            iso_date = self._normalize_rpg_date(m.group(1))
            result.fecha_factura = iso_date
        # Total: busca importe tras fecha de vencimiento
        m = re.search(r"\d{2}/\d{2}/\d{4}\s+([0-9]+[.,][0-9]{2})", text)
        if m:
            result.total = float(m.group(1).replace(",", "."))
        else:
            m = re.search(r"Total Factura\s*([0-9]+[.,][0-9]{2})", text)
            if m:
                result.total = float(m.group(1).replace(",", "."))
        finalized = result.finalize()
        if iso_date:
            finalized.fecha_factura = iso_date
        return finalized

    def _normalize_rpg_date(self, value: str) -> str:
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", value)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return value
