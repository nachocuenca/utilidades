from __future__ import annotations

import streamlit as st

from src.ui.components import format_amount, get_invoice_service, render_detail_field

st.title("Detalle de factura")

service = get_invoice_service()

if "selected_invoice_id" not in st.session_state:
    st.session_state["selected_invoice_id"] = None

default_invoice_id = int(st.session_state.get("selected_invoice_id") or 0)

control_col1, control_col2 = st.columns([2, 1])

with control_col1:
    invoice_id = st.number_input(
        "ID de factura",
        min_value=0,
        step=1,
        value=default_invoice_id,
    )

with control_col2:
    st.write("")
    st.write("")
    if st.button("Volver a facturas", use_container_width=True):
        st.switch_page("src/ui/pages/1_Facturas.py")

st.session_state["selected_invoice_id"] = int(invoice_id)

if invoice_id <= 0:
    st.info("Selecciona una factura desde la pantalla principal o escribe un ID.")
    st.stop()

record = service.get_invoice(int(invoice_id))

if record is None:
    st.warning(f"No existe la factura con ID {int(invoice_id)}.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Subtotal", format_amount(record.subtotal))
col2.metric("IVA", format_amount(record.iva))
col3.metric("Total", format_amount(record.total))

info_col1, info_col2 = st.columns(2)

with info_col1:
    render_detail_field("ID", record.id)
    render_detail_field("Archivo", record.archivo)
    render_detail_field("Ruta", record.ruta_archivo)
    render_detail_field("Parser usado", record.parser_usado)
    render_detail_field("Numero de factura", record.numero_factura)
    render_detail_field("Fecha de factura", record.fecha_factura)

with info_col2:
    render_detail_field("Proveedor", record.nombre_proveedor)
    render_detail_field("Cliente", record.nombre_cliente)
    render_detail_field("NIF cliente", record.nif_cliente)
    render_detail_field("CP cliente", record.cp_cliente)
    render_detail_field("Creado", record.created_at)
    render_detail_field("Actualizado", record.updated_at)

st.subheader("Texto crudo")
st.text_area(
    "Contenido extraido del PDF",
    value=record.texto_crudo,
    height=500,
)