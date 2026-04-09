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

FEMPA_OCR_NON_FISCAL_TEXT = """
Adeudo recibido
IBAN C/ Vía Su 2 d C c I 8 e N I u F 0 G l r o 3 s W s a B 3 0 l A P M e 0 o N n a 3 b K d 7 l E a N r 9 s i d 8 d p V o 6 a s G ñ , a 1F Titular Fecha Página
Titular de la domiciliacion Entidad emisora
Importe euros Clausula gastos Fecha operacion Fecha valor
Referencia
Informacion adicional
En cumplimiento de la normativa vigente es posible que el concepto este incompleto. Para mas informacion sobre el cargo, debe dirigirse a la empresa emisora del mismo.
Ref. Ent. Ordenante
42/20
CER
DA
T
ing.es
le ne atircsni ,G6897300W
FIC
,dirdaM
33082
,F1
,sodalboP
sol
ed
aíV
/C ,añapsE
ne
lasrucuS
,VN
KNAB
GNI
.522275-M
ajoH
,a8
nóicceS
,1
oiloF
,89713
omoT
,dirdaM
ed
litnacreM
ortsigeR
01/04/2026 1 de 1 DANIEL CUENCA MOYA ES10 1465 0100 9617 4459 4754
CUENCA MOYA DANIEL FEDERACION DE EMPRESARIOS DEL METAL DE L
48,76 Compartidos 12/01/2026 12/01/2026
Factura N.
1S261409 1
Id. emisor: ES83000G03096963
2026-01-09-13.48.53.868903
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

TGSS_OCR_NON_FISCAL_TEXT = """
Recibos Seguridad Social
Fecha Página
IBAN Titular
Titular de la domiciliacion Entidad emisora Fecha valor Importe en euros
Informacion adicional Referencia
81/01
SSR
T
ing.es
,G6897300W
FIC
,dirdaM
33082
,F1
,sodalboP
sol
ed
aíV
/C
,añapsE
ne
lasrucuS
,VN
KNAB
GNI
.522275-M
ajoH
,a8
nóicceS
,1
oiloF
,89713
omoT
,dirdaM
ed
litnacreM
ortsigeR
le
ne
atircsni
01/04/2026 1 de 1
DANIEL CUENCA MOYA
ES10 1465 0100 9617 4459 4754
DANIEL CUENCA MOYA TESORERIA GENERAL DE 30/01/2026 446.62
PERIODO LIQUIDACION: 01 2026-01 2026
052107031089616611202105210047
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
    assert result.nif_proveedor == "G03096963"


def test_non_fiscal_parser_extracts_fempa_total_from_ocr_like_receipt() -> None:
    parser = NonFiscalReceiptParser()

    result = parser.parse(
        FEMPA_OCR_NON_FISCAL_TEXT,
        Path(r"C:\tmp\FEMPA\ENERO 48,76.pdf"),
    )

    assert result.tipo_documento == "no_fiscal"
    assert result.nombre_proveedor == "Federaci\u00f3n de Empresarios del Metal de la provincia de Alicante"
    assert result.nif_proveedor == "G03096963"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.numero_factura == "1S261409 1"
    assert result.fecha_factura == "12-01-2026"
    assert result.total == 48.76


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


def test_non_fiscal_parser_extracts_tgss_fields_from_ocr_like_receipt() -> None:
    parser = NonFiscalReceiptParser()

    result = parser.parse(
        TGSS_OCR_NON_FISCAL_TEXT,
        Path(r"C:\tmp\TGSS\ENERO 446.62.pdf"),
    )

    assert result.tipo_documento == "no_fiscal"
    assert result.nombre_proveedor == "Tesorer\u00eda General de la Seguridad Social"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.numero_factura == "052107031089616611202105210047"
    assert result.fecha_factura == "30-01-2026"
    assert result.total == 446.62
