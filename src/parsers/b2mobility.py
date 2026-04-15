from __future__ import annotations
import re
from pathlib import Path
from src.parsers.base import BaseInvoiceParser
from src.utils.invoice_patterns import extract_total_from_lines, normalize_date_ddmmyyyy

class B2MobilityInvoiceParser(BaseInvoiceParser):
    parser_name = "b2mobility"
    priority = 380

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        # Prioritize explicit tax id and full supplier name
        if self._can_handle_by_supplier(text, supplier_name="B2Mobility GmbH", supplier_tax_id="N2765289J", file_path=file_path):
            return True

        # Fallback legacy checks
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
            iso_date = normalize_date_ddmmyyyy(m.group(1))
            result.fecha_factura = iso_date
        # Total: usar utilitario común para buscar en líneas con TOTAL
        total = extract_total_from_lines(text)
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
        # kept for compatibility; delegate to shared normalizer
        return normalize_date_ddmmyyyy(value)
