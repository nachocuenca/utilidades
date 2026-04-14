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

    def _extract_with_ollama(self, pdf_path: str | Path, settings, debug: bool = False) -> Dict[str, Any]:
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

        # Try to provide OCR text to the model to improve grounding (explicitly anchor to PDF content)
        ocr_text = None
        try:
            ocr_text = read_pdf_text_only(pdf_path)
        except Exception:
            ocr_text = None

        prompt = (
            "Procesa las imágenes adjuntas (páginas de una factura) y devuelve EXACTAMENTE un objeto JSON con los campos: "
            "tipo_documento, nombre_proveedor, nif_proveedor, nombre_cliente, nif_cliente, cp_cliente, numero_factura, "
            "fecha_factura, subtotal, iva, total, confidence, warnings, evidence_snippets. "
            "DEVOLVER SOLO JSON. NO INVENTAR VALORES DE EJEMPLO BAJO NINGUN CONCEPTO. Si un campo no es claramente legible en las imágenes, devuelve null para ese campo. "
            "Por ejemplo: NO uses nombres ficticios como 'Empresa XYZ' ni 'Cliente ABC', ni NIFs de ejemplo como 'A12345678'. "
            "Nunca rellenes con valores de plantilla ni ejemplos; si no está en la imagen, devuelve null. "
            "Incluye todas las claves del esquema en el JSON (pueden ser null) y no añadas texto explicativo ni ejemplos."
        )

        if ocr_text:
            # Append OCR text as an explicit source of truth for grounding
            prompt = prompt + "\n\nTEXTO_OCR_EXTRAIDO:\n" + ocr_text

        # Use Ollama chat endpoint to request structured JSON via format/schema
        payload = {
            "model": settings.local_model_name,
            "messages": [
                {"role": "system", "content": "Eres un extractor que devuelve SOLO JSON estructurado según el esquema solicitado. NO INVENTES VALORES DE EJEMPLO. Si no ves el dato en las imágenes, responde null para ese campo."},
                {"role": "user", "content": prompt},
            ],
            "images": images_b64,
            "format": schema,
            "temperature": 0,
            "stream": False,
            "raw": False,
        }

        url = settings.ollama_base_url.rstrip("/") + "/chat"

        import os
        timeout = int(os.getenv("OLLAMA_TIMEOUT", "600"))
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()

        # Prefer parsing from message.content as requested
        generated = None
        # Ollama chat may return 'message' or 'response' or 'choices'
        if isinstance(body.get("message"), dict):
            generated = body["message"].get("content")
        elif isinstance(body.get("response"), dict):
            # sometimes 'response' is dict
            generated = body["response"].get("content") or body["response"].get("response")
        elif isinstance(body.get("choices"), list) and body["choices"]:
            first = body["choices"][0]
            if isinstance(first, dict) and isinstance(first.get("message"), dict):
                generated = first["message"].get("content")
            else:
                generated = first.get("content") if isinstance(first, dict) else None
        else:
            generated = body.get("response")

        if generated is None:
            # fallback to raw body as string
            raw = json.dumps(body, ensure_ascii=False)
            raise RuntimeError(f"No se encontró contenido de mensaje en respuesta de Ollama. Body: {raw}")

        # Attempt to parse JSON from generated content
        try:
            extraction = json.loads(generated) if isinstance(generated, str) else generated
        except Exception as e:
            # Provide raw content and error per user request
            raise RuntimeError(f"No se pudo parsear respuesta de Ollama como JSON: {e}\nRAW_CONTENT_START\n{generated}\nRAW_CONTENT_END") from e

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

        # Detect obvious placeholder/template values in the extraction (evidence or fields)
        placeholders_indicators = [
            "Empresa XYZ",
            "Cliente ABC",
            "A12345678",
            "B98765432",
            "12345",
            "Empresa",
            "Cliente",
            "XYZ",
            "ABC",
        ]

        def has_placeholders(obj):
            if obj is None:
                return False
            if isinstance(obj, str):
                for p in placeholders_indicators:
                    if p in obj:
                        return True
                return False
            if isinstance(obj, list):
                for it in obj:
                    if has_placeholders(it):
                        return True
                return False
            if isinstance(obj, dict):
                for v in obj.values():
                    if has_placeholders(v):
                        return True
                return False
            return False

        if has_placeholders(extraction):
            # Attempt a second, stricter extraction: force exact-match extraction from OCR text
            ocr_text_block = ocr_text or read_pdf_text_only(pdf_path) or ""
            strict_prompt = (
                "Usa solo el siguiente TEXTO_OCR como fuente de verdad. Para cada campo, busca su valor EXACTO como SUBCADENA en el TEXTO_OCR. "
                "Si no encuentras una coincidencia exacta para el campo, devuelve null para ese campo. \n\n"
                f"TEXTO_OCR:\n{ocr_text_block}\n\n"
                "Devuelve SOLO JSON con las mismas claves que antes. No inventes valores y no agregues texto."
            )

            payload2 = {
                "model": settings.local_model_name,
                "messages": [
                    {"role": "system", "content": "Eres un extractor estricto: solo extraes valores que aparecen textualmente en TEXTO_OCR. Si no aparece, pon null."},
                    {"role": "user", "content": strict_prompt},
                ],
                "images": images_b64,
                "format": schema,
                "temperature": 0,
                "stream": False,
                "raw": False,
            }

            import os
            timeout = int(os.getenv("OLLAMA_TIMEOUT", "600"))
            resp2 = requests.post(url, json=payload2, timeout=timeout)
            resp2.raise_for_status()
            body2 = resp2.json()

            gen2 = None
            if isinstance(body2.get("message"), dict):
                gen2 = body2["message"].get("content")
            elif isinstance(body2.get("response"), dict):
                gen2 = body2["response"].get("content") or body2["response"].get("response")
            elif isinstance(body2.get("choices"), list) and body2["choices"]:
                first = body2["choices"][0]
                if isinstance(first, dict) and isinstance(first.get("message"), dict):
                    gen2 = first["message"].get("content")
                else:
                    gen2 = first.get("content") if isinstance(first, dict) else None
            else:
                gen2 = body2.get("response")

            if gen2 is not None:
                try:
                    extraction2 = json.loads(gen2) if isinstance(gen2, str) else gen2
                except Exception:
                    extraction2 = None
            else:
                extraction2 = None

            if extraction2:
                # ensure keys and return the stricter extraction
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
                    if k not in extraction2:
                        extraction2[k] = None if k not in ("confidence", "warnings", "evidence_snippets") else (0.0 if k=="confidence" else [])
                if debug:
                    return extraction2, gen2
                return extraction2

        # If debug requested, also return the raw generated text alongside the normalized extraction
        if debug:
            return extraction, generated

        return extraction
