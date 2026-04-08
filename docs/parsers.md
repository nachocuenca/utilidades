# Parsers

## Visión general

La aplicación usa parsers especializados por emisor + genéricos. El registry (`src/parsers/registry.py`) resuelve por priority descendente hasta primer match en `can_handle(text)`.

**Orden actual (por priority descendente):**
1. obramat, saltoki, repsol, eseaforms, edieuropa, mercaluz (alta, específicos)
2. generic_ticket (prio=60, tickets strict)
3. maria, agus (específicos bajos)
4. generic_supplier (prio=20, facturas genéricas)
5. generic (fallback final)

Resolución incluye trace `matched_parsers` para debug. Path `/tickets/` fuerza generic_ticket.

## Cambios hechos hoy (2026-04-08)

Archivos tocados (git status + commits recientes):
- `src/parsers/registry.py`: Priorities explícitas, orden fijo, `evaluate()` con trace.
- `src/parsers/generic_ticket.py`: Endurecido `can_handle` (rechazo >60 líneas, >3 NIF, OCR basura top10, requiere ≥2 strong patterns O 1strong+support+total+fecha). Mejoras: proveedor top10 no fiscal/cliente, NIF cerca proveedor, fecha/total priorizadas.
- `src/parsers/generic_supplier.py`: Nueva para facturas estructura fiscal (base/cuota/total), evita tickets, path aliases (mercaluz→\"Componentes Eléctricos Mercaluz S.A\", etc.).
- `src/parsers/mercaluz.py`, `repsol.py`, `edieuropa.py`: Ajustes específicos + nuevos tests/fixtures.
- Tests: `test_parser_priorities.py` (generic_ticket no intercepta maria/agus/obramat/repsol), `test_parser_resolution.py` (path/evidence rules), nuevos `test_parser_mercaluz/edieuropa/repsol.py` + fixtures sample_texts.

**Impacto funcional:**
- Mejor distinción ticket/factura: menos falsos tickets en facturas largas/fiscales.
- Extracción robusta tickets: rechaza OCR basura, prioriza signals reales.
- Genéricos separados: supplier para facturas, ticket strict.
- Visibles operativa: scanner infer `tipo_documento=\"ticket\"` desde generic_ticket, trace en logs debug.

## Estado por parser

| Parser | Estado | Cubre bien | Corregido hoy | Pendiente |
|--------|--------|------------|---------------|-----------|
| obramat | OK | Facturas bricolaje | N/A | N/A |
| saltoki | OK | Resúmenes/facturas | N/A | Más formatos |
| repsol | Estable | Estándar/resúmenes/partial | Test fixtures nuevos | Tickets edge |
| eseaforms | OK | Formularios | N/A | N/A |
| edieuropa | Estable | Estándar | Nuevo test/fixture | N/A |
| mercaluz | Estable | ABV/std/resúmenes (ascii) | Nuevo test/fixtures | NIF ABV robusto |
| generic_ticket | Estable | Tickets strict (simplificadas/op) | Endurecido can_handle/extracciones | Más OCR edge |
| maria | OK | Energyinmotion | N/A | N/A |
| agus | OK | Clínica/fisio | N/A | N/A |
| generic_supplier | Nuevo | Facturas genéricas no-ticket | Separada, aliases path | Nombres ambiguos |
| generic | Fallback | Todo resto | N/A | N/A |

No eliminados/fusionados hoy.

## Criterios de extracción

- **Proveedor:** Línea top (no fiscal/cliente/OCR), path alias/hint fallback.
- **Cliente:** Cerca labels cliente/titular (no forzado en tickets).
- **Número factura:** OP/identificador en tickets, std en facturas.
- **Fecha fiscal:** Cerca \"fecha\", prior top tickets.
- **Importes:** Prior bottom líneas total, labels base/cuota/IVA. Rechazo basura OCR.
- **Ticket vs Factura:** Priority + can_handle strict (longitud/NIF/patterns). Path /tickets/ fuerza ticket.
- **Tipo IVA vs Cuota:** Labels cuota/base → IVA calculado si base+IVA=total.
- **Rechazo OCR:** Líneas upper cortas/no vowels, patterns noisy (ajoh/OILOF).

## Tests y validación

**Tests tocados/añadidos:**
- `test_parser_priorities.py`: No-intercept (maria/agus/obramat win).
- `test_parser_resolution.py`: Evidence requerida, path no fuerza específico.
- `test_parser_generic.py`: Incluye generic_ticket stricter.
- Nuevos: `test_parser_mercaluz.py`, `test_parser_edieuropa.py`, `test_parser_repsol.py`.

**Comandos validación mínima:**
```
pytest tests/test_parser_priorities.py tests/test_parser_resolution.py
```

**Completa:**
```
pytest tests/test_parser_*.py -v
```

## Pendiente real

- Robustez OCR en generic_ticket (más patterns basura).
- Parsers pendientes: Minimax (menciones commits).
- Deuda: Edge nombres ambiguos en generic_supplier.
- Warnings operativa: Tests pasados, pero validar fixtures reales en scanner.

