# Flujo de parsing

## Punto de entrada

Hoy hay tres entradas reales:

- Streamlit: `src/ui/pages/1_Facturas.py`
- CLI: `python -m scripts.rescan`
- servicio: `InvoiceScanner.scan()` / `InvoiceScanner.scan_file()`

El scanner siempre parte de `src/services/scanner.py`.

## 1. Localizar PDFs

`InvoiceScanner`:

1. resuelve la carpeta a escanear
2. lista PDFs con `src/utils/files.py`
3. calcula `sha256`
4. puede omitir hashes ya conocidos si se usa `skip_known`

La persistencia se hace por `hash_archivo`, asi que el upsert es por contenido, no por nombre de fichero.

## 2. Leer el PDF

`src/pdf/reader.py` intenta en este orden:

1. `pdfplumber`
2. `pypdf`
3. OCR con `pypdfium2` + `pytesseract` si el texto sigue siendo insuficiente y OCR esta habilitado

El resultado de lectura guarda:

- `text`
- `page_count`
- `extractor`

En el CSV de referencia `facturas_20260409_090532.csv`, las `80` filas vienen de `pdfplumber`.

## 3. Clasificacion documental previa

Antes de mirar el registry, `InvoiceScanner` decide `tipo_documento` preliminar.

Orden real:

1. `ticket` si la ruta contiene `/tickets/` o `carpeta_origen` es `tickets`
2. `no_fiscal` si `_looks_like_non_fiscal_document()` detecta TGSS, recibo bancario o documento administrativo
3. `factura` en el resto

Marcadores `no_fiscal` reales:

- carpetas como `tgss`, `seguridad social`, `banco`, `recibos`, `administrativo`
- textos como `tesoreria general de la seguridad social`, `rnt`, `rlt`, `titular de la domiciliacion`, `entidad emisora`, `cargo en cuenta`
- ausencia de marcadores fiscales fuertes cuando aparecen esas senales

## 4. Rama `no_fiscal`

Si el documento cae en `no_fiscal`:

- no entra al registry
- se parsea con `NonFiscalReceiptParser`
- se persiste con `tipo_documento=no_fiscal`
- se marca `requiere_revision_manual=True`
- el motivo de revision deja constancia de que es un documento no fiscal

Matiz importante:

- el runtime actual toma `parser_usado` del propio `NonFiscalReceiptParser`, o sea `non_fiscal_receipt`
- el CSV vivo de referencia todavia muestra `document_filter` en sus 6 filas `no_fiscal`

Eso significa que el export disponible no valida todavia el comportamiento exacto del runtime actual en esa rama.

## 5. Rama `factura` o `ticket`: resolver parser

Si el documento no es `no_fiscal`, entra en `resolve_parser_with_trace()`.

Reglas reales:

- si el usuario fuerza parser, se usa ese parser directamente
- si no, el registry ordena por `priority` descendente
- si dos parsers empatan, manda el orden de registro en `ParserRegistry._register_defaults()`
- el primer parser que devuelve `True` en `can_handle()` es el ganador
- `matched_parsers` guarda todos los parsers que devolvieron `True`
- si ninguno entra, cae a `generic`

Casos especiales:

- `generic_ticket` puede ganar solo por ruta `tickets`
- `non_fiscal` nunca compite aqui

## 6. Parsear y normalizar

El parser ganador hace `parse(text, file_path)` y despues `finalize()`.

`finalize()`:

- limpia nombres
- normaliza NIF
- normaliza `cp_cliente`
- normaliza fecha
- limpia numero de factura
- completa importes faltantes cuando hay evidencia suficiente

Regla contable compartida:

- si aparece un bloque final coherente donde `Base + IVA = Total`, ese bloque manda

Limite real:

- esa regla por si sola no garantiza que la tripleta sea correcta
- el CSV vivo actual de `edieuropa` demuestra que una tripleta puede sumar y aun asi estar mal mapeada

## 7. Tipo documental final

El scanner no persiste cualquier `tipo_documento` que devuelva el parser.

Hoy solo persiste:

- `factura`
- `ticket`
- `no_fiscal`

Consecuencia real:

- `mercaluz` puede devolver `tipo_documento=abono` internamente
- aun asi, el scanner termina guardando esas filas como `factura` con importes negativos

## 8. Contexto cliente por defecto

El contexto cliente por defecto se aplica en `InvoiceScanner._apply_default_customer_context()`.

Solo entra si se cumplen las tres condiciones:

- `tipo_documento == "factura"`
- `FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS=true`
- existe `carpeta_origen`

Valores configurados hoy en `.env`:

- `DEFAULT_CUSTOMER_NAME=Daniel Cuenca Moya`
- `DEFAULT_CUSTOMER_TAX_ID=48334490J`
- `DEFAULT_CUSTOMER_POSTAL_CODE=03501`

Que se ve en el CSV vivo:

- `74/74` facturas tienen `nombre_cliente=Daniel Cuenca Moya`
- `74/74` facturas tienen `nif_cliente=48334490J`
- `0/74` facturas tienen `cp_cliente=03501`

Conclusion operativa:

- nombre y NIF si estan materializados en el export vivo
- `cp_cliente` existe en el runtime actual y en tests, pero no esta validado por el ultimo CSV disponible

## 9. Guardado en SQLite

El scanner construye `InvoiceUpsertData` y hace upsert con `InvoiceRepository.upsert()`.

Campos clave persistidos:

- `tipo_documento`
- `parser_usado`
- `extractor_origen`
- `requiere_revision_manual`
- `motivo_revision`
- `carpeta_origen`
- proveedor / cliente / NIF / CP
- numero / fecha / subtotal / iva / total
- `texto_crudo`

No se persiste:

- `matched_parsers`

## 10. Exportacion

La exportacion vive en `src/services/exporter.py`.

Comportamiento real:

- genera `facturas_YYYYMMDD_HHMMSS.csv`
- genera `facturas_YYYYMMDD_HHMMSS.xlsx`
- escribe en `data/exports/`

La UI actual no expone un boton de exportacion. El soporte esta en:

- `InvoiceService.export_csv()`
- `InvoiceService.export_xlsx()`

## Donde mirar si un caso falla

1. `texto_crudo` del detalle o de la base.
2. `src/services/scanner.py` para ver si el problema es de clasificacion previa.
3. `src/parsers/registry.py` para ver prioridad y desempate.
4. el parser especifico del proveedor.
5. `tests/test_scanner.py`, `tests/test_parser_resolution.py` y el test del parser afectado.
6. `docs/estado_actual.md` para comprobar si el fallo ya existe en el CSV vivo de referencia.
