from __future__ import annotations

from pathlib import Path

from src.parsers.registry import resolve_parser, resolve_parser_with_trace

LEGAL_QUALITY_TEXT = """
FACTURA
Fecha: 11/03/2026
Fecha operacion: 11/03/2026
No factura: 2026/183
Cliente
LEGAL QUALITY CONSULTING ABOGADOS, SL DANIEL CUENCA MOYA
NIF: B65850711 DNI/NIF: 48334490J
C/ Picapedrers 2 Maravall, 31 2o E
08800 - VILANOVA I LA GELTRU (BARCELONA) 03500 - BENIDORM
Telefono: 938115077 ALICANTE
ESPANA
Articulo Descripcion Unidades Precio %Dto %IVA Total
Presupuesto no 2026/89 del 09/03/2026. Referencia JV/ 8925.1
PROC. VERBAL DANIEL CUENCA MOYA CONTRA MARIA NURIA ARAUJO OYA No 1 405,00 EUR 0,00% 21,00% 405,00 EUR
2026/03/JV/8925.1
Observaciones
Forma de pago Impuestos Base imponible: 405,00 EUR
Contado (Transferencia) Base %IVA Cuota IVA: 85,05 EUR
Vencimientos: 405,00 EUR 21,00 85,05 EUR
11/03/2026 490,05 EUR Total: 490,05 EUR
LEGAL QUALITY CONSULTING ABOGADOS, SL, SL CIF-B65850711 Inscrita en el Registro Mercantil de Barcelona
administracion@lqcabogados.es
"""


def test_legal_quality_real_layout_uses_specific_parser_and_real_vat() -> None:
    file_path = Path(r"C:\tmp\1T 26\LEGAL QUALITY\factura_2026_183.pdf")
    resolution = resolve_parser_with_trace(LEGAL_QUALITY_TEXT, file_path=file_path)

    assert resolution.selected_parser.parser_name == "legal_quality"
    assert "legal_quality" in resolution.matched_parsers

    result = resolution.selected_parser.parse(LEGAL_QUALITY_TEXT, file_path)

    assert result.parser_usado == "legal_quality"
    assert result.nombre_proveedor == "LEGAL QUALITY CONSULTING ABOGADOS, SL"
    assert result.nif_proveedor == "B65850711"
    assert result.numero_factura == "2026/183"
    assert result.fecha_factura == "11-03-2026"
    assert result.subtotal == 405.0
    assert result.iva == 85.05
    assert result.total == 490.05


def test_legal_quality_path_hint_alone_does_not_force_specific_parser() -> None:
    text = """
    FACTURA
    Proveedor: ACME SUMINISTROS SL
    CIF proveedor: B12345678
    Numero de factura: AC-2026-001
    Fecha factura: 08/04/2026
    Base imponible: 100,00
    Cuota IVA: 21,00
    Total factura: 121,00
    """

    parser = resolve_parser(text, file_path=Path(r"C:\tmp\LEGAL QUALITY\mezcla.pdf"))

    assert parser.parser_name == "generic_supplier"
