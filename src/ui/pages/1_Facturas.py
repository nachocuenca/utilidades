from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.parsers.registry import get_parser_registry
from src.ui.components import (
    build_invoice_option_label,
    get_common_scan_dirs,
    get_invoice_service,
    open_folder_dialog,
    render_export_download,
    render_scan_summary,
    render_summary_metrics,
)

st.title("Facturas y tickets")

service = get_invoice_service()
registry = get_parser_registry()

if "invoice_search" not in st.session_state:
    st.session_state["invoice_search"] = ""

if "selected_invoice_id" not in st.session_state:
    st.session_state["selected_invoice_id"] = None

if "scan_dir_input" not in st.session_state:
    st.session_state["scan_dir_input"] = str(service.settings.inbox_dir)

if "confirm_clear_results" not in st.session_state:
    st.session_state["confirm_clear_results"] = False

search = st.text_input(
    "Buscar",
    value=st.session_state["invoice_search"],
    placeholder="Proveedor, cliente, NIF, numero, archivo...",
)
st.session_state["invoice_search"] = search

st.subheader("Origen de escaneo")

scan_dir_input = st.text_input(
    "Carpeta a escanear",
    value=st.session_state["scan_dir_input"],
    placeholder=r"C:\Users\ignac\Downloads\Facturas",
)
st.session_state["scan_dir_input"] = scan_dir_input

common_dirs = get_common_scan_dirs(service.settings.inbox_dir)

path_col1, path_col2, path_col3, path_col4 = st.columns(4)

with path_col1:
    if st.button("Elegir carpeta", use_container_width=True):
        selected = open_folder_dialog(scan_dir_input)
        if selected:
            st.session_state["scan_dir_input"] = selected
            st.rerun()

with path_col2:
    if st.button("Inbox", use_container_width=True):
        st.session_state["scan_dir_input"] = common_dirs["inbox"]
        st.rerun()

with path_col3:
    if st.button("Descargas", use_container_width=True):
        st.session_state["scan_dir_input"] = common_dirs["descargas"]
        st.rerun()

with path_col4:
    if st.button("Escritorio", use_container_width=True):
        st.session_state["scan_dir_input"] = common_dirs["escritorio"]
        st.rerun()

resolved_scan_dir: Path | None = None
scan_dir_error: str | None = None

try:
    resolved_scan_dir = service.resolve_scan_dir(scan_dir_input)
    if not resolved_scan_dir.exists():
        scan_dir_error = f"La carpeta no existe: {resolved_scan_dir}"
    elif not resolved_scan_dir.is_dir():
        scan_dir_error = f"La ruta no es una carpeta: {resolved_scan_dir}"
except Exception as error:
    scan_dir_error = str(error)

if scan_dir_error:
    st.warning(scan_dir_error)
else:
    st.caption(f"Carpeta activa: {resolved_scan_dir}")

parser_options = ["auto", *registry.list_names()]
tipo_options = ["todos", "factura", "ticket"]

control_col1, control_col2, control_col3, control_col4, control_col5 = st.columns([2, 1, 1, 1, 1])
with control_col1:
    selected_parser = st.selectbox(
        "Parser para el reescaneo",
        options=parser_options,
        index=0,
        format_func=lambda item: "auto" if item == "auto" else item,
    )

with control_col2:
    skip_known = st.toggle("Omitir ya procesadas", value=False)

with control_col3:
    recursive = st.toggle("Recursivo", value=True)

with control_col4:
    only_manual_review = st.toggle("Solo revisar", value=False)

with control_col5:
    selected_document_type = st.selectbox(
        "Tipo",
        options=tipo_options,
        index=0,
    )

document_type_filter = None if selected_document_type == "todos" else selected_document_type

button_col1, button_col2, button_col3, button_col4 = st.columns(4)

with button_col1:
    if st.button("Reescanear carpeta", use_container_width=True):
        if scan_dir_error:
            st.error("Corrige la carpeta de escaneo antes de continuar.")
        else:
            summary = service.rescan_inbox(
                parser_name=None if selected_parser == "auto" else selected_parser,
                recursive=recursive,
                skip_known=skip_known,
                inbox_dir=resolved_scan_dir,
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

with button_col4:
    if st.button("Vaciar resultados", use_container_width=True):
        if not st.session_state.get("confirm_clear_results", False):
            st.error("Marca antes la confirmacion de vaciado.")
        else:
            total_deleted = service.clear_all_results()
            st.session_state["selected_invoice_id"] = None
            st.session_state["last_scan_summary"] = None
            st.success(f"Se han eliminado {total_deleted} registros de la base de datos.")

st.toggle(
    "Confirmo vaciar resultados de la base de datos",
    key="confirm_clear_results",
)

st.caption("Vaciar resultados borra solo los registros escaneados. No borra tus PDFs.")

render_scan_summary(st.session_state.get("last_scan_summary"))
render_summary_metrics(
    service,
    search=search or None,
    tipo_documento=document_type_filter,
)

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
    only_manual_review=True if only_manual_review else None,
    tipo_documento=document_type_filter,
)

st.subheader("Tabla de documentos")

if dataframe.empty:
    st.info("No hay resultados guardados todavia.")
else:
    dataframe = dataframe.copy()
    dataframe["requiere_revision_manual"] = dataframe["requiere_revision_manual"].map(
        lambda value: "Sí" if bool(value) else "No"
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )

    rows = service.list_invoices_dataframe(
        search=search or None,
        visible_only=False,
        only_manual_review=True if only_manual_review else None,
        tipo_documento=document_type_filter,
    ).to_dict(orient="records")

    invoice_ids = [int(row["id"]) for row in rows]
    label_map = {int(row["id"]): build_invoice_option_label(row) for row in rows}

    current_selected = st.session_state.get("selected_invoice_id")
    default_index = 0
    if current_selected in invoice_ids:
        default_index = invoice_ids.index(current_selected)

    st.subheader("Abrir detalle")

    selected_invoice_id = st.selectbox(
        "Selecciona un documento",
        options=invoice_ids,
        index=default_index,
        format_func=lambda invoice_id: label_map[invoice_id],
    )

    st.session_state["selected_invoice_id"] = int(selected_invoice_id)

    if st.button("Abrir detalle", use_container_width=True):
        st.switch_page("src/ui/pages/2_Detalle.py")

st.caption(f"Ruta por defecto configurada: {Path(service.settings.inbox_dir)}")