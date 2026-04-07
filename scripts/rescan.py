from __future__ import annotations

import argparse
from pathlib import Path

from config.settings import get_settings
from src.db.repositories import InvoiceRepository
from src.parsers.registry import get_parser_registry
from src.services.scanner import InvoiceScanner


def build_parser() -> argparse.ArgumentParser:
    registry = get_parser_registry()

    parser = argparse.ArgumentParser(description="Reescanea la carpeta local de facturas PDF.")
    parser.add_argument(
        "--parser",
        dest="parser_name",
        choices=["auto", *registry.list_names()],
        default="auto",
        help="Parser forzado. Por defecto intenta resolver automaticamente.",
    )
    parser.add_argument(
        "--inbox-dir",
        dest="inbox_dir",
        default=None,
        help="Ruta alternativa de carpeta de entrada.",
    )
    parser.add_argument(
        "--db-path",
        dest="db_path",
        default=None,
        help="Ruta alternativa al fichero SQLite.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Busca PDFs tambien en subcarpetas.",
    )
    parser.add_argument(
        "--skip-known",
        action="store_true",
        help="Omite archivos cuyo hash ya existe en base de datos.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()

    repository = InvoiceRepository(db_path=args.db_path)
    inbox_dir = Path(args.inbox_dir).resolve() if args.inbox_dir else settings.inbox_dir

    scanner = InvoiceScanner(
        repository=repository,
        inbox_dir=inbox_dir,
    )

    summary = scanner.scan(
        parser_name=None if args.parser_name == "auto" else args.parser_name,
        recursive=args.recursive,
        skip_known=args.skip_known,
    )

    print(f"Directorio: {summary.directorio}")
    print(f"Encontrados: {summary.total_encontrados}")
    print(f"Procesados: {summary.procesados}")
    print(f"Creados: {summary.creados}")
    print(f"Actualizados: {summary.actualizados}")
    print(f"Omitidos: {summary.omitidos}")
    print(f"Fallidos: {summary.fallidos}")

    if summary.errores:
        print("")
        print("Errores:")
        for item in summary.errores:
            print(f"- {item.archivo}: {item.error}")

    return 1 if summary.fallidos > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())