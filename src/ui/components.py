from __future__ import annotations

from pathlib import Path
from typing import Mapping, Any

import pandas as pd
import streamlit as st

from src.db.database import init_database
from src.services.invoice_service import InvoiceService
from src.services.scanner import ScanSummary


@st.cache_resource
def get_invoice_service() -> InvoiceService:
    init_database()
    return InvoiceService()


def format_amount(value: object | None) -> str:
    if value is None or value == "":
        return "-"
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{numeric_value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def format_text(value: object | None, fallback: str = "-") -> str:
    if value is None:
        return fallback

    text = str(value).strip()
    return text if text else fallback


def build_invoice_option_label(row: Mapping[str, Any]) -> str:
    invoice_id = format_text(row.get("id"))
    archivo = format_text(row.get("archivo"))
    proveedor = format_text(row.get("nombre_proveedor"))
    cliente = format_text(row.get("nombre_cliente"))
    fecha = format_text(row.get("fecha_factura"))
    total = format_amount(row.get("total"))

    return f"ID {invoice_id} | {archivo} | {proveedor} | {cliente} | {fecha} | {total}"


def render_summary_metrics(service: InvoiceService, search: str | None = None) -> None:
    dataframe = service.list_invoices_dataframe(
        search=search,
        visible_only=False,
    )

    total_facturas = len(dataframe.index)
    total_importe = 0.0
    total_iva = 0.0

    if not dataframe.empty:
        total_importe = pd.to_numeric(dataframe["total"], errors="coerce").fillna(0).sum()
        total_iva = pd.to_numeric(dataframe["iva"], errors="coerce").fillna(0).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Facturas", total_facturas)
    col2.metric("Suma total", format_amount(total_importe))
    col3.metric("Suma IVA", format_amount(total_iva))


def render_scan_summary(summary: ScanSummary | None) -> None:
    if summary is None:
        return

    st.success("Reescaneo completado.")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Encontrados", summary.total_encontrados)
    col2.metric("Procesados", summary.procesados)
    col3.metric("Creados", summary.creados)
    col4.metric("Actualizados", summary.actualizados)
    col5.metric("Omitidos", summary.omitidos)
    col6.metric("Fallidos", summary.fallidos)

    if summary.errores:
        st.warning("Algunos archivos no se pudieron procesar.")
        error_rows = [
            {
                "archivo": item.archivo,
                "ruta_archivo": item.ruta_archivo,
                "error": item.error,
            }
            for item in summary.errores
        ]
        st.dataframe(pd.DataFrame(error_rows), use_container_width=True, hide_index=True)


def render_export_download(path_str: str | None, label: str, mime: str) -> None:
    if not path_str:
        return

    path = Path(path_str)
    if not path.exists():
        return

    st.success(f"Exportacion generada: {path}")

    with path.open("rb") as file_handler:
        st.download_button(
            label=label,
            data=file_handler.read(),
            file_name=path.name,
            mime=mime,
            use_container_width=True,
        )


def render_detail_field(label: str, value: object | None) -> None:
    st.markdown(f"**{label}**")
    st.write(format_text(value))