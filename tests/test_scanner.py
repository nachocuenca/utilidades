from __future__ import annotations

from pathlib import Path

from config.settings import get_settings
from src.db.repositories import InvoiceRepository
from src.pdf.reader import PdfReadResult
from src.services.scanner import InvoiceScanner


def test_scanner_processes_pdf_and_persists_result(load_sample_text, monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "maria_01.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)
    sample_text = load_sample_text("maria_01.txt")

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=sample_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    summary = scanner.scan()

    assert summary.total_encontrados == 1
    assert summary.procesados == 1
    assert summary.creados == 1
    assert summary.actualizados == 0
    assert summary.fallidos == 0
    assert repository.count() == 1

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].nombre_proveedor == "María González Arranz"
    assert stored[0].nombre_cliente == "ACME CONSULTING SL"

    second_summary = scanner.scan(skip_known=True)

    assert second_summary.total_encontrados == 1
    assert second_summary.omitidos == 1
    assert second_summary.procesados == 0
    assert repository.count() == 1


def test_scanner_marks_ticket_type_from_resolved_parser_and_skips_default_customer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS", "true")
    monkeypatch.setenv("DEFAULT_CUSTOMER_NAME", "Daniel Cuenca Moya")
    monkeypatch.setenv("DEFAULT_CUSTOMER_TAX_ID", "48334490J")
    get_settings.cache_clear()

    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "gasolina"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "ticket_repsol.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    ticket_text = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: TK-2026-77
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=ticket_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    scanner.scan(recursive=True)

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].parser_usado == "generic_ticket"
    assert stored[0].tipo_documento == "ticket"
    assert stored[0].nombre_cliente is None
    assert stored[0].nif_cliente is None


def test_scanner_process_file_returns_parser_trace_with_matched_parsers(monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "varios"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "ticket_fuera_de_carpeta.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    ticket_text = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: 998877
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=ticket_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    result = scanner._process_file(
        pdf_path=pdf_path.resolve(),
        file_hash="dummyhash",
        parser_name=None,
        folder_origin="varios",
    )

    assert isinstance(result["matched_parsers"], list)
    assert "generic_ticket" in result["matched_parsers"]
    assert result["document_type"] == "ticket"
    assert int(result["invoice_id"]) > 0
