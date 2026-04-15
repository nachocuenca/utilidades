from __future__ import annotations

from pathlib import Path
import tempfile
import json
from typing import List

import streamlit as st

from src.ui.components import open_folder_dialog, get_common_scan_dirs, format_text, format_amount
from src.services.ai_service import AIService


st.set_page_config(page_title="Modo IA - Extracción IA", layout="wide")

st.title("Modo IA — Extracción con OpenAI")

service = AIService()

col_left, col_right = st.columns([3, 1])

with col_left:
    st.header("Seleccionar PDFs")

    # single file upload
    uploaded = st.file_uploader("Sube un PDF individual", type=["pdf"], accept_multiple_files=False)

    st.markdown("---")

    # folder selection (uses OS dialog)
    folder_input = st.text_input("Carpeta con PDFs (opcional)", value="")
    choose_btn_col, process_btn_col = st.columns([1, 1])
    with choose_btn_col:
        if st.button("Elegir carpeta"):
            selected = open_folder_dialog(folder_input)
            if selected:
                folder_input = selected
                st.session_state["ia_folder"] = selected
                st.experimental_rerun()

    with process_btn_col:
        pass

    if "ia_folder" in st.session_state:
        folder_input = st.session_state.get("ia_folder")

    files_to_process: List[Path] = []

    if uploaded is not None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(uploaded.getbuffer())
        tmp.flush()
        files_to_process.append(Path(tmp.name))

    if folder_input:
        p = Path(folder_input)
        if p.exists() and p.is_dir():
            for f in sorted(p.glob("**/*.pdf")):
                files_to_process.append(f)

    st.markdown(f"**Archivos detectados:** {len(files_to_process)}")

    if files_to_process:
        if st.button("Procesar con IA"):
            st.session_state["ia_results"] = []
            with st.spinner("Procesando con OpenAI, esto puede tardar..."):
                for f in files_to_process:
                    try:
                        res = service.process_file(f)
                        st.session_state["ia_results"].append({"path": str(f), "data": res})
                    except Exception as e:
                        st.session_state["ia_results"].append({"path": str(f), "error": str(e)})

with col_right:
    st.header("Acciones rápidas")
    st.caption("Configuración: usa variables OPENAI_API_KEY y OPENAI_MODEL")
    st.markdown("---")
    st.write("Puedes procesar un PDF individual o una carpeta entera.")

st.markdown("---")

results = st.session_state.get("ia_results")

if not results:
    st.info("No se han procesado documentos todavía. Sube o selecciona y haz clic en 'Procesar con IA'.")
else:
    st.header("Resultados IA")

    for idx, item in enumerate(results):
        st.subheader(f"{idx+1}. {Path(item.get('path')).name}")

        if item.get("error"):
            st.error(f"Error: {item.get('error')}")
            continue

        data = item["data"]
        extraction = data.get("extraction", {})
        is_valid = data.get("is_valid", False)
        warnings = data.get("warnings", [])

        # Show key fields as requested
        left, right = st.columns([3, 2])

        with left:
            st.markdown("**Datos extraídos**")
            st.write("- Archivo:", Path(item.get("path")).name)
            st.write("- tipo_documento:", format_text(extraction.get("tipo_documento")))
            st.write("- nombre_proveedor:", format_text(extraction.get("nombre_proveedor")))
            st.write("- nif_proveedor:", format_text(extraction.get("nif_proveedor")))
            st.write("- nombre_cliente:", format_text(extraction.get("nombre_cliente")))
            st.write("- nif_cliente:", format_text(extraction.get("nif_cliente")))
            st.write("- cp_cliente:", format_text(extraction.get("cp_cliente")))
            st.write("- numero_factura:", format_text(extraction.get("numero_factura")))
            st.write("- fecha_factura:", format_text(extraction.get("fecha_factura")))
            st.write("- subtotal:", format_amount(extraction.get("subtotal")))
            st.write("- iva:", format_amount(extraction.get("iva")))
            st.write("- total:", format_amount(extraction.get("total")))

        with right:
            st.markdown("**Validación y meta**")
            st.write("- confidence:", extraction.get("confidence"))
            st.write("- warnings:")
            if warnings:
                for w in warnings:
                    st.warning(w)
            else:
                st.success("OK — Sin warnings detectados")

            st.write("- validación:", "OK" if is_valid else "Revisión manual requerida")

        st.markdown("**Evidence snippets**")
        snippets = extraction.get("evidence_snippets") or []
        for s in snippets[:8]:
            st.code(s)

        # Actions: save / skip
        save_col, skip_col = st.columns([1, 1])
        with save_col:
            if st.button(f"Guardar resultados en BD — {Path(item.get('path')).name}"):
                # decide requiere_revision_manual by is_valid (validator logic)
                requiere = not is_valid
                motivo = None
                if requiere and warnings:
                    motivo = "; ".join(warnings)
                # Eliminar bloque try vacío y corregir indentación
                continue
            data = item["data"]
            extraction = data.get("extraction", {})
            row = {
                "ruta_archivo": item.get("path"),
                "nombre_proveedor": extraction.get("nombre_proveedor"),
                "nif_proveedor": extraction.get("nif_proveedor"),
                "nombre_cliente": extraction.get("nombre_cliente"),
                "nif_cliente": extraction.get("nif_cliente"),
                "cp_cliente": extraction.get("cp_cliente"),
                "numero_factura": extraction.get("numero_factura"),
                "fecha_factura": extraction.get("fecha_factura"),
                "subtotal": extraction.get("subtotal"),
                "iva": extraction.get("iva"),
                            "total": extraction.get("total"),
                        }
                        table_rows.append(row)
                    df = pd.DataFrame(table_rows)
                    # Formatear importes con coma decimal
                    for col in ["subtotal","iva","total"]:
                        df[col] = df[col].apply(lambda x: ("{:.2f}".format(x).replace(".", ",") if x is not None else ""))
                    st.dataframe(df, use_container_width=True)

                    # Botón de exportación CSV
                    import io
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, sep=';', index=False, encoding='utf-8-sig')
                    st.download_button("Exportar CSV", data=csv_buffer.getvalue(), file_name="resultados_ia.csv", mime="text/csv")
