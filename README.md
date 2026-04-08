# Utilidades

Utilidad local para procesar facturas/tickets PDF desde `data/inbox/`, extraer datos, guardar en SQLite, revisar/exportar via Streamlit.

## Stack

- Python 3.12
- Streamlit
- SQLite
- pandas
- pdfplumber/pypdf
- pytest
- python-dotenv

## Objetivo funcional

- Leer PDFs → texto crudo.
- Resolver parser por priority/text.
- Extraer: proveedor/cliente/NIF/CP/num/fecha/subtotal/IVA/total/tipo_doc.
- Persistir SQLite con hash_archivo upsert.
- UI: tabla filtros, detalle texto_crudo, reescaneo, CSV/XLSX.
- Parsers: específicos (obramat/saltoki/repsol/mercaluz/edieuropa/eseaforms/maria/agus) + genéricos (generic_ticket prio60 strict, generic_supplier facturas, generic fallback).

## Cambios recientes (2026-04-08)

- Registry: priorities explícitas/trace matched_parsers.
- generic_ticket: stricter (rechazo largo/OCR/NIF muchos, patterns obligatorios), extracciones mejoradas.
- Nueva generic_supplier para facturas no-ticket, path aliases.
- Específicos ajustados (mercaluz ABV, repsol/edieuropa).
- Tests nuevos priorities/resolution/mercaluz/edieuropa/repsol.

Ver `docs/parsers.md` completo.

## Instalación (PowerShell)

```
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install --upgrade pip
pip install -e .[dev]
Copy-Item .env.example .env
```

## Uso

**UI local:**
```
streamlit run app.py
```

**CLI reescaneo:**
```
python -m scripts.rescan --recursive
```

**Init DB:**
```
python -m scripts.init_db
```

**Tests validación:**
```
pytest tests/test_parser_*.py -v
```

## Estructura

```
utilidades/
├── README.md ← esta
├── docs/ ← parsers.md architecture.md actualizados
├── src/parsers/ ← registry.py todos parsers
├── tests/ ← fixtures sample_texts nuevos, test_parser_*.py
├── data/inbox/ ← PDFs
└── data/app.db
```

Docs detallados: `docs/parsers.md` (estado/cambios/validación).

