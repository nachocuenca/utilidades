# Parsers

## Registro real

El registry real esta en `src/parsers/registry.py`.

Reglas que mandan hoy:

- solo entran en el registry los documentos que no han sido clasificados antes como `no_fiscal`
- se ordena por `priority` descendente
- si hay empate, gana el orden de registro en `_register_defaults()`
- `matched_parsers` existe en runtime, pero no se persiste

`NonFiscalReceiptParser` no esta registrado en el registry. Vive en `src/services/scanner.py` y solo se usa en la rama `no_fiscal`.

Orden efectivo actual:

| Orden | Priority | Parser | Base | Filas en CSV vivo |
| ---: | ---: | --- | --- | ---: |
| 1 | 520 | `leroy_merlin` | `BaseInvoiceParser` | 2 |
| 2 | 500 | `obramat` | `GenericSupplierInvoiceParser` | 29 |
| 3 | 490 | `saltoki` | `GenericSupplierInvoiceParser` | 15 |
| 4 | 420 | `legal_quality` | `GenericSupplierInvoiceParser` | 1 |
| 5 | 360 | `repsol` | `GenericSupplierInvoiceParser` | 3 |
| 6 | 360 | `versotel` | `GenericSupplierInvoiceParser` | 1 |
| 7 | 355 | `eseaforms` | `GenericSupplierInvoiceParser` | 3 |
| 8 | 350 | `edieuropa` | `BaseInvoiceParser` | 3 |
| 9 | 345 | `cementos_benidorm` | `BaseInvoiceParser` | 0 |
| 10 | 345 | `mercaluz` | `GenericSupplierInvoiceParser` | 12 |
| 11 | 340 | `davofrio` | `BaseInvoiceParser` | 1 |
| 12 | 340 | `fempa` | `GenericSupplierInvoiceParser` | 1 |
| 13 | 340 | `rhef` | `BaseInvoiceParser` | 0 |
| 14 | 340 | `wurth` | `BaseInvoiceParser` | 1 |
| 15 | 330 | `levantia` | `GenericSupplierInvoiceParser` | 2 |
| 16 | 100 | `maria` | `BaseInvoiceParser` | 0 |
| 17 | 80 | `agus` | `BaseInvoiceParser` | 0 |
| 18 | 60 | `generic_ticket` | `BaseInvoiceParser` | 0 |
| 19 | 20 | `generic_supplier` | `BaseInvoiceParser` | 0 |
| 20 | 10 | `generic` | `BaseInvoiceParser` | 0 |

## Scanner-only: `non_fiscal_receipt`

- No participa en el registry.
- Se ejecuta solo si `InvoiceScanner` clasifica antes el PDF como `no_fiscal`.
- `can_handle()` devuelve siempre `True`, pero eso no importa porque no compite con otros parsers.
- Extrae nombre de proveedor, nombre de cliente, referencia, fecha de valor y total para TGSS, FEMPA y recibos bancarios.
- Estado real:
  - codigo y tests actuales: operativo
  - CSV vivo: aun no lo valida; las 6 filas `no_fiscal` siguen como `document_filter` y vacias

## Criterios compartidos

Lo que viene de `src/parsers/base.py`:

- `looks_like_ticket_document()` reconoce tickets por ruta `tickets`, longitud corta y senales fuertes.
- `looks_like_invoice_document()` exige al menos 2 marcadores fiscales.
- si existe un bloque final coherente donde `Base + IVA = Total`, ese bloque tiene prioridad sobre extracciones mas debiles.
- `extract_supplier_tax_id()` intenta evitar coger el NIF del cliente como NIF del proveedor.
- `finalize()` limpia nombres, NIF, fecha, CP y completa importes faltantes cuando hay evidencia suficiente.

Lo que añade `generic_supplier`:

- rechaza tickets
- solo entra si ve factura fiscal y evidencia suficiente de proveedor, NIF, numero, fecha o importes
- puede usar alias de carpeta, pero no debe ganar solo por path sin senal textual

Lo que añade `generic_ticket`:

- acepta ruta `tickets` o ticket corto con patrones fuertes
- corta documentos largos
- rechaza textos con demasiados NIF o demasiado OCR basura

## Parser por parser

### Especificos con evidencia viva en el CSV

- `leroy_merlin`
  - `can_handle()`: exige marca Leroy, contexto fiscal y apoyo real de NIF/proveedor, numero, fecha o importes.
  - Extrae: proveedor, NIF proveedor, numero, fecha, `cp_cliente` y bloque fiscal final.
  - Riesgo real: el CSV vivo sigue dejando `invoice (5).pdf` e `invoice (6).pdf` sin importes, aunque los tests actuales del parser ya cubren esos dos casos.

- `obramat`
  - `can_handle()`: score por marca/path, layout de venta o devolucion y desglose fiscal; rechaza Leroy.
  - Extrae: proveedor fijo, cliente Dani, numero, fecha y tripleta fiscal para layout clasico, rectificativa y `F0018`.
  - Riesgo real: no hay huecos visibles en el CSV; depende mucho de layouts ya conocidos.

- `saltoki`
  - `can_handle()`: score por marca, path, dominio y CIF de sucursal.
  - Extrae: sucursal, proveedor, cliente Dani, numero, fecha y bloque final de totales.
  - Riesgo real: el CSV vivo deja abierto `13803_20260307_38.pdf` sin `subtotal` ni `iva`; los tests actuales ya cubren el caso multipagina.

- `legal_quality`
  - `can_handle()`: requiere factura fiscal y score alto por nombre, dominio, CIF y contexto.
  - Extrae: proveedor fijo, NIF, numero, fecha y tripleta fiscal coherente.
  - Riesgo real: solo hay una fila viva; poca muestra.

- `repsol`
  - `can_handle()`: reconoce factura Repsol, pero rechaza simplificadas/ticket.
  - Extrae: facturadora real, NIF proveedor correcto, numero, fecha y bloque fiscal final.
  - Riesgo real: el CSV vivo actual esta bien; las simplificadas siguen yendo a `generic_ticket` por diseno.

- `versotel`
  - `can_handle()`: score por Versotel/Zennio, CIF y resumen coherente con numero y fecha.
  - Extrae: emisor fiscal Versotel, NIF, numero, fecha y tripleta fiscal.
  - Riesgo real: solo una fila viva.

- `eseaforms`
  - `can_handle()`: marca/path/CIF.
  - Extrae: proveedor fijo, numero desde filename `I...`, fecha y totales etiquetados.
  - Riesgo real: parser simple y poco tolerante a layouts nuevos; el CSV vivo actual no muestra fallo.

- `edieuropa`
  - `can_handle()`: marca/path/CIF y contexto de electrodomesticos.
  - Extrae: proveedor fijo, numero robusto desde filename/texto, fecha y tripleta fiscal.
  - Riesgo real: pendiente vivo en importes. El CSV actual trae dos filas con base e IVA cruzados y una fila trivial `1 / 1 / 2`.

- `mercaluz`
  - `can_handle()`: score por marca, path, ABV y CIF.
  - Extrae: numero, fecha, proveedor, NIF y bloque final coherente; `ABV` sale con signo negativo.
  - Riesgo real: el CSV vivo esta bien en importes, pero los `ABV` siguen persistidos como `tipo_documento=factura` porque el scanner solo guarda `factura`, `ticket` o `no_fiscal`.

- `davofrio`
  - `can_handle()`: marca directa o path con patron `FVC..-....`.
  - Extrae: proveedor, NIF tolerante a OCR invertido, numero, fecha y resumen final.
  - Riesgo real: una sola fila viva.

- `fempa`
  - `can_handle()`: factura fiscal exenta FEMPA; rechaza tickets y recibos bancarios.
  - Extrae: proveedor fijo, NIF, numero, fecha, subtotal/total e `iva=0`.
  - Riesgo real: una sola fila viva. La rama `no_fiscal` de FEMPA es otra via y no queda validada por el CSV vivo.

- `wurth`
  - `can_handle()`: score por marca, dominio, CIF y cabecera/resumen propios.
  - Extrae: proveedor, NIF, numero, fecha y resumen de totales.
  - Riesgo real: una sola fila viva.

- `levantia`
  - `can_handle()`: score por marca, dominio, CIF y bloques cliente/proveedor.
  - Extrae: proveedor, NIF sin contaminar con el cliente, numero, fecha y tripleta coherente.
  - Riesgo real: dos filas vivas; poca muestra.

### Especificos registrados sin evidencia viva en el CSV de referencia

- `cementos_benidorm`
  - `can_handle()`: marca/path/CIF y layout fiscal propio.
  - Extrae: proveedor fijo, cliente, `cp_cliente`, numero, fecha y tripleta fiscal.
  - Riesgo real: sigue registrado y con tests, pero el CSV de referencia no trae ninguna fila final suya.

- `rhef`
  - `can_handle()`: score por proveedor, CIF, nombre comercial y layout de factura.
  - Extrae: proveedor fijo, cliente, `cp_cliente`, numero, fecha y total; intenta base e IVA desde bloque fiscal.
  - Riesgo real: sigue registrado y con tests, pero el CSV de referencia no trae ninguna fila final suya.

- `maria`
  - `can_handle()`: pistas muy especificas de Maria / Energy in Motion.
  - Extrae: proveedor fijo, bloque de cliente, NIF, `cp_cliente` y totales.
  - Riesgo real: registrado y con tests, pero sin evidencia viva en el CSV de referencia.

- `agus`
  - `can_handle()`: pistas de Clinica Almendros / Agus o del filename.
  - Extrae: layout Clinica Almendros; si no detecta ese layout, cae internamente a `generic`.
  - Riesgo real: sigue registrado y con tests, pero sin evidencia viva en el CSV de referencia.
  - Dependencia de fallback: si cae a `generic`, mantiene `parser_usado=agus`.

### Fallbacks

- `generic_ticket`
  - `can_handle()`: ruta `tickets` o ticket corto con senales fuertes.
  - Extrae: proveedor, NIF proveedor, numero, fecha, total y, si puede, base e IVA.
  - Riesgo real: sin filas finales en el CSV de referencia.

- `generic_supplier`
  - `can_handle()`: factura fiscal, no ticket, con proveedor o importes fiables.
  - Extrae: proveedor, NIF, numero, fecha y tripleta fiscal o total etiquetado.
  - Riesgo real: sin filas finales en el CSV de referencia.

- `generic`
  - `can_handle()`: siempre `True`.
  - Extrae: proveedor, cliente, IDs, fecha e importes de forma basica.
  - Riesgo real: es la red de seguridad final y no debe tapar a un parser especifico.

## Dependencias de fallback y de scanner

- `non_fiscal_receipt` depende del scanner, no del registry.
- `generic_ticket` y `generic_supplier` solo entran si antes no ha ganado un parser especifico.
- `generic` es el ultimo fallback del registry.
- `agus` puede delegar internamente en `generic`.
- El parser puede devolver un `tipo_documento` propio, pero el scanner actual solo persiste `factura`, `ticket` o `no_fiscal`.

## Riesgos operativos

- El CSV vivo no ejerce `ticket`, `generic_ticket`, `generic_supplier`, `generic`, `maria`, `agus`, `cementos_benidorm` ni `rhef`.
- El path y la `carpeta_origen` importan tanto para el parser ganador como para el contexto cliente.
- La validacion por suma `Base + IVA = Total` evita muchos fallos, pero no todos. Edieuropa en el CSV vivo es el caso abierto mas claro.
