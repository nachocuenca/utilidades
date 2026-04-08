from __future__ import annotations

from src.utils.amounts import calculate_missing_amounts, parse_amount
from src.utils.dates import normalize_date
from src.utils.ids import normalize_tax_id
from src.utils.names import clean_name_candidate, is_valid_name_candidate


def test_parse_amount_normalizes_spanish_amounts() -> None:
    assert parse_amount("1.234,56") == 1234.56
    assert parse_amount("23,9669") == 23.9669
    assert parse_amount("121.00") == 121.0


def test_calculate_missing_amounts_completes_subtotal() -> None:
    subtotal, iva, total = calculate_missing_amounts(None, 21.0, 121.0)

    assert subtotal == 100.0
    assert iva == 21.0
    assert total == 121.0


def test_normalize_date_returns_dd_mm_yyyy() -> None:
    assert normalize_date("2026-04-07") == "07-04-2026"
    assert normalize_date("7 de abril de 2026") == "07-04-2026"
    assert normalize_date("05/03/2026") == "05-03-2026"


def test_normalize_tax_id_removes_spaces_and_symbols() -> None:
    assert normalize_tax_id(" B-12345678 ") == "B12345678"
    assert normalize_tax_id("x 1234567 l") == "X1234567L"


def test_name_helpers_reject_tax_ids_as_names() -> None:
    assert clean_name_candidate("Cliente: ACME SL") == "ACME SL"
    assert is_valid_name_candidate("ACME CONSULTING SL") is True
    assert is_valid_name_candidate("B12345678") is False


def test_name_helpers_reject_known_heading_noise() -> None:
    assert is_valid_name_candidate("Información adicional Referencia") is False
    assert is_valid_name_candidate("En cumplimiento de la normativa vigente es posible que el concepto esté incompleto") is False
    assert is_valid_name_candidate("BRICOLAJE - CONSTRUCCIÓN - DECORACIÓN - JARDINERÍA") is False
    assert is_valid_name_candidate(")otnemucod") is False
