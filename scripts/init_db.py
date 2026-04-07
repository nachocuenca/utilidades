from __future__ import annotations

import argparse
from pathlib import Path

from config.settings import get_settings
from src.db.database import init_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inicializa la base de datos SQLite de la utilidad.")
    parser.add_argument(
        "--db-path",
        dest="db_path",
        default=None,
        help="Ruta alternativa al fichero SQLite.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    target = Path(args.db_path).resolve() if args.db_path else settings.database_path

    init_database(target)

    print(f"Base de datos inicializada en: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())