from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.parsers.registry import get_parser_registry
from src.ui.components import (
    build_invoice_option_label,
    get_invoice_service,
    open_folder_dialog,
    render_scan_summary,
    render_summary_metrics,
)

st.set_page_config(page_title="Utilidades Facturas", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.15rem;
        padding-bottom: 0.8rem;
    }

    h1 {
        margin-bottom: 0.7rem !important;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.45rem;
        align-items: end;
    }

    div[data-testid="stButton"] > button {
        min-height: 2.3rem;
        padding-top: 0.35rem;
        padding-bottom: 0.35rem;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        min-height: 2.3rem;
    }

    div[data-testid="stCaptionContainer"] {
        margin-bottom: 0rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
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

search_col, tipo_col = st.columns([8, 2])

with search_col:
    search = st.text_input(
        "Buscar",
        value=st.session_state["invoice_search"],
        placeholder="Proveedor, cliente, NIF, numero, archivo...",
        label_visibility="collapsed",
    )
    st.session_state["invoice_search"] = search

tipo_options = ["todos", "factura", "ticket", "no_fiscal"]
with tipo_col:
    selected_document_type = st.selectbox(
        "Tipo",
        options=tipo_options,
        index=0,
        label_visibility="collapsed",
    )

document_type_filter = None if selected_document_type == "todos" else selected_document_type

scan_dir_input = st.session_state["scan_dir_input"]
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

parser_options = ["auto", *registry.list_names()]

control_col1, control_col2, control_col3, control_col4, control_col5, control_col6, control_col7 = st.columns(
    [5.8, 1.8, 0.9, 1.0, 1.3, 1.2, 1.1]
)

with control_col1:
    scan_dir_input = st.text_input(
        "Carpeta",
        value=st.session_state["scan_dir_input"],
        placeholder=r"C:\Users\ignac\Downloads\Facturas",
        label_visibility="collapsed",
    )
    st.session_state["scan_dir_input"] = scan_dir_input

with control_col2:
    selected_parser = st.selectbox(
        "Parser",
        options=parser_options,
        index=0,
        format_func=lambda item: "auto" if item == "auto" else item,
        label_visibility="collapsed",
    )

with control_col3:
    if st.button("Elegir", use_container_width=True):
        selected = open_folder_dialog(scan_dir_input)
        if selected:
            st.session_state["scan_dir_input"] = selected
            st.rerun()

with control_col4:
    recursive = st.toggle("Recursivo", value=True)

with control_col5:
    skip_known = st.toggle("Omitir conocidas", value=False)

with control_col6:
    if st.button("Reescanear", use_container_width=True):
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

with control_col7:
    if st.button("Vaciar", use_container_width=True):
        total_deleted = service.clear_all_results()
        st.session_state["selected_invoice_id"] = None
        st.session_state["last_scan_summary"] = None
        st.success(f"Se han eliminado {total_deleted} registros de la base de datos.")

scan_dir_input = st.session_state["scan_dir_input"]

try:
    resolved_scan_dir = service.resolve_scan_dir(scan_dir_input)
    if not resolved_scan_dir.exists():
        scan_dir_error = f"La carpeta no existe: {resolved_scan_dir}"
    elif not resolved_scan_dir.is_dir():
        scan_dir_error = f"La ruta no es una carpeta: {resolved_scan_dir}"
    else:
        scan_dir_error = None
except Exception as error:
    scan_dir_error = str(error)

if scan_dir_error:
    st.warning(scan_dir_error)

render_scan_summary(st.session_state.get("last_scan_summary"))

dataframe = service.list_invoices_dataframe(
    search=search or None,
    visible_only=False,
    tipo_documento=document_type_filter,
)

st.subheader("Tabla de documentos")

if dataframe.empty:
    st.info("No hay resultados guardados todavia.")
else:
    dataframe = dataframe.copy()

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
        column_config={
            "tipo_documento": "Tipo",
            "parser_usado": "Parser",
            "requiere_revision_manual": st.column_config.CheckboxColumn("Revisión"),
            "nombre_proveedor": "Nombre proveedor",
            "nif_proveedor": "NIF proveedor",
            "numero_factura": "Número factura",
            "fecha_factura": "Fecha factura",
            "subtotal": st.column_config.NumberColumn("Base", format="%.2f"),
            "iva": st.column_config.NumberColumn("IVA", format="%.2f"),
            "total": st.column_config.NumberColumn("Total", format="%.2f"),
            "nombre_cliente": "Nombre cliente",
            "nif_cliente": "NIF cliente",
            "motivo_revision": "Motivo revisión",
            "carpeta_origen": "Carpeta origen",
            "archivo": "Archivo",
            "extractor_origen": "Extractor",
        },
    )

    st.caption("Resumen")
    render_summary_metrics(
        service,
        search=search or None,
        tipo_documento=document_type_filter,
    )

    rows = service.list_invoices_dataframe(
        search=search or None,
        visible_only=False,
        tipo_documento=document_type_filter,
    ).to_dict(orient="records")

    invoice_ids = [int(row["id"]) for row in rows]
    label_map = {int(row["id"]): build_invoice_option_label(row) for row in rows}

    current_selected = st.session_state.get("selected_invoice_id")
    default_index = 0
    if current_selected in invoice_ids:
        default_index = invoice_ids.index(current_selected)

    detail_col1, detail_col2 = st.columns([5, 1.2])

    with detail_col1:
        selected_invoice_id = st.selectbox(
            "Selecciona un documento",
            options=invoice_ids,
            index=default_index,
            format_func=lambda invoice_id: label_map[invoice_id],
            label_visibility="collapsed",
        )

    with detail_col2:
        open_detail = st.button("Abrir detalle", use_container_width=True)

    st.session_state["selected_invoice_id"] = int(selected_invoice_id)

    if open_detail:
        st.switch_page("src/ui/pages/2_Detalle.py")

st.caption(f"Ruta por defecto configurada: {Path(service.settings.inbox_dir)}")