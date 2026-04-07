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

## Objetivo funcional

La aplicación quedará preparada para:

- leer facturas PDF desde `data/inbox/`
- extraer:
  - archivo
  - nombre_proveedor
  - nombre_cliente
  - nif_cliente
  - cp_cliente
  - numero_factura
  - fecha_factura
  - subtotal
  - iva
  - total
- guardar el texto crudo extraído del PDF
- persistir resultados en SQLite
- mostrar un panel local con:
  - tabla de facturas
  - búsqueda y filtros
  - reescaneo de carpeta
  - detalle con texto crudo
  - exportación CSV
  - exportación XLSX
- soportar parsers por emisor:
  - generic
  - maria
  - agus
  - futuros parsers

## Instalación

### PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
Arranque

Cuando exista app.py:

streamlit run app.py
Estructura prevista
utilidades/
├─ .gitignore
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ app.py
├─ config/
│  └─ settings.py
├─ data/
│  ├─ inbox/
│  │  └─ .gitkeep
│  ├─ exports/
│  │  └─ .gitkeep
│  └─ app.db
├─ docs/
│  ├─ architecture.md
│  └─ parsers.md
├─ src/
│  ├─ __init__.py
│  ├─ db/
│  │  ├─ __init__.py
│  │  ├─ database.py
│  │  ├─ models.py
│  │  └─ repositories.py
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ scanner.py
│  │  ├─ exporter.py
│  │  └─ invoice_service.py
│  ├─ parsers/
│  │  ├─ __init__.py
│  │  ├─ base.py
│  │  ├─ registry.py
│  │  ├─ generic.py
│  │  ├─ maria.py
│  │  └─ agus.py
│  ├─ pdf/
│  │  ├─ __init__.py
│  │  ├─ reader.py
│  │  └─ text_cleaner.py
│  ├─ utils/
│  │  ├─ __init__.py
│  │  ├─ amounts.py
│  │  ├─ dates.py
│  │  ├─ ids.py
│  │  ├─ names.py
│  │  ├─ files.py
│  │  └─ hashing.py
│  └─ ui/
│     ├─ __init__.py
│     ├─ pages/
│     │  ├─ 1_Facturas.py
│     │  └─ 2_Detalle.py
│     └─ components.py
├─ tests/
│  ├─ __init__.py
│  ├─ conftest.py
│  ├─ fixtures/
│  │  ├─ sample_texts/
│  │  │  ├─ maria_01.txt
│  │  │  ├─ maria_02.txt
│  │  │  └─ agus_01.txt
│  │  └─ pdfs/
│  │     └─ .gitkeep
│  ├─ test_utils.py
│  ├─ test_parser_generic.py
│  ├─ test_parser_maria.py
│  ├─ test_parser_agus.py
│  └─ test_scanner.py
└─ scripts/
   ├─ init_db.py
   └─ rescan.py
