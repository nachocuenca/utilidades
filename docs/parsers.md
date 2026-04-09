# Parsers

## Registro real

Orden efectivo del registry a fecha `2026-04-09`.

Notas:
- El registry ordena solo por `priority` descendente.
- Cuando dos parsers comparten prioridad, decide el orden de registro actual en `ParserRegistry._register_defaults()`.
- `matched_parsers` existe en runtime, pero no se persiste en SQLite ni en CSV.

| Priority | Parser | Base | Papel real |
| --- | --- | --- | --- |
| 520 | `leroy_merlin` | `BaseInvoiceParser` | Parser especifico Leroy Merlin |
| 500 | `obramat` | `GenericSupplierInvoiceParser` | Parser especifico Obramat / Bricoman |
| 490 | `saltoki` | `GenericSupplierInvoiceParser` | Parser especifico Saltoki |
| 420 | `legal_quality` | `GenericSupplierInvoiceParser` | Parser especifico Legal Quality |
| 360 | `repsol` | `GenericSupplierInvoiceParser` | Parser especifico Repsol factura |
| 360 | `versotel` | `GenericSupplierInvoiceParser` | Parser especifico Versotel / Zennio |
| 355 | `eseaforms` | `GenericSupplierInvoiceParser` | Parser especifico Eseaforms |
| 350 | `edieuropa` | `BaseInvoiceParser` | Parser especifico Edieuropa |
| 345 | `mercaluz` | `GenericSupplierInvoiceParser` | Parser especifico Mercaluz |
| 340 | `davofrio` | `BaseInvoiceParser` | Parser especifico Davofrio |
| 340 | `fempa` | `GenericSupplierInvoiceParser` | Parser especifico Fempa |
| 340 | `wurth` | `BaseInvoiceParser` | Parser especifico Wurth |
| 330 | `levantia` | `GenericSupplierInvoiceParser` | Parser especifico Levantia |
| 100 | `maria` | `BaseInvoiceParser` | Parser especifico Maria / Energy in Motion |
| 80 | `agus` | `BaseInvoiceParser` | Parser especifico Agus / Clinica Almendros |
| 60 | `generic_ticket` | `BaseInvoiceParser` | Fallback estricto para tickets |
| 20 | `generic_supplier` | `BaseInvoiceParser` | Fallback de factura fiscal |
| 10 | `generic` | `BaseInvoiceParser` | Fallback final |

Desempates relevantes en este snapshot:
- `repsol` se evalua antes que `versotel`.
- `davofrio` se evalua antes que `fempa`.
- `fempa` se evalua antes que `wurth`.

## Relacion entre especificos y genericos

Reglas de diseno activas en el codigo actual:
- El flujo correcto es parser especifico por proveedor cuando existe evidencia suficiente.
- `generic_ticket` y `generic_supplier` estan separados para no mezclar tickets con facturas fiscales.
- `generic` solo queda como red de seguridad.
- Algunos parsers especificos heredan de `GenericSupplierInvoiceParser`, pero conservan `can_handle()` y extraccion propios.
- `Agus` es el unico parser especifico que en este snapshot puede caer internamente a `generic` cuando no detecta su layout principal.

Relacion operativa:
- `generic_ticket`: tickets reales, cortos, con senales fuertes o ruta `/tickets/`.
- `generic_supplier`: facturas con estructura fiscal, proveedor razonable y evidencia suficiente de importes.
- `generic`: heuristica amplia sin garantia de proveedor.

## Criterios reales de resolucion compartidos

Heuristicas compartidas en `src/parsers/base.py`:
- `looks_like_ticket_document()` acepta ruta `/tickets/` o texto corto con senales fuertes de ticket, total y fecha.
- `looks_like_invoice_document()` exige al menos 2 marcadores fiscales entre `factura`, `base imponible`, `cuota iva`, `importe iva`, `total factura` y similares.

Heuristicas compartidas en `generic_supplier`:
- Rechaza documentos que parezcan ticket.
- Solo entra si el documento parece factura y ademas hay combinacion de proveedor, NIF, numero, fecha o importes fiables.
- Tiene aliases de carpeta para rescatar proveedor solo cuando hay senal real de bloque de proveedor. Aliases activos: `levantia`, `davofrio`, `leroy merlin`, `repsol`, `obramat`, `saltoki benidorm`, `saltoki alicante`, `mercaluz`.

Heuristicas compartidas en `generic_ticket`:
- Rechaza documentos de mas de 60 lineas.
- Requiere 2 patrones fuertes de ticket, o 1 fuerte + 1 de soporte + total + fecha.
- Rechaza textos con demasiados NIF o demasiado OCR basura.
- Puede forzarse por ruta `/tickets/` o `/ticket/`.

## Estado parser por parser

| Parser | `can_handle()` real | Que controla al parsear | Evidencia actual | Riesgo conocido |
| --- | --- | --- | --- | --- |
| `leroy_merlin` | Exige `leroy merlin` + bloque fiscal + soporte de NIF/proveedor y numero/fecha/importes | Proveedor, NIF, numero, fecha y bloque fiscal final coherente | 2 filas en CSV, proveedor y cabecera correctos | Pendiente real: faltan `subtotal`, `iva`, `total` en las 2 filas vivas |
| `obramat` | Score por marca/path/Finestrat/desglose; rechaza Leroy | Proveedor y cliente Dani, numero, fecha y varios layouts de desglose | 29 filas vivas + test dedicado | Muy dependiente de layouts conocidos `clasico`, `rectificativa` y `F0018` |
| `saltoki` | Marca/path/CIF de sucursal | Sucursal, proveedor, Dani, numero/fecha por cabecera o filename, totales de resumen | 15 filas vivas + varios tests | Si la sucursal no se detecta, degrada nombre/NIF de proveedor |
| `legal_quality` | Marca/dominio/CIF y pinta de factura | Proveedor fijo, numero, fecha y candidatos coherentes base/iva/total | 1 fila viva + tests | Poco volumen real |
| `repsol` | Excluye simplificadas; usa marca, compania real y marcadores de factura energetica | Facturadora real, NIF proveedor correcto, numero, fecha y bloque fiscal final | 3 filas vivas + tests directos + scanner | Las simplificadas siguen yendo a `generic_ticket` por diseno |
| `versotel` | Marca/CIF/Zennio + exige resumen coherente, numero y fecha | Emisor fiscal Versotel, numero, fecha y resumen final | 1 fila viva + tests | Poco volumen real |
| `eseaforms` | Marca/path/CIF | Proveedor fijo, numero por filename `I...`, fecha y totales etiquetados | 3 filas vivas | Parser simple, sin mucha tolerancia a layouts nuevos |
| `edieuropa` | Marca/path/CIF y contexto de electrodomesticos | Numero robusto desde filename/texto, fecha y bloque fiscal coherente | 3 filas vivas + tests dedicados | Vigilar OCR que rompa el numero de factura |
| `mercaluz` | Marca/path/ABV/CIF con score | Tipo de documento ABV/FVN/VN, signo de importes, numero, fecha y bloque final coherente | 12 filas vivas + tests dedicados | Parser complejo; seguir vigilando layouts nuevos aunque el dataset vivo actual esta bien |
| `davofrio` | Marca o path + patron `FVC..-....` | NIF proveedor tolerante a OCR invertido, numero, fecha y resumen | 1 fila viva + tests | Poco volumen real |
| `fempa` | Requiere factura exenta FEMPA y rechaza recibo bancario | Proveedor fijo, cliente, numero, fecha, subtotal/total e IVA 0 | 1 fila viva + tests | Muy ligado a marcadores de exencion |
| `wurth` | Marca/path/CIF + cabecera y resumen propios | Proveedor, numero, fecha y fila de resumen con portes/neto/IVA/total | 1 fila viva | Poco volumen real |
| `levantia` | Marca/path/CIF + bloques cliente/proveedor y resumen | Proveedor, NIF evitando IDs del cliente, numero, fecha y triplete coherente | 2 filas vivas + tests | Poco volumen real |
| `maria` | Clues muy especificos de Maria / Energy in Motion | Proveedor fijo, bloque de cliente, CP y totales | Tests dedicados | No aparece como parser final en el ultimo CSV |
| `agus` | Clues de Clinica Almendros / Agus | Layout Clinica Almendros; si no, cae a `generic` y cambia `parser_usado` | Tests dedicados | No aparece en el ultimo CSV y parte del parse depende del fallback |
| `generic_ticket` | Ticket corto con senales fuertes o ruta `/tickets/` | Proveedor top10, NIF proveedor cercano, numero, fecha, total y opcional base/IVA | Tests de resolucion y scanner | No aparece como parser final en el ultimo CSV |
| `generic_supplier` | Factura fiscal, no ticket, con proveedor o importes fiables | Proveedor/NIF, numero, fecha, triplete fiscal o total etiquetado | Tests de resolucion y genericos | No aparece como parser final en el ultimo CSV |
| `generic` | Siempre `True` | Extraccion basica de nombre, IDs, fecha e importes | Fallback de seguridad | No debe tapar proveedores conocidos |

## Cobertura y evidencia real

Cobertura dedicada presente en `tests/`:
- `obramat`, `saltoki`, `repsol`, `mercaluz`, `edieuropa`, `davofrio`, `fempa`, `legal_quality`, `levantia`, `versotel`, `maria`, `agus`
- `generic_ticket`, `generic_supplier`, prioridades y resolucion
- `scanner` para `ticket`, `no_fiscal`, trace y cliente por defecto

Ausencias relevantes:
- No existe un test dedicado de `leroy_merlin` en este repo.
- El ultimo CSV vivo no ejerce `ticket`, `generic_ticket`, `generic_supplier`, `generic`, `maria` ni `agus` como parser final.

## Riesgos y advertencias operativas

- El registry no persiste `matched_parsers`; si la duda es de resolucion, hay que reproducir con tests o instrumentar scanner.
- Los hints de ruta y `carpeta_origen` importan. Renombrar o aplanar carpetas puede cambiar el parser ganador o el cliente por defecto.
- En Mercaluz, los abonos ABV terminan persistidos como `tipo_documento=factura` con importes negativos. Hoy no existe un tipo persistido `abono`.
- En el snapshot actual el unico parser con fallo visible en CSV es `leroy_merlin`.
