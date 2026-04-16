from typing import Any, Dict
from src.ai.schemas import validate_invoice_extraction

class InvoiceAIValidator:
    @staticmethod
    def validate(data: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Returns (is_valid, warnings)
        """
        warnings = []
        try:
            validate_invoice_extraction(data)
        except Exception as e:
            return False, [f"Schema validation failed: {e}"]

        # 1. VALIDACIÓN CONTABLE
        subtotal = data.get("subtotal")
        iva = data.get("iva")
        total = data.get("total")
        if subtotal is not None and iva is not None and total is not None:
            if abs((subtotal + iva) - total) > 0.02:
                warnings.append("Subtotal + IVA no cuadra con Total.")

        # 2. VALIDACIÓN DE ROLES
        if data.get("nif_proveedor") and data.get("nif_cliente"):
            if data["nif_proveedor"] == data["nif_cliente"]:
                warnings.append("NIF proveedor y cliente coinciden.")
        if data.get("nombre_proveedor"):
            np = data["nombre_proveedor"].lower() if data["nombre_proveedor"] else ""
            if any(x in np for x in ["página", "slogan", "dirección", "promoción", "footer", "cabecera"]):
                warnings.append("Nombre proveedor parece basura OCR o línea no válida.")

        # 3. VALIDACIÓN DOCUMENTAL
        if data.get("tipo_documento") == "ticket" and not data.get("nif_cliente"):
            warnings.append("Ticket sin destinatario identificado. No válido fiscalmente.")
        if data.get("tipo_documento") == "no_fiscal":
            if data.get("subtotal") or data.get("iva") or data.get("total"):
                warnings.append("Documento no fiscal no debe tener base/IVA/total.")

        # 4. VALIDACIÓN DE CONFIANZA
        if data.get("confidence", 1.0) < 0.6:
            warnings.append("Confianza IA baja.")

        is_valid = len(warnings) == 0
        return is_valid, warnings
