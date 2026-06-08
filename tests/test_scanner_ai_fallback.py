from __future__ import annotations

from pathlib import Path

from src.db.repositories import InvoiceRepository
from src.pdf.reader import PdfReadResult
from src.services.scanner import InvoiceScanner


def test_scanner_does_not_call_openai_when_fallback_disabled(monkeypatch, tmp_path: Path, load_sample_text) -> None:
    monkeypatch.setenv("OPENAI_FALLBACK_ENABLED", "false")
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = inbox_dir / "amazon.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    text = load_sample_text("amazon_invoice_2026.txt")

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        return PdfReadResult(file_path=Path(path), text=text, page_count=1, extractor="fake")

    def fail_openai(*args, **kwargs):
        raise AssertionError("OpenAI fallback must stay disabled by default")

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)
    monkeypatch.setattr("src.services.scanner.OpenAIExtractor", fail_openai)

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    result = scanner._process_file(
        pdf_path=pdf_path,
        file_hash="hash",
        parser_name=None,
        folder_origin=None,
    )

    stored = repository.list_invoices()
    assert result["requires_review"] is False
    assert stored[0].parser_usado == "amazon"
    assert stored[0].motivo_revision is None


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
    Numero de factura: AC-2026-001
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
    assert result["requires_review"] is False
    assert stored[0].parser_usado == "generic"
    assert stored[0].total == 121.0
    assert stored[0].motivo_revision is None
