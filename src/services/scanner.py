from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config.settings import get_settings
from src.db.models import InvoiceUpsertData
from src.db.repositories import InvoiceRepository
from src.parsers.registry import resolve_parser_with_trace
from src.pdf.ocr import has_meaningful_text
from src.pdf.reader import read_pdf_text
from src.utils.files import list_pdf_files
from src.utils.hashing import sha256_file
from src.utils.ids import normalize_tax_id


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
    NON_FISCAL_FOLDER_HINTS = {
        "tgss",
        "seguridad social",
        "seguridad_social",
        "banco",
        "bancos",
        "bancario",
        "bancarios",
        "recibos",
        "recibos banco",
        "recibos bancarios",
        "no fiscal",
        "no_fiscal",
        "administrativo",
        "administrativos",
    }

    TGSS_STRONG_MARKERS = (
        "tesorería general de la seguridad social",
        "tesoreria general de la seguridad social",
        "seguridad social",
        "recibo de liquidación de cotizaciones",
        "recibo de liquidacion de cotizaciones",
        "relación nominal de trabajadores",
        "relacion nominal de trabajadores",
        "sistema red",
        "tc1",
        "rnt",
        "rlt",
    )

    BANK_RECEIPT_STRONG_MARKERS = (
        "titular de la domiciliación",
        "titular de la domiciliacion",
        "entidad emisora",
        "adeudo por domiciliación",
        "adeudo por domiciliacion",
        "domiciliación bancaria",
        "domiciliacion bancaria",
        "recibo bancario",
        "cargo en cuenta",
    )

    BANK_RECEIPT_SUPPORT_MARKERS = (
        "iban",
        "ccc",
        "bic",
        "sepa",
        "cuenta de cargo",
        "fecha cargo",
        "importe adeudado",
        "referencia del adeudo",
    )

    FISCAL_MARKERS = (
        "base imponible",
        "cuota iva",
        "importe iva",
        "total factura",
        "número de factura",
        "numero de factura",
        "nº factura",
        "factura simplificada",
    )

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

    def _normalize_text(self, text: str) -> str:
        return " ".join((text or "").replace("\r", "\n").split()).lower()

    def _looks_like_non_fiscal_document(
        self,
        text: str,
        pdf_path: Path,
        folder_origin: str | None,
    ) -> bool:
        normalized_text = self._normalize_text(text)
        path_text = str(pdf_path).replace("\\", "/").lower()
        folder_text = (folder_origin or "").replace("\\", "/").lower().strip()

        folder_tokens = {token.strip() for token in folder_text.split("/") if token.strip()}
        if folder_tokens & self.NON_FISCAL_FOLDER_HINTS:
            return True

        if any(marker in normalized_text for marker in self.TGSS_STRONG_MARKERS):
            fiscal_hits = sum(1 for marker in self.FISCAL_MARKERS if marker in normalized_text)
            if fiscal_hits == 0:
                return True

        bank_strong_hits = sum(1 for marker in self.BANK_RECEIPT_STRONG_MARKERS if marker in normalized_text)
        bank_support_hits = sum(1 for marker in self.BANK_RECEIPT_SUPPORT_MARKERS if marker in normalized_text)
        fiscal_hits = sum(1 for marker in self.FISCAL_MARKERS if marker in normalized_text)

        if bank_strong_hits >= 2 and fiscal_hits == 0:
            return True

        if bank_strong_hits >= 1 and bank_support_hits >= 2 and fiscal_hits == 0:
            return True

        if "recibos seguridad social" in normalized_text and fiscal_hits == 0:
            return True

        if (
            "titular de la domiciliación" in normalized_text
            or "titular de la domiciliacion" in normalized_text
        ) and "entidad emisora" in normalized_text and fiscal_hits == 0:
            return True

        return False

    def _infer_document_type(
        self,
        pdf_path: Path,
        folder_origin: str | None,
        text: str,
    ) -> str:
        path_text = str(pdf_path).replace("\\", "/").lower()
        folder_text = (folder_origin or "").lower()

        if "/tickets/" in path_text or folder_text == "tickets" or folder_text.startswith("tickets/"):
            return "ticket"

        if self._looks_like_non_fiscal_document(text, pdf_path, folder_origin):
            return "no_fiscal"

        return "factura"

    def _infer_document_type_from_parser(
        self,
        parser_name: str,
        pdf_path: Path,
        folder_origin: str | None,
        text: str,
    ) -> str:
        if "ticket" in parser_name.lower():
            return "ticket"

        if parser_name == "document_filter":
            return self._infer_document_type(pdf_path, folder_origin, text)

        return self._infer_document_type(pdf_path, folder_origin, text)

    def _apply_default_customer_context(
        self,
        upsert_data: InvoiceUpsertData,
        document_type: str,
        folder_origin: str | None,
    ) -> None:
        if not self._should_apply_default_customer_context(
            document_type=document_type,
            folder_origin=folder_origin,
        ):
            return

        default_name = self.settings.default_customer_name.strip()
        default_tax_id = normalize_tax_id(self.settings.default_customer_tax_id)

        if default_name:
            upsert_data.nombre_cliente = default_name

        if default_tax_id:
            upsert_data.nif_cliente = default_tax_id

    def _should_apply_default_customer_context(
        self,
        document_type: str,
        folder_origin: str | None,
    ) -> bool:
        if document_type != "factura":
            return False

        if not self.settings.force_default_customer_for_facturas:
            return False

        if folder_origin is None or str(folder_origin).strip() == "":
            return False

        return True

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

                result_info = self._process_file(
                    pdf_path=pdf_path,
                    file_hash=file_hash,
                    parser_name=parser_name,
                    folder_origin=folder_origin,
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

        result = self._process_file(
            pdf_path=path,
            file_hash=file_hash,
            parser_name=parser_name,
            folder_origin=folder_origin,
        )
        return int(result["invoice_id"])

    def _process_file(
        self,
        pdf_path: Path,
        file_hash: str,
        parser_name: str | None = None,
        folder_origin: str | None = None,
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

        pre_document_type = self._infer_document_type(
            pdf_path=pdf_path,
            folder_origin=folder_origin,
            text=read_result.text,
        )

        if pre_document_type == "no_fiscal":
            non_fiscal_reason = "Documento detectado como no fiscal (recibo bancario, TGSS o administrativo)."
            if review_reason:
                review_reason = f"{review_reason} {non_fiscal_reason}"
            else:
                review_reason = non_fiscal_reason

            upsert_data = InvoiceUpsertData(
                archivo=pdf_path.name,
                ruta_archivo=str(pdf_path.resolve()),
                hash_archivo=file_hash,
                tipo_documento="no_fiscal",
                parser_usado="document_filter",
                extractor_origen=read_result.extractor,
                requiere_revision_manual=True,
                motivo_revision=review_reason,
                carpeta_origen=folder_origin,
                texto_crudo=read_result.text,
            )

            invoice_id = self.repository.upsert(upsert_data)
            return {
                "invoice_id": invoice_id,
                "requires_review": True,
                "matched_parsers": ["document_filter"],
                "document_type": "no_fiscal",
            }

        resolution = resolve_parser_with_trace(
            text=read_result.text,
            file_path=pdf_path,
            parser_name=parser_name,
        )
        parser = resolution.selected_parser
        parsed = parser.parse(read_result.text, pdf_path).finalize()
        document_type = self._infer_document_type_from_parser(
            parser_name=parsed.parser_usado,
            pdf_path=pdf_path,
            folder_origin=folder_origin,
            text=read_result.text,
        )

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
            "matched_parsers": resolution.matched_parsers,
            "document_type": document_type,
        }
