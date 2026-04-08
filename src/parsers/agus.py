from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.parsers.generic import GenericInvoiceParser

PROVIDER_NAME_PATTERN = re.compile(
    r"\bclinica\s+almendros\b",
    re.IGNORECASE,
)

CUSTOMER_NAME_INLINE_PATTERN = re.compile(
    r"^\s*titular\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

CUSTOMER_TAX_ID_PATTERN = re.compile(
    r"c\.?\s*i\.?\s*f\.?\s*/\s*n\.?\s*i\.?\s*f\.?\s*titular\s*:\s*([A-Z0-9]+)",
    re.IGNORECASE,
)

INVOICE_NUMBER_PATTERN = re.compile(
    r"factura\s*n[º°o]?\s*:\s*([A-Z0-9/-]+)",
    re.IGNORECASE,
)

DATE_PATTERN = re.compile(
    r"fecha\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
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

        clues = (
            "agus",
            "agus factura",
            "agust",
            "agustin",
            "agustín",
            "clinica almendros",
            "clínica almendros",
            "clinicaalmendros.com",
            "centro de fisioterapia",
        )

        if any(clue in normalized_text for clue in clues):
            return True

        if file_path is not None:
            file_name = Path(file_path).name.lower()
            if "agus" in file_name or "almendros" in file_name:
                return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self._generic.parse(text, file_path)
        result.parser_usado = self.parser_name

        provider_name = self.extract_agus_provider_name(lines)
        if provider_name:
            result.nombre_proveedor = provider_name

        customer_tax_id = self.extract_agus_customer_tax_id(text)
        if customer_tax_id:
            result.nif_cliente = customer_tax_id

        customer_name = self.extract_agus_customer_name(text, lines)
        if customer_name:
            result.nombre_cliente = customer_name

        provider_tax_id = self.extract_agus_provider_tax_id(
            text=text,
            lines=lines,
            customer_tax_id=result.nif_cliente,
            current_provider_tax_id=result.nif_proveedor,
        )
        if provider_tax_id:
            result.nif_proveedor = provider_tax_id

        invoice_number = self.extract_agus_invoice_number(text)
        if invoice_number:
            result.numero_factura = invoice_number

        invoice_date = self.extract_agus_date(text)
        if invoice_date:
            result.fecha_factura = invoice_date

        subtotal = self.extract_agus_subtotal(text)
        if subtotal is not None:
            result.subtotal = subtotal

        total = self.extract_agus_total(text)
        if total is not None:
            result.total = total

        if result.iva is None and result.subtotal is not None and result.total is not None:
            if round(float(result.subtotal) - float(result.total), 2) == 0:
                result.iva = 0.0

        return result.finalize()

    def extract_agus_provider_name(self, lines: list[str]) -> str | None:
        for line in lines[:10]:
            if PROVIDER_NAME_PATTERN.search(line):
                return "Clinica Almendros"

        for line in lines[:10]:
            lower_line = line.lower()
            if "agus" in lower_line or "agustin" in lower_line or "agustín" in lower_line:
                return line

        return None

    def extract_agus_customer_name(self, text: str, lines: list[str]) -> str | None:
        inline_match = CUSTOMER_NAME_INLINE_PATTERN.search(text)
        if inline_match:
            candidate = inline_match.group(1).strip()
            if self._is_valid_customer_name(candidate):
                return candidate

        for index, line in enumerate(lines):
            normalized = line.strip().lower()
            if not normalized.startswith("titular"):
                continue

            if ":" in line:
                right_side = line.split(":", 1)[1].strip()
                if self._is_valid_customer_name(right_side):
                    return right_side

            for offset in range(1, 3):
                next_index = index + offset
                if next_index >= len(lines):
                    break

                candidate = lines[next_index].strip()
                if self._is_valid_customer_name(candidate):
                    return candidate

        for line in lines:
            lower_line = line.lower()
            if "visita del paciente" in lower_line:
                candidate = re.sub(
                    r"^.*visita del paciente\s+",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if self._is_valid_customer_name(candidate):
                    return candidate

        return None

    def extract_agus_customer_tax_id(self, text: str) -> str | None:
        match = CUSTOMER_TAX_ID_PATTERN.search(text)
        if match:
            return match.group(1)

        return None

    def extract_agus_provider_tax_id(
        self,
        text: str,
        lines: list[str],
        customer_tax_id: str | None,
        current_provider_tax_id: str | None,
    ) -> str | None:
        excluded = customer_tax_id

        for line in lines[:15]:
            lower_line = line.lower()

            if "titular" in lower_line:
                continue

            if "clinica almendros" not in lower_line and "clínica almendros" not in lower_line:
                continue

            candidates = self.extract_exact_tax_ids(line)
            for candidate in candidates:
                normalized = self.normalize_agus_provider_tax_id(candidate)
                if excluded and normalized == excluded:
                    continue
                return normalized

        if current_provider_tax_id:
            normalized_current = self.normalize_agus_provider_tax_id(current_provider_tax_id)
            if not excluded or normalized_current != excluded:
                return normalized_current

        all_candidates = self.extract_exact_tax_ids(text)
        for candidate in all_candidates:
            normalized = self.normalize_agus_provider_tax_id(candidate)
            if excluded and normalized == excluded:
                continue
            return normalized

        return None

    def normalize_agus_provider_tax_id(self, value: str) -> str:
        candidate = str(value).strip().upper()

        if REVERSED_DNI_PATTERN.fullmatch(candidate):
            reversed_candidate = candidate[::-1]
            if DNI_PATTERN.fullmatch(reversed_candidate):
                return reversed_candidate

        return candidate

    def extract_agus_invoice_number(self, text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match:
            return match.group(1)

        return self.extract_invoice_number(text)

    def extract_agus_date(self, text: str) -> str | None:
        match = DATE_PATTERN.search(text)
        if match:
            return match.group(1)

        return self.extract_date(text)

    def extract_agus_subtotal(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"subtotal",
            ],
        )

    def extract_agus_total(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"total",
            ],
        )

    def _is_valid_customer_name(self, value: str | None) -> bool:
        if value is None:
            return False

        candidate = value.strip()
        if candidate == "":
            return False

        lowered = candidate.lower()
        invalid_tokens = (
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
        if any(token in lowered for token in invalid_tokens):
            return False

        if any(char.isdigit() for char in candidate):
            return False

        return True