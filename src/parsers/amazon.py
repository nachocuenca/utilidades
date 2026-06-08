from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData


class AmazonInvoiceParser(BaseInvoiceParser):
    parser_name = "amazon"
    priority = 460

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        return (
            "amazon es" in normalized
            or ("vendido por" in normalized and "numero de la factura" in normalized)
            or "el iva ha sido declarado por amazon" in normalized
        )

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        result.nombre_proveedor = self._extract_seller(text) or "Amazon"
        result.nif_proveedor = self._extract_vat_id(text)
        result.numero_factura = self._extract_after_label(text, r"N\S*mero\s+de\s+la\s+factura")
        result.fecha_factura = self._extract_invoice_date(text)
        result.subtotal = self.extract_labeled_amount(text, [r"Total\s+\(IVA\s+excluido\)"], ignore_percent=True)
        result.iva = self._extract_tax_total(text)
        result.total = self.extract_labeled_amount(text, [r"Total\s+pendiente", r"Total\s+pagado"], ignore_percent=True)
        if result.total is None:
            result.total = self._extract_last_total(text)
        return result.finalize()

    def _extract_seller(self, text: str) -> str | None:
        lines = self.extract_lines(text)
        for index, line in enumerate(lines):
            match = re.search(r"Vendido\s+por\s+(.+)", line, re.IGNORECASE)
            if not match:
                continue
            parts = [match.group(1).strip()]
            for next_line in lines[index + 1:index + 3]:
                if re.search(r"fecha|n[uú]mero|total|direcci[oó]n|iva|pedido", next_line, re.IGNORECASE):
                    break
                parts.append(next_line.strip())
            seller = re.sub(r"\s+", " ", " ".join(parts)).strip()
            return seller[:120] if seller else None
        return None

    def _extract_vat_id(self, text: str) -> str | None:
        patterns = (
            r"\b(?:ES\s*)?IVA\s+([A-Z]{2}\s*[A-Z0-9]{8,14})",
            r"N[uú]mero\s+de\s+Registro\s+de\s+IVA:\s*([A-Z]{2}\s*[A-Z0-9]{8,14})",
            r"\bIVA\s+(ES[A-Z0-9]{8,14}|DE[A-Z0-9]{8,14}|FR[A-Z0-9]{8,14}|LU[A-Z0-9]{8,14})",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return re.sub(r"\s+", "", match.group(1)).upper()
        return None

    def _extract_after_label(self, text: str, label: str) -> str | None:
        match = re.search(rf"{label}\s+([A-Z0-9][A-Z0-9\-/.]+)", text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_invoice_date(self, text: str) -> str | None:
        match = re.search(r"Fecha\s+de\s+la\s+factura(?:/Fecha\s+de\s+la\s+entrega)?\s+([^\n\r]+)", text, re.IGNORECASE)
        if match:
            return self.extract_date(match.group(1))
        return self.extract_date(text)

    def _extract_tax_total(self, text: str) -> float | None:
        for line in self.extract_lines(text):
            if re.search(r"^Total\s+", line, re.IGNORECASE) and "IVA" in line.upper():
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if values:
                    return values[-1]
        return None

    def _extract_last_total(self, text: str) -> float | None:
        totals: list[float] = []
        for line in self.extract_lines(text):
            if re.search(r"^\s*Total\b", line, re.IGNORECASE):
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if values:
                    totals.append(values[-1])
        return totals[-1] if totals else None
