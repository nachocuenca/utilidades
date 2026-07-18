from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import get_settings
from src.db.repositories import InvoiceRepository
from src.pdf.reader import PdfReadResult
from src.parsers.ortoprono import OrtopronoInvoiceParser
from src.parsers.registry import resolve_parser_with_trace
from src.services.scanner import InvoiceScanner

ORTOPRONO_PATH = Path("tests/fixtures/sample_pdfs/ortoprono_invoice.pdf")


def test_ortoprono_parser_extracts_real_ocr_fields(load_sample_text) -> None:
    text = load_sample_text("ortoprono_0000015.txt")
    parser = OrtopronoInvoiceParser()

    assert parser.can_handle(text, ORTOPRONO_PATH) is True

    result = parser.parse(text, ORTOPRONO_PATH)

    assert result.parser_usado == "ortoprono"
    assert result.nombre_proveedor == "Organizacion de Servicios Ortopedicos Totales, S.L.U."
    assert result.nif_proveedor == "B46264305"
    assert result.nombre_cliente == "Cliente Prueba Test"
    assert result.nif_cliente == "12345678Z"
    assert result.cp_cliente == "03503"
    assert result.numero_factura == "FA-2003759"
    assert result.fecha_factura == "22-05-2026"
    assert result.subtotal == pytest.approx(54.82)
    assert result.iva == pytest.approx(5.48)
    assert result.total == pytest.approx(60.30)


def test_ortoprono_can_handle_ocr_variant_without_footer_tax_id() -> None:
    text = """
    ORTOPRONO
    ORTOPEDIA TECNICA
    Factura
    FA-2003759 22/05/2026
    IVA 10% 54,82 5,48
    60,30
    """

    assert OrtopronoInvoiceParser().can_handle(text, Path("ortoprono.pdf")) is True


def test_ortoprono_rejects_clear_ticket() -> None:
    text = """
    ORTOPRONO
    FACTURA SIMPLIFICADA
    Ticket 123
    N° OP: 998877
    Fecha: 22/05/2026
    Total: 60,30
    Efectivo: 60,30
    """

    assert OrtopronoInvoiceParser().can_handle(text, Path("ticket.pdf")) is False


def test_registry_resolves_ortoprono_before_agus_and_generics(load_sample_text) -> None:
    text = load_sample_text("ortoprono_0000015.txt")

    resolution = resolve_parser_with_trace(text, file_path=ORTOPRONO_PATH)

    assert resolution.selected_parser.parser_name == "ortoprono"
    assert resolution.matched_parsers[0] == "ortoprono"
    assert "generic" in resolution.matched_parsers


def test_scanner_does_not_overwrite_ortoprono_customer_with_default(
    load_sample_text,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS", "true")
    monkeypatch.setenv("DEFAULT_CUSTOMER_NAME", "Cliente Por Defecto SL")
    monkeypatch.setenv("DEFAULT_CUSTOMER_TAX_ID", "B12345678")
    monkeypatch.setenv("DEFAULT_CUSTOMER_POSTAL_CODE", "03501")
    get_settings.cache_clear()

    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "ortoprono"
    supplier_dir.mkdir(parents=True)

    pdf_path = supplier_dir / "0000015.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")
    text = load_sample_text("ortoprono_0000015.txt")

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)
    scanner.scan(recursive=True)

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].parser_usado == "ortoprono"
    assert stored[0].nombre_cliente == "Cliente Prueba Test"
    assert stored[0].nif_cliente == "12345678Z"
    assert stored[0].cp_cliente == "03503"
