# IA Local – Fuente de Verdad

## 1. Propósito
Existe una vía IA local separada del flujo normal. La pantalla normal actual no debe contaminarse ni mezclar lógica con la vía IA.

## 2. Principios del proyecto
- Pantalla normal = flujo actual estable
- Pantalla IA = flujo separado
- No usar OpenAI
- No usar API keys
- No usar fallback cloud
- No romper exportación ni flujo normal

## 3. Runtime local obligatorio
- Provider local: Ollama
- Modelo obligatorio: `qwen2.5vl:7b`
- Endpoint local: `http://localhost:11434/api`
- No cambiar de modelo sin instrucción expresa
- No vuelvas a preguntarme qué modelo usar. Usa `qwen2.5vl:7b` sobre Ollama local hasta nuevo aviso.

## 4. Comandos operativos
- Comprobar Ollama:
  - `ollama list`
  - `curl http://localhost:11434/api/tags`
- Pull del modelo:
  - `ollama pull qwen2.5vl:7b`
- Prueba local rápida:
  - `ollama run qwen2.5vl:7b --prompt "¿Cuánto es 2+2?"`
- Ejemplo PowerShell:
  - `Invoke-RestMethod -Uri http://localhost:11434/api/generate -Method POST -Body '{"model":"qwen2.5vl:7b","prompt":"..."}' -ContentType 'application/json'`

## 5. Alcance de la vía IA local
- Puede tocar: extracción, OCR visual, postproceso, validación, comparación
- No puede tocar DB sin instrucción explícita
- No procesar todo el inbox sin orden
- No hardcodear valores del Excel para simular extracción correcta
- No usar archivos de ejemplo para justificar resultados

## 6. Flujo correcto de trabajo
1. Leer PDF real
2. Convertir a imagen/páginas
3. Llamar a Ollama local
4. Pedir JSON estructurado
5. Aplicar postproceso determinista
6. Validar
7. Comparar contra Excel cuando exista golden dataset

## 7. Golden dataset / fuente de verdad
- Usar Excel real cuando exista
- El Excel manda frente a la salida IA
- Para Benioffi:
  - Excel: `utilidadesgit/data/acreedores benioffi.xlsx`
  - Hoja: `facturas_20260414_124915`
  - PDFs reales: `utilidadesgit/data/inbox`

## 8. Reglas de seguridad y calidad
- Si devuelve placeholders tipo “Empresa XYZ”, “Cliente ABC”, etc., la extracción es inválida
- Si no hay evidencia clara, devolver `null`
- No aceptar número de ticket/caja como factura fiscal salvo evidencia fuerte
- No intercambiar proveedor y cliente
- `cp_cliente` solo del bloque cliente si existe
- Importes solo si hay bloque fiscal coherente

## 9. Errores típicos ya detectados
- Script que ignoraba el argumento de ruta y leía siempre el mismo PDF
- Riesgo de hardcodear valores del Excel
- Riesgo de dar por bueno JSON mal mapeado
- Riesgo de usar runtime incorrecto o modelo equivocado

## 10. Forma de entregar resultados
Para cada prueba:
- PDF usado
- RAW response
- JSON tras postproceso
- Validator result
- Comparación con Excel si aplica
- No cerrar tareas con resúmenes vagos
- No pedir permiso entre micro pasos
- Solo parar si:
  - Va a tocar DB
  - Va a cambiar arquitectura
  - No hay evidencia suficiente en el PDF

## 11. Estado actual conocido
- Extracción local funcional con Ollama y modelo `qwen2.5vl:7b`
- Validación y comparación con Excel implementadas
- Detectado y corregido bug de ruta en script de extracción
- No volver a hardcodear valores del Excel
- No usar modelos distintos sin instrucción
- Pendiente: mejorar robustez ante layouts nuevos y validar más casos reales

## 12. Regla de arranque obligatorio
**Antes de tocar cualquier parte de la vía IA local, leer `docs/ia-local.md`.**

**Si el contenido del documento contradice una suposición previa, manda el documento.**

**Si se hace un cambio relevante en la vía IA local, actualizar `docs/ia-local.md` al terminar.**
