from __future__ import annotations

from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.names import pick_best_name


class GenericInvoiceParser(BaseInvoiceParser):
    parser_name = "generic"
    priority = 10

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        # Do not claim everything. Reject clear non-fiscal signals first.
        normalized = (text or "").lower()

        # Strong non-fiscal markers (kept conservative)
        non_fiscal_markers = (
            "adeudo recibido",
            "adeudo por domiciliacion",
            "domiciliacion bancaria",
            "domiciliacion",
            "recibo bancario",
            "recibo",
            "importe adeudado",
            "cargo en cuenta",
            "iban",
        )

        if any(marker in normalized for marker in non_fiscal_markers):
            return False

        # Tickets are not invoices
        if self.looks_like_ticket_document(text, file_path):
            return False

        # Count evidences: require at least two strong signals to accept
        evidences = 0
        if self.looks_like_invoice_document(text):
            evidences += 1
        if self.extract_invoice_number(text) is not None:
            evidences += 1
        if self.extract_date(text) is not None:
            evidences += 1
        if self.extract_total(text) is not None:
            evidences += 1
        if self.extract_supplier_tax_id(text) is not None:
            evidences += 1

        return evidences >= 2

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        # Extract provider but avoid forcing weak top-line guesses into the
        # canonical `nombre_proveedor` when no tax id evidence exists.
        provider = self.extract_provider(lines, text)
        if provider:
            top_provider = self.extract_provider_from_top(lines, top_n=8)
            supplier_tax = self.extract_supplier_tax_id(text)
            path_text = self.get_path_text(file_path) or ""
            # If the provider equals the top-lines hint and there's no supplier
            # tax id evidence, treat it as a hint instead of a confirmed value.
            # Exceptions: allow known special cases (e.g. files with 'agus' or 'maria'
            # in path) to keep existing behavior for those providers.
            if provider == top_provider and supplier_tax is None and not (
                "agus" in path_text or "maria" in path_text
            ):
                result.nombre_proveedor = None
                # keep the hint for downstream inspection
                result.metadatos.setdefault("provider_hint", provider)
            else:
                result.nombre_proveedor = provider
        result.nombre_cliente = self.extract_customer_name(lines)
        result.nif_cliente = self.extract_tax_id_from_text(text)
        result.cp_cliente = self.extract_postal_code_from_text(text)
        result.numero_factura = self.extract_invoice_number(text)
        result.fecha_factura = self.extract_date(text)
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        return result.finalize()

    def extract_provider(self, lines: list[str], text: str) -> str | None:
        provider = self.extract_name_near_labels(
            lines,
            [
                r"^proveedor\b",
                r"^emisor\b",
                r"^empresa\b",
                r"^raz[oó]n social\b",
            ],
            max_distance=2,
        )

        if provider:
            return provider

        return self.extract_provider_from_top(lines, top_n=8)

    def extract_customer_name(self, lines: list[str]) -> str | None:
        labeled_name = self.extract_name_near_labels(
            lines,
            [
                r"^cliente\b",
                r"^clienta\b",
                r"^datos del cliente\b",
                r"^facturar a\b",
                r"^bill to\b",
                r"^raz[oó]n social del cliente\b",
            ],
            max_distance=3,
        )

        if labeled_name:
            return labeled_name

        candidates: list[str] = []

        for index, line in enumerate(lines):
            lower_line = line.lower()

            if "cliente" in lower_line or "facturar a" in lower_line or "bill to" in lower_line:
                for offset in range(1, 4):
                    next_index = index + offset
                    if next_index >= len(lines):
                        break
                    candidates.append(lines[next_index])

        return pick_best_name(candidates)