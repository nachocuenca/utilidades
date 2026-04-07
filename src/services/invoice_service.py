from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import get_settings
from src.db.models import InvoiceRecord
from src.db.repositories import InvoiceRepository
from src.services.exporter import InvoiceExporter
from src.services.scanner import InvoiceScanner, ScanSummary

VISIBLE_TABLE_COLUMNS = [
    "id",
    "archivo",
    "parser_usado",
    "extractor_origen",
    "requiere_revision_manual",
    "nombre_proveedor",
    "nombre_cliente",
    "nif_cliente",
    "cp_cliente",
    "numero_factura",
    "fecha_factura",
    "subtotal",
    "iva",
    "total",
    "created_at",
    "updated_at",
]


class InvoiceService:
    def __init__(self, repository: InvoiceRepository | None = None) -> None:
        self.settings = get_settings()
        self.repository = repository or InvoiceRepository()
        self.scanner = InvoiceScanner(
            repository=self.repository,
            inbox_dir=self.settings.inbox_dir,
        )
        self.exporter = InvoiceExporter(
            repository=self.repository,
            export_dir=self.settings.export_dir,
        )

    def resolve_scan_dir(self, inbox_dir: str | Path | None = None) -> Path:
        return self.scanner.resolve_scan_dir(inbox_dir)

    def rescan_inbox(
        self,
        parser_name: str | None = None,
        recursive: bool = False,
        skip_known: bool = False,
        inbox_dir: str | Path | None = None,
    ) -> ScanSummary:
        return self.scanner.scan(
            parser_name=parser_name,
            recursive=recursive,
            skip_known=skip_known,
            inbox_dir=inbox_dir,
        )

    def scan_single_file(
        self,
        pdf_path: str | Path,
        parser_name: str | None = None,
    ) -> int:
        return self.scanner.scan_file(
            pdf_path=pdf_path,
            parser_name=parser_name,
        )

    def list_invoices(
        self,
        search: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        only_manual_review: bool | None = None,
    ) -> list[InvoiceRecord]:
        return self.repository.list_invoices(
            search=search,
            limit=limit,
            offset=offset,
            only_manual_review=only_manual_review,
        )

    def count_invoices(self, search: str | None = None, only_manual_review: bool | None = None) -> int:
        return self.repository.count(
            search=search,
            only_manual_review=only_manual_review,
        )

    def get_invoice(self, invoice_id: int) -> InvoiceRecord | None:
        return self.repository.get_by_id(invoice_id)

    def get_raw_text(self, invoice_id: int) -> str:
        record = self.get_invoice(invoice_id)
        if record is None:
            raise ValueError(f"No existe la factura con id {invoice_id}")
        return record.texto_crudo

    def list_invoices_dataframe(
        self,
        search: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        visible_only: bool = True,
        only_manual_review: bool | None = None,
    ) -> pd.DataFrame:
        records = self.list_invoices(
            search=search,
            limit=limit,
            offset=offset,
            only_manual_review=only_manual_review,
        )

        rows: list[dict[str, object | None]] = []
        for record in records:
            rows.append(
                {
                    "id": record.id,
                    "archivo": record.archivo,
                    "ruta_archivo": record.ruta_archivo,
                    "hash_archivo": record.hash_archivo,
                    "parser_usado": record.parser_usado,
                    "extractor_origen": record.extractor_origen,
                    "requiere_revision_manual": record.requiere_revision_manual,
                    "motivo_revision": record.motivo_revision,
                    "nombre_proveedor": record.nombre_proveedor,
                    "nombre_cliente": record.nombre_cliente,
                    "nif_cliente": record.nif_cliente,
                    "cp_cliente": record.cp_cliente,
                    "numero_factura": record.numero_factura,
                    "fecha_factura": record.fecha_factura,
                    "subtotal": record.subtotal,
                    "iva": record.iva,
                    "total": record.total,
                    "texto_crudo": record.texto_crudo,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            )

        dataframe = pd.DataFrame(rows)

        all_columns = [
            "id",
            "archivo",
            "ruta_archivo",
            "hash_archivo",
            "parser_usado",
            "extractor_origen",
            "requiere_revision_manual",
            "motivo_revision",
            "nombre_proveedor",
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

        if dataframe.empty:
            if visible_only:
                return pd.DataFrame(columns=VISIBLE_TABLE_COLUMNS)
            return pd.DataFrame(columns=all_columns)

        if visible_only:
            return dataframe[VISIBLE_TABLE_COLUMNS]

        return dataframe[all_columns]

    def get_invoice_detail(self, invoice_id: int) -> dict[str, object | None]:
        record = self.get_invoice(invoice_id)
        if record is None:
            raise ValueError(f"No existe la factura con id {invoice_id}")

        return {
            "id": record.id,
            "archivo": record.archivo,
            "ruta_archivo": record.ruta_archivo,
            "hash_archivo": record.hash_archivo,
            "parser_usado": record.parser_usado,
            "extractor_origen": record.extractor_origen,
            "requiere_revision_manual": record.requiere_revision_manual,
            "motivo_revision": record.motivo_revision,
            "nombre_proveedor": record.nombre_proveedor,
            "nombre_cliente": record.nombre_cliente,
            "nif_cliente": record.nif_cliente,
            "cp_cliente": record.cp_cliente,
            "numero_factura": record.numero_factura,
            "fecha_factura": record.fecha_factura,
            "subtotal": record.subtotal,
            "iva": record.iva,
            "total": record.total,
            "texto_crudo": record.texto_crudo,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def export_csv(self, search: str | None = None) -> Path:
        return self.exporter.export_csv(search=search)

    def export_xlsx(self, search: str | None = None) -> Path:
        return self.exporter.export_xlsx(search=search)