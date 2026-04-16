# Estado actual

## Fuentes y alcance

Auditoria hecha el `2026-04-09` usando solo:

- codigo real actual del repo
- scanner y parsers reales
- CSV principal `data/exports/facturas_20260409_090532.csv`
- CSV inmediatamente anterior `data/exports/facturas_20260409_090351.csv` solo para contraste
- tests del repo como apoyo (`135 passed`)

El repo no esta en worktree limpio:

- `src/parsers/non_fiscal_receipt.py`
- `src/parsers/saltoki.py`
- `tests/test_parser_non_fiscal_receipt.py`
- `tests/test_saltoki_parser.py`

Eso importa porque este estado documenta el runtime actual del working tree, no solo el ultimo commit.

## CSV de referencia

Archivo tomado como referencia principal: `data/exports/facturas_20260409_090532.csv`

Motivo:

- es el export mas reciente completo disponible
- el inmediatamente anterior, `data/exports/facturas_20260409_090351.csv`, no es continuidad del mismo snapshot: contiene `86` filas, todas `factura`, todas `agus`

Foto del CSV de referencia:

- `80` filas
- `74` `factura`
- `6` `no_fiscal`
- `0` `ticket`
- `80` filas con `extractor_origen=pdfplumber`
- `74/74` facturas con `nombre_cliente=Daniel Cuenca Moya`
- `74/74` facturas con `nif_cliente=48334490J`
- `0/74` facturas con `cp_cliente=03501`
- `0` filas con `nif_proveedor = nif_cliente`

Distribucion real por parser final:

| Parser | Filas | Lectura rapida |
| --- | ---: | --- |
| `obramat` | 29 | sin huecos visibles en importes |
| `saltoki` | 15 | una fila abierta (`13803_20260307_38.pdf`) |
| `mercaluz` | 12 | importes correctos, ABV en negativo |
| `document_filter` | 6 | `no_fiscal` vacio en campos utiles |
| `repsol` | 3 | correcto en proveedor, NIF e importes |
| `eseaforms` | 3 | correcto en el CSV |
| `edieuropa` | 3 | pendiente real en importes |
| `leroy_merlin` | 2 | pendiente real en importes |
| `levantia` | 2 | correcto en el CSV |
| `davofrio` | 1 | correcto en el CSV |
| `fempa` | 1 | correcto en el CSV |
| `legal_quality` | 1 | correcto en el CSV |
| `versotel` | 1 | correcto en el CSV |
| `wurth` | 1 | correcto en el CSV |

## Cerrado

- Runtime y registry consolidados en codigo: scanner previo, registry explicito por prioridad y `matched_parsers` en runtime.
- Clasificacion documental real en codigo: `factura`, `ticket` y `no_fiscal`.
- Repsol esta cerrado en el export vivo actual:
  - `3/3` filas con facturadora correcta
  - NIF proveedor correcto
  - numeracion y tripleta fiscal correctas
- Mercaluz esta cerrado en general en el export vivo actual:
  - `12/12` filas con tripleta fiscal coherente
  - los `ABV` salen con importes negativos
  - el riesgo pendiente no es de importes, sino de persistencia como `factura`
- Obramat esta cerrado en el export vivo actual:
  - `29/29` filas con importes completos
  - rectificativas en negativo visibles en CSV
- `davofrio`, `eseaforms`, `fempa`, `legal_quality`, `levantia`, `versotel` y `wurth` no muestran huecos nucleares en su muestra viva actual.

## Medio cerrado

- `cp_cliente` por contexto existe en el runtime actual y esta cubierto por tests, pero el CSV vivo no lo refleja:
  - `nombre_cliente` y `nif_cliente` si aparecen en `74/74` facturas
  - `cp_cliente` sigue vacio en `74/74`
- `tipo_documento = no_fiscal` esta operativo en el runtime actual y tiene tests, pero el CSV vivo aun arrastra un estado anterior:
  - las `6` filas `no_fiscal` siguen con `parser_usado=document_filter`
  - el codigo actual usa `NonFiscalReceiptParser` y los tests esperan `non_fiscal_receipt`
- `non_fiscal_receipt` es util en el runtime actual para TGSS y FEMPA segun tests, pero esa mejora no esta validada por el CSV de referencia.
- `ticket` existe y tiene cobertura de scanner y parser, pero el CSV vivo no trae ningun caso `ticket`.
- Leroy Merlin tiene el parser actual y tests dedicados para `invoice (5)` y `invoice (6)`, pero el CSV vivo aun no confirma ese cierre.
- Saltoki tiene tests actuales para OCR y multipagina, pero el CSV vivo aun deja un caso abierto.
- Edieuropa tiene tests actuales sin regresion en importes, pero el CSV vivo sigue mostrando importes incorrectos.

## Pendiente real segun CSV

- `leroy_merlin`
  - `invoice (5).pdf`: sin `subtotal`, `iva`, `total`
  - `invoice (6).pdf`: sin `subtotal`, `iva`, `total`
- `saltoki`
  - `13803_20260307_38.pdf`: `total=196.10`, pero `subtotal` e `iva` vacios
  - es el unico caso Saltoki abierto en el CSV de referencia
- `edieuropa`
  - `Factura 1-A26-11 DANIEL CUENCA MOYA.pdf`: `29.51 / 140.50 / 170.01`
  - `Factura 1-A26-27 DANIEL CUENCA MOYA.pdf`: `1.00 / 1.00 / 2.00`
  - `Factura 1-A26-40 DANIEL CUENCA MOYA.pdf`: `29.51 / 140.50 / 170.01`
  - las tripletas suman, pero fiscalmente estan mal mapeadas
- `no_fiscal`
  - las `6` filas siguen vacias en `nombre_proveedor`, `nombre_cliente`, `numero_factura`, `fecha_factura` y `total`
  - el CSV aun conserva `parser_usado=document_filter`
- `cp_cliente`
  - `0/74` facturas con `cp_cliente=03501`
  - no se puede marcar como cierre real mientras el export vivo siga asi

## Riesgo conocido

- El CSV vivo y el runtime actual no son exactamente el mismo snapshot funcional.
  - ejemplo claro: el runtime actual usa `non_fiscal_receipt`; el CSV aun muestra `document_filter`
- `matched_parsers` no se persiste. Para depurar resolucion real hay que reproducir el caso en runtime o en tests.
- La coherencia `Base + IVA = Total` no basta por si sola para dar un caso por bueno.
  - Edieuropa en el CSV actual es la prueba: suma bien y aun asi esta mal
- El CSV de referencia no ejerce OCR ni tickets.
  - `extractor_origen=pdfplumber` en las `80` filas
  - `0` filas `ticket`
- `mercaluz` ABV y `obramat` rectificativas siguen persistiendo como `factura` porque el scanner solo persiste `factura`, `ticket` o `no_fiscal`.

## Lo que no se va a tocar ahora

- no abrir tipos documentales nuevos
- no reabrir refactors grandes de registry o genericos
- no vender como cerrado nada que el CSV vivo siga dejando abierto
- no usar tests por encima del CSV para dar por resuelto un proveedor

## Resumen corto

- Cerrado de verdad en CSV: runtime base, Repsol, Mercaluz general, Obramat y varios especificos menores.
- Medio cerrado: `cp_cliente`, `ticket`, `non_fiscal_receipt`, Leroy, Saltoki multipagina y Edieuropa en codigo actual, pero sin un nuevo CSV que lo confirme.
- Pendiente real hoy en el export vivo: Leroy, Saltoki `13803`, Edieuropa, `no_fiscal` y `cp_cliente`.
