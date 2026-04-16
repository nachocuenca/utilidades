from __future__ import annotations
import re
from pathlib import Path
from src.utils.invoice_patterns import extract_total_from_lines, normalize_date_ddmmyyyy
from src.parsers.base import BaseInvoiceParser

class EnrutaLogisticInvoiceParser(BaseInvoiceParser):
    parser_name = "enruta_logistic"
    priority = 370

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        # Prioritize explicit tax id and full supplier name
        if self._can_handle_by_supplier(text, supplier_name="ENRUTA LOGISTIC LA MARINA", supplier_tax_id="B56977283", file_path=file_path):
            return True

        # Fallback legacy checks
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
            iso_date = normalize_date_ddmmyyyy(m.group(1))
            result.fecha_factura = iso_date
        # Total
        # require amount on same line as 'Total factura' to avoid cross-line captures
        m = re.search(r"Total factura[^\n]*?([0-9]+[.,][0-9]{2})", text, re.IGNORECASE)
        if m:
            result.total = float(m.group(1).replace(",", "."))
        else:
            # Fallback: intenta extraer de líneas TOTAL usando util
            total = extract_total_from_lines(text)
            if total is not None:
                result.total = total
            else:
                # Fallback previo: busca importe con símbolo euro al final de línea
                m = re.search(r"([0-9]+[.,][0-9]{2})\s*€", text)
                if m:
                    result.total = float(m.group(1).replace(",", "."))
                else:
                    # Último recurso: tomar el último importe encontrado en el texto
                    matches = re.findall(r"([0-9]+[.,][0-9]{2})", text)
                    if matches:
                        result.total = float(matches[-1].replace(',', '.'))
        finalized = result.finalize()
        if iso_date:
            finalized.fecha_factura = iso_date
        return finalized

    def _normalize_enruta_date(self, value: str) -> str:
        return normalize_date_ddmmyyyy(value)
