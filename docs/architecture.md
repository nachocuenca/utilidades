# Arquitectura

## Objetivo

Esta utilidad procesa facturas PDF desde una carpeta local, extrae informacion clave, la guarda en SQLite y la muestra en una interfaz local en Streamlit.

## Capas del proyecto

### 1. Configuracion
- `config/settings.py`
- Carga `.env`
- Resuelve rutas locales
- Garantiza que existan directorios de trabajo

### 2. Base de datos
- `src/db/database.py`
- `src/db/models.py`
- `src/db/repositories.py`

Responsabilidades:
- crear esquema SQLite
- abrir conexiones
- persistir y consultar facturas
- exponer una capa simple para el resto de la app

### 3. Utilidades y lectura de PDF
- `src/utils/*`
- `src/pdf/*`

Responsabilidades:
- normalizar importes
- normalizar fechas
- limpiar NIF/CIF
- detectar codigos postales
- leer texto de PDFs
- limpiar texto crudo para parsers

### 4. Parsers
- `src/parsers/base.py`
- `src/parsers/registry.py`
- `src/parsers/generic.py`
- `src/parsers/maria.py`
- `src/parsers/agus.py`

Responsabilidades:
- decidir que parser aplica
- extraer campos de negocio
- encapsular logica especifica por emisor
- dejar desacoplada la evolucion futura

### 5. Servicios
- `src/services/scanner.py`
- `src/services/exporter.py`
- `src/services/invoice_service.py`

Responsabilidades:
- coordinar lectura de PDFs
- resolver parser
- guardar resultados
- exportar CSV y XLSX
- exponer operaciones listas para UI y scripts

### 6. Interfaz local
- `app.py`
- `src/ui/components.py`
- `src/ui/pages/*`

Responsabilidades:
- mostrar tabla de facturas
- buscar y filtrar
- reescanear carpeta
- abrir detalle
- descargar exportaciones

## Flujo principal

1. El usuario deja PDFs en `data/inbox/`
2. El escaner lista archivos PDF
3. Se lee el texto del PDF
4. El registry resuelve el parser adecuado
5. El parser devuelve datos normalizados
6. El repositorio hace upsert en SQLite
7. Streamlit muestra y exporta resultados

## Criterios de diseno

- local first
- sin sobrearquitectura web
- SQLite para persistencia simple
- parsers desacoplados por emisor
- texto crudo guardado para depuracion
- estructura clara para GitHub y mantenimiento

## Puntos de extension

- nuevos parsers en `src/parsers/`
- reglas nuevas de nombres, importes o fechas en `src/utils/`
- nuevos filtros o acciones de UI en `src/ui/`
- exportaciones adicionales en `src/services/exporter.py`