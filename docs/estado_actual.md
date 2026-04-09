# Estado actual

## Snapshot verificado

Fecha: `2026-04-09`.

Fuentes usadas:
- codigo real del repo
- `.\.venv\Scripts\python.exe -m pytest tests -q` -> `111 passed`
- `data/app.db`
- `data/validation_strict_real_1t26_20260409.db`
- `data/exports/facturas_20260409_090532.csv`

Observaciones de contexto que afectan a la lectura del estado:
- `data/app.db`, `data/validation_strict_real_1t26_20260409.db` y el CSV vivo estan alineados entre si.
- Ese snapshot no viene del `data/inbox` plano actual del repo, sino de un escaneo previo sobre `C:\Users\ignac\Downloads\1T26\1T 26\...`, visible en `ruta_archivo` y `carpeta_origen`.
- `data/validation_strict_20260409.db` no representa el estado real del sistema: a `2026-04-09` contiene `86` filas, todas `factura` y todas con `parser_usado=agus`.

## Foto del ultimo CSV real

Archivo: `data/exports/facturas_20260409_090532.csv`

Resumen:
- `80` registros
- `74` `factura`
- `6` `no_fiscal`
- `0` `ticket`
- `80` lecturas con `extractor_origen=pdfplumber`
- `6` filas con `requiere_revision_manual=True`, todas por `document_filter`
- `0` incoherencias contables en filas con importes (`subtotal + iva = total`)
- `0` casos donde el `nif_proveedor` coincida con el `nif_cliente`

Distribucion real por parser final:

| Parser | Filas CSV | Estado real |
| --- | --- | --- |
| `obramat` | 29 | cerrado |
| `saltoki` | 15 | cerrado |
| `mercaluz` | 12 | cerrado |
| `document_filter` | 6 | cerrado |
| `repsol` | 3 | cerrado |
| `eseaforms` | 3 | cerrado |
| `edieuropa` | 3 | cerrado |
| `levantia` | 2 | cerrado |
| `leroy_merlin` | 2 | pendiente real |
| `davofrio` | 1 | cerrado |
| `fempa` | 1 | cerrado |
| `legal_quality` | 1 | cerrado |
| `versotel` | 1 | cerrado |
| `wurth` | 1 | cerrado |

No aparecen como parser final en ese CSV:
- `maria`
- `agus`
- `generic_ticket`
- `generic_supplier`
- `generic`

## Cerrado

- Runtime y registry consolidados con prioridades explicitas y trace runtime de `matched_parsers`.
- Filtro documental `no_fiscal` activo en `scanner.py` y visible en produccion local: 6 documentos guardados con `parser_usado=document_filter` y revision manual obligatoria.
- Repsol funcionalmente corregido en el estado actual del repo: 3 filas vivas completas, tests dedicados y test de scanner pasando.
- Mercaluz mejorado y estable en el dataset vivo actual: 12 filas correctas, incluyendo abonos ABV con importes negativos y sin incoherencias contables.
- Edieuropa estable en el dataset vivo actual: 3 filas completas y tests dedicados.
- Obramat estable en el dataset vivo actual: 29 filas completas y cobertura dedicada.
- Saltoki estable en el dataset vivo actual: 15 filas completas y cobertura dedicada.
- El resto de especificos presentes en el CSV (`davofrio`, `eseaforms`, `fempa`, `legal_quality`, `levantia`, `versotel`, `wurth`) no muestran fallos de campos nucleares en el ultimo export real.

## Medio cerrado

- Flujo `ticket`: soportado en codigo y cubierto por tests, pero el ultimo CSV real no contiene ningun `ticket`. La validacion actual de tickets es por tests y casos sinteticos, no por export vivo.
- `generic_ticket`: endurecido y validado por tests, pero sin filas finales en el ultimo CSV.
- `generic_supplier`: separado de `generic_ticket` y bien cubierto por tests, pero sin filas finales en el ultimo CSV.
- Parsers `maria` y `agus`: siguen registrados y con tests propios, pero no aparecen como parser final en el ultimo CSV vivo.
- Cliente por defecto: el `.env` local tiene `FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS=true`, pero esa regla solo aplica si hay `carpeta_origen`. En el snapshot vivo actual eso funciona porque la base viene de carpetas por proveedor; el `data/inbox` plano del repo no reproduce ese contexto.

## Pendiente

- `leroy_merlin` esta pendiente real, no teorico:
  - gana el parser correcto
  - proveedor, NIF, numero y fecha salen bien
  - fallan `subtotal`, `iva` y `total` en `invoice (5).pdf` y `invoice (6).pdf`
- Si se quiere usar el `data/inbox` plano del repo como nueva fuente de validacion, hace falta un reescaneo limpio y un nuevo CSV. Hoy no existe un export vivo alineado con ese inbox.

## Riesgo conocido

- `data/validation_strict_20260409.db` es un artefacto enganoso y no debe usarse como fuente de verdad.
- Los hints de ruta y `carpeta_origen` importan. Aplanar carpetas o renombrar archivos puede cambiar resultados aunque el PDF sea el mismo.
- `matched_parsers` no queda guardado en SQLite ni en CSV. Para depurar resolucion hay que reproducir el caso en runtime o por tests.
- En Mercaluz los abonos ABV quedan persistidos como `tipo_documento=factura` con importes negativos. Hoy no existe un tipo persistido `abono`.
- `document_filter` marca `no_fiscal` con revision manual y sin campos fiscales. Eso es comportamiento esperado, no bug.

## Decisiones arquitectonicas ya tomadas

- Parser por proveedor antes que parchear sobre `generic`.
- `generic_ticket` y `generic_supplier` separados.
- Regla fuerte de bloque final coherente: si `base + iva = total`, ese bloque manda.
- Upsert por `hash_archivo`.
- Cliente por defecto aplicado en scanner, no en DB.
- `no_fiscal` resuelto antes de entrar al registry.

## Lo que no se debe volver a hacer

- No mezclar tipo de IVA con cuota de IVA.
- No coger el NIF del cliente como NIF del proveedor.
- No promocionar texto OCR basura a nombre de proveedor.
- No vender como "cerrado" algo que en el CSV real siga fallando.
- No usar `generic + parche encima` si ya existe evidencia suficiente para un parser especifico.
- No usar `data/validation_strict_20260409.db` como referencia de estado.
