# Changelog

## 2026-04-09 - Snapshot verificado del repo

Entrada creada tras verificar codigo, tests, base y ultimo CSV real.

Resumen observable en el estado actual:
- El runtime ya incluye filtro `no_fiscal` previo al registry y persiste esos documentos como `document_filter`.
- El registry ya esta consolidado con prioridades explicitas y trace runtime de `matched_parsers`.
- El parser de Repsol ya identifica la facturadora real en el snapshot actual y el CSV vivo no muestra fallos en sus 3 filas.
- Mercaluz ya usa una regla fuerte de bloque final coherente y el CSV vivo no muestra fallos en sus 12 filas.
- Edieuropa ya tiene parser especifico activo y 3 filas vivas completas.
- El ultimo CSV real (`data/exports/facturas_20260409_090532.csv`) muestra 80 registros, 6 `no_fiscal` y un pendiente abierto real en `leroy_merlin` por falta de importes.
- La documentacion viva se ha rehecho para reflejar el estado actual real, no estados intermedios.
