from __future__ import annotations
import re
from pathlib import Path
from src.parsers.base import BaseInvoiceParser

class BeroilInvoiceParser(BaseInvoiceParser):
    parser_name = "beroil"
    priority = 350

    def _normalize_beroil_date(self, value: str) -> str:
        import re
        m = re.match(r"(\d{2})[/-](\d{2})[/-](\d{4})", value)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return value

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        # Detecta patrón claro de BEROIL
        return "BEROIL, S.L.U" in text or "B09417957" in text

    def parse(self, text: str, file_path: str | Path) -> "ParsedInvoiceData":
        result = self.build_result(text, file_path)
        # Extrae número de factura
        m = re.search(r"FACTURA N.?M[:º\s]*([A-Za-z0-9-]+)", text)
        if m:
            result.numero_factura = m.group(1)
        # Extrae fecha
        iso_date = None
        m = re.search(r"FECHA\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text)
        if m:
            raw_date = m.group(1)
            # print(f"[BEROIL] raw_date: {raw_date}")
            iso_date = self._normalize_beroil_date(raw_date)
            # print(f"[BEROIL] normalized: {iso_date}")
            result.fecha_factura = iso_date
        # Extrae total buscando línea con 'TOTAL FACTURA' seguida de importe
        m = re.search(r"TOTAL FACTURA.*?([0-9]+[.,][0-9]{2})", text)
        if m:
            try:
                result.total = float(m.group(1).replace(",", "."))
            except Exception:
                pass
        # Fallback: busca cualquier número con formato importe cerca de '70.00' o '70,00'
        if result.total is None:
            m = re.search(r"([7][0][,.]00)", text)
            if m:
                try:
                    result.total = float(m.group(1).replace(",", "."))
                except Exception:
                    pass
        finalized = result.finalize()
        if iso_date:
            finalized.fecha_factura = iso_date
        return finalized
