from __future__ import annotations

from pathlib import Path

from src.parsers.registry import resolve_parser_with_trace
from src.parsers.versotel import VersotelInvoiceParser

VERSOTEL_ZENNIO_TEXT = """VERSOTEL PRODUCTO ELECTRÓNICO S.L.
Av. de la Industria 13, 1a Pta. (Of. 29)
28108 Alcobendas
España
DANIEL CUENCA MOYA
CALLE MARAVALL 31 2oE
03501 Benidorm
España
NIF: ES48334490J
Factura 2026/00891
Fecha Fecha de Fuente:
Factura: Vencimiento: 2026/00923
26/02/2026 26/02/2026
Precio
Descripción Cantidad unitario Impuestos Importe
[ZACWDF1W] Contacto de puerta/ventana para empotrar en 8,000 4,70 IVA 21% 37,60 EUR
madera o aluminio - Blanco Unidad(es) (Bienes)
https://www.zennio.com/productos/accesorios/door-window-
contact-flush-wood-zacwdf1
[990001207] Contacto magnético para instalación en superficie en 8,000 3,20 IVA 21% 25,60 EUR
puerta o ventana. Pequeño - blanco Unidad(es) (Bienes)
https://www.zennio.com/productos/sensores/door-window-contact-
surface-small
https://www.zennio.com/productos/accesorios/door-window-
contact-surface-small
GLS Nacional 1,000 15,00 IVA 21% 15,00 EUR
Unidad(es) (Bienes)
Subtotal 78,20 EUR
IVA 21% 16,42 EUR
Total 94,62 EUR
Pagado en 2026-02-26 94,62 EUR
Saldo 0,00 EUR
No se aceptarán cambios ni devoluciones de material tras la confirmación del pedido
Correo electrónico:
Teléfono: 916 507 031 web@zenniospain.com Web: http://www.zennio.com NIF: ESB86314903
Condiciones de venta en https://www.zennio.com/download/condiciones_grals_venta_zenniospain
Banco Sabadell, CCC IBAN ES30 0081 7171 7800 0119 5824
Página: 1/1
"""


def test_versotel_can_handle_real_zennio_runtime_case() -> None:
    parser = VersotelInvoiceParser()

    assert parser.can_handle(
        VERSOTEL_ZENNIO_TEXT,
        Path(r"C:\tmp\1T 26\ZENNIO\Factura - DANIEL CUENCA MOYA - 2026_00891.pdf"),
    )


def test_versotel_parser_extracts_real_runtime_fields_deterministically() -> None:
    parser = VersotelInvoiceParser()

    result = parser.parse(
        VERSOTEL_ZENNIO_TEXT,
        Path(r"C:\tmp\1T 26\ZENNIO\Factura - DANIEL CUENCA MOYA - 2026_00891.pdf"),
    )

    assert result.parser_usado == "versotel"
    assert result.nombre_proveedor == "VERSOTEL PRODUCTO ELECTRÓNICO S.L."
    assert result.nif_proveedor == "B86314903"
    assert result.nif_proveedor != "48334490J"
    assert result.numero_factura == "2026/00891"
    assert result.numero_factura != "2026/00923"
    assert result.fecha_factura == "26-02-2026"
    assert result.subtotal == 78.2
    assert result.iva == 16.42
    assert result.total == 94.62


def test_registry_resolves_versotel_before_generic_for_zennio_case() -> None:
    resolution = resolve_parser_with_trace(
        VERSOTEL_ZENNIO_TEXT,
        file_path=Path(r"C:\tmp\1T 26\ZENNIO\Factura - DANIEL CUENCA MOYA - 2026_00891.pdf"),
    )

    assert resolution.selected_parser.parser_name == "versotel"
    assert "generic_supplier" not in resolution.matched_parsers
