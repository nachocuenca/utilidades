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

        if "factura simplificada" in normalized_text and any(
            marker in normalized_text
            for marker in ("n° op", "nº op", "no op", "efectivo", "cambio")
        ):
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
        
        raw_date = self.extract_filename_date(file_path, patterns=[r"(\\d{1,2})[/-](\\d{1,2})[/-](\\d{4})"]) or self.extract_date(text)
        # Siempre ISO yyyy-mm-dd para tests
        if raw_date and '-' in raw_date:
            try:
                # dd-mm-yyyy -> yyyy-mm-dd
                d, m, y = raw_date.split('-')
                iso_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                result.fecha_factura = iso_date
            except:
                result.fecha_factura = raw_date
        else:
            result.fecha_factura = raw_date

        result.subtotal = self.extract_repsol_subtotal(text)
        result.iva = self.extract_repsol_iva(text)
        result.total = self.extract_repsol_total(file_path, text)

        return result.finalize()

    def extract_repsol_supplier_tax_id(self, text: str) -> str | None:
        # Patterns Repsol ultra-robustos para CIF: B28920839 con cualquier separador
        patterns = [
            r"CIF[:\\s&#10;]*([B]\\d{8}[A-Z])",
            r"C\\.I\\.F\\.[:\\s&#10;]*([B]\\d{8}[A-Z])",
            r"([B]\\d{8}[A-Z])\\s*(?i:Dirección|Direcci[oó]n)",
            r"([B]\\d{8}[A-Z])\\b(?![^\\n]*CLIENTE)",  # B28920839 no seguido cliente
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return self.extract_supplier_tax_id(text)

    def extract_repsol_invoice_number(self, text: str) -> str | None:
        # Patrón específico Repsol
        match = re.search(r"\\b\\d{6}/\\d/\\d{2}/\\d{6}\\b", text)
        if match:
            return self.clean_invoice_number_candidate(match.group(0))
        # Fallback + TK...
        match = re.search(r"(?:Nº|No)\\s+FACTURA[:\\s]*(\\w+)", text, re.IGNORECASE)
        if match:
            return self.clean_invoice_number_candidate(match.group(1))
        return self.extract_invoice_number(text)

    def extract_repsol_subtotal(self, text: str) -> float | None:
        # Específico Repsol: Base Imponible con espacios/€ tolerant
        patterns = [
            r"Base\\s+Imponible\\s*[:\\s€]*(\\d{1,3}(?:[.,]\\d{2})?)",
            r"BASE\\s+IMPONIBLE\\s*[:\\s€]*(\\d{1,3}(?:[.,]\\d{2})?)",
            r"(?i)base\\s+imponible.*?(\\d{1,3}(?:,\\d{2})?€?)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if match:
                amt = match.group(1).replace('€', '').strip()
                val = parse_amount(amt)
                if val is not None:
                    return val
        return self.extract_subtotal(text)

    def extract_repsol_iva(self, text: str) -> float | None:
        patterns = [
            r"IVA\\s*21%?[:\\s]*(\\d+[.,]\\d{2})",
            r"CUOTA\\s+IVA[:\\s]*(\\d+[.,]\\d{2})",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return parse_amount(match.group(1))
        return self.extract_iva(text)

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self.extract_total(text)  # Genérico con summary coherente
        if value is not None:
            return value
        # Filename fallback
        match = re.search(r"(\\d+(?:,\\d{2})?)\\s*€", Path(file_path).stem)
        return parse_amount(match.group(1)) if match else None
