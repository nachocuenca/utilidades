from __future__ import annotations

from pathlib import Path

from src.parsers.generic import GenericInvoiceParser
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


def test_generic_parser_extracts_core_fields(load_sample_text) -> None:
    text = load_sample_text("agus_01.txt")
    parser = GenericInvoiceParser()

    result = parser.parse(text, Path("agus_01.pdf"))

    assert result.parser_usado == "generic"
    assert result.nombre_proveedor == "AGUS SERVICIOS DIGITALES"
    assert result.nombre_cliente == "CLIENTE DE PRUEBA SL"
    assert result.nif_cliente == "B76543210"
    assert result.cp_cliente == "46001"
    assert result.numero_factura == "AG-77"
    assert result.fecha_factura == "14-02-2026"
    assert result.subtotal == 100.0
    assert result.iva == 21.0
    assert result.total == 121.0


def test_generic_parser_prefers_coherent_summary_over_iva_percentage() -> None:
    text = """
    VERSOTEL PRODUCTO ELECTRÓNICO S.L.
    CIF B12345678
    Cliente: Daniel Cuenca Moya
    NIF cliente: 48334490J
    Factura: V-2026-001
    Fecha factura: 11/03/2026

    Línea 1 78,20

    Base imponible 78,20
    IVA 21% 16,42
    Total factura 94,62
    """
    parser = GenericInvoiceParser()

    result = parser.parse(text, Path("versotel_001.pdf"))

    assert result.nombre_proveedor == "VERSOTEL PRODUCTO ELECTRÓNICO S.L."
    assert result.numero_factura == "V-2026-001"
    assert result.subtotal == 78.2
    assert result.iva == 16.42
    assert result.total == 94.62


def test_generic_supplier_skips_customer_tax_id_when_extracting_supplier() -> None:
    text = """
    FRANCISCO AMADOR GARCIA
    NIF 48321093W
    Factura: BFAC/260186
    Fecha factura: 11/03/2026

    Cliente: Daniel Cuenca Moya
    NIF cliente: 48334490J

    Base imponible 120,62
    IVA 25,33
    Total factura 145,95
    """
    parser = GenericSupplierInvoiceParser()

    result = parser.parse(text, Path("francisco_amador.pdf"))

    assert result.nombre_proveedor == "FRANCISCO AMADOR GARCIA"
    assert result.nif_proveedor == "48321093W"
    assert result.numero_factura == "BFAC/260186"
    assert result.subtotal == 120.62
    assert result.iva == 25.33
    assert result.total == 145.95


def test_generic_parser_rejects_invoice_number_ocr_fragment() -> None:
    assert GenericInvoiceParser.clean_invoice_number_candidate("Direcci") is None
