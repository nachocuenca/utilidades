from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.ids import normalize_postal_code, normalize_tax_id
from src.utils.names import clean_name_candidate, is_valid_name_candidate, pick_best_name

MARIA_CLUES = (
    "maría gonzález arranz",
    "maria gonzalez arranz",
    "energyinmotion.es",
    "membresía desbloquéate",
    "membresia desbloqueate",
    "desbloquéate",
    "desbloqueate",
    "es84 1465 0100 9417 6430 4696",
    "iban es84 1465 0100 9417 6430 4696",
)


class MariaInvoiceParser(BaseInvoiceParser):
    parser_name = "maria"
    priority = 100

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized_text = text.lower()
        return any(clue in normalized_text for clue in MARIA_CLUES)

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = "María González Arranz"
        result.fecha_factura = self.extract_date(text)
        result.numero_factura = self.extract_invoice_number(text)

        client_block = self.extract_client_block(lines, result.fecha_factura)

        result.nombre_cliente = client_block.get("nombre_cliente")
        result.nif_cliente = client_block.get("nif_cliente") or self.extract_tax_id_from_text(text)
        result.cp_cliente = client_block.get("cp_cliente") or self.extract_postal_code_from_text(text)

        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        return result.finalize()

    def extract_client_block(self, lines: list[str], fecha_factura: str | None) -> dict[str, str | None]:
        result = {
            "nombre_cliente": None,
            "nif_cliente": None,
            "cp_cliente": None,
        }

        start_index = self.find_reference_index(lines, fecha_factura)
        if start_index is None:
            start_index = 0

        window = lines[start_index + 1 : start_index + 8]
        name_candidates: list[str] = []

        for line in window:
            cleaned = clean_name_candidate(line)

            if cleaned and is_valid_name_candidate(cleaned):
                name_candidates.append(cleaned)

            nif_match = re.search(r"(?:nif|cif|dni|nie)\s*[:\-]?\s*([A-Z0-9\-\s\.]+)", line, re.IGNORECASE)
            if nif_match and result["nif_cliente"] is None:
                result["nif_cliente"] = normalize_tax_id(nif_match.group(1))

            cp_match = re.search(r"(?:c\.?p\.?|cp|c[oó]digo\s+postal)\s*[:\-]?\s*(\d{5})", line, re.IGNORECASE)
            if cp_match and result["cp_cliente"] is None:
                result["cp_cliente"] = normalize_postal_code(cp_match.group(1))

        result["nombre_cliente"] = pick_best_name(name_candidates)
        return result

    def find_reference_index(self, lines: list[str], fecha_factura: str | None) -> int | None:
        if fecha_factura:
            for index, line in enumerate(lines):
                if fecha_factura in line:
                    return index

        date_markers = [
            re.compile(r"^fecha\b", re.IGNORECASE),
            re.compile(r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b"),
            re.compile(r"\b\d{1,2}\s+de\s+[a-záéíóúüñ]+\s+de\s+\d{2,4}\b", re.IGNORECASE),
        ]

        for index, line in enumerate(lines):
            if any(pattern.search(line) for pattern in date_markers):
                return index

        return None