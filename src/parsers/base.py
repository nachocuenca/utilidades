from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from src.pdf.text_cleaner import split_clean_lines
from src.utils.amounts import calculate_missing_amounts, parse_amount
from src.utils.dates import extract_date_candidates, normalize_date
from src.utils.ids import extract_postal_codes, extract_tax_ids, normalize_postal_code, normalize_tax_id
from src.utils.names import clean_name_candidate, is_valid_name_candidate, pick_best_name

AMOUNT_CAPTURE_PATTERN = r"([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?)"


@dataclass(slots=True)
class ParsedInvoiceData:
    parser_usado: str
    archivo: str
    ruta_archivo: str
    nombre_proveedor: str | None = None
    nif_proveedor: str | None = None
    nombre_cliente: str | None = None
    nif_cliente: str | None = None
    cp_cliente: str | None = None
    numero_factura: str | None = None
    fecha_factura: str | None = None
    subtotal: float | None = None
    iva: float | None = None
    total: float | None = None
    texto_crudo: str = ""
    metadatos: dict[str, str] = field(default_factory=dict)

    def finalize(self) -> "ParsedInvoiceData":
        self.nombre_proveedor = clean_name_candidate(self.nombre_proveedor)
        self.nif_proveedor = normalize_tax_id(self.nif_proveedor)
        self.nombre_cliente = clean_name_candidate(self.nombre_cliente)
        self.nif_cliente = normalize_tax_id(self.nif_cliente)
        self.cp_cliente = normalize_postal_code(self.cp_cliente)
        self.fecha_factura = normalize_date(self.fecha_factura)

        self.subtotal, self.iva, self.total = calculate_missing_amounts(
            self.subtotal,
            self.iva,
            self.total,
        )

        if self.nombre_cliente and not is_valid_name_candidate(self.nombre_cliente):
            self.nombre_cliente = None

        if self.nombre_proveedor and not is_valid_name_candidate(self.nombre_proveedor):
            self.nombre_proveedor = None

        return self


class BaseInvoiceParser(ABC):
    parser_name = "base"
    priority = 0

    @abstractmethod
    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        raise NotImplementedError

    def build_result(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        path = Path(file_path).resolve()
        return ParsedInvoiceData(
            parser_usado=self.parser_name,
            archivo=path.name,
            ruta_archivo=str(path),
            texto_crudo=text,
        )

    def extract_lines(self, text: str) -> list[str]:
        return split_clean_lines(text)

    def get_path_text(self, file_path: str | Path | None) -> str:
        if file_path is None:
            return ""
        return str(Path(file_path)).replace("\\", "/").lower()

    def matches_file_path_hint(self, file_path: str | Path | None, hints: tuple[str, ...] | list[str]) -> bool:
        path_text = self.get_path_text(file_path)
        if path_text == "":
            return False
        return any(hint.lower() in path_text for hint in hints)

    def get_folder_hint_name(self, file_path: str | Path | None) -> str | None:
        if file_path is None:
            return None

        path = Path(file_path)
        parent_name = path.parent.name.strip()
        if parent_name == "":
            return None

        parent_name = parent_name.replace("_", " ").replace("-", " ")
        parent_name = re.sub(r"\s+", " ", parent_name).strip()
        return clean_name_candidate(parent_name)

    def extract_date(self, text: str) -> str | None:
        label_patterns = [
            r"fecha\s+factura",
            r"fecha\s+de\s+factura",
            r"fecha\s+emisi[oó]n",
            r"fecha",
        ]

        for label_pattern in label_patterns:
            pattern = re.compile(
                rf"{label_pattern}\s*[:\-]?\s*([^\n]+)",
                re.IGNORECASE,
            )
            match = pattern.search(text)
            if not match:
                continue

            candidate = normalize_date(match.group(1))
            if candidate:
                return candidate

        candidates = extract_date_candidates(text)
        return candidates[0] if candidates else None

    def extract_invoice_number(self, text: str) -> str | None:
        patterns = [
            r"(?:n[úu]mero\s+de\s+factura|num\.?\s+factura|n[ºo]\s*factura|factura)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
            r"(?:invoice\s+number|invoice\s+no)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
        ]

        for pattern_text in patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if not match:
                continue

            candidate = match.group(1).strip(" .,:;")
            if candidate:
                return candidate

        return None

    def extract_labeled_amount(self, text: str, label_patterns: list[str]) -> float | None:
        for label_pattern in label_patterns:
            pattern = re.compile(
                rf"{label_pattern}\s*[:\-]?\s*{AMOUNT_CAPTURE_PATTERN}",
                re.IGNORECASE,
            )
            match = pattern.search(text)
            if not match:
                continue

            value = parse_amount(match.group(1))
            if value is not None:
                return value

        return None

    def extract_subtotal(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"subtotal",
                r"base\s+imponible",
                r"importe\s+sin\s+iva",
                r"total\s+antes\s+de\s+impuestos",
            ],
        )

    def extract_iva(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"\biva\b",
                r"cuota\s+iva",
                r"impuestos?",
            ],
        )

    def extract_total(self, text: str) -> float | None:
        return self.extract_labeled_amount(
            text,
            [
                r"total",
                r"importe\s+total",
                r"total\s+factura",
            ],
        )

    def extract_tax_id_from_text(self, text: str) -> str | None:
        label_patterns = [
            r"(?:nif|cif|dni|nie)\s*(?:cliente)?\s*[:\-]?\s*([^\n\r]+)",
            r"(?:vat|tax\s+id)\s*[:\-]?\s*([^\n\r]+)",
        ]

        for pattern_text in label_patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if not match:
                continue

            candidate = normalize_tax_id(match.group(1))
            if candidate:
                return candidate

        candidates = extract_tax_ids(text)
        return candidates[0] if candidates else None

    def extract_supplier_tax_id(self, text: str) -> str | None:
        label_patterns = [
            r"(?:cif|nif)\s*(?:proveedor|emisor|empresa|raz[oó]n\s+social)?\s*[:\-]?\s*([^\n\r]+)",
            r"(?:proveedor|emisor|empresa|raz[oó]n\s+social)\s*[:\-]?\s*[^\n\r]{0,80}?(?:cif|nif)\s*[:\-]?\s*([A-Z0-9\-\s\.]+)",
        ]

        for pattern_text in label_patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if not match:
                continue

            candidate = normalize_tax_id(match.group(1))
            if candidate:
                return candidate

        candidates = extract_tax_ids(text)
        return candidates[0] if candidates else None

    def extract_postal_code_from_text(self, text: str) -> str | None:
        label_patterns = [
            r"(?:c\.?p\.?|cp|c[oó]digo\s+postal)\s*[:\-]?\s*(\d{5})",
        ]

        for pattern_text in label_patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if not match:
                continue

            candidate = normalize_postal_code(match.group(1))
            if candidate:
                return candidate

        candidates = extract_postal_codes(text)
        return candidates[0] if candidates else None

    def extract_name_near_labels(
        self,
        lines: list[str],
        labels: list[str],
        max_distance: int = 3,
    ) -> str | None:
        compiled_labels = [re.compile(label, re.IGNORECASE) for label in labels]
        candidates: list[str] = []

        for index, line in enumerate(lines):
            if not any(pattern.search(line) for pattern in compiled_labels):
                continue

            line_after_label = re.sub(
                r"^.*?:\s*",
                "",
                line,
            ).strip()

            if line_after_label and is_valid_name_candidate(line_after_label):
                candidates.append(line_after_label)

            for offset in range(1, max_distance + 1):
                next_index = index + offset
                if next_index >= len(lines):
                    break

                next_line = clean_name_candidate(lines[next_index])
                if next_line and is_valid_name_candidate(next_line):
                    candidates.append(next_line)

        return pick_best_name(candidates)

    def extract_provider_from_top(self, lines: list[str], top_n: int = 8) -> str | None:
        candidates: list[str] = []

        for line in lines[:top_n]:
            cleaned = clean_name_candidate(line)
            if cleaned and is_valid_name_candidate(cleaned):
                candidates.append(cleaned)

        return pick_best_name(candidates)