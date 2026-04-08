from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from src.db.database import init_database
from src.services.invoice_service import InvoiceService
from src.services.scanner import ScanSummary


@st.cache_resource
def get_invoice_service() -> InvoiceService:
    init_database()
    return InvoiceService()


def open_folder_dialog(initial_dir: str | None = None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        selected = filedialog.askdirectory(
            initialdir=initial_dir if initial_dir else None,
            title="Selecciona carpeta de escaneo",
        )

        root.destroy()

        if not selected:
            return None

        return str(Path(selected).resolve())
    except Exception:
        return None


def get_common_scan_dirs(default_inbox_dir: str | Path) -> dict[str, str]:
    home = Path.home()

    candidates = {
        "inbox": str(Path(default_inbox_dir).resolve()),
        "descargas": str((home / "Downloads").resolve()),
        "escritorio": str((home / "Desktop").resolve()),
        "documentos": str((home / "Documents").resolve()),
    }

    return candidates


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


def format_bool_badge(value: object | None) -> str:
    return "Sí" if bool(value) else "No"


def build_invoice_option_label(row: Mapping[str, Any]) -> str:
    invoice_id = format_text(row.get("id"))
    tipo_documento = format_text(row.get("tipo_documento"))
    archivo = format_text(row.get("archivo"))
    proveedor = format_text(row.get("nombre_proveedor"))
    fecha = format_text(row.get("fecha_factura"))
    total = format_amount(row.get("total"))

    return f"ID {invoice_id} | {tipo_documento} | {archivo} | {proveedor} | {fecha} | {total}"


def render_inline_metrics(items: list[tuple[str, str]]) -> None:
    if not items:
        return

    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.caption(label)
            st.markdown(f"**{value}**")


def render_summary_metrics(
    service: InvoiceService,
    search: str | None = None,
    tipo_documento: str | None = None,
) -> None:
    dataframe = service.list_invoices_dataframe(
        search=search,
        visible_only=False,
        tipo_documento=tipo_documento,
    )

    total_documentos = len(dataframe.index)
    total_importe = 0.0
    total_iva = 0.0

    if not dataframe.empty:
        total_importe = pd.to_numeric(dataframe["total"], errors="coerce").fillna(0).sum()
        total_iva = pd.to_numeric(dataframe["iva"], errors="coerce").fillna(0).sum()

    render_inline_metrics(
        [
            ("Documentos", str(total_documentos)),
            ("Suma total", format_amount(total_importe)),
            ("Suma IVA", format_amount(total_iva)),
        ]
    )


def render_scan_summary(summary: ScanSummary | None) -> None:
    if summary is None:
        return

    st.caption("Último reescaneo")

    render_inline_metrics(
        [
            ("Encontrados", str(summary.total_encontrados)),
            ("Procesados", str(summary.procesados)),
            ("Creados", str(summary.creados)),
            ("Actualizados", str(summary.actualizados)),
            ("Omitidos", str(summary.omitidos)),
            ("Fallidos", str(summary.fallidos)),
        ]
    )

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