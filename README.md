# Utilidades Facturas

Proyecto local para escanear PDFs fiscales, resolver un parser determinista por proveedor y guardar el resultado normalizado en SQLite para revision operativa desde Streamlit.

## Snapshot verificado

Fecha de verificacion: `2026-04-09`.

Fuentes usadas para esta documentacion:
- codigo real del repo
- `data/app.db`
- `data/exports/facturas_20260409_090532.csv`
- `data/validation_strict_real_1t26_20260409.db`
- suite de tests del repo (`111 passed`)

Hechos verificados:
- Tipos documentales activos en runtime: `factura`, `ticket`, `no_fiscal`
- El filtro `no_fiscal` corta el flujo antes del registry y guarda `parser_usado=document_filter`
- El ultimo CSV real contiene `80` registros: `74 factura`, `6 no_fiscal`, `0 ticket`
- No hay filas finales con `generic`, `generic_supplier` ni `generic_ticket` en ese CSV
- El unico fallo visible en el CSV actual es `leroy_merlin` sin importes en `invoice (5).pdf` y `invoice (6).pdf`
- `data/app.db` y el CSV vivo proceden de un escaneo previo sobre `C:\Users\ignac\Downloads\1T26\1T 26\...`; no salen del `data/inbox` plano actual del repo

## Stack real

- Python 3.12
- Streamlit
- SQLite
- pandas
- pdfplumber
- pypdf
- pypdfium2 + pytesseract + Tesseract para OCR
- openpyxl
- pytest
- python-dotenv

## Flujo real

1. El usuario reescanea una carpeta desde Streamlit o desde `scripts/rescan.py`.
2. `src/services/scanner.py` lista PDFs, calcula `sha256` y puede omitir hashes ya conocidos.
3. `src/pdf/reader.py` intenta leer con `pdfplumber`, luego `pypdf` y usa OCR solo si el texto sigue siendo insuficiente y OCR esta habilitado.
4. El scanner clasifica primero el documento:
   - `ticket` si la ruta contiene `/tickets/`
   - `no_fiscal` si detecta TGSS, recibo bancario o senales administrativas
   - `factura` en el resto de casos
5. Si el resultado previo es `no_fiscal`, no entra al registry. Se guarda directamente con `parser_usado=document_filter` y `requiere_revision_manual=True`.
6. Si no es `no_fiscal`, el registry resuelve el parser ganador por prioridad descendente y conserva un trace runtime con `matched_parsers`.
7. El parser ganador extrae datos y `finalize()` normaliza nombres, NIF, fecha e importes, incluyendo calculo de importes faltantes cuando hay suficiente evidencia.
8. El scanner decide el `tipo_documento` final para persistencia. Hoy la base guarda `factura`, `ticket` o `no_fiscal`.
9. El cliente por defecto solo se aplica en scanner para `factura`, solo si `FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS=true` y solo cuando existe `carpeta_origen`.
10. El repositorio hace upsert por `hash_archivo`.
11. La UI consulta SQLite para tabla y detalle. El export CSV/XLSX existe en la capa de servicio y escribe en `data/exports/`.

## Resolucion de parser

Reglas reales:
- Si el usuario fuerza parser, se usa ese parser sin evaluar el resto.
- En modo automatico, `src/parsers/registry.py` ordena por `priority` descendente.
- Si hay empate de prioridad, gana el orden de registro actual en `_register_defaults()` porque el sort es estable.
- `generic_ticket` puede forzarse por ruta `/tickets/` aunque el texto sea debil.
- `generic_supplier` solo entra para documentos con pinta de factura y evidencia fiscal suficiente.
- `generic` es el fallback final y no debe ser la solucion principal para un proveedor conocido.

Registro actual:
- `leroy_merlin` 520
- `obramat` 500
- `saltoki` 490
- `legal_quality` 420
- `repsol` 360
- `versotel` 360
- `eseaforms` 355
- `edieuropa` 350
- `mercaluz` 345
- `davofrio` 340
- `fempa` 340
- `wurth` 340
- `levantia` 330
- `maria` 100
- `agus` 80
- `generic_ticket` 60
- `generic_supplier` 20
- `generic` 10

Detalle completo en `docs/parsers.md`.

## Tipos documentales soportados en este snapshot

- `factura`: parser especifico o generico de factura, con importes y datos fiscales si el documento lo permite.
- `ticket`: en el snapshot `2026-04-09` depende de `generic_ticket` o de un parser cuyo nombre contenga `ticket`. El ultimo CSV real no contiene filas `ticket`.
- `no_fiscal`: filtro previo de scanner para TGSS, recibos bancarios y administrativos. Se persiste con revision manual obligatoria.

## Reglas de negocio ya incorporadas

- En Dani, salvo tickets, el cliente objetivo es `Daniel Cuenca Moya / 48334490J`.
- En tickets manda el proveedor, no el cliente.
- La resolucion correcta del proyecto es determinista y especifica por proveedor.
- Si existe un bloque final coherente donde `Base + IVA = Total`, ese bloque manda.
- No se debe usar el NIF del cliente como NIF del proveedor.
- No se debe tratar el porcentaje de IVA como cuota de IVA.
- No se debe promocionar a proveedor texto OCR basura.

## Donde mirar cuando algo falla

- `docs/estado_actual.md`: estado real cerrado / medio cerrado / pendiente / riesgo.
- `docs/parsers.md`: registry real, prioridades y riesgos por parser.
- `docs/flujo_parsing.md`: flujo de entrada, clasificacion, resolucion y guardado.
- `src/services/scanner.py`: preclasificacion `ticket` / `no_fiscal`, cliente por defecto y persistencia.
- `src/parsers/registry.py`: orden real y desempate por registro.
- `tests/test_scanner.py`: comportamiento de scanner, `no_fiscal`, trace y cliente por defecto.
- `tests/test_parser_resolution.py` y `tests/test_parser_priorities.py`: reglas de resolucion.
- Tests dedicados por proveedor en `tests/test_parser_*.py`.
- La pantalla de detalle de Streamlit, en especial `texto_crudo`, para ver que texto real llego al parser.

## Arranque rapido

Instalacion:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .[dev]
Copy-Item .env.example .env
```

UI local:

```powershell
streamlit run app.py
```

Reescaneo CLI:

```powershell
python -m scripts.rescan --recursive
```

Inicializar base:

```powershell
python -m scripts.init_db
```

Tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Documentacion viva

- `docs/estado_actual.md`
- `docs/parsers.md`
- `docs/flujo_parsing.md`
- `docs/architecture.md`
- `CHANGELOG.md`
