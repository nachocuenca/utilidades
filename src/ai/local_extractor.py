from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from src.pdf.reader import read_pdf_text_only
from config.settings import get_settings
try:
    import pypdfium2 as pdfium
except Exception:
    pdfium = None


class LocalExtractor:
    """Simple local extractor that uses PDF text extraction + heuristics
    to fill the invoice extraction schema. This is a lightweight local
    alternative to calling OpenAI; not a full LLM, but suitable for
    offline runs and testing the IA flow.
    """

    def __init__(self) -> None:
        pass

    def extract_from_pdf(self, pdf_path: str | Path, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        settings = get_settings()

        # If configured to use a real local model provider (e.g. Ollama), try that path.
        if settings.local_model_enabled and settings.local_model_provider and settings.local_model_provider.lower() == "ollama":
            try:
                return self._extract_with_ollama(pdf_path, settings)
            except Exception:
                # Fall back to heuristic extractor on any local-model error (no network/OpenAPI calls)
                pass

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

    def _render_pdf_pages_to_base64(self, pdf_path: str | Path, dpi: int = 200, max_pages: Optional[int] = 4) -> List[str]:
        """Render first pages of PDF into base64-encoded PNG images using pypdfium2.

        Returns list of base64 PNG strings (no data URI prefix).
        """
        if pdfium is None:
            raise RuntimeError("pypdfium2 is required to render PDF pages to images for local model.")

        path = Path(pdf_path).resolve()
        document = pdfium.PdfDocument(str(path))
        try:
            page_count = len(document)
            images_b64: List[str] = []
            scale = max(dpi, 72) / 72.0
            pages_to_render = min(page_count, max_pages or page_count)
            for i in range(pages_to_render):
                page = document[i]
                bitmap = page.render(scale=scale)
                pil = bitmap.to_pil()
                buf = io.BytesIO()
                pil.save(buf, format="PNG")
                buf.seek(0)
                b64 = base64.b64encode(buf.read()).decode("ascii")
                images_b64.append(b64)
                try:
                    bitmap.close()
                except Exception:
                    pass
                try:
                    page.close()
                except Exception:
                    pass
            return images_b64
        finally:
            try:
                document.close()
            except Exception:
                pass

    def _extract_with_ollama(self, pdf_path: str | Path, settings) -> Dict[str, Any]:
        """Call local Ollama server to process PDF images and return structured JSON.

        Uses POST {OLLAMA_BASE_URL}/generate with JSON body:
        {
          "model": <model>,
          "prompt": <prompt>,
          "images": [<base64 strings>],
          "format": <json schema>
        }
        """
        images_b64 = self._render_pdf_pages_to_base64(pdf_path, dpi=settings.ocr_render_dpi, max_pages=4)

        # Define JSON schema for strict structured output
        schema = {
            "type": "object",
            "properties": {
                "tipo_documento": {"type": "string"},
                "nombre_proveedor": {"type": ["string", "null"]},
                "nif_proveedor": {"type": ["string", "null"]},
                "nombre_cliente": {"type": ["string", "null"]},
                "nif_cliente": {"type": ["string", "null"]},
                "cp_cliente": {"type": ["string", "null"]},
                "numero_factura": {"type": ["string", "null"]},
                "fecha_factura": {"type": ["string", "null"]},
                "subtotal": {"type": ["number", "null"]},
                "iva": {"type": ["number", "null"]},
                "total": {"type": ["number", "null"]},
                "confidence": {"type": "number"},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "evidence_snippets": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tipo_documento", "confidence", "warnings", "evidence_snippets"],
        }

        prompt = (
            "Procesa las imágenes adjuntas (páginas de una factura) y devuelve EXACTAMENTE un objeto JSON con los campos: "
            "tipo_documento, nombre_proveedor, nif_proveedor, nombre_cliente, nif_cliente, cp_cliente, numero_factura, "
            "fecha_factura, subtotal, iva, total, confidence, warnings, evidence_snippets. "
            "Devuelve null para campos no disponibles. No agregues texto adicional, solo JSON."
        )

        payload = {
            "model": settings.local_model_name,
            "prompt": prompt,
            "images": images_b64,
            "format": schema,
            "stream": False,
            "raw": False,
        }

        url = settings.ollama_base_url.rstrip("/") + "/generate"

        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        body = resp.json()

        # Ollama returns generated text in body['response'] (string) when format is used it may be JSON string
        generated = body.get("response")
        if isinstance(generated, dict):
            extraction = generated
        else:
            try:
                extraction = json.loads(generated)
            except Exception as e:
                raise RuntimeError(f"No se pudo parsear respuesta de Ollama como JSON: {e}\n{generated}") from e

        # Ensure shape contains required keys
        for k in [
            "tipo_documento",
            "nombre_proveedor",
            "nif_proveedor",
            "nombre_cliente",
            "nif_cliente",
            "cp_cliente",
            "numero_factura",
            "fecha_factura",
            "subtotal",
            "iva",
            "total",
            "confidence",
            "warnings",
            "evidence_snippets",
        ]:
            if k not in extraction:
                extraction[k] = None if k not in ("confidence", "warnings", "evidence_snippets") else (0.0 if k=="confidence" else [])

        return extraction
