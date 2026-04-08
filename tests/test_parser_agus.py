from __future__ import annotations

from pathlib import Path

from src.parsers.agus import AgusInvoiceParser


def test_agus_parser_handles_known_text(load_sample_text) -> None:
    text = load_sample_text("agus_01.txt")
    parser = AgusInvoiceParser()

    assert parser.can_handle(text, Path("agus_01.pdf")) is True

    result = parser.parse(text, Path("agus_01.pdf"))

    assert result.parser_usado == "agus"
    assert result.nombre_proveedor == "AGUS SERVICIOS DIGITALES"
    assert result.nombre_cliente == "CLIENTE DE PRUEBA SL"
    assert result.nif_cliente == "B76543210"
    assert result.cp_cliente == "46001"
    assert result.numero_factura == "AG-77"
    assert result.fecha_factura == "14-02-2026"
    assert result.subtotal == 100.0
    assert result.iva == 21.0
    assert result.total == 121.0


def test_agus_parser_extracts_clinica_almendros_customer_block() -> None:
    text = """Clinica Almendros
Benidorm
03501
Alacant - España
613024023 - administracion@clinicaalmendros.com
Factura Nº: 026/00010
Fecha: 23/01/2026
C.I.F. / N.I.F. Titular: 51875479Z
Titular: Asuncion Jimenez Martin
Direccion:
Provincia: - España C.P.:
Clinica Almendros K90213384
Ref. Concepto Cantidad Precio Importe
Visita del paciente Asuncion Jimenez Martin 1 uds 30.00 € 30.00 €
Subtotal 30.00 €
Total 30.00 €"""

    parser = AgusInvoiceParser()

    assert parser.can_handle(text, Path("factura-00010.pdf")) is True

    result = parser.parse(text, Path("factura-00010.pdf"))

    assert result.parser_usado == "agus"
    assert result.nombre_proveedor == "Clinica Almendros"
    assert result.nif_proveedor == "48331209K"
    assert result.nombre_cliente == "Asuncion Jimenez Martin"
    assert result.nif_cliente == "51875479Z"
    assert result.numero_factura == "026/00010"
    assert result.fecha_factura == "23-01-2026"
    assert result.subtotal == 30.0
    assert result.iva == 0.0
    assert result.total == 30.0


def test_agus_parser_extracts_customer_name_when_titular_value_is_on_next_line() -> None:
    text = """Clinica Almendros
Factura Nº: 026/00011
Fecha: 23/01/2026
C.I.F. / N.I.F. Titular: 51875479Z
Titular:
Asuncion Jimenez Martin
Direccion:
Provincia: - España C.P.:
Clinica Almendros K90213384
Subtotal 30.00 €
Total 30.00 €"""

    parser = AgusInvoiceParser()
    result = parser.parse(text, Path("factura-00011.pdf"))

    assert result.nombre_cliente == "Asuncion Jimenez Martin"
    assert result.nif_cliente == "51875479Z"
    assert result.nif_proveedor == "48331209K"
    assert result.numero_factura == "026/00011"
    assert result.fecha_factura == "23-01-2026"
    assert result.iva == 0.0