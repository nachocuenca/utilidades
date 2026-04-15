from __future__ import annotations
import re
from pathlib import Path
from src.parsers.base import BaseInvoiceParser
from src.utils.invoice_patterns import extract_total_from_lines, normalize_date_ddmmyyyy


class DanielFernandezInvoiceParser(BaseInvoiceParser):
    parser_name = "daniel_fernandez"
    priority = 390

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        t = text.lower()
        return "daniel" in t and "fern" in t or "48335522" in t

    def parse(self, text: str, file_path: str | Path) -> "ParsedInvoiceData":
        result = self.build_result(text, file_path)

        # numero_factura: aparece como 'No FACTURA: 220224'
        m = re.search(r"No\s*FACTURA[:\s]*([0-9A-Za-z-]+)", text, re.IGNORECASE)
        if m:
            result.numero_factura = m.group(1).strip()

        # fecha_factura
        iso_date = None
        m = re.search(r"FECHA[:\s]*([0-9]{2}/[0-9]{2}/[0-9]{2,4})", text, re.IGNORECASE)
        if m:
            iso_date = normalize_date_ddmmyyyy(m.group(1))
            result.fecha_factura = iso_date

        # total: buscar líneas con 'TOTAL' y tomar el último importe de esas líneas
        total = extract_total_from_lines(text)
        if total is not None:
            result.total = total

        finalized = result.finalize()
        if iso_date:
            finalized.fecha_factura = iso_date
        return finalized
