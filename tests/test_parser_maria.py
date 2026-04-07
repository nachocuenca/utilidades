from __future__ import annotations

from pathlib import Path

from src.parsers.maria import MariaInvoiceParser


def test_maria_parser_detects_known_emitter(load_sample_text) -> None:
    text = load_sample_text("maria_01.txt")
    parser = MariaInvoiceParser()

    assert parser.can_handle(text, Path("maria_01.pdf")) is True

    result = parser.parse(text, Path("maria_01.pdf"))

    assert result.parser_usado == "maria"
    assert result.nombre_proveedor == "Maria Gonzalez Arranz"
    assert result.nombre_cliente == "ACME CONSULTING SL"
    assert result.nif_cliente == "B12345678"
    assert result.cp_cliente == "28013"
    assert result.numero_factura == "M-2026-001"
    assert result.fecha_factura == "05-03-2026"
    assert result.subtotal == 23.9669
    assert result.iva == 5.0331
    assert result.total == 29.0


def test_maria_parser_calculates_missing_subtotal(load_sample_text) -> None:
    text = load_sample_text("maria_02.txt")
    parser = MariaInvoiceParser()

    result = parser.parse(text, Path("maria_02.pdf"))

    assert result.parser_usado == "maria"
    assert result.nombre_proveedor == "Maria Gonzalez Arranz"
    assert result.nombre_cliente == "NOVA STUDIO LAB"
    assert result.nif_cliente == "A1B2C3D4"
    assert result.cp_cliente == "46001"
    assert result.numero_factura == "M-2026-002"
    assert result.fecha_factura == "07-04-2026"
    assert result.subtotal == 100.0
    assert result.iva == 21.0
    assert result.total == 121.0