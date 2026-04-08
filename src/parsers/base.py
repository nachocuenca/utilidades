from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from src.pdf.text_cleaner import split_clean_lines
from src.utils.amounts import calculate_missing_amounts, parse_amount
from src.utils.dates import extract_date_candidates, normalize_date
from src.utils.ids import extract_postal_codes, normalize_postal_code, normalize_tax_id
from src.utils.names import clean_name_candidate, is_valid_name_candidate, pick_best_name

AMOUNT_CAPTURE_PATTERN = r"([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?)"
AMOUNT_CAPTURE_REGEX = re.compile(AMOUNT_CAPTURE_PATTERN)
EXACT_TAX_ID_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:ES)?([A-Z]\d{8}|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])(?![A-Z0-9])",
    re.IGNORECASE,
)
INVALID_INVOICE_NUMBER_VALUES = {
    "",
    "de",
    "del",
    "no",
    "n",
    "fecha",
    "contiene",
    "cliente",
    "factura",
    "numero",
    "número",
    "hoja",
    "direcci",
    "direccion",
    "descripci",
    "descripcion",
    "concepto",
    "referencia",
    "documento",
}
CUSTOMER_LINE_PATTERN = re.compile(
    r"\b(cliente|clienta|destinatario|facturar a|bill to|comprador|titular)\b",
    re.IGNORECASE,
)
SUMMARY_BASE_LABELS = (
    "subtotal",
    "base imponible",
    "importe sin iva",
    "total antes de impuestos",
    "base",
)
SUMMARY_IVA_LABELS = (
    "cuota iva",
    "importe iva",
    "iva",
    "impuesto",
)
SUMMARY_TOTAL_LABELS = (
    "importe total",
    "total factura",
    "total",
)


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
        self.numero_factura = BaseInvoiceParser.clean_invoice_number_candidate(self.numero_factura)

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

    @staticmethod
    def clean_invoice_number_candidate(value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip(" .,:;#/-")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if cleaned == "":
            return None

        lowered = cleaned.lower()
        if lowered in INVALID_INVOICE_NUMBER_VALUES:
            return None

        if len(cleaned) <= 2 and lowered not in {"f1", "f2"}:
            return None

        if lowered.startswith("fecha"):
            return None

        if re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", cleaned) and not any(character.isdigit() for character in cleaned):
            return None

        return cleaned

    def extract_exact_tax_ids(self, text: str) -> list[str]:
        raw_candidates = EXACT_TAX_ID_PATTERN.findall(text.upper())
        normalized: list[str] = []
        seen: set[str] = set()

        for item in raw_candidates:
            candidate = normalize_tax_id(item)
            if not candidate:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)

        return normalized

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

            candidate = self.clean_invoice_number_candidate(match.group(1))
            if candidate:
                return candidate

        return None

    def extract_filename_invoice_number(
        self,
        file_path: str | Path,
        patterns: list[str],
    ) -> str | None:
        stem = Path(file_path).stem

        for pattern_text in patterns:
            match = re.search(pattern_text, stem, re.IGNORECASE)
            if not match:
                continue

            candidate = self.clean_invoice_number_candidate(match.group(1))
            if candidate:
                return candidate

        return None

    def extract_filename_date(
        self,
        file_path: str | Path,
        patterns: list[str] | None = None,
    ) -> str | None:
        stem = Path(file_path).stem

        search_patterns = patterns or [
            r"(20\d{2}[01]\d[0-3]\d)",
            r"([0-3]\d[_\-][01]\d[_\-]20\d{2})",
            r"(20\d{2}[_\-][01]\d[_\-][0-3]\d)",
        ]

        for pattern_text in search_patterns:
            match = re.search(pattern_text, stem)
            if not match:
                continue

            raw_value = match.group(1).replace("_", "-")
            if re.fullmatch(r"20\d{2}[01]\d[0-3]\d", raw_value):
                raw_value = f"{raw_value[6:8]}-{raw_value[4:6]}-{raw_value[0:4]}"

            candidate = normalize_date(raw_value)
            if candidate:
                return candidate

        return None

    def extract_amounts_from_fragment(
        self,
        fragment: str,
        *,
        ignore_percent: bool = False,
    ) -> list[float]:
        amounts: list[float] = []

        for match in AMOUNT_CAPTURE_REGEX.finditer(fragment):
            start, end = match.span(1)
            surrounding = fragment[max(0, start - 2): min(len(fragment), end + 2)]
            if ignore_percent and "%" in surrounding:
                continue

            value = parse_amount(match.group(1))
            if value is None:
                continue
            amounts.append(value)

        return amounts

    def extract_labeled_amount(self, text: str, label_patterns: list[str], *, ignore_percent: bool = False) -> float | None:
        for label_pattern in label_patterns:
            pattern = re.compile(
                rf"{label_pattern}\s*[:\-]?\s*([^\n\r]*)",
                re.IGNORECASE,
            )

            for match in pattern.finditer(text):
                fragment = match.group(1)
                values = self.extract_amounts_from_fragment(fragment, ignore_percent=ignore_percent)
                if not values:
                    continue
                return values[-1]

        return None

    def extract_summary_amounts(self, text: str) -> tuple[float | None, float | None, float | None]:
        lines = self.extract_lines(text)
        if not lines:
            return None, None, None

        tail_lines = lines[-18:]
        base_candidates: list[float] = []
        iva_candidates: list[float] = []
        total_candidates: list[float] = []

        for line in tail_lines:
            lowered = line.lower()

            if any(label in lowered for label in SUMMARY_BASE_LABELS):
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if values:
                    base_candidates.append(values[-1])

            if any(label in lowered for label in SUMMARY_IVA_LABELS):
                values = self.extract_amounts_from_fragment(line, ignore_percent=True)
                if values:
                    iva_candidates.append(values[-1])

            if any(label in lowered for label in SUMMARY_TOTAL_LABELS) and "subtotal" not in lowered:
                values = self.extract_amounts_from_fragment(line)
                if values:
                    total_candidates.append(values[-1])

        for total_value in reversed(total_candidates):
            for base_value in reversed(base_candidates):
                for iva_value in reversed(iva_candidates):
                    if abs((base_value + iva_value) - total_value) <= 0.02:
                        return base_value, iva_value, total_value

        base_value = base_candidates[-1] if base_candidates else None
        iva_value = iva_candidates[-1] if iva_candidates else None
        total_value = total_candidates[-1] if total_candidates else None
        return base_value, iva_value, total_value

    def extract_subtotal(self, text: str) -> float | None:
        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            return summary_base

        return self.extract_labeled_amount(
            text,
            [
                r"subtotal",
                r"base\s+imponible",
                r"importe\s+sin\s+iva",
                r"total\s+antes\s+de\s+impuestos",
            ],
            ignore_percent=True,
        )

    def extract_iva(self, text: str) -> float | None:
        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            return summary_iva

        return self.extract_labeled_amount(
            text,
            [
                r"cuota\s+iva",
                r"importe\s+iva",
                r"\biva\b",
            ],
            ignore_percent=True,
        )

    def extract_total(self, text: str) -> float | None:
        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)
        if summary_base is not None and summary_iva is not None and summary_total is not None:
            return summary_total

        return self.extract_labeled_amount(
            text,
            [
                r"importe\s+total",
                r"total\s+factura",
                r"\btotal\b",
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

            line_fragment = match.group(1)
            candidates = self.extract_exact_tax_ids(line_fragment)
            if candidates:
                return candidates[0]

            candidate = normalize_tax_id(line_fragment)
            if candidate:
                return candidate

        candidates = self.extract_exact_tax_ids(text)
        return candidates[0] if candidates else None

    def extract_supplier_tax_id(self, text: str) -> str | None:
        lines = self.extract_lines(text)
        customer_tax_ids: set[str] = set()

        for line in lines:
            if CUSTOMER_LINE_PATTERN.search(line):
                customer_tax_ids.update(self.extract_exact_tax_ids(line))

        label_patterns = [
            r"(?:cif|nif)\s*(?:proveedor|emisor|empresa|raz[oó]n\s+social)?\s*[:\-]?\s*([^\n\r]+)",
            r"(?:proveedor|emisor|empresa|raz[oó]n\s+social)\s*[:\-]?\s*([^\n\r]{0,120})",
        ]

        for pattern_text in label_patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if not match:
                continue

            line_fragment = match.group(1)
            candidates = [candidate for candidate in self.extract_exact_tax_ids(line_fragment) if candidate not in customer_tax_ids]
            if candidates:
                return candidates[0]

        for line in lines[:12]:
            if CUSTOMER_LINE_PATTERN.search(line):
                continue
            candidates = [candidate for candidate in self.extract_exact_tax_ids(line) if candidate not in customer_tax_ids]
            if candidates:
                return candidates[0]

        all_candidates = [candidate for candidate in self.extract_exact_tax_ids(text) if candidate not in customer_tax_ids]
        return all_candidates[0] if all_candidates else None

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

            line_after_label = re.sub(r"^.*?:\s*", "", line).strip()

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

        ignore_patterns = [
            re.compile(r"factura", re.IGNORECASE),
            re.compile(r"cliente", re.IGNORECASE),
            re.compile(r"fecha", re.IGNORECASE),
            re.compile(r"hoja", re.IGNORECASE),
            re.compile(r"subtotal", re.IGNORECASE),
            re.compile(r"base", re.IGNORECASE),
            re.compile(r"iva", re.IGNORECASE),
            re.compile(r"total", re.IGNORECASE),
            re.compile(r"www\.", re.IGNORECASE),
            re.compile(r"^c/", re.IGNORECASE),
            re.compile(r"referencia", re.IGNORECASE),
            re.compile(r"normativa vigente", re.IGNORECASE),
            re.compile(r"empresa emisora", re.IGNORECASE),
            re.compile(r"siempre cerca", re.IGNORECASE),
            re.compile(r"bricolaje", re.IGNORECASE),
            re.compile(r"construcci[oó]n", re.IGNORECASE),
            re.compile(r"decoraci[oó]n", re.IGNORECASE),
            re.compile(r"jardiner[ií]a", re.IGNORECASE),
            re.compile(r"otnemucod", re.IGNORECASE),
            re.compile(r"n[oó]icpircsn[ií]", re.IGNORECASE),
        ]

        for line in lines[:top_n]:
            cleaned = clean_name_candidate(line)
            if not cleaned:
                continue

            if any(pattern.search(cleaned) for pattern in ignore_patterns):
                continue

            if is_valid_name_candidate(cleaned):
                candidates.append(cleaned)

        return pick_best_name(candidates)
