# Arquitectura

## Objetivo

Procesa PDFs → texto → parser → datos normalizados → SQLite → UI/export.

## Capas

### 1. Configuración
`config/settings.py`: .env, rutas, OCR toggle, default_parser=\"generic\".

### 2. Base de datos
`src/db/*`: SQLite facturas (hash_archivo PK, upsert, filtros fecha/parser).

### 3. Utils/PDF
`src/utils/*`, `src/pdf/*`: Normaliza fechas/importes/nombres/NIF, lee/limpia texto.

### 4. Parsers **(actualizado hoy)**
`src/parsers/*`:

- Registry `registry.py`: Priority descendente (Obramat>Saltoki>Repsol>Edieuropa>Mercaluz>generic_ticket60>Maria/Agus>generic_supplier20>generic).
- `resolve_with_trace()`: selected + matched_parsers para debug.
- Base: Estructura salida, helpers.
- Específicos: Alta prio por texto/path (ej. mercaluz NIF/A BV).
- generic_ticket: Strict tickets (patterns + !largo/!OCR/!NIF muchos).
- generic_supplier: Facturas genéricas (fiscal markers).
- generic: Fallback.

### 5. Servicios
`src/services/scanner.py`: Lista PDFs, read_text, resolve_parser, infer tipo_doc (\"ticket\" si generic_ticket), upsert.
Otros: export CSV/XLSX.

### 6. UI
`app.py` + `src/ui/*`: Tabla facturas, filtros, detalle texto_crudo/requiere_revision, reescaneo.

## Flujo principal

1. PDFs en `data/inbox/`.
2. Scanner: read_pdf_text → registry.evaluate(text, path) → parse() → upsert.
3. UI: Query repo → render/export.
4. Scripts: `rescan.py` CLI.

## Extensiones

- Nuevo parser: Hereda Base, register(), test fixture.
- Debug: `resolve_parser_with_trace()` logs matched.
- Ver `docs/parsers.md` cambios/estado detallado.

## Diseño

- Local/SQLite.
- Parsers desacoplados.
- Texto_crudo para debug.
- Tests por parser + fixtures reales.

