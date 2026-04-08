from __future__ import annotations

from pathlib import Path

from src.parsers.registry import resolve_parser_with_trace
from src.parsers.repsol import RepsolInvoiceParser


def test_repsol_parser_rejects_factura_simplificada_ticket_text() -> None:
    text = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: TK-2026-77
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """
    parser = RepsolInvoiceParser()

    assert parser.can_handle(text, Path(r"C:\temp\repsol\ticket.pdf")) is False


def test_registry_prefers_generic_ticket_for_repsol_simplificada() -> None:
    text = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: 998877
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """

    resolution = resolve_parser_with_trace(
        text=text,
        file_path=Path(r"C:\temp\repsol\mezcla\ticket_fuera_de_carpeta.pdf"),
    )

    assert resolution.selected_parser.parser_name == "generic_ticket"
    assert "generic_ticket" in resolution.matched_parsers
    assert "repsol" not in resolution.matched_parsers


def test_registry_keeps_repsol_for_standard_invoice_shape() -> None:
    text = """
    REPSOL COMERCIAL DE PRODUCTOS PETROLIFEROS S.A.
    CIF: A80298839
    FACTURA: 123456/1/26/123456
    FECHA FACTURA: 08/04/2026
    BASE IMPONIBLE: 100,00
    CUOTA IVA: 21,00
    TOTAL: 121,00
    """

    resolution = resolve_parser_with_trace(
        text=text,
        file_path=Path(r"C:\temp\proveedores\repsol\factura_abril.pdf"),
    )

    assert resolution.selected_parser.parser_name == "repsol"
    assert "repsol" in resolution.matched_parsers


def test_repsol_std_complete_parsing() -> None:
    fixture_path = Path("tests/fixtures/sample_texts/repsol_std.txt")
    text = fixture_path.read_text()
    file_path = Path(r"C:\temp\repsol\factura_std.pdf")

    parser = RepsolInvoiceParser()
    result = parser.parse(text, file_path)

    assert result.parser_usado == "repsol"
    assert result.nombre_proveedor == "REPSOL"
    assert result.nif_proveedor == "B28920839"
    assert result.numero_factura == "123456/1/24/000123"
    assert result.fecha_factura == "2024-04-15"
    assert result.subtotal == 310.0
    assert result.iva == 65.1
    assert result.total == 375.1


def test_repsol_resumen_coherente() -> None:
    fixture_path = Path("tests/fixtures/sample_texts/repsol_resumen.txt")
    text = fixture_path.read_text()
    file_path = Path(r"C:\temp\repsol\resumen.pdf")

    parser = RepsolInvoiceParser()
    result = parser.parse(text, file_path)

    assert result.subtotal == 500.0
    assert result.iva == 105.0
    assert result.total == 605.0
    # Verifica coherencia Base + IVA = Total
    assert abs(result.subtotal + result.iva - result.total) < 0.01


def test_repsol_partial_no_desglose() -> None:
    fixture_path = Path("tests/fixtures/sample_texts/repsol_partial.txt")
    text = fixture_path.read_text()
    file_path = Path(r"C:\temp\repsol\partial.pdf")

    parser = RepsolInvoiceParser()
    result = parser.parse(text, file_path)

    assert result.numero_factura == "TK202412345"
    assert result.fecha_factura == "2024-04-25"
    assert result.total == 45.67
    # Sin desglose: subtotal/iva None o calculados
    # Parser deja huecos si no visible, OK
