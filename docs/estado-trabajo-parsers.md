# Estado del trabajo en Parsers - 2024-10-XX

## Resumen del trabajo de hoy

**Fecha:** [Insertar fecha actual]  
**Archivos principales tocados:** Basado en pestañas abiertas, search en repo y docs/parsers.md actual.

### 1. Qué se ha corregido hoy
- **Diferenciación ticket/factura endurecida:** `generic_ticket.can_handle()` ahora rechaza documentos >60 líneas, >3 NIFs, OCR basura en top10 líneas, requiere ≥2 strong patterns O (1 strong + support + total + fecha).
- **Extracciones robustas en tickets:** Proveedor top10 excluye fiscal/cliente/OCR noisy, NIF cerca proveedor, fecha/total priorizados.
- **Genéricos separados claramente:** `generic_ticket` (prio 60, strict tickets) vs `generic_supplier` (prio 20, facturas fiscales base/IVA/total).
- **Aliases path en generic_supplier:** Ej. "mercaluz" → "Componentes Eléctricos Mercaluz S.A." para OCR malo.

### 2. Parsers tocados/modificados
| Parser | Cambios específicos |
|--------|---------------------|
| `registry.py` | Priorities explícitas, trace `matched_parsers`, orden fijo (obramat/saltoki/repsol/edieuropa/mercaluz > generic_ticket > ...). |
| `generic_ticket.py` | `can_handle` estricta + rechazos OCR/NIF/largo. Mejoras extracción. |
| `generic_supplier.py` | Nuevo/actualizado: facturas no-ticket, aliases path, extracción base/cuota/total coherente. |
| `mercaluz.py` | Ajustes + fixtures nuevos (std/abv/resumen, ascii). |
| `repsol.py` | Ajustes + fixtures (std/resumen/partial). |
| `edieuropa.py` | Ajustes + fixture/test nuevo. |

**No tocados:** obramat, saltoki, eseaforms, maria, agus, generic (fallback).

### 3. Lógica endurecida
- **Registry resolution:** Priority descendente + trace debug. Path `/tickets/` fuerza generic_ticket.
- **Rechazo OCR basura:** Patterns noisy (ajoh/OILOF), líneas cortas sin vocales.
- **Validación importes:** Base + IVA = Total en bloque final → usar. Rechazo % como cuota.
- **NIF proveedor:** Cerca proveedor, ignora cliente/fiscal.
- **Impacto:** Menos falsos positivos tickets en facturas, mejor robustez OCR.

### 4. Tests nuevos/actualizados
- **Nuevos archivos tests:** `test_parser_mercaluz.py`, `test_parser_repsol.py`, `test_parser_edieuropa.py`.
- **Fixtures nuevos:** `sample_texts/mercaluz_*` (std/abv/resumen/ascii), `repsol_*` (std/resumen/partial), `edieuropa.txt`.
- **Tests actualizados:**
  | Test | Cubre |
  |------|-------|
  | `test_parser_priorities.py` | generic_ticket NO intercepta maria/agus/obramat/repsol. |
  | `test_parser_resolution.py` | Path no fuerza específico sin evidence, generic_ticket requiere strong signals. |
  | `test_parser_generic.py` | Incluye stricter generic_ticket + supplier. |
  | `test_scanner.py` | (Abierto, probable actualizaciones). |

**Validación:** 
```
pytest tests/test_parser_*.py -v
```

### 5. Qué sigue pendiente (por impacto real)
- **Alta prioridad:**
  - NIF ABV robusto en mercaluz.
  - Más OCR edge en generic_ticket (patterns basura adicionales).
  - Nombres ambiguos en generic_supplier (edge cases).
- **Media:**
  - Tickets edge repsol (simplificadas).
  - Más formatos saltoki.
  - Nuevo parser Minimax (mencionado).
- **Baja:** Validar fixtures reales en scanner operativa.

## Estado actual del repo (detectado)
- **docs/parsers.md:** Ya resume cambios previos (2026-04-08? → corregir fecha), tabla estado parsers.
- **Pestañas abiertas:** tests/fixtures para mercaluz/repsol/edieuropa/saltoki + parsers/src relacionados → foco en estos.
- **Tests coverage:** Amplio por parser específico + priorities/resolution/generic.
- **Próximo:** Commit cambios + pytest full + scanner real PDFs.

**Git status probable:** Modificados parsers/*.py, tests/test_parser_*.py, fixtures/sample_texts/*.txt.

