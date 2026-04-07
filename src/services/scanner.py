from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config.settings import get_settings
from src.db.models import InvoiceUpsertData
from src.db.repositories import InvoiceRepository
from src.parsers.registry import resolve_parser
from src.pdf.reader import read_pdf_text
from src.utils.files import list_pdf_files
from src.utils.hashing import sha256_file


@dataclass(slots=True)
class ScanFailure:
    archivo: str
    ruta_archivo: str
    error: str


@dataclass(slots=True)
class ScanSummary:
    directorio: str
    total_encontrados: int = 0
    procesados: int = 0
    creados: int = 0
    actualizados: int = 0
    omitidos: int = 0
    fallidos: int = 0
    errores: list[ScanFailure] = field(default_factory=list)


class InvoiceScanner:
    def __init__(
        self,
        repository: InvoiceRepository | None = None,
        inbox_dir: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository or InvoiceRepository()
        self.inbox_dir = Path(inbox_dir or settings.inbox_dir).resolve()

    def scan(
        self,
        parser_name: str | None = None,
        recursive: bool = False,
        skip_known: bool = False,
    ) -> ScanSummary:
        files = list_pdf_files(self.inbox_dir, recursive=recursive)
        summary = ScanSummary(
            directorio=str(self.inbox_dir),
            total_encontrados=len(files),
        )

        for pdf_path in files:
            try:
                file_hash = sha256_file(pdf_path)

                if skip_known and self.repository.exists_by_hash(file_hash):
                    summary.omitidos += 1
                    continue

                existed_before = self.repository.exists_by_hash(file_hash)
                invoice_id = self._process_file(
                    pdf_path=pdf_path,
                    file_hash=file_hash,
                    parser_name=parser_name,
                )

                if invoice_id <= 0:
                    raise RuntimeError(f"No se pudo guardar la factura: {pdf_path.name}")

                summary.procesados += 1
                if existed_before:
                    summary.actualizados += 1
                else:
                    summary.creados += 1

            except Exception as error:
                summary.fallidos += 1
                summary.errores.append(
                    ScanFailure(
                        archivo=pdf_path.name,
                        ruta_archivo=str(pdf_path),
                        error=str(error),
                    )
                )

        return summary

    def scan_file(
        self,
        pdf_path: str | Path,
        parser_name: str | None = None,
    ) -> int:
        path = Path(pdf_path).resolve()
        file_hash = sha256_file(path)

        return self._process_file(
            pdf_path=path,
            file_hash=file_hash,
            parser_name=parser_name,
        )

    def _process_file(
        self,
        pdf_path: Path,
        file_hash: str,
        parser_name: str | None = None,
    ) -> int:
        read_result = read_pdf_text(pdf_path)
        parser = resolve_parser(
            text=read_result.text,
            file_path=pdf_path,
            parser_name=parser_name,
        )
        parsed = parser.parse(read_result.text, pdf_path).finalize()

        upsert_data = InvoiceUpsertData(
            archivo=parsed.archivo,
            ruta_archivo=parsed.ruta_archivo,
            hash_archivo=file_hash,
            parser_usado=parsed.parser_usado,
            nombre_proveedor=parsed.nombre_proveedor,
            nombre_cliente=parsed.nombre_cliente,
            nif_cliente=parsed.nif_cliente,
            cp_cliente=parsed.cp_cliente,
            numero_factura=parsed.numero_factura,
            fecha_factura=parsed.fecha_factura,
            subtotal=parsed.subtotal,
            iva=parsed.iva,
            total=parsed.total,
            texto_crudo=parsed.texto_crudo,
        )

        return self.repository.upsert(upsert_data)