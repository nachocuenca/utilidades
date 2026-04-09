# Changelog

## 2026-04-09 - Auditoria y regeneracion documental

Entrada creada solo con evidencia verificada de:

- codigo actual del repo
- scanner y parsers reales
- CSV principal `data/exports/facturas_20260409_090532.csv`
- CSV comparado `data/exports/facturas_20260409_090351.csv`
- tests del repo como apoyo (`135 passed`)

Estado verificado en esta fecha:

- Runtime y registry
  - el runtime actual ya esta consolidado alrededor de `InvoiceScanner`, `ParserRegistry` y upsert por `hash_archivo`
  - el registry tiene prioridades explicitas y desempate estable por orden de registro
  - `matched_parsers` existe en runtime, pero no se persiste

- Contexto cliente por defecto
  - el codigo actual lee `DEFAULT_CUSTOMER_NAME`, `DEFAULT_CUSTOMER_TAX_ID` y `DEFAULT_CUSTOMER_POSTAL_CODE`
  - la aplicacion del contexto por defecto vive en scanner y solo entra para `factura` con `carpeta_origen`
  - el CSV vivo actual confirma nombre y NIF de Dani en `74/74` facturas
  - el CSV vivo actual no confirma `cp_cliente`: sigue vacio en `74/74`

- `no_fiscal`
  - el runtime actual clasifica `no_fiscal` antes del registry
  - el codigo actual usa `NonFiscalReceiptParser`
  - los tests actuales ya esperan `parser_usado=non_fiscal_receipt`
  - el CSV vivo aun conserva `6` filas `no_fiscal` con `parser_usado=document_filter` y sin campos utiles

- Repsol
  - el parser actual y el CSV vivo estan alineados en las `3` filas presentes
  - proveedor, NIF, numero, fecha y tripleta fiscal salen bien

- Mercaluz
  - el parser actual aplica la regla fuerte de bloque final coherente
  - el CSV vivo actual trae `12` filas con importes correctos
  - los `ABV` salen en negativo
  - esos `ABV` siguen persistidos como `factura`

- Leroy Merlin
  - el parser actual y sus tests ya cubren `invoice (5).pdf` e `invoice (6).pdf`
  - el CSV vivo actual todavia deja esas dos filas sin `subtotal`, `iva` ni `total`

- Saltoki
  - el parser actual y sus tests ya cubren OCR y caso multipagina
  - el CSV vivo actual todavia deja `13803_20260307_38.pdf` sin `subtotal` ni `iva`

- Edieuropa
  - el parser actual y sus tests cubren la tripleta fiscal corregida
  - el CSV vivo actual sigue mostrando `3` filas con importes mal mapeados

- Documentacion
  - `README.md`, `docs/estado_actual.md`, `docs/parsers.md` y `docs/flujo_parsing.md` se han rehecho para reflejar estado real auditado
  - el CSV principal de referencia queda fijado en `data/exports/facturas_20260409_090532.csv`
  - el CSV `data/exports/facturas_20260409_090351.csv` queda explicitamente descartado como continuidad del mismo snapshot porque es un export distinto de `86` filas `agus`
