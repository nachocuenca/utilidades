from __future__ import annotations

from pathlib import Path

import pytest

from src.parsers.leroy_merlin import LeroyMerlinInvoiceParser
from src.parsers.registry import resolve_parser_with_trace

LEROY_INVOICE_5_TEXT = """BRICOLAJE - CONSTRUCCION - DECORACION - JARDINERIA
FACTURA 079-0002-831442
ORIGINAL
Finestrat, a 19 Febrero 2026
DANIEL CUENCA MOYA EI
Leroy Merlin Finestrat
MARAVALL 31
LEROY MERLIN SLU
03501 BENIDORM
CIF B-84818442
ALICANTE
Avda Finestrat,11-13
ESPANA
03509 Finestrat-ALICANTE
TELF: 965 595 555
Numero NIF: 48334490J
Telefono: 613026600
Fecha de venta: 19/02/2026
Ticket de caja: 079-000505-005-3188-NFS: 002560 19/02/2026 15:57 Venta
Tickets Originales:
N Designacion y Referencia articulo Cantidad Unid. Prec. unid Descu. Total. SI Tasa Precio Importe
Venta SI (EUR) unid SI (EUR) IVA/ Unidad TTI (EUR)
1 92008060 1 UNID. 98,35 0,00 98,35 21,00 119,00 119,00
Modos de pago Tasa IVA/IGIC/IPSI Total SI (EUR) Total IVA/IGIC/IPSI Total TII (EUR)
TARJ. BANCARIA (EUR) 119,00 21.00 98,35 20,65 119,00
EUR 98,35 20,65 119,00
Leroy Merlin Espana S.L.U. Avenida de la Vega 2, 28108 Alcobendas Madrid N.I.F.B-84818442.
"""

LEROY_INVOICE_6_TEXT = """BRICOLAJE - CONSTRUCCION - DECORACION - JARDINERIA
FACTURA 079-0003-843353
ORIGINAL
Finestrat, a 27 Marzo 2026
DANIEL CUENCA MOYA EI
Leroy Merlin Finestrat
MARAVALL 31
LEROY MERLIN SLU
03501 BENIDORM
CIF B-84818442
ALICANTE
Avda Finestrat,11-13
ESPANA
03509 Finestrat-ALICANTE
TELF: 965 595 555
Numero NIF: 48334490J
Telefono: 613026600
Fecha de venta: 27/03/2026
Ticket de caja: 079-000502-002-5550-NFS: 023796 27/03/2026 19:51 Venta
Tickets Originales:
N Designacion y Referencia articulo Cantidad Unid. Prec. unid Descu. Total. SI Tasa Precio Importe
Venta SI (EUR) unid SI (EUR) IVA/ Unidad TTI (EUR)
1 1 UNID. 660,33 0,00 660,33 21,00 799,00 799,00
2 49513982 1 UNID. 0,01 0,01 0,00 21,00 0,00 0,00
3 88035238 2 UNID. 1,17 0,00 1,17 21,00 1,42 2,84
Modos de pago Tasa IVA/IGIC/IPSI Total SI (EUR) Total IVA/IGIC/IPSI Total TII (EUR)
EFECTIVO (EUR) 801,84 21.00 662,68 139,16 801,84
EUR 662,68 139,16 801,84
Leroy Merlin Espana S.L.U. Avenida de la Vega 2, 28108 Alcobendas Madrid N.I.F.B-84818442.
"""


@pytest.mark.parametrize(
    ("text", "file_name"),
    [
        (LEROY_INVOICE_5_TEXT, "invoice (5).pdf"),
        (LEROY_INVOICE_6_TEXT, "invoice (6).pdf"),
    ],
)
def test_registry_resolves_leroy_merlin_for_runtime_invoices(text: str, file_name: str) -> None:
    resolution = resolve_parser_with_trace(
        text=text,
        file_path=Path(rf"C:\temp\{file_name}"),
    )

    assert resolution.selected_parser.parser_name == "leroy_merlin"


@pytest.mark.parametrize(
    ("text", "file_name", "invoice_number", "invoice_date", "subtotal", "iva", "total"),
    [
        (
            LEROY_INVOICE_5_TEXT,
            "invoice (5).pdf",
            "079-0002-831442",
            "19-02-2026",
            98.35,
            20.65,
            119.00,
        ),
        (
            LEROY_INVOICE_6_TEXT,
            "invoice (6).pdf",
            "079-0003-843353",
            "27-03-2026",
            662.68,
            139.16,
            801.84,
        ),
    ],
)
def test_leroy_merlin_extracts_runtime_totals_and_customer_cp(
    text: str,
    file_name: str,
    invoice_number: str,
    invoice_date: str,
    subtotal: float,
    iva: float,
    total: float,
) -> None:
    parser = LeroyMerlinInvoiceParser()

    result = parser.parse(
        text,
        Path(rf"C:\temp\{file_name}"),
    )

    assert result.parser_usado == "leroy_merlin"
    assert result.numero_factura == invoice_number
    assert result.fecha_factura == invoice_date
    assert result.cp_cliente == "03501"
    assert result.subtotal == pytest.approx(subtotal)
    assert result.iva == pytest.approx(iva)
    assert result.total == pytest.approx(total)
