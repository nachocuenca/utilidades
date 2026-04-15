from __future__ import annotations

from pathlib import Path
from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData

class SparkInvoiceParser(BaseInvoiceParser):
    parser_name = "spark"
    priority = 20

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        # Detecta por nombre proveedor o patrón claro de Spark
        return "SPARK" in text.upper() or "SPARK ENERGIA" in text.upper()

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        # Ejemplo de extracción mínima, ajustar según layout real
        result.nombre_proveedor = "SPARK ENERGIA SL"
        result.nombre_cliente = self.extract_customer_name(lines)
        result.nif_cliente = self.extract_tax_id_from_text(text)
        result.cp_cliente = self.extract_postal_code_from_text(text)
        result.numero_factura = self.extract_invoice_number(text)
        result.fecha_factura = self.extract_date(text)
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        return result.finalize()

    def extract_customer_name(self, lines: list[str]) -> str | None:
        candidates: list[str] = []
        for index, line in enumerate(lines):
            lower_line = line.lower()
            if "cliente" in lower_line or "facturar a" in lower_line or "bill to" in lower_line:
                for offset in range(1, 4):
                    next_index = index + offset
                    if next_index >= len(lines):
                        break
                    candidates.append(lines[next_index])
        from src.utils.names import pick_best_name
        return pick_best_name(candidates)
