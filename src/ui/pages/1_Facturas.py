from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.parsers.registry import get_parser_registry
from src.ui.components import (
    build_invoice_option_label,
    get_invoice_service,
    render_export_download,
    render_scan_summary,
    render_summary_metrics,
)

st.title("Facturas")

service = get_invoice_service()
registry = get_parser_registry()

if "invoice_search" not in st.session_state:
    st.session_state["invoice_search"] = ""

if "selected_invoice_id" not in st.session_state:
    st.session_state["selected_invoice_id"] = None

search = st.text_input(
    "Buscar",
    value=st.session_state["invoice_search"],
    placeholder="Proveedor, cliente, NIF, numero, archivo...",
)
st.session_state["invoice_search"] = search

parser_options = ["auto", *registry.list_names()]

control_col1, control_col2 = st.columns([2, 1])
with control_col1:
    selected_parser = st.selectbox(
        "Parser para el reescaneo",
        options=parser_options,
        index=0,
        format_func=lambda item: "auto" if item == "auto" else item,
    )

with control_col2:
    skip_known = st.toggle("Omitir ya procesadas", value=False)

button_col1, button_col2, button_col3 = st.columns(3)

with button_col1:
    if st.button("Reescanear carpeta", use_container_width=True):
        summary = service.rescan_inbox(
            parser_name=None if selected_parser == "auto" else selected_parser,
            recursive=False,
            skip_known=skip_known,
        )
        st.session_state["last_scan_summary"] = summary

with button_col2:
    if st.button("Exportar CSV", use_container_width=True):
        csv_path = service.export_csv(search=search or None)
        st.session_state["last_csv_export"] = str(csv_path)

with button_col3:
    if st.button("Exportar XLSX", use_container_width=True):
        xlsx_path = service.export_xlsx(search=search or None)
        st.session_state["last_xlsx_export"] = str(xlsx_path)

render_scan_summary(st.session_state.get("last_scan_summary"))
render_summary_metrics(service, search=search or None)

download_col1, download_col2 = st.columns(2)
with download_col1:
    render_export_download(
        st.session_state.get("last_csv_export"),
        label="Descargar CSV",
        mime="text/csv",
    )

with download_col2:
    render_export_download(
        st.session_state.get("last_xlsx_export"),
        label="Descargar XLSX",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

dataframe = service.list_invoices_dataframe(
    search=search or None,
    visible_only=True,
)

st.subheader("Tabla de facturas")

if dataframe.empty:
    st.info("No hay facturas guardadas todavia.")
else:
    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )

    rows = dataframe.to_dict(orient="records")
    invoice_ids = [int(row["id"]) for row in rows]
    label_map = {int(row["id"]): build_invoice_option_label(row) for row in rows}

    current_selected = st.session_state.get("selected_invoice_id")
    default_index = 0
    if current_selected in invoice_ids:
        default_index = invoice_ids.index(current_selected)

    st.subheader("Abrir detalle")

    selected_invoice_id = st.selectbox(
        "Selecciona una factura",
        options=invoice_ids,
        index=default_index,
        format_func=lambda invoice_id: label_map[invoice_id],
    )

    st.session_state["selected_invoice_id"] = int(selected_invoice_id)

    if st.button("Abrir detalle", use_container_width=True):
        st.switch_page("src/ui/pages/2_Detalle.py")

st.caption(f"Carpeta monitorizada: {Path(service.settings.inbox_dir)}")