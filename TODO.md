# Tareas pendientes - Fase Corrección Extracción Base Genérica ✅ COMPLETADA

## Plan ejecutado:

1. [x] **CREAR TODO.md** 
2. [x] Editar `src/parsers/base.py` 
   - ✅ is_probable_noise_name(): +detectores OCR (palíndromos, ajoh/oilof)
   - ✅ extract_supplier_tax_id(): +patrones cliente (adquiriente, consumidor final)
   - ✅ clean_invoice_number_candidate(): +filtros anti-OCR (solo vocales/consonantes)
   - ✅ extract_summary_amounts(): tail[-25:], Base+IVA=Total tol 0.01€
   - ✅ extract_labeled_amount(): ignore_percent=True default
3. [x] Editar `src/utils/names.py`
   - ✅ +NOISE_NAME_PATTERNS (ajoh?/oilof?)
4. [x] Editar `tests/test_parser_generic.py`
   - ✅ +5 tests: ocr_proveedor, nif_cliente, numero_ocr, iva_cuota, bloque_final
5. [x] **TESTEAR**: pytest tests/test_parser_generic.py -v → **14 PASSED**

## Siguiente:
- [ ] git add/commit/push
- [ ] Tarea nueva?
