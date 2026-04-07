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
Ejemplar cliente
BRICOLAJE BRICOMAN, S.L.U. R.M. Madrid Tomo 21.744, Secc. 8 del Libro 0, Folio 21, Hoja M-387251
RAZON SOCIAL Calle Margarita Salas, 6, 28919-Leganes (Madrid) C.I.F. B-84406289
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
Condiciones de reglamen. : Precio al contado sin descuento
Condiciones de venta : Mencionados sobre el documento
Ticket de caja : 029-000037-010-1851-NFS: 010026 02/02/2026 13:22 Venta
Observaciones :
Pag. 1 / 1
Modos de pagos
TARJ. REDSYS BB(EUR) 33,50
TARJ: 000474678??????8759
Tasa IVA/IGIC/IPSI Total. SI (EUR)
Total IVA/IGIC/IPSI Total TTI (EUR)
21.00 27.69 5.81 33,50
"""

OBRAMAT_RECTIFICATIVA_TEXT = """FACTURA RECTIFICATIVA 029-0002-R090760
BRICOLAJE BRICOMAN,S.L.U
CIF: B-84406289
Avda. Pais Valencia 9
Teléfono: 965594325
Finestrat, a 10 Febrero 2026
SR DANIEL CUENCA MOYA
C/ MARAVALL 31 2 E
03501 BENIDORM
ESPAÑA
Numero NIF : 48334490J
Fecha de venta : 10/02/2026
Ticket de caja : 029-000037-010-1851-NFS: 010026 10/02/2026 09:20 Venta
Tasa IVA/IGIC/IPSI Total. SI (EUR)
Total IVA/IGIC/IPSI Total TTI (EUR)
IVA 21.00% -27,69 -5,81 -33,50
BRICOLAJE BRICOMAN, S.L.U. R.M. Madrid Tomo 21.744, Secc. 8 del Libro 0, Folio 21, Hoja M-387251
RAZON SOCIAL Calle Margarita Salas, 6, 28919-Leganes (Madrid) C.I.F. B-84406289
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
    assert result.nombre_proveedor == "BRICOLAJE BRICOMAN, S.L.U."
    assert result.nif_proveedor == "B84406289"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.nif_cliente == "48334490J"
    assert result.numero_factura == "029-0002-883420"
    assert result.fecha_factura == "02-02-2026"
    assert result.subtotal == pytest.approx(27.69)
    assert result.iva == pytest.approx(5.81)
    assert result.total == pytest.approx(33.50)


def test_obramat_supports_rectificative_negative_amounts() -> None:
    parser = ObramatInvoiceParser()

    result = parser.parse(
        OBRAMAT_RECTIFICATIVA_TEXT,
        Path(r"C:\temp\OBRAMAT - N° Factura029-0002-R090760.pdf"),
    )

    assert result.parser_usado == "obramat"
    assert result.nombre_proveedor == "BRICOLAJE BRICOMAN, S.L.U."
    assert result.nif_proveedor == "B84406289"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.nif_cliente == "48334490J"
    assert result.numero_factura == "029-0002-R090760"
    assert result.fecha_factura == "10-02-2026"
    assert result.subtotal == pytest.approx(-27.69)
    assert result.iva == pytest.approx(-5.81)
    assert result.total == pytest.approx(-33.50)