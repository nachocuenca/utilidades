from __future__ import annotations

from pathlib import Path

from src.parsers.generic import GenericInvoiceParser


def test_generic_parser_extracts_core_fields(load_sample_text) -> None:
    text = load_sample_text("agus_01.txt")
    parser = GenericInvoiceParser()

    result = parser.parse(text, Path("agus_01.pdf"))

    assert result.parser_usado == "generic"
    assert result.nombre_proveedor == "AGUS SERVICIOS DIGITALES"
    assert result.nombre_cliente == "CLIENTE DE PRUEBA SL"
    assert result.nif_cliente == "B76543210"
    assert result.cp_cliente == "46001"
    assert result.numero_factura == "AG-77"
    assert result.fecha_factura == "14-02-2026"
    assert result.subtotal == 100.0
    assert result.iva == 21.0
    assert result.total == 121.0