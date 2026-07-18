from __future__ import annotations

from pathlib import Path

import pytest

from src.parsers.registry import resolve_parser


@pytest.mark.parametrize(
    ("fixture_name", "parser_name"),
    [
        ("sabadell_invoice_2025.txt", "sabadell"),
        ("amazon_invoice_2026.txt", "amazon"),
        ("orange_invoice_2026.txt", "orange"),
        ("brildor_invoice_2026.txt", "brildor"),
        ("bbva_invoice_2025.txt", "bbva"),
        ("b2mobility_invoice_2026.txt", "b2mobility"),
        ("lcm_agua_invoice_2026.txt", "lcm_agua"),
        ("endesa_invoice_2026.txt", "endesa"),
        ("non_fiscal_bankinter_confirming.txt", "non_fiscal_receipt"),
    ],
)
def test_new_family_parsers_win_over_generic(load_sample_text, fixture_name: str, parser_name: str) -> None:
    text = load_sample_text(fixture_name)

    parser = resolve_parser(text, file_path=Path(fixture_name.replace(".txt", ".pdf")))

    assert parser.parser_name == parser_name
    assert parser.parser_name not in {"generic", "generic_supplier", "generic_ticket"}


def test_sabadell_invoice_extraction(load_sample_text) -> None:
    text = load_sample_text("sabadell_invoice_2025.txt")
    parsed = resolve_parser(text).parse(text, Path("sabadell.pdf"))

    assert parsed.nombre_proveedor == "Banco de Sabadell, S.A."
    assert parsed.nif_proveedor == "A08000143"
    assert parsed.numero_factura == "000000008371329"
    assert parsed.fecha_factura == "31-12-2025"
    assert parsed.subtotal == 0.16
    assert parsed.iva == 0.0
    assert parsed.total == 0.16


def test_amazon_invoice_extraction(load_sample_text) -> None:
    text = load_sample_text("amazon_invoice_2026.txt")
    parsed = resolve_parser(text).parse(text, Path("amazon.pdf"))

    assert parsed.nombre_proveedor == "zhong shan shi min zhong zhen pei xin mao yi shang"
    assert parsed.nif_proveedor == "LU20260743"
    assert parsed.numero_factura == "ES6CGQTEAEUD"
    assert parsed.fecha_factura == "26-05-2026"
    assert parsed.total == 14.98


def test_orange_invoice_extraction(load_sample_text) -> None:
    text = load_sample_text("orange_invoice_2026.txt")
    parsed = resolve_parser(text).parse(text, Path("orange.pdf"))

    assert parsed.nombre_proveedor == "Orange Espagne, S.A.U."
    assert parsed.nif_proveedor == "A82000612"
    assert parsed.numero_factura == "401-KF26-39510"
    assert parsed.fecha_factura == "09-06-2026"
    assert parsed.subtotal == 52.0
    assert parsed.iva == 10.92
    assert parsed.total == 62.92


def test_bbva_b2mobility_and_lcm_amounts(load_sample_text) -> None:
    bbva_text = load_sample_text("bbva_invoice_2025.txt")
    bbva = resolve_parser(bbva_text).parse(bbva_text, Path("bbva.pdf"))
    assert bbva.parser_usado == "bbva"
    assert bbva.subtotal == 38.64
    assert bbva.iva == 8.11
    assert bbva.total == 46.75

    b2_text = load_sample_text("b2mobility_invoice_2026.txt")
    b2 = resolve_parser(b2_text).parse(b2_text, Path("b2.pdf"))
    assert b2.nif_proveedor == "DE316163295"
    assert b2.numero_factura == "2691002145"
    assert b2.iva == 0.0
    assert b2.total == 4.55

    lcm_text = load_sample_text("lcm_agua_invoice_2026.txt")
    lcm = resolve_parser(lcm_text).parse(lcm_text, Path("lcm.pdf"))
    assert lcm.subtotal == 36.0
    assert lcm.iva == 3.6
    assert lcm.total == 39.6


def test_bankinter_confirming_is_non_fiscal_not_sabadell_invoice(load_sample_text) -> None:
    text = load_sample_text("non_fiscal_bankinter_confirming.txt")
    parsed = resolve_parser(text).parse(text, Path("bankinter.pdf"))

    assert parsed.parser_usado == "non_fiscal_receipt"
    assert parsed.tipo_documento == "no_fiscal"
    assert parsed.subtotal is None
    assert parsed.iva is None
