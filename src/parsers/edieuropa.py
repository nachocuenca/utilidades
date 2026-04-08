from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.amounts import parse_amount


class EdieuropaInvoiceParser(BaseInvoiceParser):
    parser_name = "edieuropa"
    priority = 350
    SUPPLIER_TAX_ID = "B03310091"

    SUMMARY_PATTERNS = {
        'base': [
            r"base\s+imponible[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"subtotal[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
        'iva': [
            r"iva\s*\d*%?[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"cuota\s+iva[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
        'total': [
            r"total\s+factura[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"total[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ]
    }

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        if "edieuropa" not in normalized_text and "edi europa" not in normalized_text:
            return False
        score = 0

        if self.matches_file_path_hint(file_path, ("edieuropa", "edi europa")):
            score += 1

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 2

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        # Datos fijos del proveedor
        result.nombre_proveedor = "EDIEUROPA"
        result.nif_proveedor = self.SUPPLIER_TAX_ID

        # Número y fecha desde filename (patrón específico Edieuropa)
        result.numero_factura = self.extract_filename_invoice_number(
            file_path,
            [r"[Ff]ac-?(\d{4}-\d+)", r"[Ff]actura\s*([0-9A-Z\-]+)"],
        ) or self.extract_invoice_number(text)

        result.fecha_factura = self.extract_filename_date(file_path) or self.extract_date(text)

        # Extracción específica: priorizar BLOQUE FINAL coherente Base+IVA=Total
        lines = self.extract_lines(text)
        tail_lines = lines[-20:]  # Últimas 20 líneas para resumen
        tail_text = " ".join(tail_lines)

        base_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS['base'])
        iva_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS['iva'])
        total_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS['total'])

        # REGLA FUERTE: si Base + IVA = Total en bloque final, usarlos
        if base_match and iva_match and total_match:
            base_val = self._parse_amount_match(base_match)
            iva_val = self._parse_amount_match(iva_match)
            total_val = self._parse_amount_match(total_match)
            if base_val is not None and iva_val is not None and total_val is not None:
                if abs((base_val + iva_val) - total_val) <= 0.01:
                    result.subtotal = base_val
                    result.iva = iva_val
                    result.total = total_val
                    return result.finalize()

        # Fallback a métodos base si no hay bloque coherente
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        return result.finalize()

    def _extract_amount(self, text: str, patterns: list[str]) -> Optional[re.Match]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match
        return None

    def _parse_amount_match(self, match: re.Match) -> Optional[float]:
        if not match:
            return None
        return parse_amount(match.group(1))  # Usa parse_amount de utils.amounts

