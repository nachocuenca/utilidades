from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.names import clean_name_candidate, pick_best_name

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
SUPPLIER_STRUCTURAL_MARKERS = (
    "proveedor",
    "emisor",
    "razón social",
    "razon social",
    "datos del proveedor",
    "datos del emisor",
)
SUPPLIER_INVOICE_MARKERS = (
    "base imponible",
    "cuota iva",
    "importe iva",
    "importe total",
    "total factura",
    "nº factura",
    "número de factura",
)
SUPPLIER_NAME_LABELS = [
    r"^proveedor\b",
    r"^emisor\b",
    r"^empresa\b",
    r"^raz[oó]n social\b",
    r"^datos del proveedor\b",
    r"^datos del emisor\b",
]
CUSTOMER_NAME_LABELS = [
    r"^cliente\b",
    r"^clienta\b",
    r"^destinatario\b",
    r"^facturar a\b",
    r"^bill to\b",
    r"^comprador\b",
    r"^titular\b",
    r"^adquiriente\b",
]
CUSTOMER_CONTEXT_PATTERN = re.compile(
    r"\b(cliente|clienta|destinatario|facturar a|bill to|comprador|titular|adquiriente|consumidor final)\b",
    re.IGNORECASE,
)
SUPPLIER_CONTEXT_PATTERN = re.compile(
    r"\b(proveedor|emisor|empresa|raz[oó]n social|datos del proveedor|datos del emisor)\b",
    re.IGNORECASE,
)
SUPPLIER_TAX_CONTEXT_PATTERN = re.compile(
    r"\b(?:cif|nif)\s*(?:proveedor|emisor|empresa|raz[oó]n\s+social)?\b"
    r"|\b(?:proveedor|emisor|raz[oó]n\s+social|datos del proveedor|datos del emisor)\b",
    re.IGNORECASE,
)
SUPPLIER_NAME_BLOCK_PATTERNS = (
    re.compile(r"\b(cliente|clienta|destinatario|facturar a|bill to|comprador|titular|adquiriente)\b", re.IGNORECASE),
    re.compile(r"\b(base imponible|cuota iva|importe iva|importe total|total factura|subtotal|fecha|albar[aá]n|pedido)\b", re.IGNORECASE),
    re.compile(r"\b(c/|avda\.?|avenida|calle|pol[ií]gono|cp\b|c\.?p\.?)", re.IGNORECASE),
    re.compile(r"\b(www\.|https?://|@|iban|tel[eé]fono|telefono|email|e-mail)\b", re.IGNORECASE),
)


class GenericSupplierInvoiceParser(BaseInvoiceParser):
    parser_name = "generic_supplier"
    priority = 20

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        if self.looks_like_ticket_document(text, file_path):
            return False
        # Require invoice-like document as baseline
        if not self.looks_like_invoice_document(text):
            return False

        normalized_text = text.lower()
        structural_hits = sum(1 for marker in SUPPLIER_STRUCTURAL_MARKERS if marker in normalized_text)
        invoice_hits = sum(1 for marker in SUPPLIER_INVOICE_MARKERS if marker in normalized_text)
        has_supplier_tax_id = self.extract_supplier_tax_id(text) is not None
        has_invoice_number = self.extract_invoice_number(text) is not None
        has_date = self.extract_date(text) is not None
        has_reliable_amounts = self.has_reliable_amount_evidence(text)
        alias = self._alias_from_file_path(file_path) is not None

        noisy_present = any(candidate.lower() in normalized_text for candidate in NOISY_PROVIDER_CANDIDATES)

        # Strong evidences
        strong = 0
        if has_supplier_tax_id:
            strong += 1
        if has_reliable_amounts:
            strong += 1
        if has_invoice_number and has_date:
            strong += 1

        # Supplementary evidences
        supplemental = 0
        if structural_hits >= 1:
            supplemental += 1
        if invoice_hits >= 2:
            supplemental += 1
        if alias:
            supplemental += 1

        total_evidences = strong + supplemental

        # If a known noisy provider token appears and we don't have either a
        # supplier tax id or reliable amount evidence, reject to avoid false
        # positives coming from CSV/import anomalies or OCR garbage.
        if noisy_present and not (has_reliable_amounts or has_supplier_tax_id):
            return False

        # Relaxed: accept when total evidences >= 1, but avoid alias-only decisions
        if total_evidences >= 1:
            # Prevent folder alias being the sole deciding factor
            if alias and strong == 0 and supplemental == 1:
                return False
            return True

        return False

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(text, lines, file_path)
        result.nif_proveedor = self.extract_supplier_tax_id(text)
        result.numero_factura = self.extract_invoice_number(text)
        result.fecha_factura = self.extract_date(text)

        if self.has_reliable_amount_evidence(text):
            result.subtotal = self.extract_subtotal(text)
            result.iva = self.extract_iva(text)
            result.total = self.extract_total(text)
        else:
            result.total = self.extract_labeled_amount(
                text,
                [
                    r"neto\s+a\s*pagar",
                    r"importe\s+total",
                    r"total\s+factura",
                ],
            )

        return result.finalize()

    def _alias_from_file_path(self, file_path: str | Path) -> str | None:
        path_text = self.get_path_text(file_path)
        if not path_text:
            return None

        for key, value in SUPPLIER_FOLDER_ALIASES.items():
            if key in path_text:
                return value

        return None

    def has_reliable_amount_evidence(self, text: str) -> bool:
        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            return True

        labeled_hits = 0
        if self.extract_labeled_amount(
            text,
            [
                r"subtotal",
                r"base\s+imponible",
                r"importe\s+sin\s+iva",
                r"total\s+antes\s+de\s+impuestos",
                r"total\s+ai",
                r"total\s+si",
            ],
            ignore_percent=True,
        ) is not None:
            labeled_hits += 1

        if self.extract_labeled_amount(
            text,
            [
                r"cuota\s+iva",
                r"importe\s+iva",
                r"\biva\b",
                r"impuesto",
                r"importe\s+impuesto",
            ],
            ignore_percent=True,
        ) is not None:
            labeled_hits += 1

        if self.extract_labeled_amount(
            text,
            [
                r"neto\s+a\s*pagar",
                r"importe\s+total",
                r"total\s+factura",
                r"total\s+ii",
                r"total\s+tti",
            ],
        ) is not None:
            labeled_hits += 1

        return labeled_hits >= 2

    def _extract_customer_name(self, lines: list[str]) -> str | None:
        return self.extract_name_near_labels(
            lines,
            CUSTOMER_NAME_LABELS,
            max_distance=2,
        )

    def _find_first_customer_index(self, lines: list[str]) -> int | None:
        for index, line in enumerate(lines):
            if CUSTOMER_CONTEXT_PATTERN.search(line):
                return index
        return None

    def _is_safe_supplier_candidate(self, candidate: str | None, customer_name: str | None = None) -> bool:
        cleaned = clean_name_candidate(candidate)
        if not cleaned:
            return False

        if cleaned.lower() in {
            "proveedor",
            "emisor",
            "empresa",
            "razon social",
            "razón social",
            "datos del proveedor",
            "datos del emisor",
        }:
            return False

        if cleaned in NOISY_PROVIDER_CANDIDATES or self.is_probable_noise_name(cleaned):
            return False

        if self.extract_exact_tax_ids(cleaned):
            return False

        if customer_name and cleaned.lower() == customer_name.lower():
            return False

        # Reject probable OCR noise or too short candidates
        compact_alnum = re.sub(r"[^A-Za-z0-9]", "", cleaned)
        if len(compact_alnum) <= 4:
            return False

        return not any(pattern.search(cleaned) for pattern in SUPPLIER_NAME_BLOCK_PATTERNS)

    def _extract_top_supplier_candidate(self, lines: list[str], customer_name: str | None) -> str | None:
        customer_index = self._find_first_customer_index(lines)
        search_limit = customer_index if customer_index is not None else 10
        search_limit = max(0, min(search_limit, 10))

        candidates_with_tax: list[str] = []
        candidates: list[str] = []

        for index, line in enumerate(lines[:search_limit]):
            cleaned = clean_name_candidate(line)
            if not self._is_safe_supplier_candidate(cleaned, customer_name):
                continue

            nearby_has_tax = any(
                self.extract_exact_tax_ids(lines[neighbour])
                for neighbour in range(max(0, index - 1), min(len(lines), index + 2))
            )
            if nearby_has_tax:
                candidates_with_tax.append(cleaned)
            else:
                candidates.append(cleaned)

        return pick_best_name(candidates_with_tax or candidates)

    def _extract_customer_tax_ids(self, lines: list[str]) -> set[str]:
        customer_tax_ids: set[str] = set()

        for index, line in enumerate(lines):
            if not CUSTOMER_CONTEXT_PATTERN.search(line):
                continue

            for offset in range(0, 3):
                next_index = index + offset
                if next_index >= len(lines):
                    break
                customer_tax_ids.update(self.extract_exact_tax_ids(lines[next_index]))

        return customer_tax_ids

    def _has_supplier_labeled_block(self, lines: list[str]) -> bool:
        return any(SUPPLIER_CONTEXT_PATTERN.search(line) for line in lines[:12])

    def extract_supplier_tax_id(self, text: str) -> str | None:
        lines = self.extract_lines(text)
        customer_tax_ids = self._extract_customer_tax_ids(lines)
        customer_name = self._extract_customer_name(lines)

        for index, line in enumerate(lines[:20]):
            if not SUPPLIER_TAX_CONTEXT_PATTERN.search(line):
                continue

            for offset in range(0, 3):
                next_index = index + offset
                if next_index >= len(lines):
                    break

                candidates = [
                    candidate
                    for candidate in self.extract_exact_tax_ids(lines[next_index])
                    if candidate not in customer_tax_ids
                ]
                if candidates:
                    return candidates[0]

        customer_index = self._find_first_customer_index(lines)
        search_limit = customer_index if customer_index is not None else 8
        search_limit = max(0, min(search_limit, 8))

        for index, line in enumerate(lines[:search_limit]):
            candidates = [
                candidate
                for candidate in self.extract_exact_tax_ids(line)
                if candidate not in customer_tax_ids
            ]
            if not candidates:
                continue

            has_nearby_supplier_name = any(
                self._is_safe_supplier_candidate(lines[neighbour], customer_name)
                for neighbour in range(max(0, index - 1), min(len(lines), index + 2))
            )
            if has_nearby_supplier_name:
                return candidates[0]

        return None

    def extract_supplier_name(self, text: str, lines: list[str], file_path: str | Path) -> str | None:
        customer_name = self._extract_customer_name(lines)

        provider = self.extract_name_near_labels(
            lines,
            SUPPLIER_NAME_LABELS,
            max_distance=2,
        )
        if self._is_safe_supplier_candidate(provider, customer_name):
            return provider

        top_provider = self._extract_top_supplier_candidate(lines, customer_name)
        if self._is_safe_supplier_candidate(top_provider, customer_name):
            return top_provider

        alias = self._alias_from_file_path(file_path)
        if alias and self.has_reliable_amount_evidence(text) and (
            self.extract_supplier_tax_id(text) is not None or self._has_supplier_labeled_block(lines)
        ):
            return alias

        return None
