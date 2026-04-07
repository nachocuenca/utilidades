# Utilidades

Utilidad local para procesar facturas PDF desde una carpeta configurable, extraer datos relevantes, guardarlos en SQLite y revisarlos desde una interfaz sencilla en Streamlit.

## Stack

- Python 3.12
- Streamlit
- SQLite
- pandas
- pdfplumber
- pypdf
- openpyxl
- python-dotenv
- pytest

## Instalación

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
Arranque

Cuando exista app.py:

streamlit run app.py
