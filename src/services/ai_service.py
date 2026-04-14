from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict, List, Optional, Tuple

from src.ai.openai_extractor import OpenAIExtractor
from src.ai.validator import InvoiceAIValidator
from src.ai.local_extractor import LocalExtractor
from src.db.repositories import InvoiceRepository
from src.db.models import InvoiceUpsertData
from src.utils.hashing import sha256_file
from src.utils.dates import normalize_date


class AIService:
    def __init__(self, db_path: str | Path | None = None, api_key: Optional[str] = None, model: Optional[str] = None, use_local_model: Optional[bool] = None):
        self.repo = InvoiceRepository(db_path)
        self.validator = InvoiceAIValidator()

        # decide extractor: local model if requested or no API key provided
        import os

        env_local = os.getenv("LOCAL_MODEL_ENABLED")
        if use_local_model is None:
            use_local_model = (env_local or "").lower() in ("1", "true", "yes")

        if use_local_model or not (api_key or os.getenv("OPENAI_API_KEY")):
            # use LocalExtractor (no external API key required)
            self.extractor = LocalExtractor()
        else:
            self.extractor = OpenAIExtractor(api_key=api_key, model=model)

    def process_file(self, pdf_path: str | Path, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)
        result = self.extractor.extract_from_pdf(pdf_path, context=context)
        # Normalize minimal fields before validation
        norm = self._normalize_extraction(result)
        is_valid, warnings = self.validator.validate(norm)

        # Attach validation metadata
        result_meta = {
            "extraction": norm,
            "is_valid": is_valid,
            "warnings": warnings,
        }
        return result_meta

    def _normalize_extraction(self, extraction: Dict[str, Any]) -> Dict[str, Any]:
        """Apply minimal normalization required before validation.

        - normalize `tipo_documento` to expected enum values
        - sanitize NIFs (remove spaces and dashes)
        - normalize `fecha_factura` using `normalize_date`
        - ensure numeric amounts are floats if possible
        """
        data = dict(extraction) if extraction else {}

        # tipo_documento normalization
        td = (data.get("tipo_documento") or "").strip()
        td_up = td.upper().replace(" ", "_")
        if td_up in {"FACTURA", "FACTURA_ELECTRONICA"}:
            data["tipo_documento"] = "factura"
        elif td_up in {"TICKET", "TICKET_FACTURA"}:
            data["tipo_documento"] = "ticket"
        elif td_up in {"NO_FISCAL", "NO-FISCAL", "NO FISCAL", "NOFISCAL"}:
            data["tipo_documento"] = "no_fiscal"
        else:
            # fallback: lowercase value or 'desconocido'
            low = td.lower()
            data["tipo_documento"] = low if low in {"factura", "ticket", "no_fiscal", "desconocido"} else (low or "desconocido")

        # NIF normalization helper
        def clean_nif(v: Any) -> Any:
            if not v:
                return None
            s = str(v).upper()
            s = s.replace("-", "").replace(" ", "").replace(".", "")
            return s

        data["nif_proveedor"] = clean_nif(data.get("nif_proveedor"))
        data["nif_cliente"] = clean_nif(data.get("nif_cliente"))

        # fecha_factura normalization
        try:
            data["fecha_factura"] = normalize_date(data.get("fecha_factura"))
        except Exception:
            # leave original if normalization fails
            pass

        # amounts: safe cast to float
        for key in ("subtotal", "iva", "total"):
            val = data.get(key)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                data[key] = float(val)
                continue
            try:
                s = str(val).strip().replace('.', '').replace(',', '.') if isinstance(val, str) and (',' in val or '.' in val) else str(val)
                data[key] = float(s)
            except Exception:
                # keep original if cannot parse
                data[key] = val

        return data

    def process_many(self, pdf_paths: List[str | Path], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for p in pdf_paths:
            try:
                results.append({"path": str(p), "result": self.process_file(p, context=context)})
            except Exception as e:
                results.append({"path": str(p), "error": str(e)})
        return results

    def save_result(self, pdf_path: str | Path, extraction: Dict[str, Any], requiere_revision_manual: bool, motivo_revision: Optional[str] = None, carpeta_origen: Optional[str] = None) -> int:
        pdf_path = Path(pdf_path)
        file_hash = sha256_file(pdf_path)

        texto_crudo = json.dumps(extraction, ensure_ascii=False)

        upsert = InvoiceUpsertData(
            archivo=pdf_path.name,
            ruta_archivo=str(pdf_path.resolve()),
            hash_archivo=file_hash,
            tipo_documento=extraction.get("tipo_documento", "desconocido") or "desconocido",
            parser_usado=("openai_gpt-4o" if getattr(self.extractor, "__class__", None) and self.extractor.__class__.__name__ == "OpenAIExtractor" else "local_heuristic"),
            extractor_origen=("openai" if getattr(self.extractor, "__class__", None) and self.extractor.__class__.__name__ == "OpenAIExtractor" else "local"),
            requiere_revision_manual=bool(requiere_revision_manual),
            motivo_revision=motivo_revision,
            carpeta_origen=carpeta_origen,
            nombre_proveedor=extraction.get("nombre_proveedor"),
            nif_proveedor=extraction.get("nif_proveedor"),
            nombre_cliente=extraction.get("nombre_cliente"),
            nif_cliente=extraction.get("nif_cliente"),
            cp_cliente=extraction.get("cp_cliente"),
            numero_factura=extraction.get("numero_factura"),
            fecha_factura=extraction.get("fecha_factura"),
            subtotal=extraction.get("subtotal"),
            iva=extraction.get("iva"),
            total=extraction.get("total"),
            texto_crudo=texto_crudo,
        )

        return self.repo.upsert(upsert)
