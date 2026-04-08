from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.parsers.generic import GenericInvoiceParser

CLINICA_PROVIDER_NAME = "Clinica Almendros"
CLINICA_PROVIDER_TAX_ID = "48331209K"

CUSTOMER_NAME_INLINE_PATTERN = re.compile(
    r"Titular:\s*(.+)",
    re.IGNORECASE,
)

CUSTOMER_TAX_ID_PATTERN = re.compile(
    r"C\.?I\.?F\.?\s*/\s*N\.?I\.?F\.?\s*Titular:\s*([A-Z0-9]+)",
    re.IGNORECASE,
)

INVOICE_NUMBER_PATTERN = re.compile(
    r"Factura\s*N[º°o]?:\s*([A-Z0-9/-]+)",
    re.IGNORECASE,
)

DATE_PATTERN = re.compile(
    r"Fecha:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
    re.IGNORECASE,
)

REVERSED_DNI_PATTERN = re.compile(r"^[A-Z]\d{8}$")
DNI_PATTERN = re.compile(r"^\d{8}[A-Z]$")


class AgusInvoiceParser(BaseInvoiceParser):
    parser_name = "agus"
    priority = 80

    def __init__(self) -> None:
        self._generic = GenericInvoiceParser()

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()

        if any(
            clue in normalized_text
            for clue in (
                "clinica almendros",
                "clínica almendros",
                "clinicaalmendros.com",
                "centro de fisioterapia",
                "agus",
                "agustin",
                "agustín",
            )
        ):
            return True

        if file_path is not None:
            file_name = Path(file_path).name.lower()
            if "agus" in file_name or "almendros" in file_name:
                return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        if self.is_clinica_almendros_layout(text, file_path):
            return self.parse_clinica_almendros(text, file_path)

        result = self._generic.parse(text, file_path)
        result.parser_usado = self.parser_name
        return result.finalize()

    def is_clinica_almendros_layout(self, text: str, file_path: str | Path) -> bool:
        normalized_text = text.lower()
        path_text = self.get_path_text(file_path)

        return (
            "clinica almendros" in normalized_text
            or "clínica almendros" in normalized_text
            or "clinicaalmendros.com" in normalized_text
            or "almendros" in path_text
        )

    def parse_clinica_almendros(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)
        result.parser_usado = self.parser_name

        result.nombre_proveedor = CLINICA_PROVIDER_NAME
        result.nif_proveedor = self.extract_clinica_provider_tax_id(text, lines)
        result.nombre_cliente = self.extract_clinica_customer_name(text, lines)
        result.nif_cliente = self.extract_clinica_customer_tax_id(text)
        result.numero_factura = self.extract_clinica_invoice_number(text)
        result.fecha_factura = self.extract_clinica_date(text)
        result.subtotal = self.extract_labeled_amount(text, [r"subtotal"])
        result.total = self.extract_labeled_amount(text, [r"total"])

        if result.subtotal is not None and result.total is not None:
            if round(float(result.subtotal) - float(result.total), 2) == 0:
                result.iva = 0.0

        return result.finalize()

    def extract_clinica_customer_name(self, text: str, lines: list[str]) -> str | None:
        match = CUSTOMER_NAME_INLINE_PATTERN.search(text)
        if match:
            candidate = match.group(1).strip()
            if self.is_valid_customer_name(candidate):
                return candidate

        for index, line in enumerate(lines):
            stripped = line.strip()

            if not stripped.lower().startswith("titular"):
                continue

            if ":" in stripped:
                candidate = stripped.split(":", 1)[1].strip()
                if self.is_valid_customer_name(candidate):
                    return candidate

            if index + 1 < len(lines):
                candidate = lines[index + 1].strip()
                if self.is_valid_customer_name(candidate):
                    return candidate

        return None

    def extract_clinica_customer_tax_id(self, text: str) -> str | None:
        match = CUSTOMER_TAX_ID_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def extract_clinica_provider_tax_id(self, text: str, lines: list[str]) -> str:
        customer_tax_id = self.extract_clinica_customer_tax_id(text)

        for line in lines:
            if "clinica almendros" not in line.lower() and "clínica almendros" not in line.lower():
                continue

            for candidate in self.extract_exact_tax_ids(line):
                normalized = self.normalize_clinica_provider_tax_id(candidate)
                if customer_tax_id and normalized == customer_tax_id:
                    continue
                return normalized

        for candidate in self.extract_exact_tax_ids(text):
            normalized = self.normalize_clinica_provider_tax_id(candidate)
            if customer_tax_id and normalized == customer_tax_id:
                continue
            if normalized == CLINICA_PROVIDER_TAX_ID:
                return normalized

        return CLINICA_PROVIDER_TAX_ID

    def normalize_clinica_provider_tax_id(self, value: str) -> str:
        candidate = str(value).strip().upper()

        if REVERSED_DNI_PATTERN.fullmatch(candidate):
            reversed_candidate = candidate[::-1]
            if DNI_PATTERN.fullmatch(reversed_candidate):
                return reversed_candidate

        return candidate

    def extract_clinica_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            return match.group(1)
        return self.extract_invoice_number(text)

    def extract_clinica_date(self, text: str) -> str | None:
        match = DATE_PATTERN.search(text)
        if match:
            return match.group(1)
        return self.extract_date(text)

    def is_valid_customer_name(self, value: str | None) -> bool:
        if value is None:
            return False

        candidate = value.strip()
        if candidate == "":
            return False

        lowered = candidate.lower()
        if any(
            token in lowered
            for token in (
                "direccion",
                "dirección",
                "provincia",
                "c.p.",
                "cp",
                "españa",
                "espana",
                "factura",
                "fecha",
            )
        ):
            return False

        if any(character.isdigit() for character in candidate):
            return False

        return True