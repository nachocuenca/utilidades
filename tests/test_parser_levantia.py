from __future__ import annotations

from pathlib import Path

from src.parsers.levantia import LevantiaInvoiceParser
from src.parsers.registry import resolve_parser

LEVANTIA_TEXT_0100604203149 = """77410930B
.F.I.N
-
a1
NÓICPIRCSNI.315.42-A
AJOH
,231
OILOF
,956.1
OMOT
,ETNACILA
ED
.CREM
.GER
NE
ATIRCSNI
Aislamientos Acústicos Levante, S.L.
CL Isidoro de Sevilla esquina CL Bolulla,
03009 Alicante
Telf.: 965173258 965173909 Fax: 965171885
info@levantia.es
Especialistas en ahorro energético www.levantia.es
Factura
Dirección Cliente: Dirección Envío Factura:
DANIEL CUENCA MOYA DANIEL CUENCA MOYA
CL MARAVALL, 31 2-E CL MARAVALL, 31 2-E
03501 BENIDORM 03501 BENIDORM
ALICANTE ALICANTE
Fecha Factura Cliente C.I.F. Ref.Proveedor Agente Página
20/03/2026 604203149 18100 48334490J 7.016 1 de 1
CAF: Referencia
Código Cantidad Descripción RAEE* Precio Descuento Importe
ALBARAN R-602202252 FECHA 17/03/2026 REF: REF.
AUX:
KITADEAS71-X 1,00 CJTO. CONDUCTOS DAIKIN ACTIVE ADEA71A + 1.303,000
ARXM71R + BRC1E53A (control estándar)
Componentes:
ADEA71A 1,00 Unidad interior conducto SKYAIR ACTIVE ADEA71A2VEB 630,858 630,86
ARXM71R 1,00 Unidad exterior SKYAIR ACTIVE ARXM71R/A R5VIB 618,702 618,70
BRC1E53A 1,00 Control remoto cable para VAM-FB/VKM-GB - BRC1E53A7 53,440 53,44
(*) Tarifa por unidad
Portes Bruto Imp. RAEE Imp.Gas Base Imponible 21,00 % I.V.A. 0,00% REC. TOTAL €
1.303,00 1.303,00 273,63 1.576,63€
Forma de pago: Giro 30d f/f ING DIRECT, N.V., SUCURSAL EN ESPAÑA **** **** **** **** 4754
Vencimiento :
1.576,63
19/04/2026
"""

LEVANTIA_TEXT_0100604202562 = """77410930B
.F.I.N
-
a1
NÓICPIRCSNI.315.42-A
AJOH
,231
OILOF
,956.1
OMOT
,ETNACILA
ED
.CREM
.GER
NE
ATIRCSNI
Aislamientos Acústicos Levante, S.L.
CL Isidoro de Sevilla esquina CL Bolulla,
03009 Alicante
Telf.: 965173258 965173909 Fax: 965171885
info@levantia.es
Especialistas en ahorro energético www.levantia.es
Factura
Dirección Cliente: Dirección Envío Factura:
DANIEL CUENCA MOYA DANIEL CUENCA MOYA
CL MARAVALL, 31 2-E CL MARAVALL, 31 2-E
03501 BENIDORM 03501 BENIDORM
ALICANTE ALICANTE
Fecha Factura Cliente C.I.F. Ref.Proveedor Agente Página
06/03/2026 604202562 18100 48334490J 7.016 1 de 1
CAF: Referencia
Código Cantidad Descripción RAEE* Precio Descuento Importe
ALBARAN R-602201855 FECHA 05/03/2026 REF: REF.
AUX:
3NGR0575 1,00 CJTO. SPLIT CONDUCTO U-MATCH 30 R-32 1.065,000
Componentes:
3NGR0576 1,00 UI CONDUCTO U-MATCH CDT 30 - GUD85PHS1/A-S 380,163 380,16
3NGR0577 1,00 UE U-MATCH 30 - GUD85W1/NhA-S 684,837 684,84
(*) Tarifa por unidad
Portes Bruto Imp. RAEE Imp.Gas Base Imponible 21,00 % I.V.A. 0,00% REC. TOTAL €
1.065,00 1.065,00 223,65 1.288,65€
Forma de pago: Giro 30d f/f ING DIRECT, N.V., SUCURSAL EN ESPAÑA **** **** **** **** 4754
Vencimiento :
1.288,65
05/04/2026
"""


def test_levantia_can_handle_without_folder_hint() -> None:
    parser = LevantiaInvoiceParser()

    assert parser.can_handle(LEVANTIA_TEXT_0100604203149, Path("factura.pdf"))


def test_levantia_parser_extracts_supplier_number_date_and_amounts() -> None:
    parser = LevantiaInvoiceParser()

    result = parser.parse(
        LEVANTIA_TEXT_0100604203149,
        Path(r"C:\tmp\1T 26\LEVANTIA\0100604203149.pdf"),
    )

    assert result.parser_usado == "levantia"
    assert result.nombre_proveedor == "Aislamientos Acústicos Levante, S.L."
    assert result.nif_proveedor == "B03901477"
    assert result.nif_proveedor not in {"77410930B", "48334490J"}
    assert result.numero_factura == "604203149"
    assert result.fecha_factura == "20-03-2026"
    assert result.subtotal == 1303.0
    assert result.iva == 273.63
    assert result.total == 1576.63


def test_levantia_parser_applies_final_coherent_block_on_second_real_layout() -> None:
    parser = LevantiaInvoiceParser()

    result = parser.parse(
        LEVANTIA_TEXT_0100604202562,
        Path(r"C:\tmp\1T 26\LEVANTIA\0100604202562.pdf"),
    )

    assert result.nif_proveedor == "B03901477"
    assert result.numero_factura == "604202562"
    assert result.fecha_factura == "06-03-2026"
    assert result.subtotal == 1065.0
    assert result.iva == 223.65
    assert result.total == 1288.65


def test_registry_resolves_levantia_before_generic_supplier() -> None:
    parser = resolve_parser(
        LEVANTIA_TEXT_0100604203149,
        file_path=Path(r"C:\tmp\1T 26\LEVANTIA\0100604203149.pdf"),
    )

    assert parser.parser_name == "levantia"
