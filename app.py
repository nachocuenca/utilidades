from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from src.db.database import init_database

settings = get_settings()
init_database(settings.database_path)

st.set_page_config(
    page_title=settings.app_name,
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page(
        "src/ui/pages/1_Facturas.py",
        title="Facturas",
        icon="📄",
        default=True,
    ),
    st.Page(
        "src/ui/pages/2_Detalle.py",
        title="Detalle",
        icon="🔎",
    ),
]

with st.sidebar:
    st.title(settings.app_name)
    st.caption(f"Entorno: {settings.app_env}")
    st.caption(f"Inbox: {settings.inbox_dir}")
    st.caption(f"Exportaciones: {settings.export_dir}")
    st.caption(f"Base de datos: {settings.database_path}")

navigation = st.navigation(pages)
navigation.run()