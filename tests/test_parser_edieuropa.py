from pathlib import Path

import pytest

from src.parsers.edieuropa import EdieuropaInvoiceParser
from src.parsers.base import ParsedInvoiceData


@pytest.fixture
def edieuropa_sample() -> str:
    return Path("tests/fixtures/sample_texts/edieuropa.txt").read_text()


@pytest.fixture
def parser() -> EdieuropaInvoiceParser:
    return EdieuropaInvoiceParser()


def test_edieuropa_can_handle_true(edieuropa_sample: str, parser: EdieuropaInvoiceParser) -> None:
    assert parser.can_handle(edieuropa_sample, "data/edieuropa/FAC-2024-0456.pdf")


def test_edieuropa_can_handle_false_generic(parser: EdieuropaInvoiceParser) -> None:
    generic_text = "Factura genérica sin Edieuropa"
    assert not parser.can_handle(generic_text)


def test_edieuropa_parse_completo(edieuropa_sample: str, parser: EdieuropaInvoiceParser) -> None:
    result = parser.parse(edieuropa_sample, "data/edieuropa/FAC-2024-0456.pdf")

    assert result.parser_usado == "edieuropa"
    assert result.nombre_proveedor == "EDIEUROPA"
    assert result.nif_proveedor == "B03310091"
    assert result.numero_factura == "FAC-2024-0456"
    assert result.fecha_factura == "2024-10-15"
    assert result.subtotal == 800.0
    assert result.iva == 168.0
    assert result.total == 968.0


def test_edieuropa_parse_summary_priority(edieuropa_sample: str, parser: EdieuropaInvoiceParser) -> None:
    """Verifica que usa bloque final coherente Base+IVA=Total."""
    result = parser.parse(edieuropa_sample, "data/edieuropa/FAC-2024-0456.pdf")
    assert abs((result.subtotal or 0) + (result.iva or 0) - (result.total or 0)) <= 0.01

