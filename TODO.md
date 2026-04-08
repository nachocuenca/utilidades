# TODO - Ciclo de endurecimiento de parsers (sin commit)

- [ ] 1. Endurecer inferencia agresiva de proveedor en parsers genéricos
  - [ ] 1.1 Añadir alias por carpeta/origen (LEVANTIA, DAVOFRIO, LEROY, etc.)
  - [ ] 1.2 Bloquear candidatos OCR basura (ej. OILOF, ajoH) cuando haya señales más fiables
  - [ ] 1.3 Mantener compatibilidad con reglas actuales y tests existentes

- [ ] 2. Mejorar inferencia agresiva de importes en `base.py`
  - [ ] 2.1 Detección robusta de ABONO/RECTIFICATIVA
  - [ ] 2.2 Coherencia de signo negativo en subtotal/iva/total
  - [ ] 2.3 Reconciliación matemática cuando falten campos

- [ ] 3. Añadir tests de regresión
  - [ ] 3.1 Caso LEVANTIA con OCR ruidoso
  - [ ] 3.2 Caso DAVOFRIO con proveedor corrupto
  - [ ] 3.3 Caso ABONO/RECTIFICATIVA con importes negativos

- [ ] 4. Validación técnica
  - [ ] 4.1 Ejecutar pytest
  - [ ] 4.2 Reescaneo real de `C:\Users\ignac\Downloads\1T26`
  - [ ] 4.3 Exportar CSV y auditar incoherencias objetivo
