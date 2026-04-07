from __future__ import annotations

from pathlib import Path

import pytest

from src.parsers.obramat import ObramatInvoiceParser
from src.parsers.registry import resolve_parser

OBRAMAT_STANDARD_TEXT = """FACTURA 029-0001-872430
DUPLICADO
BRICOLAJE BRICOMAN, S.L.U. R.M. Madrid Tomo 21.744, Secc. 8 del Libro 0, Folio 21, Hoja M-387251
RAZON SOCIAL Calle Margarita Salas, 6, 28919-Leganes (Madrid) C.I.F. B-84406289
Ejemplar cliente
BRICOLAJE BRICOMAN,S.L.U
CIF: B-84406289
Avda. Pais Valencia 9
Teléfono: 965594325
Finestrat, a 16 Enero 2026
SR DANIEL CUENCA MOYA
C/ MARAVALL 31 2 E
03501 BENIDORM
ESPAÑA
Numero NIF : 48334490J
Numero de cuenta : 2225777
Telefono : 613026600
Fecha de venta : 16/01/2026
Condiciones de reglamen. : Precio al contado sin descuento
Condiciones de venta : Mencionados sobre el documento
Ticket de caja : 029-000010-003-3603-NFS: 000480 16/01/2026 13:06 Venta
Observaciones :
Pag. 1 / 1
N° Designacion y Referencia articulo Cantidad Unid. Venta Prec. unid SI (EUR) Descu. Unid. SI (EUR) Total. SI (EUR) Tasa IVA/IGIC/IPSI Precio Unidad TTI (EUR) Importe TTI (EUR)
1 LLAVE ESCU LARG ANTICAL 1/2"-3/8" ARCO 10410015 2 UNID. 4,21 0,00 4,21 21.00 5,10 10,20
Modos de pagos
EFECTIVO (EUR) 20,20
CAMBIO (EUR) 10,00
Tasa IVA/IGIC/IPSI Total. SI (EUR)
Total IVA/IGIC/IPSI Total TTI (EUR)
IVA 21.00% 8.43 1.77 10,20
"""

OBRAMAT_WITHOUT_IVA_LABEL_TEXT = """FACTURA 029-0002-883420
DUPLICADO
BRICOLAJE BRICOMAN, S.L.U. R.M. Madrid Tomo 21.744, Secc. 8 del Libro 0, Folio 21, Hoja M-387251
RAZON SOCIAL Calle Margarita Salas, 6, 28919-Leganes (Madrid) C.I.F. B-84406289
Ejemplar cliente
BRICOLAJE BRICOMAN,S.L.U
CIF: B-84406289
Avda. Pais Valencia 9
Teléfono: 965594325
Finestrat, a 2 Febrero 2026
SR DANIEL CUENCA MOYA
C/ MARAVALL 31 2 E
03501 BENIDORM
ESPAÑA
Numero NIF : 48334490J
Numero de cuenta : 2225777
Telefono : 613026600
Fecha de venta : 02/02/2026
Ticket de caja : 029-000037-010-1851-NFS: 010026 02/02/2026 13:22 Venta
Modos de pagos
TARJ. REDSYS BB(EUR) 33,50
TARJ: 000474678??????8759
Tasa IVA/IGIC/IPSI Total. SI (EUR)
Total IVA/IGIC/IPSI Total TTI (EUR)
21.00 27.69 5.81 33,50
"""

OBRAMAT_RECTIFICATIVA_WITH_IVA_TEXT = """FACTURA RECTIFICATIVA 029-0001-R089568
DUPLICADO
Ejemplar cliente
BRICOLAJE BRICOMAN, S.L.U. R.M. Madrid Tomo 21.744, Secc. 8 del Libro 0, Folio 21, Hoja M-387251
RAZON SOCIAL Calle Margarita Salas, 6, 28919-Leganes (Madrid) C.I.F. B-84406289
corrige a la factura 029-0001-869054 - 12/01/2026 13:03:34
BRICOLAJE BRICOMAN,S.L.U
CIF: B-84406289
Avda. Pais Valencia 9
Teléfono: 965594325
Finestrat, a 21 Enero 2026
SR DANIEL CUENCA MOYA
C/ MARAVALL 31 2 E
03501 BENIDORM
ESPAÑA
Numero NIF : 48334490J
Numero de cuenta : 2225777
Telefono : 613026600
Fecha de devolucion : 21/01/2026
Ticket de caja : 029-000004-013-2380-NFS: 001099 21/01/2026 15:35 Devolucion Mercancias
Tasa IVA/IGIC/IPSI Total. SI (EUR)
Total IVA/IGIC/IPSI Total TTI (EUR)
IVA 21.00% -21.98 -4.61 -26,59
"""

OBRAMAT_RECTIFICATIVA_WITHOUT_IVA_TEXT = """FACTURA RECTIFICATIVA 029-0002-R090760
DUPLICADO
Ejemplar cliente
BRICOLAJE BRICOMAN, S.L.U. R.M. Madrid Tomo 21.744, Secc. 8 del Libro 0, Folio 21, Hoja M-387251
RAZON SOCIAL Calle Margarita Salas, 6, 28919-Leganes (Madrid) C.I.F. B-84406289
corrige a la factura 029-0001-869054 - 12/01/2026 13:03:34
corrige a la factura 029-0002-883420 - 02/02/2026 13:22:26
BRICOLAJE BRICOMAN,S.L.U
CIF: B-84406289
Avda. Pais Valencia 9
Teléfono: 965594325
Finestrat, a 9 Febrero 2026
SR DANIEL CUENCA MOYA
C/ MARAVALL 31 2 E
03501 BENIDORM
ESPAÑA
Numero NIF : 48334490J
Numero de cuenta : 2225777
Telefono : 613026600
Fecha de devolucion : 09/02/2026
Ticket de caja : 029-000019-020-4693-NFS: 003350 09/02/2026 12:51 Devolucion Mercancias
Tasa IVA/IGIC/IPSI Total. SI (EUR)
Total IVA/IGIC/IPSI Total TTI (EUR)
21.00 -13.6 -2.85 -16,45
"""

OBRAMAT_F0018_TEXT_93 = """12 Enero 2026
DUPLICADO
FACTURA F0018-029-52/0000093
OBRAMAT FINESTRAT
AVINGUDA PAÍS VALENCIÀ, 11
BULEVARD COMERCIAL
03509 FINESTRAT
TLF.: 965 59 43 25
DANIEL CUENCA
C/ MARAVALL 31 2 E
BENIDORM ALICANTE/ALACANT 03501 ES
NIF: 48334490J
Observaciones:
ARTÍCULO Y REFERENCIA CANT.
PRECIO
UNIT. SIN
IVA
TASA
PRECIO
UNIT.
CON IVA
DESCUENTO TOTAL
2 3.02 LATIGUILLO RFZD 30CM 1/2"-1/2" DN-13 H-H
8424902221202 21% 3.65 7.30
1 3.80 LATIGUILLO RFZD 50CM 3/4"-3/4" DN-13 H-H
8424902221288 21% 4.60 4.60
1 3.18 LATIGUILLO RFZD 50CM 1/2"-1/2" DN-13 H-H
8424902221264 21% 3.85 3.85
0018-029-52/0000269 - 12/01/2026 13:18 - Venta - Factura emitida por 018
TOTAL
ART. TASA TOTAL BI TOTAL IVA TOTAL
4 IVA 21% 13.02 2.73 15.75
4 EUR 13.02 2.73 15.75
FECHA MÉTODO DE PAGO CANT.
12/01/2026 Tarjeta Bancaria BB 15.75
"""

OBRAMAT_F0018_TEXT_94 = """12 Enero 2026
DUPLICADO
FACTURA F0018-029-52/0000094
OBRAMAT FINESTRAT
AVINGUDA PAÍS VALENCIÀ, 11
BULEVARD COMERCIAL
03509 FINESTRAT
TLF.: 965 59 43 25
DANIEL CUENCA
C/ MARAVALL 31 2 E
BENIDORM ALICANTE/ALACANT 03501 ES
NIF: 48334490J
Observaciones:
ARTÍCULO Y REFERENCIA CANT.
PRECIO
UNIT. SIN
IVA
TASA
PRECIO
UNIT.
CON IVA
DESCUENTO TOTAL
1 3.18 LATIGUILLO RFZD 50CM 1/2"-1/2" DN-13 H-H
8424902221264 21% 3.85 3.85
0018-029-52/0000274 - 12/01/2026 13:25 - Venta - Factura emitida por 018
TOTAL
ART. TASA TOTAL BI TOTAL IVA TOTAL
1 IVA 21% 3.18 0.67 3.85
1 EUR 3.18 0.67 3.85
FECHA MÉTODO DE PAGO CANT.
12/01/2026 Tarjeta Bancaria BB 3.85
"""

LEROY_TEXT = """BRICOLAJE - CONSTRUCCIÓN - DECORACIÓN - JARDINERÍA
Leroy Merlin Espana S.L.U. Avenida de la Vega 2, 28108 Alcobendas Madrid N.I.F.B-84818442
FACTURA 079-0003-843353
Leroy Merlin Finestrat
LEROY MERLIN SLU
CIF B-84818442
Avda Finestrat,11-13
03509 Finestrat-ALICANTE
DANIEL CUENCA MOYA EI
MARAVALL 31
03501 BENIDORM
Número NIF: 48334490J
Fecha de venta: 27/03/2026
"""


def test_obramat_registry_resolution_beats_generic_ticket() -> None:
    parser = resolve_parser(
        text=OBRAMAT_STANDARD_TEXT,
        file_path=Path(r"C:\temp\OBRAMAT - N° Factura029-0001-872430.pdf"),
    )

    assert parser.parser_name == "obramat"


def test_obramat_extracts_standard_invoice_fields() -> None:
    parser = ObramatInvoiceParser()

    result = parser.parse(
        OBRAMAT_STANDARD_TEXT,
        Path(r"C:\temp\OBRAMAT - N° Factura029-0001-872430.pdf"),
    )

    assert result.parser_usado == "obramat"
    assert result.nombre_proveedor == "BRICOLAJE BRICOMAN, S.L.U."
    assert result.nif_proveedor == "B84406289"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.nif_cliente == "48334490J"
    assert result.numero_factura == "029-0001-872430"
    assert result.fecha_factura == "16-01-2026"
    assert result.subtotal == pytest.approx(8.43)
    assert result.iva == pytest.approx(1.77)
    assert result.total == pytest.approx(10.20)


def test_obramat_extracts_tax_breakdown_without_explicit_iva_label() -> None:
    parser = ObramatInvoiceParser()

    result = parser.parse(
        OBRAMAT_WITHOUT_IVA_LABEL_TEXT,
        Path(r"C:\temp\OBRAMAT - N° Factura029-0002-883420.pdf"),
    )

    assert result.parser_usado == "obramat"
    assert result.numero_factura == "029-0002-883420"
    assert result.fecha_factura == "02-02-2026"
    assert result.subtotal == pytest.approx(27.69)
    assert result.iva == pytest.approx(5.81)
    assert result.total == pytest.approx(33.50)


def test_obramat_supports_rectificative_negative_amounts_with_iva_label() -> None:
    parser = ObramatInvoiceParser()

    result = parser.parse(
        OBRAMAT_RECTIFICATIVA_WITH_IVA_TEXT,
        Path(r"C:\temp\OBRAMAT - N° Factura029-0001-R089568.pdf"),
    )

    assert result.parser_usado == "obramat"
    assert result.numero_factura == "029-0001-R089568"
    assert result.fecha_factura == "21-01-2026"
    assert result.subtotal == pytest.approx(-21.98)
    assert result.iva == pytest.approx(-4.61)
    assert result.total == pytest.approx(-26.59)


def test_obramat_supports_rectificative_negative_amounts_without_iva_label() -> None:
    parser = ObramatInvoiceParser()

    result = parser.parse(
        OBRAMAT_RECTIFICATIVA_WITHOUT_IVA_TEXT,
        Path(r"C:\temp\OBRAMAT - N° Factura029-0002-R090760.pdf"),
    )

    assert result.parser_usado == "obramat"
    assert result.numero_factura == "029-0002-R090760"
    assert result.fecha_factura == "09-02-2026"
    assert result.subtotal == pytest.approx(-13.60)
    assert result.iva == pytest.approx(-2.85)
    assert result.total == pytest.approx(-16.45)


def test_obramat_supports_f0018_invoice_number_family_and_totals_93() -> None:
    parser = ObramatInvoiceParser()

    result = parser.parse(
        OBRAMAT_F0018_TEXT_93,
        Path(r"C:\temp\OBRAMAT - N° FacturaF0018-029-52_0000093.pdf"),
    )

    assert result.parser_usado == "obramat"
    assert result.numero_factura == "F0018-029-52/0000093"
    assert result.fecha_factura == "12-01-2026"
    assert result.subtotal == pytest.approx(13.02)
    assert result.iva == pytest.approx(2.73)
    assert result.total == pytest.approx(15.75)


def test_obramat_supports_f0018_invoice_number_family_and_totals_94() -> None:
    parser = ObramatInvoiceParser()

    result = parser.parse(
        OBRAMAT_F0018_TEXT_94,
        Path(r"C:\temp\OBRAMAT - N° FacturaF0018-029-52_0000094.pdf"),
    )

    assert result.parser_usado == "obramat"
    assert result.numero_factura == "F0018-029-52/0000094"
    assert result.fecha_factura == "12-01-2026"
    assert result.subtotal == pytest.approx(3.18)
    assert result.iva == pytest.approx(0.67)
    assert result.total == pytest.approx(3.85)


def test_obramat_does_not_absorb_leroy_merlin() -> None:
    parser = ObramatInvoiceParser()

    assert parser.can_handle(
        LEROY_TEXT,
        Path(r"C:\temp\invoice (6).pdf"),
    ) is False