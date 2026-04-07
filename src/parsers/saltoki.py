from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.amounts import parse_amount
from src.utils.names import clean_name_candidate


class SaltokiInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "saltoki"
    priority = 490

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if self.matches_file_path_hint(file_path, ("saltoki",)):
            return True

        return "saltoki" in normalized_text

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        lines = self.extract_lines(text)

        result.nombre_proveedor = self.extract_supplier_name_from_text(lines, file_path)
        result.nif_proveedor = self.extract_supplier_tax_id_from_text(text, file_path)
        result.nombre_cliente = self.extract_customer_name(lines)
        result.nif_cliente = self.extract_customer_tax_id_from_text(text)

        numero_factura, fecha_factura = self.extract_header_data(lines, file_path)
        result.numero_factura = numero_factura
        result.fecha_factura = fecha_factura

        subtotal, iva, total = self.extract_totals(text)
        result.subtotal = subtotal
        result.iva = iva
        result.total = total

        return result.finalize()

    def extract_supplier_name_from_text(self, lines: list[str], file_path: str | Path) -> str | None:
        folder_hint = self.get_folder_hint_name(file_path)

        for line in lines[:8]:
            upper_line = line.upper()
            if "SALTOKI" not in upper_line:
                continue

            if "ALICANTE" in upper_line:
                return "SALTOKI ALICANTE"
            if "BENIDORM" in upper_line:
                return "SALTOKI BENIDORM"

        if folder_hint:
            return folder_hint

        return "SALTOKI"

    def extract_supplier_tax_id_from_text(self, text: str, file_path: str | Path) -> str | None:
        match = re.search(r"CIF:\s*(B\d{8})", text, re.IGNORECASE)
        if match:
            return match.group(1)

        folder_hint = (self.get_folder_hint_name(file_path) or "").lower()
        if "alicante" in folder_hint:
            return "B71406623"
        if "benidorm" in folder_hint:
            return "B71406607"

        return None

    def extract_customer_name(self, lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            compact = line.replace(" ", "").upper()
            if compact == "FACTURA":
                for offset in range(1, 5):
                    next_index = index + offset
                    if next_index >= len(lines):
                        break

                    candidate = lines[next_index].strip()
                    if candidate == "":
                        continue
                    if candidate.upper().startswith("CL "):
                        continue
                    if "N.I.F" in candidate.upper():
                        continue

                    cleaned = clean_name_candidate(candidate)
                    if cleaned:
                        return cleaned

        for index, line in enumerate(lines):
            if "N.I.F" not in line.upper():
                continue

            for back in range(1, 5):
                prev_index = index - back
                if prev_index < 0:
                    break

                candidate = lines[prev_index].strip()
                if candidate == "":
                    continue
                if candidate.upper().startswith("CL "):
                    continue
                if candidate.upper().startswith("CLIENTE"):
                    continue

                cleaned = clean_name_candidate(candidate)
                if cleaned:
                    return cleaned

        return None

    def extract_customer_tax_id_from_text(self, text: str) -> str | None:
        match = re.search(r"N\.?I\.?F\.?\s*([A-Z0-9]+)", text, re.IGNORECASE)
        if match:
            return match.group(1)

        exact_candidates = self.extract_exact_tax_ids(text)
        for candidate in exact_candidates:
            if candidate not in {"B71406623", "B71406607"}:
                return candidate

        return None

    def extract_header_data(self, lines: list[str], file_path: str | Path) -> tuple[str | None, str | None]:
        from_filename_number = self.extract_filename_invoice_number(
            file_path,
            [
                r"^copia de (\d+)",
                r"^(\d+)",
            ],
        )
        from_filename_date = self.extract_filename_date(file_path)

        for line in lines:
            match = re.search(
                r"^\s*\d+\s+([0-9]{2}[-/][0-9]{2}[-/][0-9]{4})\s+(\d+)\s+\d+\s*$",
                line,
                re.IGNORECASE,
            )
            if match:
                fecha = match.group(1)
                numero = self.clean_invoice_number_candidate(match.group(2))
                return numero, fecha

        return from_filename_number, from_filename_date

    def extract_totals(self, text: str) -> tuple[float | None, float | None, float | None]:
        matches = re.findall(
            r"([0-9]+(?:[.,][0-9]+)?)\s+(?:\d{1,2}[.,]\d{2})\s+([0-9]+(?:[.,][0-9]+)?)\s+([0-9]+(?:[.,][0-9]+)?)\s*€",
            text,
            re.IGNORECASE,
        )

        if matches:
            base_value, iva_value, total_value = matches[-1]
            return (
                parse_amount(base_value),
                parse_amount(iva_value),
                parse_amount(total_value),
            )

        total_match = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*€", text)
        total_value = parse_amount(total_match.group(1)) if total_match else None

        return (None, None, total_value)