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

        # Proveedor fijo + NIF optimizado Repsol
        result.nombre_proveedor = "REPSOL"
        result.nif_proveedor = self.extract_repsol_supplier_tax_id(text)
        result.numero_factura = self.extract_repsol_invoice_number(text)
        result.fecha_factura = self.extract_filename_date(
            file_path,
            patterns=[
                r"([0-3]\\d[_\-][01]\\d[_\-]20\\d{2})",
            ],
        ) or self.extract_date(text)

        # Usar métodos genéricos con summary coherente Base+IVA=Total
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_repsol_iva(text)  # Repsol-specific
        result.total = self.extract_repsol_total(file_path, text)

        return result.finalize()

    def extract_repsol_supplier_tax_id(self, text: str) -> str | None:
        # Patterns Repsol: CIF:, B28..., B48... estaciones
        for pattern in [
            r"CIF[:\\s]+(B\\d{7}[A-Z])",
            r"C\\.I\\.F\\.[:\\s]+(B\\d{7}[A-Z])",
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        # Fallback genérico
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

    def extract_repsol_iva(self, text: str) -> float | None:
        # Repsol-specific: IVA 21%: 65,10 / CUOTA IVA 21%
        patterns = [
            r"IVA\\s*\\d+%?[:\\s]*(\\d+[.,]\\d{2})",
            r"CUOTA\\s+IVA[:\\s](\\d+[.,]\\d{2})",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return parse_amount(match.group(1))
        return self.extract_iva(text)  # Fallback genérico con summary

    def extract_repsol_total(self, file_path: str | Path, text: str) -> float | None:
        value = self.extract_total(text)  # Genérico con summary coherente
        if value is not None:
            return value
        # Filename fallback
        match = re.search(r"(\\d+(?:,\\d{2})?)\\s*€", Path(file_path).stem)
        return parse_amount(match.group(1)) if match else None
