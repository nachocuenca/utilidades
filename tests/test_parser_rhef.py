from __future__ import annotations

from pathlib import Path

import pytest

from src.parsers.registry import resolve_parser_with_trace
from src.parsers.rhef import RhefInvoiceParser


def test_registry_resolves_rhef_before_generics(load_sample_text) -> None:
    text = load_sample_text("rhef_21_47.txt")

    resolution = resolve_parser_with_trace(
        text=text,
        file_path=Path(r"C:\Users\ignac\Downloads\1T26\1T 26\RHEF\CamScanner 30-3-26 21.47.pdf"),
    )

    assert resolution.selected_parser.parser_name == "rhef"
    assert "rhef" in resolution.matched_parsers


def test_rhef_extracts_real_ocr_fields(load_sample_text) -> None:
    text = load_sample_text("rhef_21_47.txt")
    parser = RhefInvoiceParser()
    file_path = Path(r"C:\Users\ignac\Downloads\1T26\1T 26\RHEF\CamScanner 30-3-26 21.47.pdf")

    assert parser.can_handle(text, file_path) is True

    result = parser.parse(text, file_path)

    assert result.parser_usado == "rhef"
    assert result.nombre_proveedor == "Francisco Amador Garcia"
    assert result.nif_proveedor == "48321093W"
    assert result.metadatos["nombre_comercial"] == "Recambios Rhef"
    assert result.nombre_cliente == "Daniel Cuenca Moya"
    assert result.cp_cliente == "03501"
    assert result.numero_factura == "BFAC/260186"
    assert result.fecha_factura == "11-03-2026"
    assert result.subtotal == pytest.approx(120.62)
    assert result.iva == pytest.approx(25.33)
    assert result.total == pytest.approx(145.95)
    assert (result.subtotal or 0) + (result.iva or 0) == pytest.approx(result.total or 0)
