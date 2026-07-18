from __future__ import annotations

import re
from pathlib import Path
from typing import List

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.dates import normalize_date
from src.utils.names import clean_name_candidate, is_valid_name_candidate, pick_best_name

TICKET_MONTHS = {
    "ene": "enero",
    "feb": "febrero",
    "mar": "marzo",
    "abr": "abril",
    "may": "mayo",
    "jun": "junio",
    "jul": "julio",
    "ago": "agosto",
    "sep": "septiembre",
    "sept": "septiembre",
    "oct": "octubre",
    "nov": "noviembre",
    "dic": "diciembre",
}

STRONG_TICKET_PATTERNS = (
    re.compile(r"factura\s+simplificada", re.IGNORECASE),
    re.compile(r"\bsala-mesa\b", re.IGNORECASE),
    re.compile(r"\bn[ºo°]\s*op\.?\b", re.IGNORECASE),
    re.compile(r"\bn[ºo°]\s*operaci[oó]n\b", re.IGNORECASE),
    re.compile(r"\bticket\b", re.IGNORECASE),
    re.compile(r"\b(n[ºo°]\s*ticket|ticket n[ºo°])\b", re.IGNORECASE),
)

SUPPORT_TICKET_PATTERNS = (
    re.compile(r"\bidentificador\b", re.IGNORECASE),
    re.compile(r"impuestos\s+incluidos", re.IGNORECASE),
    re.compile(r"\befectivo\b", re.IGNORECASE),
    re.compile(r"\bentregado\b", re.IGNORECASE),
    re.compile(r"\bcambio\b", re.IGNORECASE),
    re.compile(r"\bpagado\b", re.IGNORECASE | re.MULTILINE),
)

TOTAL_LINE_PATTERN = re.compile(
    r"(?i)(?:\btotal\b|neto\s+a\s*pagar)\s*[:\.]?\s*(\d+(?:[\.,]\d{2})?)",
    re.MULTILINE,
)

DATE_PATTERN = re.compile(r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b")
NIF_PATTERN = re.compile(r"\b([0-9A-Z]{8,9}[A-Z])\b")

OCR_BASURA_PATTERNS = [
    re.compile(r"^\s*[A-Z\s\./]{1,8}\s*$"),
    re.compile(r"^[.A-Z\s]+F\.I\.N[.A-Z\s]*$", re.I),
    re.compile(r"ajoh|OILOF|otnemucod", re.I),
]


def is_ocr_basura(line: str) -> bool:
    line_upper = line.strip().upper()
    if len(line_upper) < 4 or len(line.strip()) < 3:
        return True
    for pattern in OCR_BASURA_PATTERNS:
        if pattern.search(line):
            return True
    vowels = sum(1 for char in line.lower() if char in "aeiouáéíóú")
    if len(line) < 8 and vowels == 0:
        return True
    return False


class GenericTicketInvoiceParser(BaseInvoiceParser):
    parser_name = "generic_ticket"
    priority = 60

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        path_text = self.get_path_text(file_path) or ""
        path_text_lower = path_text.lower()
        # Detect common ticket folder hints (support both slashes and backslashes)
        path_suggests_ticket = any(
            p in path_text_lower for p in ("/tickets/", "/ticket/", "\\tickets\\", "\\ticket\\")
        )

        lines = self.extract_lines(text)
        if len(lines) > 60:
            return False

        strong_matches = sum(1 for pattern in STRONG_TICKET_PATTERNS if pattern.search(text))
        support_matches = sum(1 for pattern in SUPPORT_TICKET_PATTERNS if pattern.search(text))
        has_total = bool(TOTAL_LINE_PATTERN.search(text))
        has_date = bool(DATE_PATTERN.search(text))

        # Explicit reject if clear fiscal invoice markers are present
        normalized_text = text.lower()
        for marker in [
            "base imponible",
            "cuota iva",
            "importe iva",
            "total factura",
            "subtotal",
        ]:
            if marker in normalized_text:
                return False

        # If the path suggests a ticket, require at least one clear ticket signal
        if path_suggests_ticket and not (has_total or has_date or strong_matches >= 1 or support_matches >= 1):
            return False

        # Require a date or at least a total for reliable ticket detection.
        # Accept tickets that lack an explicit date but have a clear total.
        if not (has_date or has_total):
            return False

        # Relaxed acceptance: one strong match is enough, or support+date/total
        if not (
            strong_matches >= 1
            or (support_matches >= 1 and (has_total or has_date))
        ):
            return False

        # Reject very short or low-information texts even if they contain the word "ticket"
        joined = "\n".join(lines).strip()
        if len(joined) < 20:
            return False

        if len(NIF_PATTERN.findall(text)) > 3:
            return False

        basura_top = sum(1 for line in lines[:10] if is_ocr_basura(line))
        if basura_top > 3:
            return False

        return True

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        result = self.build_result(text, file_path)

        result.nombre_proveedor = self.extract_supplier_name(lines, file_path)
        result.nif_proveedor = self.extract_supplier_tax_id_improved(text, lines)
        result.numero_factura = self.extract_ticket_number(text)
        result.fecha_factura = self.extract_ticket_date_improved(text)
        result.total = self.extract_ticket_total_improved(text, lines)
        # For tickets, avoid filling subtotal/iva by default unless explicit labels exist
        if re.search(r"\b(subtotal|base imponible)\b", text, re.IGNORECASE):
            result.subtotal = self.extract_ticket_subtotal(text)
        else:
            result.subtotal = None

        if re.search(r"\b(cuota iva|importe iva|\biva\b)\b", text, re.IGNORECASE):
            result.iva = self.extract_ticket_iva(text)
        else:
            result.iva = None

        # Extract simple Spanish postal code (5 digits) from header lines (first ~10 lines).
        # Ignore lines that look like they contain prices/amounts.
        result.cp_cliente = None
        for line in lines[:10]:
            if re.search(r"\d+[\.,]\d{2}", line):
                # likely a price line, skip
                continue
            m = re.search(r"\b(\d{5})\b", line)
            if m:
                result.cp_cliente = m.group(1)
                break

        return result.finalize()

    def extract_supplier_name(self, lines: List[str], file_path: str | Path) -> str | None:
        ignored_patterns = [
            re.compile(r"(?i)(factura\s+simplificada|subtotal|total|base|cuota|producto|importe|entregado|cambio|efectivo|tel[.:]|avenida|calle)"),
            re.compile(r"(?i)(c/|c\.|poblacion|provincia)"),
            re.compile(r"(?i)(informacion\s+adicional|referencia|cumplimiento|normativa)"),
            re.compile(r"(?i)(nif\s+cliente|cliente)"),
        ]

        candidates: list[tuple[int, str, str]] = []
        for idx, line in enumerate(lines[:10]):
            if is_ocr_basura(line):
                continue

            cleaned = clean_name_candidate(line)
            if not cleaned:
                continue

            if any(pattern.search(cleaned) for pattern in ignored_patterns):
                continue

            if len(cleaned) >= 4 and is_valid_name_candidate(cleaned):
                candidates.append((idx, cleaned, line))

        # If a NIF appears in the first lines, prefer the candidate on the same
        # line or the immediately previous line.
        nif_candidates: list[tuple[int, str]] = []
        for i, line in enumerate(lines[:10]):
            nifs = NIF_PATTERN.findall(line)
            for nif in nifs:
                nif_candidates.append((i, nif))

        if nif_candidates and candidates:
            nif_index = nif_candidates[0][0]
            # prefer candidate on same line or previous
            for idx, cleaned, orig in candidates:
                if idx == nif_index or idx == nif_index - 1:
                    return cleaned

        # If a line contains a person name plus a NIF (e.g. "Juan Perez / NIF: X...")
        # prefer that person's name as supplier (more reliable than noisy commercial OCR)
        for idx, line in enumerate(lines[:10]):
            if NIF_PATTERN.search(line):
                # try to extract a name-like portion before common separators
                parts = re.split(r"[/\\\-]|NIF[:\s]*", line, flags=re.IGNORECASE)
                if parts:
                    candidate = clean_name_candidate(parts[0])
                    if candidate and not is_ocr_basura(candidate):
                        return candidate

        # Heuristic: if top lines look like product/menu lines (multiple lines
        # that start with an item count or contain prices), avoid filling
        # proveedor unless we have NIF evidence.
        product_like = 0
        for line in lines[:10]:
            if re.match(r"^\s*\d+\s+\S+", line):
                product_like += 1
            if re.search(r"\d+[\.,]\d{2}", line):
                product_like += 1

        if product_like >= 2 and not nif_candidates:
            return None

        # Fallback: pick best by existing heuristic
        best = pick_best_name([c[1] for c in candidates])
        if best and not is_ocr_basura(best):
            return best

        folder_hint = self.get_folder_hint_name(file_path)
        if folder_hint and len(folder_hint) > 4 and not is_ocr_basura(folder_hint):
            return folder_hint

        return None

    def extract_supplier_tax_id_improved(self, text: str, lines: List[str]) -> str | None:
        nif_candidates: list[tuple[int, str]] = []
        for index, line in enumerate(lines[:25]):
            nifs = NIF_PATTERN.findall(line)
            for nif in nifs:
                # Skip NIFs that are clearly associated to a client line
                if index > 0 and "cliente" in lines[index - 1].lower():
                    continue

                # If the NIF appears on a line that looks like a person (e.g. "Nombre Apellido / NIF: ..."),
                # treat it as likely a person identifier and avoid returning it as supplier tax id.
                line_lower = line.lower()
                if "nif" in line_lower:
                    # heuristics: if line contains two words with letters (a personal name), skip
                    if re.search(r"[A-Za-zÀ-ÿ]+\s+[A-Za-zÀ-ÿ]+", line):
                        continue

                nif_candidates.append((index, nif))

        if nif_candidates:
            return nif_candidates[0][1]

        return self.extract_supplier_tax_id(text)

    def extract_ticket_date_improved(self, text: str) -> str | None:
        fecha_sections = re.split(r"(?i)fecha", text, maxsplit=1)
        if len(fecha_sections) > 1:
            local_match = DATE_PATTERN.search(fecha_sections[1])
            if local_match:
                candidate = normalize_date(local_match.group(1))
                if candidate:
                    return candidate

        return self.extract_ticket_date(text)

    def extract_ticket_total_improved(self, text: str, lines: List[str]) -> float | None:
        for line in reversed(lines[-10:]):
            # Find all occurrences of the TOTAL_LINE_PATTERN in the line and take the last one
            matches = list(TOTAL_LINE_PATTERN.finditer(line))
            if matches:
                last = matches[-1]
                try:
                    return float(last.group(1).replace(",", "."))
                except (ValueError, IndexError):
                    # fallback to scanning numbers inside the matched text
                    numbers = re.findall(r"(\d+(?:[\.,]\d{2})?)", last.group(0))
                    if numbers:
                        try:
                            return float(numbers[-1].replace(",", "."))
                        except ValueError:
                            pass

        # Fallback: find all TOTAL matches in the whole text and pick the last one
        matches = list(TOTAL_LINE_PATTERN.finditer(text))
        if matches:
            last = matches[-1]
            try:
                return float(last.group(1).replace(",", "."))
            except (ValueError, IndexError):
                numbers = re.findall(r"(\d+(?:[\.,]\d{2})?)", last.group(0))
                if numbers:
                    try:
                        return float(numbers[-1].replace(",", "."))
                    except ValueError:
                        pass

        return self.extract_ticket_total(text)

    def extract_ticket_number(self, text: str) -> str | None:
        patterns = [
            r"(?:n[ºo°]\s*op\.?|n[ºo°]\s*operaci[oó]n)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
            r"(?:identificador)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
            r"(?:ticket)\s*[:#\-]?\s*([A-Z0-9\/\-.]+)",
        ]

        for pattern_text in patterns:
            match = re.search(pattern_text, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip(" .,:;")
                if candidate:
                    return candidate

        return self.extract_invoice_number(text)

    def extract_ticket_date(self, text: str) -> str | None:
        numeric_match = re.search(r"\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b", text)
        if numeric_match:
            candidate = normalize_date(numeric_match.group(1))
            if candidate:
                return candidate

        month_match = re.search(
            r"\b(\d{1,2})\s*(ene|feb|mar|abr|may|jun|jul|ago|sep|sept|oct|nov|dic)\.?\s*(\d{2,4})\b",
            text,
            re.IGNORECASE,
        )
        if month_match:
            day_value, month_abbrev, year_value = month_match.groups()
            month_name = TICKET_MONTHS.get(month_abbrev.lower())
            if month_name:
                candidate = normalize_date(f"{day_value} de {month_name} de {year_value}")
                if candidate:
                    return candidate

        return self.extract_date(text)

    def extract_ticket_subtotal(self, text: str) -> float | None:
        value = self.extract_labeled_amount(text, [r"\bbase\b", r"subtotal", r"base\s+imponible"])
        if value is not None:
            return value
        return self.extract_subtotal(text)

    def extract_ticket_iva(self, text: str) -> float | None:
        value = self.extract_labeled_amount(text, [r"\bcuota\b", r"\biva\b"])
        if value is not None:
            return value
        return self.extract_iva(text)

    def extract_ticket_total(self, text: str) -> float | None:
        value = self.extract_labeled_amount(text, [r"total\s*\(.*?incl.*?\)", r"\btotal\b"])
        if value is not None:
            return value
        return self.extract_total(text)