import jsonschema

INVOICE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "tipo_documento": {
            "type": "string",
            "enum": ["factura", "ticket", "no_fiscal", "desconocido"]
        },
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
        "warnings": {
            "type": "array",
            "items": {"type": "string"}
        },
        "evidence_snippets": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": [
        "tipo_documento", "nombre_proveedor", "nif_proveedor", "nombre_cliente", "nif_cliente", "cp_cliente", "numero_factura", "fecha_factura", "subtotal", "iva", "total", "confidence", "warnings", "evidence_snippets"
    ],
    "additionalProperties": False
}

def validate_invoice_extraction(data: dict) -> None:
    jsonschema.validate(instance=data, schema=INVOICE_EXTRACTION_SCHEMA)
