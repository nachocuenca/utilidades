# Utilidades Facturas

Proyecto local para escanear PDFs, clasificarlos como `factura`, `ticket` o `no_fiscal`, resolver un parser determinista y guardar el resultado en SQLite para revision desde Streamlit.

## Referencia auditada

Fecha de auditoria: `2026-04-09`.

Fuentes usadas para esta documentacion:
- codigo real actual del repo
- scanner y parsers reales
- CSV principal `data/exports/facturas_20260409_090532.csv`
- CSV comparado solo para contraste `data/exports/facturas_20260409_090351.csv`
- tests del repo como apoyo (`135 passed`)

Notas importantes:
- `facturas_20260409_090532.csv` es el export de referencia porque es el mas reciente completo disponible.
- `facturas_20260409_090351.csv` no es la version anterior del mismo dataset: contiene `86` filas, todas `factura`, todas `agus`.
- El CSV de referencia no valida todo el runtime actual: no trae ningun `ticket`, deja `cp_cliente` vacio en las `74` facturas y mantiene `document_filter` en las `6` filas `no_fiscal`.

## Que hace hoy

El flujo real actual es este:

1. El scanner lista PDFs, calcula `sha256` y opcionalmente omite hashes ya conocidos.
2. `src/pdf/reader.py` intenta leer con `pdfplumber`, luego `pypdf` y usa OCR si el texto sigue siendo insuficiente y OCR esta habilitado.
3. `src/services/scanner.py` clasifica primero el documento:
   - `ticket` si la ruta apunta a carpeta `tickets`
   - `no_fiscal` si detecta TGSS, recibo bancario o administrativo
   - `factura` en el resto de casos
4. Si es `no_fiscal`, el documento no entra al registry. Se parsea con `NonFiscalReceiptParser`, se marca revision manual y se guarda como `tipo_documento=no_fiscal`.
5. Si no es `no_fiscal`, el registry resuelve el parser ganador por prioridad descendente.
6. El parser ganador extrae datos y `finalize()` normaliza nombres, NIF, fecha, CP e importes.
7. El scanner aplica el contexto cliente por defecto solo a `factura`, solo si `FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS=true` y solo si existe `carpeta_origen`.
8. La persistencia hace upsert por `hash_archivo`.
9. La UI permite reescaneo, tabla y detalle. La exportacion CSV/XLSX existe en `InvoiceService` y `InvoiceExporter`.

## Tipos documentales soportados

- `factura`: parser especifico o fallback fiscal.
- `ticket`: parser de ticket o ruta `tickets`; el CSV de referencia no contiene casos vivos de este tipo.
- `no_fiscal`: TGSS, recibos bancarios y documentos administrativos detectados antes del registry.

## Como se resuelve el parser

Reglas reales:

- Si el usuario fuerza parser, se usa ese parser sin evaluar el resto.
- `no_fiscal` no participa en el registry; se decide antes.
- `src/parsers/registry.py` ordena por `priority` descendente.
- Si dos parsers tienen la misma `priority`, gana el orden de registro en `_register_defaults()` porque el sort es estable.
- `generic_ticket` es el fallback de tickets.
- `generic_supplier` es el fallback de facturas fiscales.
- `generic` es el fallback final.
- `matched_parsers` existe en runtime, pero no se persiste en SQLite ni en el CSV.

Detalle completo en `docs/parsers.md`.

## Estado rapido del CSV vivo

Sobre `data/exports/facturas_20260409_090532.csv`:

- `80` filas
- `74` `factura`
- `6` `no_fiscal`
- `0` `ticket`
- `80` filas con `extractor_origen=pdfplumber`
- `74/74` facturas con `nombre_cliente=Daniel Cuenca Moya`
- `74/74` facturas con `nif_cliente=48334490J`
- `0/74` facturas con `cp_cliente=03501`

Pendientes visibles en ese export:

- `leroy_merlin`: `invoice (5).pdf` e `invoice (6).pdf` siguen sin `subtotal`, `iva` y `total`
- `saltoki`: `13803_20260307_38.pdf` sigue sin `subtotal` ni `iva`
- `edieuropa`: las 3 filas vivas siguen mal en importes
- `no_fiscal`: las 6 filas siguen vacias en proveedor, cliente, referencia, fecha y total, y aun salen como `document_filter`

## Stack real

- Python 3.12
- Streamlit
- SQLite
- pandas
- pdfplumber
- pypdf
- pypdfium2
- pytesseract
- Tesseract OCR
- openpyxl
- python-dotenv
- pytest

## Donde mirar cuando algo falla

- `docs/estado_actual.md`: que esta cerrado, medio cerrado y pendiente real segun CSV.
- `docs/parsers.md`: parsers registrados, prioridad real, `can_handle()` y riesgos.
- `docs/flujo_parsing.md`: flujo de entrada, clasificacion y persistencia.
- `src/services/scanner.py`: clasificacion `factura` / `ticket` / `no_fiscal`, contexto cliente y guardado.
- `src/parsers/registry.py`: orden real y desempate del parser ganador.
- `src/parsers/*.py`: parser especifico del proveedor afectado.
- `tests/test_scanner.py`, `tests/test_parser_resolution.py` y `tests/test_parser_priorities.py`: comportamiento de scanner y registry.
- vista detalle de Streamlit: `texto_crudo` es la referencia mas util para depurar un caso real.

## Uso minimo

Instalacion:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .[dev]
```

UI:

```powershell
streamlit run app.py
```

Reescaneo:

```powershell
python -m scripts.rescan --recursive
```

Tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Exportacion desde codigo:

- `InvoiceService.export_csv()`
- `InvoiceService.export_xlsx()`

## Documentacion viva

- `docs/estado_actual.md`
- `docs/parsers.md`
- `docs/flujo_parsing.md`
- `docs/architecture.md`
- `CHANGELOG.md`
