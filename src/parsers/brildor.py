from __future__ import annotations

import re
from pathlib import Path

from src.parsers.base import BaseInvoiceParser, ParsedInvoiceData
from src.utils.amounts import parse_amount


AMOUNT_TOKEN_PATTERN = re.compile(
    r"[+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,4})?"
)


class BrildorInvoiceParser(BaseInvoiceParser):
    parser_name = "brildor"
    priority = 440

    def can_handle(self, text: str, file_path: str | Path | None = None) -> bool:
        normalized = self._normalize_lookup_text(text)
        compact = re.sub(r"\s+", "", normalized)

        return (
            "brildor" in normalized
            or "brildor com" in normalized
            or "brildor.com" in normalized
            or "b03308681" in compact
            or "esb03308681" in compact
        )

    def parse(self, text: str, file_path: str | Path) -> ParsedInvoiceData:
        result = self.build_result(text, file_path)
        result.nombre_proveedor = "Brildor S.L."
        result.nif_proveedor = "B03308681"
        result.numero_factura = self._extract_invoice_number(text)
        result.fecha_factura = self._extract_invoice_date(text)

        subtotal, iva, total = self._extract_summary_triplet(text)

        result.subtotal = subtotal if subtotal is not None else self.extract_labeled_amount(
            text,
            [
                r"base\s+imponible",
                r"subtotal",
                r"importe\s+sin\s+iva",
            ],
            ignore_percent=True,
        )

        result.iva = iva if iva is not None else self.extract_labeled_amount(
            text,
            [
                r"cuota\s+iva",
                r"importe\s+iva",
                r"iva\s*21\s*%",
                r"\biva\b",
            ],
            ignore_percent=True,
        )

        result.total = total if total is not None else self._extract_final_total(text)

        return result.finalize()

    def _extract_invoice_number(self, text: str) -> str | None:
        patterns = [
            r"(?:factura|n[º°o]?\s*factura|número\s+de\s+factura|numero\s+de\s+factura)\s*[:#-]?\s*([A-Z0-9/-]{5,})",
            r"\b(0{2,}\d{4,}(?:-\d+)?)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = self.clean_invoice_number_candidate(match.group(1))
                if candidate:
                    return candidate

        return self.extract_invoice_number(text)

    def _extract_invoice_date(self, text: str) -> str | None:
        match = re.search(
            r"Fecha\s+Pedido\s+Pago\s+.*?(\d{1,2}/\d{1,2}/\d{2,4})",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return self.extract_date(match.group(1))

        return self.extract_date(text)

    def _extract_summary_triplet(self, text: str) -> tuple[float | None, float | None, float | None]:
        """
        Prioriza un bloque coherente de importes: base + IVA = total.
        Esto evita coger líneas sueltas como descuentos (-9,00) o unidades (4,00).
        """
        summary_base, summary_iva, summary_total = self.extract_summary_amounts(text)

        if self._is_valid_triplet(summary_base, summary_iva, summary_total):
            return summary_base, summary_iva, summary_total

        lines = self.extract_lines(text)

        for line in reversed(lines[-50:]):
            amounts = self._parse_amounts_from_line(line)
            if len(amounts) < 3:
                continue

            # Caso típico: base, tipo IVA, cuota IVA, total
            if len(amounts) >= 4:
                for index in range(len(amounts) - 3):
                    base = amounts[index]
                    rate = amounts[index + 1]
                    iva = amounts[index + 2]
                    total = amounts[index + 3]

                    if round(rate, 2) in {4.0, 10.0, 21.0} and self._is_valid_triplet(base, iva, total):
                        return base, iva, total

            # Caso típico: base, IVA, total
            for index in range(len(amounts) - 2):
                base = amounts[index]
                iva = amounts[index + 1]
                total = amounts[index + 2]

                if self._is_valid_triplet(base, iva, total):
                    return base, iva, total

        return None, None, None

    def _extract_final_total(self, text: str) -> float | None:
        """
        Fallback seguro: solo acepta líneas de total final, no cualquier línea con la palabra Total.
        """
        lines = self.extract_lines(text)

        for line in reversed(lines[-50:]):
            if not self._looks_like_final_total_line(line):
                continue

            amounts = [value for value in self._parse_amounts_from_line(line) if value > 0]
            if amounts:
                return amounts[-1]

        return None

    def _looks_like_final_total_line(self, line: str) -> bool:
        normalized = line.lower()

        strong_total_markers = (
            "total factura",
            "importe total",
            "total a pagar",
            "total pedido",
        )

        if any(marker in normalized for marker in strong_total_markers):
            return True

        if not re.search(r"^\s*total\b", normalized, re.IGNORECASE):
            return False

        noisy_markers = (
            "subtotal",
            "descuento",
            "dto",
            "unidad",
            "unidades",
            "cantidad",
            "articulo",
            "artículo",
            "articulos",
            "artículos",
            "producto",
            "productos",
            "portes",
            "envio",
            "envío",
            "base",
            "iva",
            "%",
        )

        return not any(marker in normalized for marker in noisy_markers)

    def _parse_amounts_from_line(self, line: str) -> list[float]:
        values: list[float] = []

        for raw_amount in AMOUNT_TOKEN_PATTERN.findall(line):
            parsed = parse_amount(raw_amount)
            if parsed is None:
                continue
            values.append(parsed)

        return values

    def _is_valid_triplet(
        self,
        subtotal: float | None,
        iva: float | None,
        total: float | None,
    ) -> bool:
        if subtotal is None or iva is None or total is None:
            return False

        if total <= 0:
            return False

        if abs((subtotal + iva) - total) > 0.05:
            return False

        return True

    def _normalize_lookup_text(self, text: str) -> str:
        return (
            text.lower()
            .replace("\n", " ")
            .replace("\r", " ")
            .replace(".", " ")
            .replace(",", " ")
        )