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
    CIF: B28920839
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
    assert result.nombre_proveedor == "Repsol Comercial de Productos Petrolíferos, S.A."
    assert result.nif_proveedor == "B28920839"
    assert result.numero_factura == "123456/1/24/000123"
    assert result.fecha_factura == "15-04-2024"
    assert result.subtotal == 310.0
    assert result.iva == 65.1
    assert result.total == 375.1


def test_repsol_resumen_coherente() -> None:
    fixture_path = Path("tests/fixtures/sample_texts/repsol_resumen.txt")
    text = fixture_path.read_text()
    file_path = Path(r"C:\temp\repsol\resumen.pdf")

    parser = RepsolInvoiceParser()
    result = parser.parse(text, file_path)

    assert result.nombre_proveedor == "Repsol Petróleo, S.A."
    assert result.nif_proveedor == "B28049929"
    assert result.subtotal == 500.0
    assert result.iva == 105.0
    assert result.total == 605.0
    assert abs(result.subtotal + result.iva - result.total) < 0.01


def test_repsol_partial_no_desglose() -> None:
    fixture_path = Path("tests/fixtures/sample_texts/repsol_partial.txt")
    text = fixture_path.read_text()
    file_path = Path(r"C:\temp\repsol\partial.pdf")

    parser = RepsolInvoiceParser()
    result = parser.parse(text, file_path)

    assert result.numero_factura == "TK202412345"
    assert result.fecha_factura == "25-04-2024"
    assert result.total == 45.67


def test_repsol_2026_real_facturadora_0901() -> None:
    text = """Nº Factura: 096943/5/26/000169
Fecha: 09/01/2026
F. Operación: 09/01/2026
E.S./A.S. Lugar Suministro (*)
CRED BENIDORM
CR CV-70 P.K. 47
03500 BENIDORM (ALICANTE)
CAMPSA ESTACIONES SERVICIO SA
Adquiriente
CUENCA MOYA DANIEL
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Matrícula: 8991KBS
Datos Fiscales Adquiriente CUENCA MOYA DANIEL (CIF/NIF: 48334490J)
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Datos del suministro
Fecha Productos Litros €/L Importe
09.01.2026 Diesel e+ 53,01 1,429 75,75
Importe del producto (Base Imponible) 62,60 €
IVA 21,00% de 62,60 € 13,15 €
TOTAL FACTURA EUROS........ 75,75 €
(*) Esta factura está emitida en nombre y por cuenta de Repsol Soluciones Energéticas, S.A.
Repsol Soluciones Energéticas, S.A. Méndez Alvaro, 44. Madrid 28045
Registro Mercantil de Madrid, Tomo 2530 gral, Folio 1, Hoja M-44194, incr 665 C.I.F. A-80298839"""
    result = RepsolInvoiceParser().parse(text, Path(r"C:\temp\repsol\09_01 75,75 €.pdf"))
    assert result.nombre_proveedor == "Repsol Soluciones Energéticas, S.A."
    assert result.nif_proveedor == "A80298839"
    assert result.numero_factura == "096943/5/26/000169"
    assert result.fecha_factura == "09-01-2026"
    assert result.subtotal == 62.6
    assert result.iva == 13.15
    assert result.total == 75.75


def test_repsol_2026_real_facturadora_2602() -> None:
    text = """Nº Factura: 096943/5/26/000932
Fecha: 26/02/2026
F. Operación: 26/02/2026
E.S./A.S. Lugar Suministro (*)
CRED BENIDORM
CR CV-70 P.K. 47
03500 BENIDORM (ALICANTE)
CAMPSA ESTACIONES SERVICIO SA
Adquiriente
CUENCA MOYA DANIEL
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Matrícula: 8991KBS
Datos Fiscales Adquiriente CUENCA MOYA DANIEL (CIF/NIF: 48334490J)
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Datos del suministro
Fecha Productos Litros €/L Importe
26.02.2026 Diesel e+ 55,68 1,509 84,02
Importe del producto (Base Imponible) 69,44 €
IVA 21,00% de 69,44 € 14,58 €
TOTAL FACTURA EUROS........ 84,02 €
(*) Esta factura está emitida en nombre y por cuenta de Repsol Soluciones Energéticas, S.A.
Repsol Soluciones Energéticas, S.A. Méndez Alvaro, 44. Madrid 28045
Registro Mercantil de Madrid, Tomo 2530 gral, Folio 1, Hoja M-44194, incr 665 C.I.F. A-80298839"""
    result = RepsolInvoiceParser().parse(text, Path(r"C:\temp\repsol\26_02 84,02 €.pdf"))
    assert result.nombre_proveedor == "Repsol Soluciones Energéticas, S.A."
    assert result.nif_proveedor == "A80298839"
    assert result.numero_factura == "096943/5/26/000932"
    assert result.fecha_factura == "26-02-2026"
    assert result.subtotal == 69.44
    assert result.iva == 14.58
    assert result.total == 84.02


def test_repsol_2026_real_facturadora_2403_respeta_impreso() -> None:
    text = """Nº Factura: 096943/5/26/001358
Fecha: 24/03/2026
F. Operación: 24/03/2026
E.S./A.S. Lugar Suministro (*)
CRED BENIDORM
CR CV-70 P.K. 47
03500 BENIDORM (ALICANTE)
CAMPSA ESTACIONES SERVICIO SA
Adquiriente
CUENCA MOYA DANIEL
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Matrícula: 8991KBS
Datos Fiscales Adquiriente CUENCA MOYA DANIEL (CIF/NIF: 48334490J)
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Datos del suministro
Fecha Productos Litros €/L Importe
24.03.2026 Diesel e+ 55,00 1,799 98,95
Importe del producto (Base Imponible) 89,96 €
IVA 10,00% de 89,96 € 9,00 €
TOTAL FACTURA EUROS........ 98,95 €
(*) Esta factura está emitida en nombre y por cuenta de Repsol Soluciones Energéticas, S.A.
Repsol Soluciones Energéticas, S.A. Méndez Alvaro, 44. Madrid 28045
Registro Mercantil de Madrid, Tomo 2530 gral, Folio 1, Hoja M-44194, incr 665 C.I.F. A-80298839"""
    result = RepsolInvoiceParser().parse(text, Path(r"C:\temp\repsol\24_03 98,95 €.pdf"))
    assert result.nombre_proveedor == "Repsol Soluciones Energéticas, S.A."
    assert result.nif_proveedor == "A80298839"
    assert result.numero_factura == "096943/5/26/001358"
    assert result.fecha_factura == "24-03-2026"
    assert result.subtotal == 89.96
    assert result.iva == 9.0
    assert result.total == 98.95
