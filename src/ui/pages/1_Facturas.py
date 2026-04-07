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

st.set_page_config(page_title="Utilidades Facturas", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
    }

    h1 {
        margin-bottom: 0.6rem !important;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.5rem;
        align-items: end;
    }

    div[data-testid="stButton"] > button {
        min-height: 2.35rem;
        padding-top: 0.35rem;
        padding-bottom: 0.35rem;
    }

    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stToggle"] label {
        font-size: 0.88rem !important;
    }

    div[data-testid="stCaptionContainer"] {
        margin-bottom: 0rem;
    }

    hr {
        margin-top: 0.5rem;
        margin-bottom: 0.75rem;
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

if "confirm_clear_results" not in st.session_state:
    st.session_state["confirm_clear_results"] = False

parser_options = ["auto", *registry.list_names()]
tipo_options = ["todos", "factura", "ticket"]

search_col, tipo_col, revisar_col = st.columns([7, 1.8, 1.2])

with search_col:
    search = st.text_input(
        "Buscar",
        value=st.session_state["invoice_search"],
        placeholder="Proveedor, cliente, NIF, numero, archivo...",
        label_visibility="collapsed",
    )
    st.session_state["invoice_search"] = search

with tipo_col:
    selected_document_type = st.selectbox(
        "Tipo",
        options=tipo_options,
        index=0,
        label_visibility="collapsed",
    )

with revisar_col:
    only_manual_review = st.toggle("Solo revisar", value=False)

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

common_dirs = get_common_scan_dirs(service.settings.inbox_dir)

path_col, choose_col, inbox_col, down_col, desk_col, docs_col = st.columns([7, 1.1, 1, 1, 1, 1])

with path_col:
    scan_dir_input = st.text_input(
        "Carpeta a escanear",
        value=st.session_state["scan_dir_input"],
        placeholder=r"C:\Users\ignac\Downloads\Facturas",
        label_visibility="collapsed",
    )
    st.session_state["scan_dir_input"] = scan_dir_input

with choose_col:
    if st.button("Elegir", use_container_width=True):
        selected = open_folder_dialog(scan_dir_input)
        if selected:
            st.session_state["scan_dir_input"] = selected
            st.rerun()

with inbox_col:
    if st.button("Inbox", use_container_width=True):
        st.session_state["scan_dir_input"] = common_dirs["inbox"]
        st.rerun()

with down_col:
    if st.button("Descargas", use_container_width=True):
        st.session_state["scan_dir_input"] = common_dirs["descargas"]
        st.rerun()

with desk_col:
    if st.button("Escritorio", use_container_width=True):
        st.session_state["scan_dir_input"] = common_dirs["escritorio"]
        st.rerun()

with docs_col:
    if st.button("Docs", use_container_width=True):
        st.session_state["scan_dir_input"] = common_dirs["documentos"]
        st.rerun()

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
else:
    st.caption(f"Carpeta activa: {resolved_scan_dir}")

action_col1, action_col2, action_col3, action_col4, action_col5, action_col6, action_col7 = st.columns(
    [2.2, 1.1, 1.2, 1.15, 1, 1, 1]
)

with action_col1:
    selected_parser = st.selectbox(
        "Parser para el reescaneo",
        options=parser_options,
        index=0,
        format_func=lambda item: "auto" if item == "auto" else item,
        label_visibility="collapsed",
    )

with action_col2:
    recursive = st.toggle("Recursivo", value=True)

with action_col3:
    skip_known = st.toggle("Omitir conocidas", value=False)

with action_col4:
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

with action_col5:
    if st.button("CSV", use_container_width=True):
        csv_path = service.export_csv(search=search or None)
        st.session_state["last_csv_export"] = str(csv_path)

with action_col6:
    if st.button("XLSX", use_container_width=True):
        xlsx_path = service.export_xlsx(search=search or None)
        st.session_state["last_xlsx_export"] = str(xlsx_path)

with action_col7:
    if st.button("Vaciar", use_container_width=True):
        if not st.session_state.get("confirm_clear_results", False):
            st.error("Marca antes la confirmacion de vaciado.")
        else:
            total_deleted = service.clear_all_results()
            st.session_state["selected_invoice_id"] = None
            st.session_state["last_scan_summary"] = None
            st.success(f"Se han eliminado {total_deleted} registros de la base de datos.")

confirm_col, csv_download_col, xlsx_download_col = st.columns([2.2, 1, 1])

with confirm_col:
    st.toggle(
        "Confirmar vaciado",
        key="confirm_clear_results",
    )

with csv_download_col:
    render_export_download(
        st.session_state.get("last_csv_export"),
        label="Descargar CSV",
        mime="text/csv",
    )

with xlsx_download_col:
    render_export_download(
        st.session_state.get("last_xlsx_export"),
        label="Descargar XLSX",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.divider()

render_scan_summary(st.session_state.get("last_scan_summary"))
render_summary_metrics(
    service,
    search=search or None,
    tipo_documento=document_type_filter,
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

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
        column_config={
            "nombre_proveedor": "Nombre proveedor",
            "nif_proveedor": "NIF proveedor",
            "numero_factura": "Número factura",
            "fecha_factura": "Fecha factura",
            "subtotal": st.column_config.NumberColumn("Base", format="%.2f"),
            "iva": st.column_config.NumberColumn("IVA", format="%.2f"),
            "total": st.column_config.NumberColumn("Total", format="%.2f"),
            "nombre_cliente": "Nombre cliente",
            "nif_cliente": "NIF cliente",
        },
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

    detail_col1, detail_col2 = st.columns([5, 1.5])

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