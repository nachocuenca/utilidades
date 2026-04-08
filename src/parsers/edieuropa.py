from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.amounts import parse_amount
from src.utils.dates import normalize_date


DATE_PATTERN = re.compile(r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b")


class EdieuropaInvoiceParser(BaseInvoiceParser):
    parser_name = "edieuropa"
    priority = 350
    SUPPLIER_TAX_ID = "B03310091"

    SUMMARY_PATTERNS = {
        "base": [
            r"base\s+imponible[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"subtotal(?:\s+art[íi]culos)?[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
        "iva": [
            r"iva\s*\d*%?[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"cuota\s+iva[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
        "total": [
            r"total\s+factura[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
            r"total[:\s]*([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2})?)",
        ],
    }

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if "sin edieuropa" in normalized_text:
            return False

        path_hint = self.matches_file_path_hint(file_path, ("edieuropa", "edi europa"))
        has_brand = "edieuropa" in normalized_text or "edi europa" in normalized_text
        has_tax_id = self.SUPPLIER_TAX_ID.lower() in normalized_text
        has_company_context = any(
            marker in normalized_text
            for marker in ("electrodom", "máquinas", "maquinas", "electrodomésticos")
        )

        return has_tax_id or (has_brand and (path_hint or has_company_context))

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = "EDIEUROPA"
        result.nif_proveedor = self.SUPPLIER_TAX_ID

        text_invoice_number = self.extract_invoice_number(text)
        filename_invoice_number = self.extract_filename_invoice_number(
            file_path,
            [
                r"([Ff][Aa][Cc]-?\d{4}-\d+)",
                r"([Ff]actura[-_ ]*[0-9A-Z\-]+)",
                r"(1-A\d{2}-\d+)",
            ],
        )
        result.numero_factura = self._normalize_invoice_number(
            text_invoice_number or filename_invoice_number
        )

        result.fecha_factura = self._extract_project_date(text) or self._extract_project_date(
            str(Path(file_path).stem)
        )

        lines = self.extract_lines(text)
        tail_text = " ".join(lines[-20:])

        base_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS["base"])
        iva_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS["iva"])
        total_match = self._extract_amount(tail_text, self.SUMMARY_PATTERNS["total"])

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

        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        return result.finalize()

    def _extract_amount(self, text: str, patterns: list[str]) -> re.Match[str] | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match
        return None

    def _parse_amount_match(self, match: re.Match[str] | None) -> float | None:
        if not match:
            return None
        return parse_amount(match.group(1))

    def _extract_project_date(self, value: str | None) -> str | None:
        if not value:
            return None

        match = DATE_PATTERN.search(value)
        if not match:
            return None

        return normalize_date(match.group(0))

    def _normalize_invoice_number(self, value: str | None) -> str | None:
        if not value:
            return None

        cleaned = value.strip()
        cleaned = re.sub(r"^[Ff][Aa][Cc]-?", "", cleaned).strip()
        cleaned = re.sub(r"^[Ff]actura\s+", "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned