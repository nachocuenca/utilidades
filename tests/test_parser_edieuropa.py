from pathlib import Path

import pytest

from src.parsers.edieuropa import EdieuropaInvoiceParser


REAL_EDIEUROPA_CASES = [
    ("edieuropa_real_1_a26_11.txt", "Factura 1-A26-11 DANIEL CUENCA MOYA.pdf", "1-A26-11", "01-01-2026"),
    ("edieuropa_real_1_a26_27.txt", "Factura 1-A26-27 DANIEL CUENCA MOYA.pdf", "1-A26-27", "01-02-2026"),
    ("edieuropa_real_1_a26_40.txt", "Factura 1-A26-40 DANIEL CUENCA MOYA.pdf", "1-A26-40", "01-03-2026"),
]


@pytest.fixture
def edieuropa_sample() -> str:
    return Path("tests/fixtures/sample_texts/edieuropa.txt").read_text(encoding='latin1')


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
    assert result.numero_factura == "2024-0456"  # FAC omitido por regex filename
    assert result.fecha_factura == "15-10-2024"  # Formato DD-MM-YYYY del texto
    assert result.subtotal == 800.0
    assert result.iva == 168.0
    assert result.total == 968.0


def test_edieuropa_parse_summary_priority(edieuropa_sample: str, parser: EdieuropaInvoiceParser) -> None:
    """Verifica que usa bloque final coherente Base+IVA=Total."""
    result = parser.parse(edieuropa_sample, "data/edieuropa/FAC-2024-0456.pdf")
    assert abs((result.subtotal or 0) + (result.iva or 0) - (result.total or 0)) <= 0.01


def test_edieuropa_prefiere_filename_robusto_frente_a_ocr_basura(parser: EdieuropaInvoiceParser) -> None:
    text = """EDIEUROPA
CIF: B03310091
FECHA EMISION: 09/04/2026
Nº FACTURA: DANIEL

Base Imponible: 100.00 €
IVA 21%: 21.00 €
TOTAL FACTURA: 121.00 €
"""

    result = parser.parse(text, "data/edieuropa/Factura_1-A26-11.pdf")

    assert result.numero_factura == "1-A26-11"
    assert result.fecha_factura == "09-04-2026"
    assert result.subtotal == 100.0
    assert result.iva == 21.0
    assert result.total == 121.0


def test_edieuropa_sanea_fragmento_ocr_contaminado(parser: EdieuropaInvoiceParser) -> None:
    text = """EDIEUROPA
CIF: B03310091
FECHA EMISION: 09/04/2026
tura 1-A26-27

Base Imponible: 200.00 €
IVA 21%: 42.00 €
TOTAL FACTURA: 242.00 €
"""

    result = parser.parse(text, "data/edieuropa/documento_sin_numero.pdf")

    assert result.numero_factura == "1-A26-27"


def test_edieuropa_rechaza_numero_basura_sin_estructura(parser: EdieuropaInvoiceParser) -> None:
    text = """EDIEUROPA
CIF: B03310091
FECHA EMISION: 09/04/2026
Nº FACTURA: DANIEL

Base Imponible: 300.00 €
IVA 21%: 63.00 €
TOTAL FACTURA: 363.00 €
"""

    result = parser.parse(text, "data/edieuropa/documento_sin_patron.pdf")

    assert result.numero_factura is None


@pytest.mark.parametrize(
    ("fixture_name", "pdf_name", "invoice_number", "invoice_date"),
    REAL_EDIEUROPA_CASES,
)
def test_edieuropa_extrae_tripleta_fiscal_real_sin_regresion(
    load_sample_text,
    parser: EdieuropaInvoiceParser,
    fixture_name: str,
    pdf_name: str,
    invoice_number: str,
    invoice_date: str,
) -> None:
    text = load_sample_text(fixture_name)

    result = parser.parse(text, Path("data/edieuropa") / pdf_name)

    assert result.numero_factura == invoice_number
    assert result.fecha_factura == invoice_date
    assert result.subtotal == pytest.approx(140.50)
    assert result.iva == pytest.approx(29.51)
    assert result.total == pytest.approx(170.01)


def test_edieuropa_extrae_tripleta_fiscal_en_bloque_compactado(parser: EdieuropaInvoiceParser) -> None:
    text = """EDIEUROPA
CIF: B03310091
FECHA EMISION: 01/01/2026
FACTURA
Resumen final Base Imponible % IVA Cuota IVA Total Factura Transferencia bancaria 01/01/2026 140,50 21 29,51 170,01 €
"""

    result = parser.parse(text, "data/edieuropa/Factura_1-A26-11.pdf")

    assert result.numero_factura == "1-A26-11"
    assert result.fecha_factura == "01-01-2026"
    assert result.subtotal == pytest.approx(140.50)
    assert result.iva == pytest.approx(29.51)
    assert result.total == pytest.approx(170.01)


def test_edieuropa_extrae_tripleta_etiquetada_con_tipo_iva_en_linea(parser: EdieuropaInvoiceParser) -> None:
    text = """EDIEUROPA
CIF: B03310091
FECHA EMISION: 01/02/2026
Base Imponible 140,50 Cuota IVA 21 29,51 Total Factura 170,01 €
"""

    result = parser.parse(text, "data/edieuropa/Factura_1-A26-27.pdf")

    assert result.numero_factura == "1-A26-27"
    assert result.fecha_factura == "01-02-2026"
    assert result.subtotal == pytest.approx(140.50)
    assert result.iva == pytest.approx(29.51)
    assert result.total == pytest.approx(170.01)


def test_edieuropa_rechaza_tripleta_intercambiada_con_pistas_fiscales(parser: EdieuropaInvoiceParser) -> None:
    text = """EDIEUROPA
CIF: B03310091
FACTURA
No Factura Fecha Pág.
11A26 01/01/2026 1
CONDICIONES DE PAGO Base Imponible % IVACuota IVA TOTAL FACTURA
Contado Vencimientos
Transferencia bancaria 01/01/2026 29,51 21 140,50 170,01 €
"""

    result = parser.parse(text, "data/edieuropa/Factura_1-A26-11.pdf")

    assert result.numero_factura == "1-A26-11"
    assert result.subtotal is None
    assert result.iva is None
    assert result.total is None


def test_edieuropa_rechaza_tripleta_trivial_tipo_1_1_2(parser: EdieuropaInvoiceParser) -> None:
    text = """EDIEUROPA
CIF: B03310091
FACTURA
No Factura Fecha Pág.
27A26 01/02/2026 1
CONDICIONES DE PAGO Base Imponible % IVACuota IVA TOTAL FACTURA
Contado Vencimientos
Transferencia bancaria 01/02/2026 1,00 1 1,00 2,00 €
"""

    result = parser.parse(text, "data/edieuropa/Factura_1-A26-27.pdf")

    assert result.numero_factura == "1-A26-27"
    assert result.subtotal is None
    assert result.iva is None
    assert result.total is None

