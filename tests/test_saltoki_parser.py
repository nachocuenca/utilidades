from __future__ import annotations

from pathlib import Path

import pytest

from src.parsers.saltoki import SaltokiInvoiceParser


SALTOKI_ALICANTE_TEXT = """SALTOKI ALICANTE, S.L.
CIF: B71406623
C/ Rosa de los Vientos, 13 03007 Alicante
Tel: 965 31 37 61
alicante@saltoki.es
CLIENTE FECHA NÚMERO HOJA
REF. PROVEEDOR
CÓDIGO CANTIDAD CONCEPTO PRECIO % DTO IMPORTE
IMP. BRUTO DESCUENTOS % CARGOS %
BASE IMPONIBLE % I.V.A. % R. EQUIV. TOTAL
FORMA DE PAGO TOTAL
369718 31-03-2026 20083 1
_F_A_C_T_U_R_A_
CUENCA MOYA, DANIEL
CL MARAVALL 31 2º E
03501 BENIDORM
ALICANTE
N.I.F. 48334490J
4350011514
4354001114
3,00
3,00
ALBARAN Nº 836.131 FECHA 25-03-2026
S/REF:REJILLA+COMPUERTA
REJILLA IMPULSION 300X150MM H DOBLE BLANCA MA11
REGULADOR DE CAUDAL C/PALANCA 300X150 MA46
35,060
19,050
70
65
31,55
20,00
51,55 62,38
TRANSFERENCIA A 30 IBAN..: ES69 0049 1821 0922 1068 2951
.
24-04-2026 62,38
21,00 10,83
51,55
62,38 €
"""

SALTOKI_BENIDORM_TEXT = """SALTOKI BENIDORM, S.L.
CIF: B71406607
Avda. Finestrat,12 03502 Benidorm (Alicante)
Tel: 965 86 34 11
benidorm@saltoki.es
CLIENTE FECHA NÚMERO HOJA
REF. PROVEEDOR
CÓDIGO CANTIDAD CONCEPTO PRECIO % DTO IMPORTE
IMP. BRUTO DESCUENTOS % CARGOS %
BASE IMPONIBLE % I.V.A. % R. EQUIV. TOTAL
FORMA DE PAGO TOTAL
369718 18-01-2026 2761 1
F A C T U R A
CUENCA MOYA, DANIEL
CL MARAVALL 31 2º E
03501 BENIDORM
ALICANTE
N.I.F. 48334490J
4255010069
4200015002
1900020120
1900020116
5102050037
5102050324
4256000512
1800000701
4251020101
1801001130
1801001090
1801001135
1801001270
1,00
1,00
25,00
25,00
1,00
1,00
4,00
10,00
4,00
4,00
4,00
4,00
4,00
ALBARAN Nº 326.590 FECHA 5-01-2026
S/REF:RET DANIEL
MANDO A DISTANCIA UNIVERSAL 4000 CODIGOS
ALBARAN Nº 332.986 FECHA 15-01-2026
ROLLO 20M TUBERIA DOBLE AISLADA FRIO 1/4-3/8
ML TUBO EVACUACION C BLANCO 20/4 ROLLO 25M HIDROTUBO
ML TUBO EVACUACION C BLANCO 16/3 ROLLO 25M HIDROTUBO
BOLSA 100 BRIDAS NYLON NEGRAS 3,6 300
BOLSA 100 BRIDAS NYLON GRIS 4,8X290
ML CANALETA 65X50 CLIMA PLUS C/PROTECCION VECAMCO
ML TUBO PVC PRESION UNE-ISO 1452 W 20/16 SERIE LISA
CODO DRENAJE SPLITS C/TAPON
TE 90 PVC SERIE LISA 20
CODO 90 PVC SERIE LISA 20
TE 45 PVC SERIE LISA 20
MANGUITO UNION PVC SERIE LISA 20
17,470
94,748
5,540
4,910
6,370
7,730
6,270
2,970
6,480
0,800
0,690
5,020
0,710
45
NETO
80
80
60
60
51
78
37
65
65
65
65
9,61
94,75
27,70
24,55
2,55
3,09
12,29
6,53
16,33
1,12
0,97
7,03
0,99
207,51
251,09
TRANSFERENCIA A 30 IBAN..: ES52 0049 1821 0526 1068 2935
207,51 21,00 43,58
251,09 €
.
9-02-2026 251,09
"""


def test_saltoki_alicante_extracts_totals_and_header() -> None:
    parser = SaltokiInvoiceParser()

    result = parser.parse(
        SALTOKI_ALICANTE_TEXT,
        Path(r"C:\temp\saltoki\alicante\20083_20260331_38.pdf"),
    )

    assert result.parser_usado == "saltoki"
    assert result.nombre_proveedor == "SALTOKI ALICANTE, S.L."
    assert result.nif_proveedor == "B71406623"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.nif_cliente == "48334490J"
    assert result.numero_factura == "20083"
    assert result.fecha_factura == "31-03-2026"
    assert result.subtotal == pytest.approx(51.55)
    assert result.iva == pytest.approx(10.83)
    assert result.total == pytest.approx(62.38)


def test_saltoki_benidorm_extracts_totals_and_header() -> None:
    parser = SaltokiInvoiceParser()

    result = parser.parse(
        SALTOKI_BENIDORM_TEXT,
        Path(r"C:\temp\saltoki\benidorm\Copia de 2761_20260118_40.pdf"),
    )

    assert result.parser_usado == "saltoki"
    assert result.nombre_proveedor == "SALTOKI BENIDORM, S.L."
    assert result.nif_proveedor == "B71406607"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.nif_cliente == "48334490J"
    assert result.numero_factura == "2761"
    assert result.fecha_factura == "18-01-2026"
    assert result.subtotal == pytest.approx(207.51)
    assert result.iva == pytest.approx(43.58)
    assert result.total == pytest.approx(251.09)


SALTOKI_BENIDORM_OCR_FRAGMENT_TEXT = """REF. PROVEEDOR
F A C T U R A
CLIENTE FECHA NÚMERO HOJA
369718 31-01-2026 6475 1
SALTOKI BENIDORM, S.L.
CIF: B71406607 CUENCA MOYA, DANIEL
N.I.F. 48334490J
BASE IMPONIBLE % I.V.A. % R. EQUIV. TOTAL
118,04 21 , 0 0 24,79 142,83
FORMA DE PAGO TOTAL
TRANSFERENCIA A 30 IBAN..: ES52 0049 1821 0526 1068 2935
142,83 €
"""


def test_saltoki_benidorm_ocr_fragment_recovers_base_iva_total() -> None:
    parser = SaltokiInvoiceParser()

    result = parser.parse(
        SALTOKI_BENIDORM_OCR_FRAGMENT_TEXT,
        Path(r"C:\temp\saltoki\benidorm\Copia de 6475_20260131_40.pdf"),
    )

    assert result.parser_usado == "saltoki"
    assert result.nombre_proveedor == "SALTOKI BENIDORM, S.L."
    assert result.nif_proveedor == "B71406607"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.nif_cliente == "48334490J"
    assert result.numero_factura == "6475"
    assert result.fecha_factura == "31-01-2026"
    assert result.subtotal == pytest.approx(118.04)
    assert result.iva == pytest.approx(24.79)
    assert result.total == pytest.approx(142.83)


SALTOKI_ALICANTE_MULTIPAGE_FINAL_SUMMARY_TEXT = """REF. PROVEEDOR
F A C T U R A
CLIENTE FECHA NÚMERO HOJA
369718 7-03-2026 13803 1
SALTOKI ALICANTE, S.L.
CIF: B71406623
CUENCA MOYA, DANIEL
48334490J
IMP. BRUTO DESCUENTOS % CARGOS %
BASE IMPONIBLE % I.V.A. % R. EQUIV. TOTAL
FORMA DE PAGO TOTAL
€

REF. PROVEEDOR
F A C T U R A
CLIENTE FECHA NÚMERO HOJA
369718 7-03-2026 13803 2
SALTOKI ALICANTE, S.L.
CIF: B71406623
CUENCA MOYA, DANIEL
48334490J
SUMA ANTERIOR ........> 2.134,99
IMP. BRUTO DESCUENTOS % CARGOS %
BASE IMPONIBLE % I.V.A. % R. EQUIV. TOTAL
FORMA DE PAGO TOTAL
€

REF. PROVEEDOR
F A C T U R A
CLIENTE FECHA NÚMERO HOJA
369718 7-03-2026 13803 3
SALTOKI ALICANTE, S.L.
CIF: B71406623
CUENCA MOYA, DANIEL
48334490J
SUMA ANTERIOR ........> 5.120,74
IMP. BRUTO DESCUENTOS % CARGOS %
5.120,74
BASE IMPONIBLE % I.V.A. % R. EQUIV. TOTAL
5.120,74 21 , 0 0 1.075,36 6.196,10
FORMA DE PAGO TOTAL
TRANSFERENCIA A 30 IBAN..: ES69 0049 1821 0922 1068 2951
6.196,10 €
al
ne
sodiulcni
lanosrep
retcárac
ed sotad
sol
áratart
elbasnopseR
lE
.ikotlaS
opurG
led
saserpme
ed
otser
le
omoc
ísa
,arutcaf
etneserp
al
ed
rosime
le
otnat
nos
otneimatart
led
selbasnopseR
soL
dadicavirP
. 
3-04-2026 6.196,10
"""


def test_saltoki_alicante_multipage_prefers_last_fiscal_summary_block() -> None:
    parser = SaltokiInvoiceParser()

    result = parser.parse(
        SALTOKI_ALICANTE_MULTIPAGE_FINAL_SUMMARY_TEXT,
        Path(r"C:\temp\saltoki\alicante\13803_20260307_38.pdf"),
    )

    assert result.parser_usado == "saltoki"
    assert result.nombre_proveedor == "SALTOKI ALICANTE, S.L."
    assert result.nif_proveedor == "B71406623"
    assert result.numero_factura == "13803"
    assert result.fecha_factura == "07-03-2026"
    assert result.subtotal == pytest.approx(5120.74)
    assert result.iva == pytest.approx(1075.36)
    assert result.total == pytest.approx(6196.10)


SALTOKI_BENIDORM_OCR_FRAGMENT_BROKEN_RATE_TEXT = """REF. PROVEEDOR
F A C T U R A
CLIENTE FECHA NÚMERO HOJA
369718 31-01-2026 6475 1
SALTOKI BENIDORM, S.L.
CIF: B71406607 CUENCA MOYA, DANIEL
N.I.F. 48334490J
BASE IMPONIBLE % I.V.A. % R. EQUIV. TOTAL
118,04 2 1 , 0 0 24,79 142,83
FORMA DE PAGO TOTAL
TRANSFERENCIA A 30 IBAN..: ES52 0049 1821 0526 1068 2935
142,83 €
"""


def test_saltoki_benidorm_ocr_fragment_with_split_rate_recovers_totals() -> None:
    parser = SaltokiInvoiceParser()

    result = parser.parse(
        SALTOKI_BENIDORM_OCR_FRAGMENT_BROKEN_RATE_TEXT,
        Path(r"C:\temp\saltoki\benidorm\Copia de 6475_20260131_40.pdf"),
    )

    assert result.parser_usado == "saltoki"
    assert result.nombre_proveedor == "SALTOKI BENIDORM, S.L."
    assert result.nif_proveedor == "B71406607"
    assert result.numero_factura == "6475"
    assert result.fecha_factura == "31-01-2026"
    assert result.subtotal == pytest.approx(118.04)
    assert result.iva == pytest.approx(24.79)
    assert result.total == pytest.approx(142.83)
