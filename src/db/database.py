from __future__ import annotations

import sqlite3
from pathlib import Path

from config.settings import get_settings

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS facturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    hash_archivo TEXT NOT NULL UNIQUE,
    parser_usado TEXT NOT NULL DEFAULT 'generic',
    extractor_origen TEXT NOT NULL DEFAULT 'unknown',
    requiere_revision_manual INTEGER NOT NULL DEFAULT 0,
    motivo_revision TEXT,
    nombre_proveedor TEXT,
    nombre_cliente TEXT,
    nif_cliente TEXT,
    cp_cliente TEXT,
    numero_factura TEXT,
    fecha_factura TEXT,
    subtotal REAL,
    iva REAL,
    total REAL,
    texto_crudo TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

INDEXES_SQL = (
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_archivo
        ON facturas (archivo);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_nombre_proveedor
        ON facturas (nombre_proveedor);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_nombre_cliente
        ON facturas (nombre_cliente);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_nif_cliente
        ON facturas (nif_cliente);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_numero_factura
        ON facturas (numero_factura);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_fecha_factura
        ON facturas (fecha_factura);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_total
        ON facturas (total);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_facturas_revision_manual
        ON facturas (requiere_revision_manual);
    """,
)

TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_facturas_updated_at
AFTER UPDATE ON facturas
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE facturas
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;
"""

REQUIRED_COLUMNS = {
    "extractor_origen": "TEXT NOT NULL DEFAULT 'unknown'",
    "requiere_revision_manual": "INTEGER NOT NULL DEFAULT 0",
    "motivo_revision": "TEXT",
}


def _resolve_database_path(db_path: str | Path | None = None) -> Path:
    settings = get_settings()

    if db_path is None:
        return settings.database_path

    path = Path(db_path)
    if not path.is_absolute():
        path = settings.project_root / path

    return path.resolve()


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    database_path = _resolve_database_path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def _get_existing_columns(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("PRAGMA table_info(facturas);").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_required_columns(connection: sqlite3.Connection) -> None:
    existing_columns = _get_existing_columns(connection)

    for column_name, column_definition in REQUIRED_COLUMNS.items():
        if column_name in existing_columns:
            continue

        connection.execute(
            f"ALTER TABLE facturas ADD COLUMN {column_name} {column_definition};"
        )

    connection.commit()


def _create_indexes(connection: sqlite3.Connection) -> None:
    for statement in INDEXES_SQL:
        connection.execute(statement)
    connection.commit()


def _create_triggers(connection: sqlite3.Connection) -> None:
    connection.execute(TRIGGER_SQL)
    connection.commit()


def create_tables(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_TABLE_SQL)
    connection.commit()

    _ensure_required_columns(connection)
    _create_indexes(connection)
    _create_triggers(connection)


def init_database(db_path: str | Path | None = None) -> None:
    with get_connection(db_path) as connection:
        create_tables(connection)