from __future__ import annotations
import re
from pathlib import Path
from src.parsers.base import BaseInvoiceParser

class EnrutaLogisticInvoiceParser(BaseInvoiceParser):
    parser_name = "enruta_logistic"
    priority = 370

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        return "ENRUTA LOGISTIC LA MARINA" in text or "B56977283" in text

    def parse(self, text: str, file_path: str | Path) -> "ParsedInvoiceData":
        result = self.build_result(text, file_path)
        # Número de factura
        m = re.search(r"Factura No\s*[:]?\s*([A-Za-z0-9]+)", text)
        if m:
            result.numero_factura = m.group(1)
        # Fecha
        iso_date = None
        m = re.search(r"Fecha\s*[:]?\s*([0-9]{2}/[0-9]{2}/[0-9]{2,4})", text)
        if m:
            iso_date = self._normalize_enruta_date(m.group(1))
            result.fecha_factura = iso_date
        # Total
        m = re.search(r"Total factura\s*([0-9]+[.,][0-9]{2})", text, re.IGNORECASE)
        if m:
            result.total = float(m.group(1).replace(",", "."))
        else:
            # Fallback: busca importe con símbolo euro al final de línea
            m = re.search(r"([0-9]+[.,][0-9]{2})\s*€", text)
            if m:
                result.total = float(m.group(1).replace(",", "."))
        finalized = result.finalize()
        if iso_date:
            finalized.fecha_factura = iso_date
        return finalized

    def _normalize_enruta_date(self, value: str) -> str:
        m = re.match(r"(\d{2})/(\d{2})/(\d{2,4})", value)
        if m:
            year = m.group(3)
            if len(year) == 2:
                year = "20" + year
            return f"{year}-{m.group(2)}-{m.group(1)}"
        return value
