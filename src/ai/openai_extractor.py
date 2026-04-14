import os
import logging
import requests
from pathlib import Path
from typing import Any, Dict, Optional
from src.ai.schemas import validate_invoice_extraction

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_FALLBACK_ENABLED = os.getenv("OPENAI_FALLBACK_ENABLED", "true").lower() == "true"
OPENAI_FALLBACK_MIN_CONFIDENCE = float(os.getenv("OPENAI_FALLBACK_MIN_CONFIDENCE", 0.7))
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", 40))

logger = logging.getLogger("openai_extractor")

OPENAI_API_URL = "https://api.openai.com/v1/files"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

INVOICE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "tipo_documento": {"type": "string", "enum": ["factura", "ticket", "no_fiscal", "desconocido"]},
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
        "evidence_snippets": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["tipo_documento", "nombre_proveedor", "nif_proveedor", "nombre_cliente", "nif_cliente", "cp_cliente", "numero_factura", "fecha_factura", "subtotal", "iva", "total", "confidence", "warnings", "evidence_snippets"],
    "additionalProperties": False
}

class OpenAIExtractor:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model or OPENAI_MODEL
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

    def extract_from_pdf(self, pdf_path: str | Path, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        logger.info(f"Uploading PDF to OpenAI: {pdf_path}")
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            data = {"purpose": "user_data"}
            headers = {"Authorization": f"Bearer {self.api_key}"}
            upload_resp = requests.post(OPENAI_API_URL, files=files, data=data, headers=headers, timeout=OPENAI_TIMEOUT)
            upload_resp.raise_for_status()
            file_id = upload_resp.json()["id"]
        logger.info(f"File uploaded to OpenAI, file_id={file_id}")
        prompt = self._build_prompt(context)
        # Build Responses API payload with file reference and structured JSON schema
        payload = {
            "model": self.model,
            "input": [
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                {"role": "user", "content": [{"type": "input_file", "file_id": file_id}]}
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "invoice_extraction",
                    "schema": INVOICE_EXTRACTION_SCHEMA,
                }
            },
            "max_output_tokens": 1500,
            "temperature": 0.0,
        }

        logger.info(f"Requesting extraction from OpenAI Responses API model={self.model}")
        resp = requests.post(OPENAI_RESPONSES_URL, json=payload, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=OPENAI_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        logger.debug(f"OpenAI raw response: {result}")

        # Responses API returns `output` list; try to extract the structured JSON result
        data = None
        output = result.get("output") or result.get("results") or []
        if isinstance(output, list) and output:
            # look for json_schema output
            for item in output:
                # item may contain 'content' with structured value or 'response' key
                content = item.get("content") or item.get("response")
                if isinstance(content, list):
                    for c in content:
                        if c.get("type") == "output_json_schema":
                            data = c.get("value")
                            break
                        if c.get("type") == "output_text":
                            # try parse JSON text
                            try:
                                import json
                                parsed = json.loads(c.get("text", "{}"))
                                data = parsed
                                break
                            except Exception:
                                continue
                if data:
                    break

        if data is None:
            # fallback: try to find top-level 'output' as dict
            if isinstance(result, dict) and result.get("output") and isinstance(result.get("output"), dict):
                data = result.get("output")

        if data is None:
            raise RuntimeError("No structured JSON found in OpenAI response")

        validate_invoice_extraction(data)
        return data

    def _build_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        base = (
            "Extrae los siguientes campos de la factura PDF adjunta. "
            "Devuelve un JSON estricto con el siguiente esquema: "
            "tipo_documento, nombre_proveedor, nif_proveedor, nombre_cliente, nif_cliente, cp_cliente, numero_factura, fecha_factura, subtotal, iva, total, confidence, warnings, evidence_snippets. "
            "No inventes datos. Si un campo no está, pon null. "
            "Enumera warnings si hay dudas. "
            "Incluye evidence_snippets con los fragmentos de texto que justifiquen cada campo. "
            "No confundas NIF proveedor/cliente. "
            "No aceptes proveedor basura OCR. "
            "Si es ticket sin destinatario, marca como no válido fiscalmente. "
            "No inventes base/IVA si es no_fiscal. "
        )
        if context:
            base += f"\nContexto cliente: {context}"
        return base
