from pathlib import Path

import pytest
from src.parsers.registry import resolve_parser
from src.parsers.mercaluz import MercaluzInvoiceParser


@pytest.fixture
def mercaluz_std_text():
    return Path("tests/fixtures/sample_texts/mercaluz_std_ascii.txt").read_text()


@pytest.fixture
def mercaluz_abv_text():
    return Path("tests/fixtures/sample_texts/mercaluz_abv_ascii.txt").read_text()


@pytest.fixture
def mercaluz_resumen_text():
    return Path("tests/fixtures/sample_texts/mercaluz_resumen_ascii.txt").read_text()


def test_mercaluz_std_layout(mercaluz_std_text):
    parser = resolve_parser(mercaluz_std_text, file_path=Path("mercaluz/factura_std.pdf"))
    result = parser.parse(mercaluz_std_text, Path("mercaluz/factura_std.pdf"))
    
    assert result.parser_usado == "mercaluz"
    assert result.nombre_proveedor == "mercaluz"
    assert result.nif_proveedor == "A03204864"
    assert result.numero_factura == "FVN2024-00123-456789" or result.numero_factura == "VN2024-00123-456789"
    assert result.fecha_factura == "15-10-2024"
    assert result.subtotal == 29.50
    assert result.iva == 6.20
    assert result.total == 35.70


def test_mercaluz_abv_layout(mercaluz_abv_text):
    parser = resolve_parser(mercaluz_abv_text, file_path=Path("mercaluz/ABV2024-00789-123456.pdf"))
    result = parser.parse(mercaluz_abv_text, Path("mercaluz/ABV2024-00789-123456.pdf"))
    
    assert result.parser_usado == "mercaluz"
    assert result.nombre_proveedor == "mercaluz"
    assert result.nif_proveedor == "A03204864"
    assert result.numero_factura == "ABV2024-00789-123456"
    assert result.fecha_factura == "16-10-2024"
    assert result.tipo_documento == "abono"
    assert result.subtotal == -112.50
    assert result.iva == -23.63
    assert result.total == -136.13


def test_mercaluz_resumen_final_suma_coherente(mercaluz_resumen_text):
    parser = resolve_parser(mercaluz_resumen_text, file_path=Path("mercaluz/resumen.pdf"))
    result = parser.parse(mercaluz_resumen_text, Path("mercaluz/resumen.pdf"))
    
    assert result.parser_usado == "mercaluz"
    assert result.numero_factura == "FVN2024-01234-567890" or result.numero_factura == "VN2024-01234-567890"  # Ignora ABV anulada
    assert result.subtotal == 250.00
    assert result.iva == 52.50
    assert result.total == 302.50  # Regla fuerte: 250+52.5=302.5


def test_mercaluz_fallback_no_filename(mercaluz_std_text):
    parser = resolve_parser(mercaluz_std_text, file_path=Path("test.pdf"))
    result = parser.parse(mercaluz_std_text, Path("test.pdf"))
    
    assert result.parser_usado == "mercaluz"
    assert result.numero_factura is not None  # Extrae de texto
    assert result.subtotal == 29.50


def test_mercaluz_prefers_coherent_final_block_over_iva_rate() -> None:
    text = """
    MERCALUZ SA
    NIF A03204864
    FACTURA ABV2024-00001-123456
    Fecha: 17/10/2024

    BASE IMPONIBLE
    250,00
    IVA
    21,00
    52,50
    TOTAL FACTURA
    302,50
    """

    parser = resolve_parser(text, file_path=Path("mercaluz/ABV2024-00001-123456.pdf"))
    result = parser.parse(text, Path("mercaluz/ABV2024-00001-123456.pdf"))

    assert result.parser_usado == "mercaluz"
    assert result.tipo_documento == "abono"
    assert result.subtotal == -250.00
    assert result.iva == -52.50
    assert result.total == -302.50


def test_mercaluz_detects_fvn_from_document_number_not_credit_words() -> None:
    text = """
    MERCALUZ SA
    NIF A03204864
    FACTURA FVN2024-00002-123456
    Fecha: 18/10/2024

    Observaciones: abono por transferencia y devolucion interna

    BASE IMPONIBLE
    250,00
    IVA
    21,00
    52,50
    TOTAL FACTURA
    302,50
    """

    parser = MercaluzInvoiceParser()

    assert parser.detect_mercaluz_document_kind(
        Path("mercaluz/FVN2024-00002-123456.pdf"),
        text,
        "FVN2024-00002-123456",
    ) == "FVN"

    result = parser.parse(text, Path("mercaluz/FVN2024-00002-123456.pdf"))

    assert result.tipo_documento == "factura"
    assert result.subtotal == 250.00
    assert result.iva == 52.50
    assert result.total == 302.50


def test_mercaluz_ignores_21_amount_when_real_iva_quota_comes_after() -> None:
    text = """
    MERCALUZ SA
    NIF A03204864
    FACTURA FVN2024-00003-123456
    Fecha: 19/10/2024

    BASE IMPONIBLE
    250,00
    CUOTA IVA
    21,00
    52,50
    TOTAL FACTURA
    302,50
    """

    parser = resolve_parser(text, file_path=Path("mercaluz/FVN2024-00003-123456.pdf"))
    result = parser.parse(text, Path("mercaluz/FVN2024-00003-123456.pdf"))

    assert result.parser_usado == "mercaluz"
    assert result.subtotal == 250.00
    assert result.iva == 52.50
    assert result.total == 302.50


def test_mercaluz_prefers_total_factura_over_contaminated_importe_a_pagar() -> None:
    text = """
    MERCALUZ SA
    NIF A03204864
    FACTURA FVN2024-00004-123456
    Fecha: 20/10/2024

    BASE IMPONIBLE            250,00
    CUOTA IVA 21%             52,50
    TOTAL FACTURA             302,50
    DESCUENTO PRONTO PAGO     -10,00
    IMPORTE A PAGAR           292,50
    """

    parser = resolve_parser(text, file_path=Path("mercaluz/FVN2024-00004-123456.pdf"))
    result = parser.parse(text, Path("mercaluz/FVN2024-00004-123456.pdf"))

    assert result.parser_usado == "mercaluz"
    assert result.subtotal == 250.00
    assert result.iva == 52.50
    assert result.total == 302.50

