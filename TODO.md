# TODO: Corregir 6 pytest fails (71/77 → 77/77)

## Plan aprobado paso a paso:

### ✅ Paso 0: Crear TODO.md [COMPLETADO]

### ⏳ Paso 1: Corregir src/parsers/repsol.py
- Regex NIF tolerante HTML/acentos para test_repsol_std_complete_parsing
- extract_repsol_subtotal específico "Base Imponible" para test_repsol_resumen_coherente  
- Normalizar fecha a yyyy-mm-dd para test_repsol_partial_no_desglose

### Paso 2: Corregir src/parsers/generic_ticket.py
- Aflojar extract_supplier_name para aceptar REPSOL upper-case
- Mejorar TOTAL_LINE_PATTERN para test_generic_ticket_extrae_total_final + repsol_simplificada

### Paso 3: Corregir tests/test_parser_priorities.py  
- Cambiar assert para NO requerir 'repsol' en matched_parsers (can_handle False lógico)

### Paso 4: Verificar/validar
```
pytest tests/test_parser_repsol.py -v
pytest tests/test_parser_generic.py::test_generic_ticket_can_handle_acepta_repsol_simplificada -v  
pytest tests/test_parser_priorities.py::test_repsol_simplificada_still_goes_to_generic_ticket -v
pytest -q  # Debe ser 77/77
streamlit run app.py  # Verificar arranque
```

### Paso 5: Completar ✅

