from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import get_settings
from src.db.repositories import InvoiceRepository
from src.pdf.reader import PdfReadResult
from src.parsers.carrefour import CarrefourInvoiceParser
from src.parsers.registry import get_parser_registry, resolve_parser_with_trace
from src.services.scanner import InvoiceScanner

CARREFOUR_PATH = Path("tests/fixtures/sample_pdfs/carrefour_invoice.pdf")


def test_carrefour_parser_extracts_real_pdf_fields(load_sample_text) -> None:
    text = load_sample_text("carrefour_invoice_2026.txt")
    parser = CarrefourInvoiceParser()

    assert parser.can_handle(text, CARREFOUR_PATH) is True

    result = parser.parse(text, CARREFOUR_PATH)

    assert result.parser_usado == "carrefour"
    assert result.nombre_proveedor == "Carrefour S.A."
    assert result.nif_proveedor == "A28425270"
    assert result.nombre_cliente == "Cliente Prueba Compra SL"
    assert result.nif_cliente == "B23456789"
    assert result.cp_cliente == "03502"
    assert result.numero_factura == "26A0720754"
    assert result.fecha_factura == "20-06-2026"
    assert result.subtotal == pytest.approx(222.31)
    assert result.iva == pytest.approx(46.69)
    assert result.total == pytest.approx(269.00)


def test_carrefour_can_handle_supplier_tax_id_with_ocr_spacing() -> None:
    text = """
    FACTURA 26A0720754 20/06/2026
    Carrefour
    DATOS FACTURACION
    COD FACTURA = 26A0720754 FECHA FACTURA 20/06/2026
    DETALLE DEL PEDIDO
    Subtotal sin IVA 222,31
    Total IVA 46,69
    TOTAL FACTURA 269,00
    Carrefour S.A. - A - 28425270 - www.carrefour.es
    """

    assert CarrefourInvoiceParser().can_handle(text, Path("invoice.pdf")) is True


def test_carrefour_rejects_clear_ticket() -> None:
    text = """
    Carrefour
    FACTURA SIMPLIFICADA
    Ticket 123
    N OP: 998877
    Fecha: 20/06/2026
    Total: 269,00
    Efectivo: 269,00
    """

    assert CarrefourInvoiceParser().can_handle(text, Path("ticket.pdf")) is False


def test_registry_resolves_carrefour_before_generics(load_sample_text) -> None:
    text = load_sample_text("carrefour_invoice_2026.txt")
    registry = get_parser_registry()

    assert registry.get("carrefour").parser_name == "carrefour"

    resolution = resolve_parser_with_trace(text, file_path=CARREFOUR_PATH)

    assert resolution.selected_parser.parser_name == "carrefour"
    assert resolution.matched_parsers[0] == "carrefour"
    assert "generic_supplier" in resolution.matched_parsers
    assert "generic" in resolution.matched_parsers


def test_scanner_does_not_overwrite_carrefour_customer_with_default(
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
    supplier_dir = inbox_dir / "carrefour"
    supplier_dir.mkdir(parents=True)

    pdf_path = supplier_dir / "invoice (3).pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")
    text = load_sample_text("carrefour_invoice_2026.txt")

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
    assert stored[0].parser_usado == "carrefour"
    assert stored[0].nombre_cliente == "Cliente Prueba Compra SL"
    assert stored[0].nif_cliente == "B23456789"
    assert stored[0].cp_cliente == "03502"

    get_settings.cache_clear()
