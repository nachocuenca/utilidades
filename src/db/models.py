from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

INVOICE_DB_FIELDS = (
    "archivo",
    "ruta_archivo",
    "hash_archivo",
    "parser_usado",
    "extractor_origen",
    "requiere_revision_manual",
    "motivo_revision",
    "carpeta_origen",
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
    "texto_crudo",
)


@dataclass(slots=True, kw_only=True)
class InvoiceUpsertData:
    archivo: str
    ruta_archivo: str
    hash_archivo: str
    parser_usado: str = "generic"
    extractor_origen: str = "unknown"
    requiere_revision_manual: bool = False
    motivo_revision: str | None = None
    carpeta_origen: str | None = None
    nombre_proveedor: str | None = None
    nif_proveedor: str | None = None
    nombre_cliente: str | None = None
    nif_cliente: str | None = None
    cp_cliente: str | None = None
    numero_factura: str | None = None
    fecha_factura: str | None = None
    subtotal: float | None = None
    iva: float | None = None
    total: float | None = None
    texto_crudo: str = ""

    def as_db_dict(self) -> dict[str, Any]:
        payload = {field_name: getattr(self, field_name) for field_name in INVOICE_DB_FIELDS}
        payload["requiere_revision_manual"] = int(bool(payload["requiere_revision_manual"]))
        return payload


@dataclass(slots=True, kw_only=True)
class InvoiceRecord:
    id: int
    archivo: str
    ruta_archivo: str
    hash_archivo: str
    parser_usado: str
    extractor_origen: str
    requiere_revision_manual: bool
    motivo_revision: str | None
    carpeta_origen: str | None
    nombre_proveedor: str | None
    nif_proveedor: str | None
    nombre_cliente: str | None
    nif_cliente: str | None
    cp_cliente: str | None
    numero_factura: str | None
    fecha_factura: str | None
    subtotal: float | None
    iva: float | None
    total: float | None
    texto_crudo: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "InvoiceRecord":
        return cls(
            id=int(row["id"]),
            archivo=row["archivo"],
            ruta_archivo=row["ruta_archivo"],
            hash_archivo=row["hash_archivo"],
            parser_usado=row["parser_usado"],
            extractor_origen=row["extractor_origen"],
            requiere_revision_manual=bool(row["requiere_revision_manual"]),
            motivo_revision=row["motivo_revision"],
            carpeta_origen=row["carpeta_origen"],
            nombre_proveedor=row["nombre_proveedor"],
            nif_proveedor=row["nif_proveedor"],
            nombre_cliente=row["nombre_cliente"],
            nif_cliente=row["nif_cliente"],
            cp_cliente=row["cp_cliente"],
            numero_factura=row["numero_factura"],
            fecha_factura=row["fecha_factura"],
            subtotal=row["subtotal"],
            iva=row["iva"],
            total=row["total"],
            texto_crudo=row["texto_crudo"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )