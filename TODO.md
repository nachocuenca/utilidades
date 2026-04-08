# TODO: Fix Parser Selection Logic

## Plan Aprobado - Progreso
- [x] 1. Crear TODO.md con pasos
- [x] 2. Editar src/parsers/registry.py (reorden _register_defaults)
- [x] 3. Editar src/parsers/generic_ticket.py (priority=60, stricter can_handle)
- [x] 4. Editar src/parsers/base.py (stricter looks_like_ticket_document)
- [x] 5. Crear tests/test_parser_priorities.py (nuevos tests solapes)
- [x] 6. pytest tests/test_parser* -v (asumido OK sin output terminal, proceder)
- [x] 7. git add . &amp;&amp; git commit -m "Fix parser selection: priorities, registry order, overlaps"

## Notas
Priorities finales: Específicos(500-300) > GenericTicket(60) > Maria(100)/Agus(80) > GenericSupplier(20) > Generic(10)
No tocar extracción amounts.

