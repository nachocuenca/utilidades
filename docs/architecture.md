# Arquitectura

## Mapa real del proyecto

El sistema actual es pequeno y bastante directo:
- `config/settings.py`: lee `.env`, resuelve rutas y banderas de OCR / cliente por defecto.
- `src/pdf/`: lectura con `pdfplumber` / `pypdf` y OCR con `pypdfium2` + `pytesseract`.
- `src/parsers/`: registry + parsers especificos + genericos.
- `src/services/scanner.py`: clasificacion `ticket` / `no_fiscal` / `factura`, resolucion de parser, cliente por defecto y persistencia.
- `src/db/`: SQLite, upsert por hash y consultas para UI / export.
- `src/services/exporter.py`: export CSV/XLSX.
- `src/ui/`: tabla, detalle y reescaneo desde Streamlit.

## Invariantes que ya existen

- El scanner clasifica `no_fiscal` antes de pasar por el registry.
- El registry decide por prioridad descendente; si hay empate, manda el orden de registro.
- La persistencia usa `hash_archivo` como clave unica de upsert.
- En el snapshot `2026-04-09` los tipos documentales persistidos son `factura`, `ticket` y `no_fiscal`.
- `matched_parsers` es una traza de runtime, no una columna persistida.
- El cliente por defecto vive en scanner, no en la base.

## Lo importante para depurar

- Si falla la lectura: mirar `src/pdf/reader.py` y `src/pdf/ocr.py`.
- Si falla la clasificacion `no_fiscal`: mirar `InvoiceScanner._looks_like_non_fiscal_document()`.
- Si falla la resolucion de parser: mirar `src/parsers/registry.py`, `tests/test_parser_resolution.py` y `tests/test_parser_priorities.py`.
- Si falla un proveedor: mirar su parser especifico y su test dedicado.
- Si el dato se guardo mal: mirar `src/db/repositories.py` y el CSV mas reciente.

## Documentacion viva

- Estado del sistema: `docs/estado_actual.md`
- Registry y parsers: `docs/parsers.md`
- Flujo de parsing: `docs/flujo_parsing.md`
- Bitacora verificada: `CHANGELOG.md`
