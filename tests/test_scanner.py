from __future__ import annotations

from pathlib import Path

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
    assert stored[0].nombre_proveedor == "Maria Gonzalez Arranz"
    assert stored[0].nombre_cliente == "ACME CONSULTING SL"

    second_summary = scanner.scan(skip_known=True)

    assert second_summary.total_encontrados == 1
    assert second_summary.omitidos == 1
    assert second_summary.procesados == 0
    assert repository.count() == 1