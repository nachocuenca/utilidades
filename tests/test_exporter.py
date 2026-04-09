from __future__ import annotations

import codecs
import csv
from pathlib import Path

import pandas as pd
import pytest

from src.db.models import InvoiceUpsertData
from src.db.repositories import InvoiceRepository
from src.services.exporter import EXPORT_COLUMNS, InvoiceExporter


def test_export_csv_uses_spanish_excel_format_for_monetary_columns(tmp_path: Path) -> None:
    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    exporter = InvoiceExporter(repository=repository, export_dir=tmp_path / "exports")

    repository.upsert(
        InvoiceUpsertData(
            archivo="factura_principal.pdf",
            ruta_archivo=str(tmp_path / "factura_principal.pdf"),
            hash_archivo="hash-export-1",
            nombre_proveedor="Proveedor; SL",
            numero_factura="F-2026-0001",
            fecha_factura="09-04-2026",
            subtotal=1303.0,
            iva=273.63,
            total=1576.63,
            texto_crudo="Linea 1; detalle\nLinea 2",
        )
    )
    repository.upsert(
        InvoiceUpsertData(
            archivo="ticket_total.pdf",
            ruta_archivo=str(tmp_path / "ticket_total.pdf"),
            hash_archivo="hash-export-2",
            tipo_documento="ticket",
            parser_usado="generic_ticket",
            nombre_proveedor="Proveedor secundario",
            numero_factura="TK-2026-0002",
            fecha_factura="08-04-2026",
            subtotal=None,
            iva=None,
            total=48.76,
            texto_crudo="Ticket simple",
        )
    )

    output_path = exporter.export_csv()

    assert output_path.read_bytes().startswith(codecs.BOM_UTF8)

    with output_path.open("r", encoding="utf-8-sig", newline="") as file_handler:
        rows = list(csv.DictReader(file_handler, delimiter=";"))

    assert len(rows) == 2
    assert rows[0]["subtotal"] == "1303,00"
    assert rows[0]["iva"] == "273,63"
    assert rows[0]["total"] == "1576,63"
    assert rows[0]["fecha_factura"] == "09-04-2026"
    assert rows[0]["nombre_proveedor"] == "Proveedor; SL"
    assert rows[0]["texto_crudo"] == "Linea 1; detalle\nLinea 2"
    assert rows[1]["subtotal"] == ""
    assert rows[1]["iva"] == ""
    assert rows[1]["total"] == "48,76"

    exported = pd.read_csv(output_path, sep=";", decimal=",", encoding="utf-8-sig")

    assert list(exported.columns) == EXPORT_COLUMNS
    assert exported.loc[0, "subtotal"] == pytest.approx(1303.0)
    assert exported.loc[0, "iva"] == pytest.approx(273.63)
    assert exported.loc[0, "total"] == pytest.approx(1576.63)
    assert pd.isna(exported.loc[1, "subtotal"])
    assert pd.isna(exported.loc[1, "iva"])
    assert exported.loc[1, "total"] == pytest.approx(48.76)


def test_export_csv_respects_document_type_filter(tmp_path: Path) -> None:
    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    exporter = InvoiceExporter(repository=repository, export_dir=tmp_path / "exports")

    repository.upsert(
        InvoiceUpsertData(
            archivo="factura_filtrada.pdf",
            ruta_archivo=str(tmp_path / "factura_filtrada.pdf"),
            hash_archivo="hash-filter-1",
            tipo_documento="factura",
            subtotal=118.04,
            iva=24.79,
            total=142.83,
            texto_crudo="Factura",
        )
    )
    repository.upsert(
        InvoiceUpsertData(
            archivo="ticket_filtrado.pdf",
            ruta_archivo=str(tmp_path / "ticket_filtrado.pdf"),
            hash_archivo="hash-filter-2",
            tipo_documento="ticket",
            total=9.99,
            texto_crudo="Ticket",
        )
    )

    output_path = exporter.export_csv(tipo_documento="factura")

    with output_path.open("r", encoding="utf-8-sig", newline="") as file_handler:
        rows = list(csv.DictReader(file_handler, delimiter=";"))

    assert len(rows) == 1
    assert rows[0]["tipo_documento"] == "factura"
    assert rows[0]["subtotal"] == "118,04"
    assert rows[0]["iva"] == "24,79"
    assert rows[0]["total"] == "142,83"
