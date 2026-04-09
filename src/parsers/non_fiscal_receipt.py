from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.amounts import parse_amount
from src.utils.dates import extract_date_candidates, normalize_date
from src.utils.names import clean_name_candidate, is_valid_name_candidate, pick_best_name

DECIMAL_AMOUNT_PATTERN = re.compile(
    r"([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{2,4}))"
)
IBAN_PATTERN = re.compile(r"\bES\d{2}(?:\s?[A-Z0-9]){8,30}\b", re.IGNORECASE)
CODE_TOKEN_PATTERN = re.compile(r"\b([A-Z0-9][A-Z0-9/.\-]{2,})\b", re.IGNORECASE)
LONG_DIGIT_REFERENCE_PATTERN = re.compile(r"\b\d(?:\s*\d){17,}\b")
REFERENCE_FRAGMENT_PATTERN = re.compile(
    r"^[A-Z0-9][A-Z0-9/.\-]*(?:\s+[A-Z0-9][A-Z0-9/.\-]*)*$",
    re.IGNORECASE,
)
PERSON_NAME_TOKEN_PATTERN = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'/-]+$")


class NonFiscalReceiptParser(BaseInvoiceParser):
    parser_name = "non_fiscal_receipt"
    priority = 0
    LOOKAHEAD_LINES = 12

    FEMPA_SUPPLIER_NAME = "Federaci\u00f3n de Empresarios del Metal de la provincia de Alicante"
    TGSS_SUPPLIER_NAME = "Tesorer\u00eda General de la Seguridad Social"
    TGSS_COMPACT_SUPPLIER_MARKERS = (
        "tesoreria general de",
        "tgss",
    )

    FEMPA_MARKERS = (
        "fed. empresarios del metal",
        "federacion de empresarios del metal",
        "fempa",
        "g03096963",
    )
    TGSS_MARKERS = (
        "tesoreria general de la seguridad social",
        "tesoreria gral. de la seguridad social",
        "tgss",
        "recibo de liquidacion de cotizaciones",
        "seguridad social",
        "sistema red",
        "rnt",
        "rlt",
    )
    SUPPLIER_LABEL_PATTERNS = (
        r"entidad\s+emisora",
        r"empresa\s+emisora",
        r"^emisor(?:a)?\b",
        r"^acreedor\b",
        r"^beneficiario\b",
        r"^proveedor\b",
    )
    CUSTOMER_LABEL_PATTERNS = (
        r"titular\s+de\s+la\s+domiciliaci[o\u00f3]n",
        r"^titular\b",
        r"raz[o\u00f3]n\s+social",
        r"sujeto\s+responsable",
        r"^deudor\b",
        r"^pagador\b",
        r"^cliente\b",
    )
    VALUE_DATE_LABEL_PATTERNS = (
        r"fecha\s+de\s+valor",
        r"fecha\s+valor",
        r"f\.\s*valor",
    )
    INLINE_TOTAL_LABEL_PATTERNS = (
        r"importe\s+adeudado",
        r"importe\s+del\s+recibo",
        r"importe\s+del\s+cargo",
        r"importe\s+euros",
        r"importe",
        r"total",
    )
    HEADER_TOTAL_LABEL_PATTERNS = (
        "importe euros",
        "importe adeudado",
        "importe del recibo",
        "importe del cargo",
    )
    PROVIDER_HINT_WORDS = (
        "s.l",
        "slu",
        "s.a",
        "sl",
        "sa",
        "federacion",
        "tesoreria",
        "asociacion",
        "ayuntamiento",
        "comunidad",
        "seguros",
        "suministros",
    )
    STRUCTURAL_NOISE_MARKERS = (
        "adeudo recibido",
        "adeudo por domiciliacion",
        "domiciliacion bancaria",
        "titular de la domiciliacion",
        "entidad emisora",
        "informacion adicional",
        "fecha operacion",
        "fecha valor",
        "referencia del adeudo",
        "clausula gastos",
        "recibo bancario",
        "cargo en cuenta",
        "iban",
        "sepa",
        "pagina",
        "recibos seguridad social",
    )
    TGSS_CUSTOMER_CONTEXT_PATTERNS = (
        r"nombre(?:\s+y\s+apellidos)?",
        r"raz[o\u00f3]n\s+social",
        r"sujeto\s+responsable",
        r"aut[o\u00f3]nomo",
        r"trabajador",
    )
    COMPANY_TOKENS = {
        "sl",
        "s.l",
        "s.l.",
        "slu",
        "s.l.u",
        "s.l.u.",
        "sa",
        "s.a",
        "s.a.",
        "sc",
        "s.c",
        "s.c.",
        "cb",
        "c.b",
        "c.b.",
        "coop",
        "cooperativa",
        "autonomo",
        "autonomos",
    }

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        return True

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        lines = self.extract_lines(text)
        profile = self.detect_profile(text, file_path)
        result = self.build_result(text, file_path)

        result.tipo_documento = "no_fiscal"
        result.nombre_proveedor = self.extract_supplier_name(lines, profile)
        result.nombre_cliente = self.extract_customer_name(lines, profile, result.nombre_proveedor)
        result.total = self.extract_receipt_total(lines, profile)
        result.fecha_factura = self.extract_value_date(lines, profile)
        result.numero_factura = self.extract_reference_number(lines, profile)

        return result.finalize()

    def detect_profile(self, text: str, file_path: str | Path | None = None) -> str:
        normalized_text = self._normalize_for_matching(text)
        path_text = self.get_path_text(file_path)

        if any(marker in normalized_text for marker in self.FEMPA_MARKERS) or "fempa" in path_text:
            return "fempa"

        if any(marker in normalized_text for marker in self.TGSS_MARKERS) or "tgss" in path_text:
            return "tgss"

        return "generic"

    def extract_supplier_name(self, lines: list[str], profile: str) -> str | None:
        if profile == "fempa":
            return self.FEMPA_SUPPLIER_NAME

        if profile == "tgss":
            return self.TGSS_SUPPLIER_NAME

        labeled_candidates = self._extract_names_near_labels(
            lines,
            self.SUPPLIER_LABEL_PATTERNS,
            role="provider",
        )
        provider = pick_best_name(labeled_candidates)
        if provider:
            return provider

        fallback_candidates: list[tuple[int, str]] = []

        for line in lines[:20]:
            candidate = clean_name_candidate(line)
            if not self._is_valid_role_name(candidate, role="provider"):
                continue

            lowered = self._normalize_for_matching(candidate)
            score = 0

            if any(hint in lowered for hint in self.PROVIDER_HINT_WORDS):
                score += 2

            if re.search(r"\b(?:sl|s\.l\.|sa|s\.a\.|slu|s\.l\.u\.)\b", candidate, re.IGNORECASE):
                score += 2

            if score == 0:
                continue

            fallback_candidates.append((score, candidate))

        if not fallback_candidates:
            return None

        fallback_candidates.sort(key=lambda item: (-item[0], -len(item[1]), item[1]))
        return fallback_candidates[0][1]

    def extract_customer_name(
        self,
        lines: list[str],
        profile: str,
        supplier_name: str | None,
    ) -> str | None:
        if profile == "tgss":
            compact_customer = self._extract_tgss_customer_name(lines)
            if compact_customer:
                return compact_customer

        candidate_groups = [
            self._extract_names_near_labels(
                lines,
                self.CUSTOMER_LABEL_PATTERNS,
                role="customer",
            ),
        ]

        profile_candidates = self._extract_profile_customer_candidates(lines, profile, supplier_name)
        iban_candidates = self._extract_names_from_iban_lines(lines)

        if profile == "fempa":
            candidate_groups.extend([iban_candidates, profile_candidates])
        else:
            candidate_groups.extend([profile_candidates, iban_candidates])

        if supplier_name:
            candidate_groups.append(self._extract_name_before_supplier(lines, supplier_name, profile))

        for candidates in candidate_groups:
            customer = self._pick_customer_name(candidates)
            if customer:
                return customer

        return None

    def extract_receipt_total(self, lines: list[str], profile: str) -> float | None:
        inline_value = self._extract_amount_near_labels(
            lines,
            self.INLINE_TOTAL_LABEL_PATTERNS,
            lookahead=self.LOOKAHEAD_LINES,
        )
        if inline_value is not None:
            return inline_value

        for index, line in enumerate(lines):
            lowered = self._normalize_for_matching(line)
            if not any(label in lowered for label in self.HEADER_TOTAL_LABEL_PATTERNS):
                continue

            for next_line in lines[index + 1:index + self.LOOKAHEAD_LINES + 1]:
                value = self._extract_first_decimal_amount(next_line)
                if value is not None:
                    return value

        if profile == "tgss":
            compact_total = self._extract_tgss_compact_total(lines)
            if compact_total is not None:
                return compact_total

            return self._extract_amount_near_labels(
                lines,
                (r"importe",),
                lookahead=self.LOOKAHEAD_LINES,
            )

        if profile == "fempa":
            compact_total = self._extract_amount_from_date_line(lines, minimum_dates=2)
            if compact_total is not None:
                return compact_total

        return None

    def extract_value_date(self, lines: list[str], profile: str) -> str | None:
        for index, line in enumerate(lines):
            lowered = self._normalize_for_matching(line)
            if not any(re.search(pattern, lowered, re.IGNORECASE) for pattern in self.VALUE_DATE_LABEL_PATTERNS):
                continue

            same_line_dates = extract_date_candidates(line)
            if same_line_dates:
                return same_line_dates[-1]

            fallback_date: str | None = None

            for next_line in lines[index + 1:index + self.LOOKAHEAD_LINES + 1]:
                raw_date_matches = re.findall(r"\b\d{1,4}[\/\-.]\d{1,2}[\/\-.]\d{1,4}\b", next_line)
                if len(raw_date_matches) >= 2:
                    candidate = normalize_date(raw_date_matches[-1])
                    if candidate:
                        return candidate

                next_dates = extract_date_candidates(next_line)
                if len(next_dates) >= 2:
                    return next_dates[-1]
                if next_dates and fallback_date is None:
                    fallback_date = next_dates[-1]

            if fallback_date:
                return fallback_date

        if profile == "fempa":
            for line in lines:
                raw_date_matches = re.findall(r"\b\d{1,4}[\/\-.]\d{1,2}[\/\-.]\d{1,4}\b", line)
                if len(raw_date_matches) >= 2:
                    candidate = normalize_date(raw_date_matches[-1])
                    if candidate:
                        return candidate

        if profile == "tgss":
            return self._extract_tgss_compact_value_date(lines)

        return None

    def extract_reference_number(self, lines: list[str], profile: str) -> str | None:
        long_reference_patterns = (
            r"referencia(?!\s+del\s+adeudo)",
            r"referencia\s*/\s*observaciones?",
            r"observaciones?",
        )
        receipt_patterns = (
            r"n[u\u00fa]mero\s+de\s+recibo",
            r"num\.?\s*recibo",
            r"n[.:\u00bao]\s*recibo",
            r"recibo\s+n[.:\u00bao]?",
        )
        factura_patterns = (
            r"factura\s+n[.:\u00bao]?",
        )
        generic_reference_patterns = (
            r"observaciones?",
            r"referencia(?!\s+del\s+adeudo)",
            r"referencia\s*/\s*observaciones?",
        )
        adeudo_patterns = (
            r"referencia\s+del\s+adeudo",
            r"referencia\s+de\s+adeudo",
            r"referencia\s+adeudo",
        )

        for patterns in (long_reference_patterns, generic_reference_patterns):
            candidate = self._extract_code_near_labels(lines, patterns, lookahead=4)
            if self._is_long_reference(candidate):
                return candidate

        if profile == "tgss":
            compact_long_reference = self._extract_standalone_long_reference(lines)
            if compact_long_reference:
                return compact_long_reference

        for patterns in (receipt_patterns, factura_patterns, generic_reference_patterns, adeudo_patterns):
            candidate = self._extract_code_near_labels(lines, patterns, lookahead=4)
            if candidate:
                return candidate

        if profile == "tgss":
            return self._extract_long_reference_from_lines(lines)

        return None

    def _extract_names_near_labels(
        self,
        lines: list[str],
        label_patterns: tuple[str, ...],
        *,
        role: str,
    ) -> list[str]:
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in label_patterns]
        candidates: list[str] = []

        for index, line in enumerate(lines):
            for pattern in compiled_patterns:
                match = pattern.search(line)
                if not match:
                    continue

                inline_candidate = clean_name_candidate(line[match.end():])
                if self._is_valid_role_name(inline_candidate, role=role):
                    candidates.append(inline_candidate)

                for next_line in lines[index + 1:index + 3]:
                    candidate = clean_name_candidate(next_line)
                    if self._is_valid_role_name(candidate, role=role):
                        candidates.append(candidate)
                break

        return candidates

    def _extract_tgss_customer_name(self, lines: list[str]) -> str | None:
        compact_line = self._find_tgss_compact_line(lines)
        if compact_line:
            normalized_line = self._normalize_for_matching(compact_line)
            split_index = -1

            for marker in self.TGSS_COMPACT_SUPPLIER_MARKERS:
                split_index = normalized_line.find(marker)
                if split_index >= 0:
                    break

            if split_index > 0:
                candidate = clean_name_candidate(compact_line[:split_index])
                if self._looks_like_human_name(candidate) and self._is_valid_role_name(candidate, role="customer"):
                    return self._normalize_customer_name(candidate)

        for index, line in enumerate(lines[1:], start=1):
            if not IBAN_PATTERN.search(line):
                continue

            candidate = clean_name_candidate(lines[index - 1])
            if self._looks_like_human_name(candidate) and self._is_valid_role_name(candidate, role="customer"):
                return self._normalize_customer_name(candidate)

        return None

    def _extract_name_before_supplier(
        self,
        lines: list[str],
        supplier_name: str,
        profile: str,
    ) -> list[str]:
        supplier_markers = [self._normalize_for_matching(supplier_name)]

        if profile == "fempa":
            supplier_markers.extend(
                [
                    "federacion de empresarios del metal",
                    "fed. empresarios del metal",
                ]
            )

        results: list[str] = []

        for line in lines:
            normalized_line = self._normalize_for_matching(line)
            split_index = -1

            for marker in supplier_markers:
                split_index = normalized_line.find(marker)
                if split_index >= 0:
                    break

            if split_index <= 0:
                continue

            prefix = clean_name_candidate(line[:split_index])
            if self._is_valid_role_name(prefix, role="customer"):
                results.append(prefix)

        return results

    def _extract_names_from_iban_lines(self, lines: list[str]) -> list[str]:
        candidates: list[str] = []

        for line in lines:
            if not IBAN_PATTERN.search(line):
                continue

            fragment = IBAN_PATTERN.sub("", line)
            fragment = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", " ", fragment)
            fragment = re.sub(r"\b\d+\s+de\s+\d+\b", " ", fragment, flags=re.IGNORECASE)
            fragment = re.sub(r"\b\d+\b", " ", fragment)
            fragment = re.sub(r"\s+", " ", fragment).strip(" -,:;|/")

            candidate = clean_name_candidate(fragment)
            if self._is_valid_role_name(candidate, role="customer"):
                candidates.append(candidate)

        return candidates

    def _extract_profile_customer_candidates(
        self,
        lines: list[str],
        profile: str,
        supplier_name: str | None,
    ) -> list[str]:
        if profile != "tgss":
            return []

        scored_candidates: list[tuple[int, int, str]] = []
        compiled_context = [re.compile(pattern, re.IGNORECASE) for pattern in self.TGSS_CUSTOMER_CONTEXT_PATTERNS]
        normalized_supplier = self._normalize_for_matching(supplier_name or "")

        for index, line in enumerate(lines[:25]):
            candidate = clean_name_candidate(line)
            if not self._is_valid_role_name(candidate, role="customer"):
                continue

            normalized_candidate = self._normalize_for_matching(candidate)
            if normalized_supplier and normalized_candidate == normalized_supplier:
                continue

            window_text = " ".join(lines[max(0, index - 1): min(len(lines), index + 2)])
            score = 0

            if any(pattern.search(window_text) for pattern in compiled_context):
                score += 3
            if self._looks_like_human_name(candidate):
                score += 2
            if self._looks_like_company_name(candidate):
                score += 1

            if score == 0:
                continue

            scored_candidates.append((score, index, candidate))

        scored_candidates.sort(key=lambda item: (-item[0], item[1], -len(item[2])))
        return [candidate for _, _, candidate in scored_candidates]

    def _pick_customer_name(self, candidates: list[str]) -> str | None:
        customer = pick_best_name(candidates)
        if not customer:
            return None
        return self._normalize_customer_name(customer)

    def _normalize_customer_name(self, candidate: str) -> str:
        cleaned = clean_name_candidate(candidate) or candidate
        if self._looks_like_company_name(cleaned) or not self._looks_like_human_name(cleaned):
            return cleaned

        tokens = cleaned.split()
        normalized_tokens = []
        for token in tokens:
            lowered = token.lower()
            if lowered in {"de", "del", "la", "las", "los", "y"}:
                normalized_tokens.append(lowered)
                continue
            normalized_tokens.append(token[:1].upper() + token[1:].lower())

        return " ".join(normalized_tokens)

    def _looks_like_human_name(self, candidate: str | None) -> bool:
        cleaned = clean_name_candidate(candidate)
        if cleaned is None or self._looks_like_company_name(cleaned):
            return False

        tokens = cleaned.split()
        if not 2 <= len(tokens) <= 4:
            return False

        return all(PERSON_NAME_TOKEN_PATTERN.fullmatch(token) for token in tokens)

    def _looks_like_company_name(self, candidate: str | None) -> bool:
        cleaned = clean_name_candidate(candidate)
        if cleaned is None:
            return False

        normalized_tokens = {
            token.lower().strip(".,")
            for token in cleaned.replace(",", " ").split()
        }
        return any(token in self.COMPANY_TOKENS for token in normalized_tokens)

    def _extract_amount_near_labels(
        self,
        lines: list[str],
        label_patterns: tuple[str, ...],
        *,
        lookahead: int = 2,
    ) -> float | None:
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in label_patterns]

        for index, line in enumerate(lines):
            for pattern in compiled_patterns:
                match = pattern.search(line)
                if not match:
                    continue

                inline_value = self._extract_first_decimal_amount(line[match.start():])
                if inline_value is not None:
                    return inline_value

                for next_line in lines[index + 1:index + lookahead + 1]:
                    next_value = self._extract_first_decimal_amount(next_line)
                    if next_value is not None:
                        return next_value
                break

        return None

    def _extract_first_decimal_amount(self, fragment: str) -> float | None:
        for match in DECIMAL_AMOUNT_PATTERN.finditer(fragment):
            value = parse_amount(match.group(1))
            if value is not None:
                return value
        return None

    def _extract_last_decimal_amount(self, fragment: str) -> float | None:
        value: float | None = None
        for match in re.finditer(r"\b\d+[.,]\d{2,4}\b", fragment):
            parsed = parse_amount(match.group(0))
            if parsed is not None:
                value = parsed
        return value

    def _extract_amount_from_date_line(
        self,
        lines: list[str],
        *,
        minimum_dates: int = 1,
    ) -> float | None:
        for line in lines:
            raw_date_matches = re.findall(r"\b\d{1,4}[\/\-.]\d{1,2}[\/\-.]\d{1,4}\b", line)
            if len(raw_date_matches) < minimum_dates:
                continue

            value = self._extract_first_decimal_amount(line)
            if value is not None:
                return value

        return None

    def _extract_code_near_labels(
        self,
        lines: list[str],
        label_patterns: tuple[str, ...],
        *,
        lookahead: int = 2,
    ) -> str | None:
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in label_patterns]

        for index, line in enumerate(lines):
            for pattern in compiled_patterns:
                match = pattern.search(line)
                if not match:
                    continue

                inline_candidate = self._extract_code_from_fragment(line[match.end():])
                if inline_candidate:
                    return inline_candidate

                for next_line in lines[index + 1:index + lookahead + 1]:
                    candidate = self._extract_code_from_fragment(next_line)
                    if candidate:
                        return candidate
                break

        return None

    def _extract_code_from_fragment(self, fragment: str) -> str | None:
        full_fragment_candidate = self._extract_full_fragment_reference(fragment)
        if full_fragment_candidate:
            return full_fragment_candidate

        tokens = CODE_TOKEN_PATTERN.findall(fragment)
        ranked_tokens: list[tuple[int, str]] = []

        for token in tokens:
            normalized_token = token.strip()
            cleaned_token = self.clean_invoice_number_candidate(normalized_token)
            if not cleaned_token:
                continue

            if normalize_date(cleaned_token):
                continue

            if re.fullmatch(r"20\d{2}", cleaned_token):
                continue

            if re.fullmatch(r"ES\d{2}", cleaned_token, re.IGNORECASE):
                continue

            has_letters = any(character.isalpha() for character in cleaned_token)
            has_digits = any(character.isdigit() for character in cleaned_token)

            if not has_digits:
                continue

            score = 0
            if has_letters:
                score += 2
            if any(separator in cleaned_token for separator in ("/", "-", ".")):
                score += 1
            if len(cleaned_token) >= 6:
                score += 1

            ranked_tokens.append((score, cleaned_token))

        if ranked_tokens:
            ranked_tokens.sort(key=lambda item: (-item[0], -len(item[1]), item[1]))
            return ranked_tokens[0][1]

        cleaned_fragment = self.clean_invoice_number_candidate(fragment)
        if cleaned_fragment and any(character.isdigit() for character in cleaned_fragment):
            return cleaned_fragment

        return None

    def _extract_full_fragment_reference(self, fragment: str) -> str | None:
        cleaned_fragment = self.clean_invoice_number_candidate(fragment)
        if not cleaned_fragment:
            return None

        normalized_fragment = self._normalize_reference_candidate(cleaned_fragment)
        if not normalized_fragment:
            return None

        if not REFERENCE_FRAGMENT_PATTERN.fullmatch(normalized_fragment):
            return None

        if normalize_date(normalized_fragment):
            return None

        if not any(character.isdigit() for character in normalized_fragment):
            return None

        return normalized_fragment

    def _normalize_reference_candidate(self, candidate: str | None) -> str | None:
        cleaned = self.clean_invoice_number_candidate(candidate)
        if not cleaned:
            return None

        tokens = cleaned.split()
        if len(tokens) > 1 and all(re.fullmatch(r"\d+", token) for token in tokens):
            return "".join(tokens)

        return cleaned

    def _is_long_reference(self, candidate: str | None) -> bool:
        normalized = self._normalize_reference_candidate(candidate)
        if not normalized:
            return False

        digits_only = re.sub(r"\D", "", normalized)
        return len(digits_only) >= 18

    def _extract_long_reference_from_lines(self, lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            context = self._normalize_for_matching(
                " ".join(lines[max(0, index - 1): min(len(lines), index + 2)])
            )
            if not any(marker in context for marker in ("referencia", "recibo", "adeudo")):
                continue

            match = LONG_DIGIT_REFERENCE_PATTERN.search(line)
            if not match:
                continue

            candidate = self._normalize_reference_candidate(match.group(0))
            if self._is_long_reference(candidate):
                return candidate

        return None

    def _extract_standalone_long_reference(self, lines: list[str]) -> str | None:
        for line in lines:
            if IBAN_PATTERN.search(line):
                continue

            match = LONG_DIGIT_REFERENCE_PATTERN.search(line)
            if not match:
                continue

            candidate = self._normalize_reference_candidate(match.group(0))
            if self._is_long_reference(candidate):
                return candidate

        return None

    def _is_valid_role_name(self, candidate: str | None, *, role: str) -> bool:
        cleaned = clean_name_candidate(candidate)
        if cleaned is None or not is_valid_name_candidate(cleaned):
            return False

        lowered = self._normalize_for_matching(cleaned)

        if any(marker in lowered for marker in self.STRUCTURAL_NOISE_MARKERS):
            return False

        if role == "provider" and any(
            marker in lowered
            for marker in (
                "titular",
                "cliente",
                "deudor",
                "pagador",
            )
        ):
            return False

        if role == "customer" and any(
            marker in lowered
            for marker in (
                "entidad emisora",
                "emisor",
                "acreedor",
                "beneficiario",
                "proveedor",
            )
        ):
            return False

        return True

    def _find_tgss_compact_line(self, lines: list[str]) -> str | None:
        for line in lines:
            normalized_line = self._normalize_for_matching(line)
            if not any(marker in normalized_line for marker in self.TGSS_COMPACT_SUPPLIER_MARKERS):
                continue

            if self._extract_first_decimal_amount(line) is None:
                continue

            if not extract_date_candidates(line):
                continue

            return line

        return None

    def _extract_tgss_compact_value_date(self, lines: list[str]) -> str | None:
        compact_line = self._find_tgss_compact_line(lines)
        if not compact_line:
            return None

        dates = extract_date_candidates(compact_line)
        return dates[-1] if dates else None

    def _extract_tgss_compact_total(self, lines: list[str]) -> float | None:
        compact_line = self._find_tgss_compact_line(lines)
        if not compact_line:
            return None

        return self._extract_last_decimal_amount(compact_line)

    def _normalize_for_matching(self, value: str) -> str:
        compact = " ".join((value or "").replace("\r", "\n").split()).lower()
        replacements = {
            "\u00e1": "a",
            "\u00e9": "e",
            "\u00ed": "i",
            "\u00f3": "o",
            "\u00fa": "u",
            "\u00fc": "u",
            "\u00f1": "n",
        }

        for original, replacement in replacements.items():
            compact = compact.replace(original, replacement)

        return compact
