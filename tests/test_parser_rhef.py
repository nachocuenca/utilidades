from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import get_settings
from src.db.repositories import InvoiceRepository
from src.pdf.reader import PdfReadResult
from src.parsers.registry import resolve_parser_with_trace
from src.parsers.rhef import RhefInvoiceParser
from src.services.scanner import InvoiceScanner

RHEF_PATH = Path("tests/fixtures/sample_pdfs/rhef_invoice.pdf")


def test_registry_resolves_rhef_before_generics(load_sample_text) -> None:
    text = load_sample_text("rhef_21_47.txt")

    resolution = resolve_parser_with_trace(
        text=text,
        file_path=RHEF_PATH,
    )

    assert resolution.selected_parser.parser_name == "rhef"
    assert resolution.matched_parsers[0] == "rhef"
    assert "generic_supplier" in resolution.matched_parsers
    assert "generic" in resolution.matched_parsers


def test_rhef_extracts_real_ocr_fields(load_sample_text) -> None:
    text = load_sample_text("rhef_21_47.txt")
    parser = RhefInvoiceParser()

    assert parser.can_handle(text, RHEF_PATH) is True

    result = parser.parse(text, RHEF_PATH)

    assert result.parser_usado == "rhef"
    assert result.nombre_proveedor == "Francisco Amador Garcia"
    assert result.nif_proveedor == "48321093W"
    assert result.metadatos["nombre_comercial"] == "Recambios Rhef"
    assert result.nombre_cliente == "Cliente Prueba Rhef Sl"
    assert result.nif_cliente == "B12345678"
    assert result.cp_cliente == "03501"
    assert result.numero_factura == "BFAC/260186"
    assert result.fecha_factura == "11-03-2026"
    assert result.subtotal == pytest.approx(120.62)
    assert result.iva == pytest.approx(25.33)
    assert result.total == pytest.approx(145.95)
    assert (result.subtotal or 0) + (result.iva or 0) == pytest.approx(result.total or 0)


def test_rhef_can_handle_supplier_tax_id_with_ocr_spacing() -> None:
    text = """
    RECAMBIOS RHEF
    FRANCISCO AMADOR GARCIA CIF: 48321093 W
    N CLIENTE 18438
    N DE FACTURA BFAC/260186
    FECHA FACTURA 11/03/2026
    Base Imponible 21% IVA
    TOTAL FACTURA 145,95
    """

    assert RhefInvoiceParser().can_handle(text, RHEF_PATH) is True


def test_rhef_rejects_clear_ticket() -> None:
    text = """
    RECAMBIOS RHEF
    FACTURA SIMPLIFICADA
    Ticket 123
    N OP: 998877
    Fecha: 11/03/2026
    Total: 145,95
    Efectivo: 145,95
    """

    assert RhefInvoiceParser().can_handle(text, Path("ticket.pdf")) is False


def test_scanner_does_not_overwrite_rhef_customer_with_default(
    load_sample_text,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS", "true")
    monkeypatch.setenv("DEFAULT_CUSTOMER_NAME", "Cliente Por Defecto SL")
    monkeypatch.setenv("DEFAULT_CUSTOMER_TAX_ID", "B12345678")
    monkeypatch.setenv("DEFAULT_CUSTOMER_POSTAL_CODE", "03001")
    get_settings.cache_clear()

    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "rhef"
    supplier_dir.mkdir(parents=True)

    pdf_path = supplier_dir / "CamScanner 30-3-26 21.47.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")
    text = load_sample_text("rhef_21_47.txt")

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
    assert stored[0].parser_usado == "rhef"
    assert stored[0].nombre_cliente == "Cliente Prueba Rhef Sl"
    assert stored[0].nif_cliente == "B12345678"
    assert stored[0].cp_cliente == "03501"

    get_settings.cache_clear()
