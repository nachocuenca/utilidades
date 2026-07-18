from __future__ import annotations

from pathlib import Path

from src.db.database import get_connection, init_database
from src.db.models import INVOICE_DB_FIELDS, InvoiceRecord, InvoiceUpsertData

SEARCHABLE_COLUMNS = (
    "archivo",
    "tipo_documento",
    "carpeta_origen",
    "nombre_proveedor",
    "nif_proveedor",
    "nombre_cliente",
    "nif_cliente",
    "cp_cliente",
    "numero_factura",
    "fecha_factura",
    "parser_usado",
    "extractor_origen",
    "motivo_revision",
)


class InvoiceRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        init_database(self.db_path)

    def upsert(self, invoice: InvoiceUpsertData) -> int:
        payload = invoice.as_db_dict()
        columns = ", ".join(payload.keys())
        placeholders = ", ".join(f":{key}" for key in payload.keys())

        update_assignments = [
            f"{column} = excluded.{column}"
            for column in payload.keys()
            if column != "hash_archivo"
        ]
        update_assignments.append("updated_at = CURRENT_TIMESTAMP")
        update_clause = ", ".join(update_assignments)

        query = f"""
        INSERT INTO facturas ({columns})
        VALUES ({placeholders})
        ON CONFLICT(hash_archivo) DO UPDATE SET
            {update_clause};
        """

        with get_connection(self.db_path) as connection:
            connection.execute(query, payload)
            row = connection.execute(
                "SELECT id FROM facturas WHERE hash_archivo = ?;",
                (invoice.hash_archivo,),
            ).fetchone()

            if row is None:
                raise RuntimeError("No se pudo recuperar la factura guardada.")

            return int(row["id"])

    def delete_all(self) -> int:
        with get_connection(self.db_path) as connection:
            row = connection.execute("SELECT COUNT(*) AS total_registros FROM facturas;").fetchone()
            total = int(row["total_registros"]) if row is not None else 0

            connection.execute("DELETE FROM facturas;")
            try:
                connection.execute("DELETE FROM sqlite_sequence WHERE name = 'facturas';")
            except Exception:
                pass

            connection.commit()
            return total

    def get_by_id(self, invoice_id: int) -> InvoiceRecord | None:
        query = """
        SELECT
            id,
            archivo,
            ruta_archivo,
            hash_archivo,
            tipo_documento,
            parser_usado,
            extractor_origen,
            requiere_revision_manual,
            motivo_revision,
            carpeta_origen,
            nombre_proveedor,
            nif_proveedor,
            nombre_cliente,
            nif_cliente,
            cp_cliente,
            numero_factura,
            fecha_factura,
            subtotal,
            iva,
            total,
            texto_crudo,
            created_at,
            updated_at
        FROM facturas
        WHERE id = ?;
        """

        with get_connection(self.db_path) as connection:
            row = connection.execute(query, (invoice_id,)).fetchone()

        if row is None:
            return None

        return InvoiceRecord.from_row(row)

    def get_by_hash(self, file_hash: str) -> InvoiceRecord | None:
        query = """
        SELECT
            id,
            archivo,
            ruta_archivo,
            hash_archivo,
            tipo_documento,
            parser_usado,
            extractor_origen,
            requiere_revision_manual,
            motivo_revision,
            carpeta_origen,
            nombre_proveedor,
            nif_proveedor,
            nombre_cliente,
            nif_cliente,
            cp_cliente,
            numero_factura,
            fecha_factura,
            subtotal,
            iva,
            total,
            texto_crudo,
            created_at,
            updated_at
        FROM facturas
        WHERE hash_archivo = ?;
        """

        with get_connection(self.db_path) as connection:
            row = connection.execute(query, (file_hash,)).fetchone()

        if row is None:
            return None

        return InvoiceRecord.from_row(row)

    def exists_by_hash(self, file_hash: str) -> bool:
        query = "SELECT 1 FROM facturas WHERE hash_archivo = ? LIMIT 1;"

        with get_connection(self.db_path) as connection:
            row = connection.execute(query, (file_hash,)).fetchone()

        return row is not None

    def list_invoices(
        self,
        search: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        only_manual_review: bool | None = None,
        tipo_documento: str | None = None,
        carpeta_origen: str | None = None,
    ) -> list[InvoiceRecord]:
        where_clause, params = self._build_search_clause(
            search=search,
            only_manual_review=only_manual_review,
            tipo_documento=tipo_documento,
            carpeta_origen=carpeta_origen,
        )

        query = f"""
        SELECT
            id,
            archivo,
            ruta_archivo,
            hash_archivo,
            tipo_documento,
            parser_usado,
            extractor_origen,
            requiere_revision_manual,
            motivo_revision,
            carpeta_origen,
            nombre_proveedor,
            nif_proveedor,
            nombre_cliente,
            nif_cliente,
            cp_cliente,
            numero_factura,
            fecha_factura,
            subtotal,
            iva,
            total,
            texto_crudo,
            created_at,
            updated_at
        FROM facturas
        {where_clause}
        ORDER BY
            COALESCE(fecha_factura, '') DESC,
            id DESC
        """

        if limit is not None:
            query += " LIMIT ? OFFSET ?;"
            params.extend([limit, offset])
        else:
            query += ";"

        with get_connection(self.db_path) as connection:
            rows = connection.execute(query, params).fetchall()

        return [InvoiceRecord.from_row(row) for row in rows]

    def count(
        self,
        search: str | None = None,
        only_manual_review: bool | None = None,
        tipo_documento: str | None = None,
        carpeta_origen: str | None = None,
    ) -> int:
        where_clause, params = self._build_search_clause(
            search=search,
            only_manual_review=only_manual_review,
            tipo_documento=tipo_documento,
            carpeta_origen=carpeta_origen,
        )

        query = f"""
        SELECT COUNT(*) AS total_registros
        FROM facturas
        {where_clause};
        """

        with get_connection(self.db_path) as connection:
            row = connection.execute(query, params).fetchone()

        if row is None:
            return 0

        return int(row["total_registros"])

    def list_for_export(
        self,
        search: str | None = None,
        only_manual_review: bool | None = None,
        tipo_documento: str | None = None,
        carpeta_origen: str | None = None,
    ) -> list[dict[str, object | None]]:
        records = self.list_invoices(
            search=search,
            only_manual_review=only_manual_review,
            tipo_documento=tipo_documento,
            carpeta_origen=carpeta_origen,
        )

        export_rows: list[dict[str, object | None]] = []
        for record in records:
            export_rows.append(
                {
                    "id": record.id,
                    **{field_name: getattr(record, field_name) for field_name in INVOICE_DB_FIELDS},
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            )

        return export_rows

    def _build_search_clause(
        self,
        search: str | None,
        only_manual_review: bool | None = None,
        tipo_documento: str | None = None,
        carpeta_origen: str | None = None,
    ) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []

        if search is not None and search.strip() != "":
            term = f"%{search.strip()}%"
            expressions = [f"COALESCE({column}, '') LIKE ?" for column in SEARCHABLE_COLUMNS]
            expressions.append("COALESCE(CAST(total AS TEXT), '') LIKE ?")
            clauses.append("(" + " OR ".join(expressions) + ")")
            params.extend([term] * len(expressions))

        if only_manual_review is True:
            clauses.append("requiere_revision_manual = 1")

        if tipo_documento is not None and tipo_documento.strip() != "":
            clauses.append("tipo_documento = ?")
            params.append(tipo_documento.strip())

        if carpeta_origen is not None and str(carpeta_origen).strip() != "":
            clauses.append("carpeta_origen = ?")
            params.append(str(carpeta_origen).strip())

        if not clauses:
            return "", []

        return "WHERE " + " AND ".join(clauses), params