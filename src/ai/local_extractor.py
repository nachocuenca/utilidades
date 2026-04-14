from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pdf.reader import read_pdf_text_only


class LocalExtractor:
    """Simple local extractor that uses PDF text extraction + heuristics
    to fill the invoice extraction schema. This is a lightweight local
    alternative to calling OpenAI; not a full LLM, but suitable for
    offline runs and testing the IA flow.
    """

    def __init__(self) -> None:
        pass

    def extract_from_pdf(self, pdf_path: str | Path, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        text = read_pdf_text_only(pdf_path)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        def find_first(patterns: List[str]) -> Optional[str]:
            for p in patterns:
                rx = re.compile(p, re.IGNORECASE)
                for ln in lines:
                    m = rx.search(ln)
                    if m:
                        return m.group(1).strip() if m.groups() else ln
            return None

        # heuristics
        numero = find_first([r"n[úu]mero[:\s]*([A-Za-z0-9\-\/]+)", r"factura[:\s]*([A-Za-z0-9\-\/]+)", r"n[oº]\.?[:\s]*([0-9\-\/]+)"])
        fecha = find_first([r"(\d{2}[\/\-]\d{2}[\/\-]\d{4})", r"(\d{4}[\-]\d{2}[\-]\d{2})"])

        # nif pattern: spanish NIF/CIF (simplified)
        nif = find_first([r"([A-ZÑa-zñ0-9]{1,2}\d{7}[A-Z0-9])", r"\b([0-9]{8}[A-Z])\b"]) or None

        # amounts: look for lines with total, subtotal, iva
        def find_amount(keyword: str) -> Optional[float]:
            rx = re.compile(rf"{keyword}[^0-9\-\,\.]*(\d+[\d\.,]*\d)", re.IGNORECASE)
            for ln in lines[::-1]:
                m = rx.search(ln)
                if m:
                    g = m.group(1) if m.groups() else None
                    if not g:
                        continue
                    val = g.replace('.', '').replace(',', '.')
                    try:
                        return float(val)
                    except Exception:
                        continue
            return None

        total = find_amount(r"total")
        iva = find_amount(r"iva|tax")
        subtotal = None
        if total is not None and iva is not None:
            try:
                subtotal = round(total - iva, 2)
            except Exception:
                subtotal = None

        provider = find_first([r"^(.*)\bS\.L\.U\.|^(.+?)\s+S\.L\.?", r"^(.+?)\s+S\.A\.", r"proveedor[:\s]*(.+)"])
        client = find_first([r"cliente[:\s]*(.+)", r"destinatario[:\s]*(.+)"])

        warnings: List[str] = []
        if total is None:
            warnings.append("No se encontró total claramente.")
        if nif is None:
            warnings.append("No se detectó NIF claramente.")

        confidence = 0.85 if total is not None and nif is not None else 0.5

        evidence: List[str] = []
        # collect lines that contain key hits
        keys = ["total", "iva", "subtotal", "factura", "nif", "cliente", "proveedor"]
        for ln in lines:
            low = ln.lower()
            if any(k in low for k in keys):
                evidence.append(ln)
                if len(evidence) >= 10:
                    break

        result = {
            "tipo_documento": "factura",
            "nombre_proveedor": provider,
            "nif_proveedor": nif,
            "nombre_cliente": client,
            "nif_cliente": None,
            "cp_cliente": None,
            "numero_factura": numero,
            "fecha_factura": fecha,
            "subtotal": subtotal,
            "iva": iva,
            "total": total,
            "confidence": float(confidence),
            "warnings": warnings,
            "evidence_snippets": evidence,
        }

        return result
