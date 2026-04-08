from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount


class RepsolInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "repsol"
    priority = 360

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        # Rechazo fuerte para simplificadas
        if "factura simplificada" in normalized_text:
            return False

        score = 0

        if self.matches_file_path_hint(file_path, ("repsol",)):
            score += 1

        if "repsol" in normalized_text:
            score += 2

        if any(marker in normalized_text for marker in ("waylet", "repsol comercial", "estación de servicio", "estacion de servicio")):
            score += 1

        return score >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)

        result.nombre_proveedor = "REPSOL"
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(text)
        result.numero_factura = self.extract_repsol_invoice_number(text)
        
        result.fecha_factura = self.extract_date(text)

        result.subtotal = self.extract_repsol_subtotal(text)
        result.iva = self.extract_repsol_iva(text)
        result.total = self.extract_repsol_total(file_path, text)

        return result.finalize()

    def extract_repsol_supplier_tax_id(self, text: str) -> str | None:
        patterns = [
            r"CIF\s*:\s*([B]\d{8}[A-Z])",
            r"C\.I\.F\.\s*([B]\d{8}[A-Z])",
            r"([B]\d{8}[A-Z])\s*(?i:Dirección|Direcci[oó]n)",
            r"\b([B]\d{8}[A-Z])\b(?![^ \n]*cliente)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).upper()
        return self.extract_supplier_tax_id(text)

    def extract_repsol_invoice_number(self, text: str) -> str | None:
        match = re.search(r"\b(\d{6}/\d/\d{2,4}/\d{6})\b", text)
        if match:
            return self.clean_invoice_number_candidate(match.group(1))
        match = re.search(r"(?:Nº|No|NÂº)\s+FACTURA[:\s]*(\w+)", text, re.IGNORECASE)
        if match:
            return self.clean_invoice_number_candidate(match.group(1))
        return self.extract_invoice_number(text)

    def extract_repsol_subtotal(self, text: str) -> float | None:
        patterns = [
            r"BASE\s+IMPONIBLE\s+21%\s+(\d+\.?\d{2})",
            r"Base\s+Imponible\s+(\d+,\d{2}€?)",
            r"Base\s+Imponible\s*[:\s€]*(\d{1,3}(?:[.,]\d{2})?)",
            r"BASE\s+IMPONIBLE\s*[:\s€]*(\d{1,3}(?:[.,]\d{2})?)",
            r"(?i:base\s+imponible).*?(\d{1,3}(?:[.,]\d{2})?€?)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if match:
                amt = match.group(1).replace('€', '').strip()
                val = parse_amount(amt)
                if val:
                    return val
        return self.extract_subtotal(text)

    def extract_repsol_iva(self, text: str) -> float | None:
        patterns = [
            r"CUOTA\s+IVA\s*21%\s*(\d+[.,]\d{2})",
            r"IVA\s*21%[:\s]*(\d+[.,]\d{2})",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if match:
                return parse_amount(match.group(1))
        return self.extract_iva(text)

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self.extract_total(text)
        if value:
            return value
        match = re.search(r"(\d+(?:,\d{2})?)\s*€", Path(file_path).stem)
        return parse_amount(match.group(1)) if match else None

