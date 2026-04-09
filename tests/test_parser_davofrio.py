from __future__ import annotations

from pathlib import Path

from src.parsers.davofrio import DavofrioInvoiceParser
from src.parsers.registry import resolve_parser_with_trace

DAVOFRIO_TEXT = """
99914145-B
:FIC
.a1
nóicpircsnI
,51349-A
on
ajoH
,731
oilof
,0
orbiL
,6703
omoT
,etnacilA
ed
litnacreM
ortsiger
le
ne
atircsnI
.U.L.S
,OIRFOVAD
.)etnacilA(
giepsaR
del
etneciV
naS
09630-
35
on
aícraG
zeugírdoR
ordisI
leunaM
oiranireteV
/C
.U.L.S
OIRFOVAD
T. 965 058 731 - F. 965 058 730 www.davofrio.com
Cliente 4300006825
DANIEL CUENCA MOYA
MARAVALL 31, PISO 2, PTA E
03501 Benidorm
FACTURA Fecha Factura C.I.F Cliente
Alicante
FVC26-0381 26/3/2026 48334490J
Cód. DESCRIPCIÓN Ubicación Cantidad Precio % Dto Importe
AVISO: OT26-0605
PREDIAGNOSTICO S/ OFERTA OF26-477/0
C/ SUECIA 15A
03570- VILLAJOYOSA (ALICANTE)
NMAN-000 Mano de obra oficial 3,00 55,00 0,00 165,00
NDESP-000 Desplazamiento 1,00 54,00 0,00 54,00
Importe neto Base imponible Imp I.V.A.: % Rec. equiv. SUBTOTAL
219,00 21,00 % 45,99
€ 219,00 0,00 264,99
Retención TOTAL
0,00 264,99
Forma de Pago Transferencia
Domiciliación BANCO SANTANDER CTA. CORRIENTE ES21 0075 0544 96 0600237695 Swift: BSCHESMMXXX
Vencimientos 17/03/2026 264,99
Observaciones
PAGADO
Página 1 de 1
"""

DAVOFRIO_PATH = Path(r"C:\Users\ignac\Downloads\1T26\1T 26\DAVOFRIO\FVC26-0381.pdf")


def test_davofrio_parser_extracts_real_ocr_fields() -> None:
    parser = DavofrioInvoiceParser()

    assert parser.can_handle(DAVOFRIO_TEXT, DAVOFRIO_PATH)

    result = parser.parse(DAVOFRIO_TEXT, DAVOFRIO_PATH)

    assert result.parser_usado == "davofrio"
    assert result.nombre_proveedor == "DAVOFRIO, S.L.U."
    assert result.nif_proveedor == "B54141999"
    assert result.numero_factura == "FVC26-0381"
    assert result.fecha_factura == "26-03-2026"
    assert result.subtotal == 219.0
    assert result.iva == 45.99
    assert result.total == 264.99


def test_registry_resolves_davofrio_before_generic_supplier() -> None:
    resolution = resolve_parser_with_trace(DAVOFRIO_TEXT, file_path=DAVOFRIO_PATH)

    assert resolution.selected_parser.parser_name == "davofrio"
    assert resolution.matched_parsers[0] == "davofrio"
