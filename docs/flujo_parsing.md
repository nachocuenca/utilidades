# Flujo de parsing

## Entrada

Puntos de entrada actuales:
- Streamlit: pagina `src/ui/pages/1_Facturas.py`
- CLI: `python -m scripts.rescan`
- API interna: `InvoiceScanner.scan()` o `InvoiceScanner.scan_file()`

El scanner:
1. Resuelve la carpeta de escaneo.
2. Lista PDFs con `src/utils/files.py`.
3. Calcula `sha256` para cada archivo.
4. Puede omitir hashes ya conocidos con `--skip-known`.

## Lectura del PDF

`src/pdf/reader.py` intenta en este orden:
1. `pdfplumber`
2. `pypdf`
3. OCR con `pypdfium2` + `pytesseract` si el texto sigue siendo insuficiente y OCR esta habilitado

El resultado guarda:
- texto normalizado
- numero de paginas
- `extractor_origen`

En el ultimo CSV vivo, todos los registros entraron por `pdfplumber`.

## Clasificacion previa del documento

La clasificacion previa vive en `InvoiceScanner._infer_document_type()`.

Orden real:
1. `ticket` si la ruta contiene `/tickets/` o la carpeta origen es `tickets`
2. `no_fiscal` si `_looks_like_non_fiscal_document()` detecta TGSS, recibo bancario o administrativo
3. `factura` en el resto de casos

Marcadores reales de `no_fiscal`:
- carpetas tipo `tgss`, `seguridad social`, `banco`, `recibos`, `administrativo`
- texto tipo `tesoreria general de la seguridad social`, `rnt`, `rlt`, `titular de la domiciliacion`, `entidad emisora`, `recibo bancario`, `cargo en cuenta`
- ausencia de marcadores fiscales fuertes cuando aparecen esas senales

## Atajo `no_fiscal`

Si el documento se clasifica como `no_fiscal`:
- no pasa por el registry
- se guarda con `tipo_documento=no_fiscal`
- `parser_usado=document_filter`
- `requiere_revision_manual=True`
- el motivo de revision explica que es un documento no fiscal

Esto es el comportamiento correcto actual del sistema.

## Resolucion del parser ganador

Si el documento no es `no_fiscal`, entra en `resolve_parser_with_trace()`.

Reglas reales:
- si el usuario fuerza parser, se usa ese parser sin evaluar los demas
- en auto, el registry ordena parsers por `priority` descendente
- el primer parser que devuelve `True` en `can_handle()` es el `selected_parser`
- el trace `matched_parsers` guarda todos los parsers que devolvieron `True`, no solo el ganador
- si ninguno devuelve `True`, cae a `generic`

Puntos importantes:
- `generic_ticket` puede ganar por ruta `/tickets/`
- un hint de carpeta por si solo no deberia forzar un parser especifico sin evidencia textual
- los empates de prioridad dependen del orden de registro actual

## Parseo y normalizacion

El parser ganador hace `parse(text, file_path)` y luego `finalize()`.

`finalize()` aplica:
- limpieza de nombres
- normalizacion de NIF y codigo postal
- normalizacion de fecha
- limpieza de numero de factura
- calculo de importes faltantes cuando hay suficientes campos

Regla contable compartida:
- si existe un bloque final coherente donde `base + iva = total`, ese bloque tiene preferencia

## Cliente por defecto

La regla no se aplica en todos los casos. Hoy solo se aplica si:
- `tipo_documento == "factura"`
- `FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS=true`
- existe `carpeta_origen`

Valores actuales del `.env` local:
- `DEFAULT_CUSTOMER_NAME=Daniel Cuenca Moya`
- `DEFAULT_CUSTOMER_TAX_ID=48334490J`

Implicacion practica:
- en escaneos con carpetas por proveedor, el scanner puede corregir o completar cliente
- en un inbox plano sin subcarpetas, esa ayuda no entra

## Persistencia

El scanner construye `InvoiceUpsertData` y hace upsert en SQLite por `hash_archivo`.

Columnas importantes:
- `tipo_documento`
- `parser_usado`
- `extractor_origen`
- `requiere_revision_manual`
- `motivo_revision`
- `carpeta_origen`
- datos fiscales y `texto_crudo`

Matices reales:
- `matched_parsers` no se persiste
- Mercaluz ABV puede poner importes negativos, pero la base sigue guardando `tipo_documento=factura`

## Exportacion

La exportacion vive en `src/services/exporter.py`.

Comportamiento real:
- genera `facturas_YYYYMMDD_HHMMSS.csv`
- genera `facturas_YYYYMMDD_HHMMSS.xlsx`
- escribe en `data/exports/`
- en el snapshot `2026-04-09` la pagina principal de Streamlit esta centrada en escaneo, tabla y detalle; el soporte de export existe en la capa de servicio

## Debug rapido

Si un caso falla:
1. mirar `texto_crudo` en la vista detalle o en la base
2. comprobar si fue filtrado como `no_fiscal`
3. comprobar que parser gano y, si hace falta, reproducir con tests para ver `matched_parsers`
4. revisar si la ruta y `carpeta_origen` daban contexto importante
5. revisar el parser especifico antes de tocar `generic`
