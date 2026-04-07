from __future__ import annotations

from pathlib import Path

from src.parsers.agus import AgusInvoiceParser


def test_agus_parser_handles_known_text(load_sample_text) -> None:
    text = load_sample_text("agus_01.txt")
    parser = AgusInvoiceParser()

    assert parser.can_handle(text, Path("agus_01.pdf")) is True

    result = parser.parse(text, Path("agus_01.pdf"))

    assert result.parser_usado == "agus"
    assert result.nombre_proveedor == "AGUS SERVICIOS DIGITALES"
    assert result.nombre_cliente == "CLIENTE DE PRUEBA SL"
    assert result.nif_cliente == "B76543210"
    assert result.cp_cliente == "46001"
    assert result.numero_factura == "AG-77"
    assert result.fecha_factura == "14-02-2026"
    assert result.subtotal == 100.0
    assert result.iva == 21.0
    assert result.total == 121.0