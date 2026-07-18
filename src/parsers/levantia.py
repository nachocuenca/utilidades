from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.parsers.base import ParsedInvoiceData
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.utils.dates import normalize_date

SUMMARY_TAX_PATTERN = re.compile(r"\bi\.?v\.?a\.?\b", re.IGNORECASE)


class LevantiaInvoiceParser(GenericSupplierInvoiceParser):
    parser_name = "levantia"
    priority = 330

    SUPPLIER_NAME = "Aislamientos Acústicos Levante, S.L."
    SUPPLIER_TAX_ID = "B03901477"

    CONTENT_MARKERS = (
        "aislamientos acusticos levante",
        "info@levantia.es",
        "www.levantia.es",
        "isidoro de sevilla",
        "direccion cliente",
        "direccion envio factura",
        "ref.proveedor",
        "base imponible",
    )
    CUSTOMER_BLOCK_MARKERS = (
        "direccion cliente",
        "direccion envio factura",
        "cliente:",
        "destinatario",
        "titular",
        "facturar a",
    )
    SUMMARY_STOP_MARKERS = (
        "forma de pago",
        "vencimiento",
    )

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False

        normalized_text = self._normalize_for_match(text)
        score = 0

        if self.matches_file_path_hint(file_path, ("levantia",)):
            score += 1

        if "aislamientos acusticos levante" in normalized_text:
            score += 3
        elif "levantia" in normalized_text:
            score += 2

        if "info@levantia.es" in normalized_text or "www.levantia.es" in normalized_text:
            score += 2

        if "isidoro de sevilla" in normalized_text and "03009 alicante" in normalized_text:
            score += 2

        if "direccion cliente" in normalized_text and "direccion envio factura" in normalized_text:
            score += 1

        if "ref.proveedor" in normalized_text and "base imponible" in normalized_text and "total" in normalized_text:
            score += 1

        if self.SUPPLIER_TAX_ID.lower() in normalized_text:
            score += 3

        return score >= 4 and self.looks_like_invoice_document(text)

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_levantia_supplier_name(lines)
        result.nif_proveedor = self.extract_levantia_supplier_tax_id(text, lines)
        result.numero_factura = self.extract_levantia_invoice_number(lines, file_path)
        result.fecha_factura = self.extract_levantia_invoice_date(lines, text)

        subtotal, iva, total = self.extract_levantia_amounts(lines, text)
        result.subtotal = subtotal
        result.iva = iva
        result.total = total

        return result.finalize()

    def extract_levantia_supplier_name(self, lines: list[str]) -> str:
        for line in lines[:20]:
            if "aislamientos acusticos levante" in self._normalize_for_match(line):
                return self.SUPPLIER_NAME

        return self.SUPPLIER_NAME

    def extract_levantia_supplier_tax_id(self, text: str, lines: list[str]) -> str:
        customer_tax_ids = self.extract_levantia_customer_tax_ids(lines)
        supplier_block = self.extract_levantia_supplier_block(lines)

        for line in supplier_block:
            candidates = [
                candidate
                for candidate in self.extract_exact_tax_ids(line)
                if candidate not in customer_tax_ids
            ]
            if candidates:
                return candidates[0]

        explicit_candidates = [
            candidate
            for candidate in self.extract_exact_tax_ids(text)
            if candidate not in customer_tax_ids and candidate == self.SUPPLIER_TAX_ID
        ]
        if explicit_candidates:
            return explicit_candidates[0]

        return self.SUPPLIER_TAX_ID

    def extract_levantia_customer_tax_ids(self, lines: list[str]) -> set[str]:
        customer_tax_ids: set[str] = set()
        block_bounds = self.find_levantia_customer_block(lines)

        if block_bounds is not None:
            start_index, end_index = block_bounds
            for line in lines[start_index:end_index]:
                customer_tax_ids.update(self.extract_exact_tax_ids(line))

        for index, line in enumerate(lines):
            normalized_line = self._normalize_for_match(line)
            if not any(marker in normalized_line for marker in self.CUSTOMER_BLOCK_MARKERS):
                continue

            for nearby_line in lines[index: min(len(lines), index + 6)]:
                customer_tax_ids.update(self.extract_exact_tax_ids(nearby_line))

        return customer_tax_ids

    def extract_levantia_supplier_block(self, lines: list[str]) -> list[str]:
        for index, line in enumerate(lines[:20]):
            normalized_line = self._normalize_for_match(line)
            if any(marker in normalized_line for marker in self.CONTENT_MARKERS[:4]):
                start_index = max(0, index - 2)
                end_index = min(len(lines), index + 6)
                return lines[start_index:end_index]

        customer_block = self.find_levantia_customer_block(lines)
        if customer_block is not None:
            start_index, _end_index = customer_block
            return lines[:start_index]

        return lines[:12]

    def extract_levantia_invoice_number(self, lines: list[str], file_path: str | Path) -> str | None:
        header_row = self.find_levantia_header_data_row(lines)
        if header_row is not None:
            match = re.search(
                r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s+([A-Z0-9./-]{6,})\b",
                header_row,
                re.IGNORECASE,
            )
            if match:
                candidate = self.clean_invoice_number_candidate(match.group(2))
                if candidate and candidate != self.SUPPLIER_TAX_ID:
                    return candidate

        filename_candidate = self.extract_filename_invoice_number(
            file_path,
            [
                r"^\d{4}(\d{9})$",
                r"^(\d{9,13})$",
            ],
        )
        if filename_candidate:
            return filename_candidate

        return self.extract_invoice_number("\n".join(lines))

    def extract_levantia_invoice_date(self, lines: list[str], text: str) -> str | None:
        header_row = self.find_levantia_header_data_row(lines)
        if header_row is not None:
            match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", header_row)
            if match:
                candidate = normalize_date(match.group(1))
                if candidate:
                    return candidate

        return self.extract_date(text)

    def extract_levantia_amounts(
        self,
        lines: list[str],
        text: str,
    ) -> tuple[float | None, float | None, float | None]:
        strong_triplet = self.extract_levantia_strong_summary_triplet(lines)
        if strong_triplet is not None:
            return strong_triplet

        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            return summary_base, summary_iva, summary_total

        return self.extract_subtotal(text), self.extract_iva(text), self.extract_total(text)

    def extract_levantia_strong_summary_triplet(
        self,
        lines: list[str],
    ) -> tuple[float, float, float] | None:
        for index in range(len(lines) - 1, -1, -1):
            if not self.is_levantia_summary_header(lines[index]):
                continue

            for offset in range(1, 5):
                next_index = index + offset
                if next_index >= len(lines):
                    break

                candidate_line = lines[next_index]
                normalized_candidate = self._normalize_for_match(candidate_line)

                if normalized_candidate == "":
                    continue

                if any(marker in normalized_candidate for marker in self.SUMMARY_STOP_MARKERS):
                    break

                values = self.extract_amounts_from_fragment(candidate_line, ignore_percent=True)
                coherent_triplet = self.pick_last_coherent_triplet(values)
                if coherent_triplet is not None:
                    return coherent_triplet

        return None

    def pick_last_coherent_triplet(
        self,
        values: list[float],
    ) -> tuple[float, float, float] | None:
        if len(values) < 3:
            return None

        for start_index in range(len(values) - 3, -1, -1):
            base_value, iva_value, total_value = values[start_index:start_index + 3]
            if abs((base_value + iva_value) - total_value) <= 0.02:
                return base_value, iva_value, total_value

        return None

    def find_levantia_customer_block(self, lines: list[str]) -> tuple[int, int] | None:
        start_index: int | None = None

        for index, line in enumerate(lines):
            normalized_line = self._normalize_for_match(line)
            if "direccion cliente" in normalized_line:
                start_index = index
                break

        if start_index is None:
            for index, line in enumerate(lines):
                normalized_line = self._normalize_for_match(line)
                if any(marker in normalized_line for marker in self.CUSTOMER_BLOCK_MARKERS):
                    start_index = index
                    break

        if start_index is None:
            return None

        end_index = min(len(lines), start_index + 8)
        for index in range(start_index + 1, len(lines)):
            normalized_line = self._normalize_for_match(lines[index])
            if (
                "codigo cantidad descripcion" in normalized_line
                or "caf: referencia" in normalized_line
                or self.is_levantia_summary_header(lines[index])
            ):
                end_index = index
                break

        if end_index <= start_index:
            end_index = min(len(lines), start_index + 8)

        return start_index, end_index

    def find_levantia_header_data_row(self, lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            normalized_line = self._normalize_for_match(line)
            if "fecha factura" not in normalized_line:
                continue
            if "c.i.f" not in normalized_line:
                continue
            if "ref.proveedor" not in normalized_line:
                continue

            for offset in range(1, 3):
                next_index = index + offset
                if next_index >= len(lines):
                    break

                candidate_line = lines[next_index]
                if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", candidate_line):
                    return candidate_line

        return None

    def is_levantia_summary_header(self, line: str) -> bool:
        normalized_line = self._normalize_for_match(line)
        if "base imponible" not in normalized_line:
            return False
        if "total" not in normalized_line:
            return False
        return SUMMARY_TAX_PATTERN.search(normalized_line) is not None

    def _normalize_for_match(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
        return re.sub(r"\s+", " ", without_accents).strip().lower()
