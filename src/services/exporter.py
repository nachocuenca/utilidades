from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import get_settings
from src.db.repositories import InvoiceRepository
from src.utils.files import build_export_path

EXPORT_COLUMNS = [
    "id",
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
    "created_at",
    "updated_at",
]


class InvoiceExporter:
    def __init__(
        self,
        repository: InvoiceRepository | None = None,
        export_dir: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository or InvoiceRepository()
        self.export_dir = Path(export_dir or settings.export_dir).resolve()

    def build_dataframe(self, search: str | None = None) -> pd.DataFrame:
        rows = self.repository.list_for_export(search=search)

        if not rows:
            return pd.DataFrame(columns=EXPORT_COLUMNS)

        dataframe = pd.DataFrame(rows)

        for column in EXPORT_COLUMNS:
            if column not in dataframe.columns:
                dataframe[column] = None

        return dataframe[EXPORT_COLUMNS]

    def export_csv(self, search: str | None = None) -> Path:
        dataframe = self.build_dataframe(search=search)
        output_path = build_export_path(
            export_dir=self.export_dir,
            prefix="facturas",
            extension="csv",
        )
        dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    def export_xlsx(self, search: str | None = None) -> Path:
        dataframe = self.build_dataframe(search=search)
        output_path = build_export_path(
            export_dir=self.export_dir,
            prefix="facturas",
            extension="xlsx",
        )
        dataframe.to_excel(output_path, index=False, engine="openpyxl")
        return output_path