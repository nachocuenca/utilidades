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


def test_agus_parser_extracts_customer_name_from_real_invoice_00018() -> None:
    text = """Clinica Almendros
Benidorm
03501
Alacant - España
613024023 - administracion@clinicaalmendros.com
Factura Nº: 026/00018
Fecha: 23/01/2026
C.I.F. / N.I.F. Titular: 13047306G
Titular: Rocio Ibañez Torres
Direccion:
Provincia: - España C.P.:
Clinica Almendros 48331209K
Ref. Concepto Cantidad Precio Importe
Visita del paciente Rocio Ibañez Torres 1 uds 30.00 € 30.00 €
Subtotal 30.00 €
Total 30.00 €"""

    parser = AgusInvoiceParser()
    result = parser.parse(text, Path("factura-00018.pdf"))

    assert result.nombre_proveedor == "Clinica Almendros"
    assert result.nif_proveedor == "48331209K"
    assert result.nombre_cliente == "Rocio Ibañez Torres"
    assert result.nif_cliente == "13047306G"
    assert result.numero_factura == "026/00018"
    assert result.fecha_factura == "23-01-2026"
    assert result.subtotal == 30.0
    assert result.iva == 0.0
    assert result.total == 30.0


def test_agus_parser_leaves_customer_tax_id_and_postal_code_empty_when_missing() -> None:
    text = """Clinica Almendros
Benidorm
03501
Alacant - España
613024023 - administracion@clinicaalmendros.com
Factura No: 026/00130 Titular: Jesus Sanchez Lopez
Fecha: 31/03/2026 Direccion:
C.I.F. / N.I.F. Titular: Provincia: - España C.P.:
K90213384
Ref. Concepto Cantidad Precio Importe
Subtotal 40.00 €
Total 40.00 €"""

    parser = AgusInvoiceParser()
    result = parser.parse(text, Path("factura-00130.pdf"))

    assert result.nif_cliente is None
    assert result.cp_cliente is None


def test_agus_parser_preserves_explicit_foreign_customer_tax_id_bd398355() -> None:
    text = """Clinica Almendros
Benidorm
03501
Alacant - España
613024023 - administracion@clinicaalmendros.com
Factura No: 026/00074 Titular: Juan Esteban Gutierrez Rojas
Fecha: 12/03/2026 Direccion:
C.I.F. / N.I.F. Titular: BD398355 Provincia: - España C.P.:
K90213384
Ref. Concepto Cantidad Precio Importe
Subtotal 45.00 €
Total 45.00 €"""

    parser = AgusInvoiceParser()
    result = parser.parse(text, Path("factura-00074.pdf"))

    assert result.nif_cliente == "BD398355"
    assert result.cp_cliente is None


def test_agus_parser_preserves_explicit_foreign_customer_tax_id_er0662892() -> None:
    text = """Clinica Almendros
Benidorm
03501
Alacant - España
613024023 - administracion@clinicaalmendros.com
Factura No: 026/00116 Titular: Sylwia SZYMCZAK
Fecha: 31/03/2026 Direccion:
C.I.F. / N.I.F. Titular: ER0662892 Provincia: - España C.P.:
K90213384
Ref. Concepto Cantidad Precio Importe
Subtotal 50.00 €
Total 50.00 €"""

    parser = AgusInvoiceParser()
    result = parser.parse(text, Path("factura-00116.pdf"))

    assert result.nif_cliente == "ER0662892"
    assert result.cp_cliente is None


def test_agus_parser_extracts_customer_postal_code_from_customer_block() -> None:
    text = """Clinica Almendros
Benidorm
03501
Alacant - España
613024023 - administracion@clinicaalmendros.com
Factura No: 026/00131 Titular: Cliente Con CP
Fecha: 31/03/2026 Direccion:
C.I.F. / N.I.F. Titular: 51875479Z
Provincia: Madrid C.P.: 28080
Clinica Almendros K90213384
Subtotal 40.00 €
Total 40.00 €"""

    parser = AgusInvoiceParser()
    result = parser.parse(text, Path("factura-00131.pdf"))

    assert result.nif_cliente == "51875479Z"
    assert result.cp_cliente == "28080"