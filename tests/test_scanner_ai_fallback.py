from __future__ import annotations

from pathlib import Path

from src.db.repositories import InvoiceRepository
from src.pdf.reader import PdfReadResult
from src.services.scanner import InvoiceScanner


def test_scanner_does_not_call_openai_when_fallback_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_FALLBACK_ENABLED", "false")

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "generic.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    text = """
    FACTURA
    Proveedor: ACME SUMINISTROS SL
    CIF proveedor: B12345678
    Nº factura: AC-2026-001
    Fecha factura: 08/04/2026
    Base imponible 100,00
    IVA 21,00
    Total factura 121,00
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        return PdfReadResult(file_path=Path(path), text=text, page_count=1, extractor="fake")

    class ForbiddenOpenAIExtractor:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("OpenAI no debería llamarse con fallback desactivado")

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)
    monkeypatch.setattr("src.services.scanner.OpenAIExtractor", ForbiddenOpenAIExtractor)

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    result = scanner._process_file(
        pdf_path=pdf_path,
        file_hash="hash",
        parser_name="generic",
        folder_origin=None,
    )

    stored = repository.list_invoices()

    assert result["invoice_id"] > 0
    assert len(stored) == 1

    invoice = stored[0]

    assert invoice.parser_usado == "generic"
    assert invoice.extractor_origen == "fake"
    assert "Fallback IA error" not in (invoice.motivo_revision or "")


def test_scanner_keeps_deterministic_data_when_openai_errors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_FALLBACK_ENABLED", "true")

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "generic.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    text = """
    FACTURA
    Proveedor: ACME SUMINISTROS SL
    CIF proveedor: B12345678
    Nº factura: AC-2026-001
    Fecha factura: 08/04/2026
    Base imponible 100,00
    IVA 21,00
    Total factura 121,00
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        return PdfReadResult(file_path=Path(path), text=text, page_count=1, extractor="fake")

    class FailingOpenAIExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract_from_pdf(self, *args, **kwargs):
            raise RuntimeError("429 Client Error: Too Many Requests")

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)
    monkeypatch.setattr("src.services.scanner.OpenAIExtractor", FailingOpenAIExtractor)

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    result = scanner._process_file(
        pdf_path=pdf_path,
        file_hash="hash",
        parser_name="generic",
        folder_origin=None,
    )

    stored = repository.list_invoices()

    assert result["invoice_id"] > 0
    assert len(stored) == 1

    invoice = stored[0]

    assert invoice.parser_usado == "generic"
    assert invoice.extractor_origen == "fake"

    # Lo importante: el fallo de OpenAI no debe machacar la extracción determinista.
    assert invoice.nombre_proveedor == "ACME SUMINISTROS SL"
    assert invoice.numero_factura == "AC-2026-001"
    assert invoice.fecha_factura == "08-04-2026"
    assert invoice.total == 121.0

    # Y tampoco debe convertir el motivo en un error de OpenAI.
    assert "Fallback IA error" not in (invoice.motivo_revision or "")
    assert "429 Client Error" not in (invoice.motivo_revision or "")

    # Con la política nueva, la revisión depende de campos reales, no de OpenAI.
    assert result["requires_review"] == bool(invoice.requiere_revision_manual)


def test_scanner_marks_incomplete_invoice_for_manual_review(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_FALLBACK_ENABLED", "false")

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "incomplete.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    text = """
    FACTURA
    Proveedor: ACME SUMINISTROS SL
    CIF proveedor: B12345678
    Fecha factura: 08/04/2026
    Base imponible 100,00
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        return PdfReadResult(file_path=Path(path), text=text, page_count=1, extractor="fake")

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    result = scanner._process_file(
        pdf_path=pdf_path,
        file_hash="hash",
        parser_name="generic",
        folder_origin=None,
    )

    stored = repository.list_invoices()

    assert result["requires_review"] is True
    assert len(stored) == 1

    invoice = stored[0]

    assert invoice.requiere_revision_manual is True
    assert "Falta número de factura" in (invoice.motivo_revision or "")
    assert "Falta total" in (invoice.motivo_revision or "")


def test_scanner_marks_invoice_without_number_but_with_calculated_total(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_FALLBACK_ENABLED", "false")

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "calculated_total.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    text = """
    FACTURA
    Proveedor: ACME SUMINISTROS SL
    CIF proveedor: B12345678
    Fecha factura: 08/04/2026
    Base imponible 100,00
    IVA 21,00
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        return PdfReadResult(file_path=Path(path), text=text, page_count=1, extractor="fake")

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    result = scanner._process_file(
        pdf_path=pdf_path,
        file_hash="hash",
        parser_name="generic",
        folder_origin=None,
    )

    stored = repository.list_invoices()

    assert result["requires_review"] is True
    assert len(stored) == 1

    invoice = stored[0]

    assert invoice.total == 121.0
    assert invoice.requiere_revision_manual is True
    assert "Falta número de factura" in (invoice.motivo_revision or "")
    assert "Falta total" not in (invoice.motivo_revision or "")


def test_scanner_does_not_require_invoice_fields_for_non_fiscal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_FALLBACK_ENABLED", "false")

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "bankinter.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    text = """
    Pago por transferencia
    BANKINTER
    Cuenta de cargo ES00 0000 0000 0000 0000 0000
    IBAN beneficiario ES00 1111 1111 1111 1111 1111
    Importe 150,00 EUR
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        return PdfReadResult(file_path=Path(path), text=text, page_count=1, extractor="fake")

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    result = scanner._process_file(
        pdf_path=pdf_path,
        file_hash="hash",
        parser_name=None,
        folder_origin=None,
    )

    stored = repository.list_invoices()

    assert result["invoice_id"] > 0
    assert len(stored) == 1

    invoice = stored[0]

    assert invoice.tipo_documento == "no_fiscal"
    assert invoice.requiere_revision_manual is False
    assert "Falta proveedor" not in (invoice.motivo_revision or "")
    assert "Falta número de factura" not in (invoice.motivo_revision or "")
    assert "Falta fecha" not in (invoice.motivo_revision or "")
    assert "Falta total" not in (invoice.motivo_revision or "")