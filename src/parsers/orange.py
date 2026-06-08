from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData


class OrangeInvoiceParser(BaseInvoiceParser):
    parser_name = "orange"
    priority = 450

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        return (
            "a82000612" in normalized
            or "orange espagne" in normalized
            or ("orange" in normalized and "numero de factura" in normalized and "fecha de factura" in normalized)
            or (("orapge" in normalized or "grange" in normalized) and "factura" in normalized)
        )

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        result.nombre_proveedor = "Orange Espagne, S.A.U."
        result.nif_proveedor = "A82000612"
        result.numero_factura = self._extract_number(text)
        result.fecha_factura = self._extract_date(text)
        result.subtotal = self.extract_labeled_amount(text, [r"Total\s+\(antes\s+de\s+impuestos\)"], ignore_percent=True)
        result.iva = self.extract_labeled_amount(text, [r"IVA\s*\(21%\)"], ignore_percent=True)
        result.total = self._extract_total(text)
        if result.subtotal is not None and result.iva is not None and result.total == result.subtotal:
            result.total = round(result.subtotal + result.iva, 2)
        return result.finalize()

    def _extract_number(self, text: str) -> str | None:
        lines = self.extract_lines(text)
        for index, line in enumerate(lines):
            if re.search(r"n\S*mero\s+de\s+factura", line, re.IGNORECASE):
                same_line = re.search(r"n\S*mero\s+de\s+factura\s*:?\s*([A-Z0-9][A-Z0-9\-]+)", line, re.IGNORECASE)
                if same_line and re.search(r"\d", same_line.group(1)):
                    return same_line.group(1)
                for next_line in lines[index + 1:index + 4]:
                    match = re.search(r"\b(\d{3}-[A-Z]{2}\d{2}-\d{4,})\b", next_line)
                    if match:
                        return match.group(1)
        match = re.search(r"\b(\d{3}-[A-Z]{2}\d{2}-\d{4,})\b", text)
        if match:
            return match.group(1)
        return None

    def _extract_date(self, text: str) -> str | None:
        match = re.search(r"Fecha\s+de\s+factura:?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})", text, re.IGNORECASE)
        if match:
            return self.extract_date(match.group(1))
        return self.extract_date(text)

    def _extract_total(self, text: str) -> float | None:
        value = self.extract_labeled_amount(text, [r"este\s+mes\s+tu\s+factura\s+es\s+de", r"total\s+factura"], ignore_percent=True)
        if value is not None:
            return value
        totals: list[float] = []
        for line in self.extract_lines(text):
            if re.fullmatch(r"Total\s+[0-9.,]+\s*€?", line, re.IGNORECASE):
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if values:
                    totals.append(values[-1])
        if totals:
            return max(totals)
        subtotal = self.extract_labeled_amount(text, [r"Total\s+\(antes\s+de\s+impuestos\)"], ignore_percent=True)
        iva = self.extract_labeled_amount(text, [r"IVA\s*\(21%\)"], ignore_percent=True)
        if subtotal is not None and iva is not None:
            return round(subtotal + iva, 2)
        return None
