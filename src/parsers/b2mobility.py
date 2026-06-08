from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser
from src.utils.invoice_patterns import extract_total_from_lines, normalize_date_ddmmyyyy


class B2MobilityInvoiceParser(BaseInvoiceParser):
    parser_name = "b2mobility"
    priority = 410

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        return "b2mobility gmbh" in normalized or "factura b2m" in normalized or "de316163295" in normalized

    def parse(self, text: str, file_path: str | Path) -> "ParsedInvoiceData":
        result = self.build_result(text, file_path)
        result.nombre_proveedor = "B2Mobility GmbH"
        result.nif_proveedor = "DE316163295"

        number_match = re.search(r"\bNUMERO\s+([0-9]{6,})\b", text, re.IGNORECASE)
        if number_match:
            result.numero_factura = number_match.group(1)

        date_match = re.search(r"\bFECHA\s*([0-9]{2}/[0-9]{2}/[0-9]{2,4})", text, re.IGNORECASE)
        iso_date = None
        if date_match:
            iso_date = normalize_date_ddmmyyyy(date_match.group(1))
            result.fecha_factura = iso_date

        result.subtotal, result.iva, result.total = self._extract_tax_summary(text)
        total = self._extract_total_factura(text)
        if total is not None:
            result.total = total

        if re.search(r"\bRC\b|inversi[oó]n\s+sujeto\s+pasivo", text, re.IGNORECASE):
            result.iva = 0.0

        finalized = result.finalize()
        if iso_date:
            finalized.fecha_factura = iso_date
        return finalized

    def _extract_total_factura(self, text: str) -> float | None:
        candidates: list[float] = []
        for line in self.extract_lines(text):
            if "TOTAL FACTURA" not in line.upper():
                continue
            values = self.extract_amounts_from_fragment(line, ignore_percent=True)
            if values:
                candidates.append(values[-1])
        if candidates:
            return candidates[-1]
        return extract_total_from_lines(text)

    def _extract_tax_summary(self, text: str) -> tuple[float | None, float | None, float | None]:
        for line in self.extract_lines(text):
            if re.search(r"\bRC\b", line, re.IGNORECASE):
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if len(values) >= 2:
                    return values[0], 0.0, values[-1]
        return None, None, None

    def _normalize_b2m_date(self, value: str) -> str:
        return normalize_date_ddmmyyyy(value)
