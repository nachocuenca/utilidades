from __future__ import annotations

from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.parsers.generic import GenericInvoiceParser


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
        )

        if any(clue in normalized_text for clue in clues):
            return True

        if file_path is not None:
            file_name = Path(file_path).name.lower()
            if "agus" in file_name:
                return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self._generic.parse(text, file_path)
        result.parser_usado = self.parser_name

        if result.nombre_proveedor is None:
            lines = self.extract_lines(text)
            for line in lines[:10]:
                lower_line = line.lower()
                if "agus" in lower_line or "agustin" in lower_line or "agustín" in lower_line:
                    result.nombre_proveedor = line
                    break

        return result.finalize()