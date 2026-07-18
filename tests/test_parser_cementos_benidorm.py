from __future__ import annotations

from pathlib import Path

import pytest

from src.parsers.cementos_benidorm import CementosBenidormInvoiceParser
from src.parsers.registry import resolve_parser_with_trace

REAL_CEMENTOS_CASES = [
    ("cementos_benidorm_21_44.txt", "CamScanner 30-3-26 21.44.pdf", "05032-000873", 16.44, 3.45, 19.89),
    ("cementos_benidorm_21_46.txt", "CamScanner 30-3-26 21.46.pdf", "05032-000874", 16.15, 3.39, 19.54),
]


@pytest.mark.parametrize(
    ("fixture_name", "pdf_name", "invoice_number", "subtotal", "iva", "total"),
    REAL_CEMENTOS_CASES,
)
def test_registry_resolves_cementos_benidorm_before_generics(
    load_sample_text,
    fixture_name: str,
    pdf_name: str,
    invoice_number: str,
    subtotal: float,
    iva: float,
    total: float,
) -> None:
    text = load_sample_text(fixture_name)

    resolution = resolve_parser_with_trace(
        text=text,
        file_path=Path(r"C:\Users\ignac\Downloads\1T26\1T 26\CEMENTOS BENIDORM") / pdf_name,
    )

    assert resolution.selected_parser.parser_name == "cementos_benidorm"
    assert "cementos_benidorm" in resolution.matched_parsers


@pytest.mark.parametrize(
    ("fixture_name", "pdf_name", "invoice_number", "subtotal", "iva", "total"),
    REAL_CEMENTOS_CASES,
)
def test_cementos_benidorm_extracts_real_ocr_fields(
    load_sample_text,
    fixture_name: str,
    pdf_name: str,
    invoice_number: str,
    subtotal: float,
    iva: float,
    total: float,
) -> None:
    text = load_sample_text(fixture_name)
    parser = CementosBenidormInvoiceParser()
    file_path = Path(r"C:\Users\ignac\Downloads\1T26\1T 26\CEMENTOS BENIDORM") / pdf_name

    assert parser.can_handle(text, file_path) is True

    result = parser.parse(text, file_path)

    assert result.parser_usado == "cementos_benidorm"
    assert result.nombre_proveedor == "Cementos Benidorm, S.A."
    assert result.nif_proveedor == "A03072816"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.cp_cliente == "03501"
    assert result.cp_cliente != "05032"
    assert result.numero_factura == invoice_number
    assert result.fecha_factura == "06-03-2026"
    assert result.subtotal == pytest.approx(subtotal)
    assert result.iva == pytest.approx(iva)
    assert result.total == pytest.approx(total)
    assert (result.subtotal or 0) + (result.iva or 0) == pytest.approx(result.total or 0)
