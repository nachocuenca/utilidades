from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData

TICKETISH_PATTERNS = (
    re.compile(r"factura\s+simplificada", re.IGNORECASE),
    re.compile(r"\bsala-mesa\b", re.IGNORECASE),
    re.compile(r"\bn[ºo]\s*op\.?\b", re.IGNORECASE),
    re.compile(r"\bn[ºo]\s*operaci[oó]n\b", re.IGNORECASE),
)


SUPPLIER_FOLDER_ALIASES: dict[str, str] = {
    "levantia": "Aislamientos Acústicos Levante, S.L.",
    "davofrio": "DAVOFRIO, S.L.U.",
    "leroy merlin": "LEROY MERLIN SLU",
    "repsol": "REPSOL",
    "obramat": "BRICOLAJE BRICOMAN, S.L.U.",
    "saltoki benidorm": "SALTOKI BENIDORM, S.L.",
    "saltoki alicante": "SALTOKI ALICANTE, S.L.",
    "mercaluz": "Componentes Eléctricos Mercaluz S.A",
}

NOISY_PROVIDER_CANDIDATES = {"oiloF", "OILOF", "ajoH", "AJOH"}


class GenericSupplierInvoiceParser(BaseInvoiceParser):
    parser_name = "generic_supplier"
    priority = 20

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        path_hint = self.get_folder_hint_name(file_path)
        normalized_text = text.lower()

        if self._looks_like_ticket(text):
            return False

        structural_markers = (
            "proveedor",
            "emisor",
            "razón social",
            "razon social",
            "datos del proveedor",
            "datos del emisor",
        )
        invoice_markers = (
            "base imponible",
            "cuota iva",
            "importe iva",
            "importe total",
            "total factura",
            "nº factura",
            "número de factura",
        )

        structural_hits = sum(1 for marker in structural_markers if marker in normalized_text)
        invoice_hits = sum(1 for marker in invoice_markers if marker in normalized_text)

        if structural_hits >= 1:
            return True

        if invoice_hits >= 2:
            return True

        if path_hint and path_hint.lower() not in {"inbox", "data", "tickets"}:
            if structural_hits >= 1 or invoice_hits >= 2:
                return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(lines, file_path)
        result.nif_proveedor = self.extract_supplier_tax_id(text)
        result.numero_factura = self.extract_invoice_number(text)
        result.fecha_factura = self.extract_date(text)
        result.subtotal = self.extract_subtotal(text)
        result.iva = self.extract_iva(text)
        result.total = self.extract_total(text)

        return result.finalize()

    def _alias_from_file_path(self, file_path: str | Path) -> str | None:
        path_text = self.get_path_text(file_path)
        if not path_text:
            return None

        for key, value in SUPPLIER_FOLDER_ALIASES.items():
            if key in path_text:
                return value

        return None

    def extract_supplier_name(self, lines: list[str], file_path: str | Path) -> str | None:
        provider = self.extract_name_near_labels(
            lines,
            [
                r"^proveedor\b",
                r"^emisor\b",
                r"^empresa\b",
                r"^raz[oó]n social\b",
                r"^datos del proveedor\b",
                r"^datos del emisor\b",
            ],
            max_distance=3,
        )

        if provider and provider not in NOISY_PROVIDER_CANDIDATES and not self.is_probable_noise_name(provider):
            return provider

        top_provider = self.extract_provider_from_top(lines, top_n=8)
        if top_provider:
            customer_name = self.extract_name_near_labels(
                lines,
                [
                    r"^cliente\b",
                    r"^clienta\b",
                    r"^destinatario\b",
                    r"^facturar a\b",
                    r"^bill to\b",
                    r"^comprador\b",
                    r"^titular\b",
                ],
                max_distance=1,
            )
            if customer_name and top_provider.lower() == customer_name.lower():
                top_provider = None

        if top_provider and top_provider not in NOISY_PROVIDER_CANDIDATES and not self.is_probable_noise_name(top_provider):
            return top_provider

        alias = self._alias_from_file_path(file_path)
        if alias:
            return alias

        folder_hint = self.get_folder_hint_name(file_path)
        if (
            folder_hint
            and folder_hint.lower() not in {"inbox", "data", "tickets"}
            and not self.is_probable_noise_name(folder_hint)
            and folder_hint not in NOISY_PROVIDER_CANDIDATES
        ):
            return folder_hint

        return None

    def _looks_like_ticket(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in TICKETISH_PATTERNS)
