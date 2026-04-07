# Parsers

## Vision general

La aplicacion usa una arquitectura basada en parsers para separar la logica de extraccion por emisor.

Actualmente existen estos parsers:

- `generic`
- `maria`
- `agus`

El registry intenta resolver automaticamente el parser correcto. Si ninguno encaja, usa `generic`.

## Base comun

Archivo:
- `src/parsers/base.py`

La clase base aporta:

- estructura comun de salida
- helpers para fechas
- helpers para importes
- helpers para NIF/CIF
- helpers para nombre de cliente y proveedor
- logica para completar subtotal, IVA y total cuando falta uno

## Parser generic

Archivo:
- `src/parsers/generic.py`

Uso:
- fallback general
- documentos sin reglas especificas aun

Extrae:
- proveedor desde cabecera o etiquetas
- cliente desde etiquetas tipo `Cliente`
- NIF/CIF
- CP
- numero de factura
- fecha
- subtotal
- IVA
- total

## Parser maria

Archivo:
- `src/parsers/maria.py`

Claves conocidas:
- `Maria Gonzalez Arranz`
- `energyinmotion.es`
- `membresia desbloqueate`
- IBAN conocido de Maria

Comportamiento:
- fija el proveedor a Maria
- busca la fecha
- toma el cliente justo despues del bloque de fecha
- soporta importes con 4 decimales
- calcula subtotal si vienen IVA y total pero no base

## Parser agus

Archivo:
- `src/parsers/agus.py`

Estado:
- preparado para evolucionar sobre muestras reales
- actualmente reutiliza la logica del parser generic y ajusta deteccion del proveedor

Se activa por:
- texto con `agus`, `agustin` o variantes
- nombre de archivo con `agus`

## Como anadir un parser nuevo

1. Crear un archivo nuevo en `src/parsers/`
2. Heredar de `BaseInvoiceParser`
3. Implementar:
   - `can_handle`
   - `parse`
4. Registrar el parser en `src/parsers/registry.py`
5. Anadir tests con muestras controladas

## Recomendaciones

- no mezclar reglas de emisores distintos
- guardar siempre `texto_crudo`
- preferir reglas pequenas y comprobables
- cubrir cada parser con fixtures y tests
- cuando un caso sea dudoso, dejar que caiga a `generic`