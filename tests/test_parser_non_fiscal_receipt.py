from __future__ import annotations

from pathlib import Path

from src.parsers.non_fiscal_receipt import NonFiscalReceiptParser

FEMPA_NON_FISCAL_TEXT = """
Adeudo recibido
IBAN ES10 1465 0100 9617 4459 4754
Titular de la domiciliacion Entidad emisora
Importe euros Clausula gastos Fecha operacion Fecha valor
Referencia del adeudo
Informacion adicional
En cumplimiento de la normativa vigente es posible que el concepto este incompleto.
01/04/2026 1 de 1 DANIEL CUENCA MOYA ES10 1465 0100 9617 4459 4754
CUENCA MOYA DANIEL FEDERACION DE EMPRESARIOS DEL METAL DE L
48,76 Compartidos 12/01/2026 12/01/2026
Factura N.
1S261409 1
Id. emisor: ES83000G03096963
"""

TGSS_NON_FISCAL_TEXT = """
TESORERIA GENERAL DE LA SEGURIDAD SOCIAL
Recibo de liquidacion de cotizaciones
Sujeto responsable
DANIEL CUENCA MOYA
Fecha de operacion: 20/05/2021
Fecha de valor: 21/05/2021
Importe del recibo: 446,62 EUR
Referencia:
052107031089616611202105210047
Numero de recibo: 011234567890
"""


def test_non_fiscal_parser_extracts_fempa_real_fields() -> None:
    parser = NonFiscalReceiptParser()

    result = parser.parse(
        FEMPA_NON_FISCAL_TEXT,
        Path(r"C:\tmp\FEMPA\ENERO 48,76.pdf"),
    )

    assert result.tipo_documento == "no_fiscal"
    assert result.nombre_proveedor == "Federaci\u00f3n de Empresarios del Metal de la provincia de Alicante"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.numero_factura == "1S261409 1"
    assert result.fecha_factura == "12-01-2026"
    assert result.total == 48.76
    assert result.subtotal is None
    assert result.iva is None
    assert result.nif_proveedor is None


def test_non_fiscal_parser_prioritizes_tgss_long_reference_and_value_date() -> None:
    parser = NonFiscalReceiptParser()

    result = parser.parse(
        TGSS_NON_FISCAL_TEXT,
        Path(r"C:\tmp\TGSS\seguros_sociales_marzo.pdf"),
    )

    assert result.tipo_documento == "no_fiscal"
    assert result.nombre_proveedor == "Tesorer\u00eda General de la Seguridad Social"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.numero_factura == "052107031089616611202105210047"
    assert result.fecha_factura == "21-05-2021"
    assert result.total == 446.62
    assert result.subtotal is None
    assert result.iva is None
    assert result.nif_proveedor is None
