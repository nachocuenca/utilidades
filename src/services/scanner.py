from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config.settings import get_settings
from src.db.models import InvoiceUpsertData
from src.db.repositories import InvoiceRepository
from src.parsers.registry import resolve_parser
from src.pdf.ocr import has_meaningful_text
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
    requieren_revision: int = 0
    errores: list[ScanFailure] = field(default_factory=list)


class InvoiceScanner:
    def __init__(
        self,
        repository: InvoiceRepository | None = None,
        inbox_dir: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.settings = settings
        self.repository = repository or InvoiceRepository()
        self.inbox_dir = Path(inbox_dir or settings.inbox_dir).resolve()

    def resolve_scan_dir(self, inbox_dir: str | Path | None = None) -> Path:
        if inbox_dir is None:
            return self.inbox_dir

        path = Path(inbox_dir)
        if not path.is_absolute():
            path = Path.cwd() / path

        return path.resolve()

    def _build_folder_origin(self, pdf_path: Path, scan_dir: Path) -> str | None:
        try:
            relative_parent = pdf_path.parent.relative_to(scan_dir)
        except ValueError:
            return pdf_path.parent.name or None

        if str(relative_parent) == ".":
            return None

        return relative_parent.as_posix()

    def _infer_document_type(self, pdf_path: Path, folder_origin: str | None) -> str:
        path_text = str(pdf_path).replace("\\", "/").lower()
        folder_text = (folder_origin or "").lower()

        if "/tickets/" in path_text or folder_text == "tickets" or folder_text.startswith("tickets/"):
            return "ticket"

        return "factura"

    def _apply_default_customer_context(
        self,
        upsert_data: InvoiceUpsertData,
        document_type: str,
        folder_origin: str | None,
    ) -> None:
        if document_type != "factura":
            return

        if not self.settings.force_default_customer_for_facturas:
            return

        # Solo aplicamos este contexto en escaneos por subcarpetas reales
        # (caso Dani por proveedor). No debe afectar a facturas genéricas
        # en la raíz ni a tests unitarios con PDFs sueltos.
        if folder_origin is None or str(folder_origin).strip() == "":
            return

        default_name = self.settings.default_customer_name.strip()
        default_tax_id = self.settings.default_customer_tax_id.strip()

        if default_name:
            upsert_data.nombre_cliente = default_name

        if default_tax_id:
            upsert_data.nif_cliente = default_tax_id

    def scan(
        self,
        parser_name: str | None = None,
        recursive: bool = False,
        skip_known: bool = False,
        inbox_dir: str | Path | None = None,
    ) -> ScanSummary:
        scan_dir = self.resolve_scan_dir(inbox_dir)

        if not scan_dir.exists():
            raise FileNotFoundError(f"La carpeta de escaneo no existe: {scan_dir}")

        if not scan_dir.is_dir():
            raise NotADirectoryError(f"La ruta de escaneo no es una carpeta: {scan_dir}")

        files = list_pdf_files(scan_dir, recursive=recursive)
        summary = ScanSummary(
            directorio=str(scan_dir),
            total_encontrados=len(files),
        )

        for pdf_path in files:
            try:
                file_hash = sha256_file(pdf_path)

                if skip_known and self.repository.exists_by_hash(file_hash):
                    summary.omitidos += 1
                    continue

                existed_before = self.repository.exists_by_hash(file_hash)
                folder_origin = self._build_folder_origin(pdf_path, scan_dir)
                document_type = self._infer_document_type(pdf_path, folder_origin)

                result_info = self._process_file(
                    pdf_path=pdf_path,
                    file_hash=file_hash,
                    parser_name=parser_name,
                    folder_origin=folder_origin,
                    document_type=document_type,
                )

                invoice_id = result_info["invoice_id"]
                requires_review = bool(result_info["requires_review"])

                if invoice_id <= 0:
                    raise RuntimeError(f"No se pudo guardar la factura: {pdf_path.name}")

                summary.procesados += 1
                if requires_review:
                    summary.requieren_revision += 1

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
        folder_origin = path.parent.name or None
        document_type = self._infer_document_type(path, folder_origin)

        result = self._process_file(
            pdf_path=path,
            file_hash=file_hash,
            parser_name=parser_name,
            folder_origin=folder_origin,
            document_type=document_type,
        )
        return int(result["invoice_id"])

    def _process_file(
        self,
        pdf_path: Path,
        file_hash: str,
        parser_name: str | None = None,
        folder_origin: str | None = None,
        document_type: str = "factura",
    ) -> dict[str, object]:
        read_result = read_pdf_text(pdf_path)

        text_is_meaningful = has_meaningful_text(
            read_result.text,
            min_text_length=self.settings.ocr_min_text_length,
        )

        requires_review = not text_is_meaningful
        review_reason: str | None = None

        if not text_is_meaningful:
            if read_result.extractor == "ocr":
                review_reason = "OCR ejecutado, pero el texto sigue siendo insuficiente."
            else:
                review_reason = "PDF sin texto util. Requiere OCR o revision manual."

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
            tipo_documento=document_type,
            parser_usado=parsed.parser_usado,
            extractor_origen=read_result.extractor,
            requiere_revision_manual=requires_review,
            motivo_revision=review_reason,
            carpeta_origen=folder_origin,
            nombre_proveedor=parsed.nombre_proveedor,
            nif_proveedor=parsed.nif_proveedor,
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

        self._apply_default_customer_context(
            upsert_data=upsert_data,
            document_type=document_type,
            folder_origin=folder_origin,
        )

        invoice_id = self.repository.upsert(upsert_data)
        return {
            "invoice_id": invoice_id,
            "requires_review": requires_review,
        }