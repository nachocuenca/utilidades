from __future__ import annotations

from pathlib import Path

from src.parsers.generic import GenericInvoiceParser
from src.parsers.generic_supplier import GenericSupplierInvoiceParser


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


def test_generic_parser_prefers_coherent_summary_over_iva_percentage() -> None:
    text = """
    VERSOTEL PRODUCTO ELECTRÓNICO S.L.
    CIF B12345678
    Cliente: Daniel Cuenca Moya
    NIF cliente: 48334490J
    Factura: V-2026-001
    Fecha factura: 11/03/2026

    Línea 1 78,20

    Base imponible 78,20
    IVA 21% 16,42
    Total factura 94,62
    """
    parser = GenericInvoiceParser()

    result = parser.parse(text, Path("versotel_001.pdf"))

    assert result.nombre_proveedor == "VERSOTEL PRODUCTO ELECTRÓNICO S.L."
    assert result.numero_factura == "V-2026-001"
    assert result.subtotal == 78.2
    assert result.iva == 16.42
    assert result.total == 94.62


def test_generic_supplier_skips_customer_tax_id_when_extracting_supplier() -> None:
    text = """
    FRANCISCO AMADOR GARCIA
    NIF 48321093W
    Factura: BFAC/260186
    Fecha factura: 11/03/2026

    Cliente: Daniel Cuenca Moya
    NIF cliente: 48334490J

    Base imponible 120,62
    IVA 25,33
    Total factura 145,95
    """
    parser = GenericSupplierInvoiceParser()

    result = parser.parse(text, Path("francisco_amador.pdf"))

    assert result.nombre_proveedor == "FRANCISCO AMADOR GARCIA"
    assert result.nif_proveedor == "48321093W"
    assert result.numero_factura == "BFAC/260186"
    assert result.subtotal == 120.62
    assert result.iva == 25.33
    assert result.total == 145.95


def test_generic_parser_rejects_invoice_number_ocr_fragment() -> None:
    assert GenericInvoiceParser.clean_invoice_number_candidate("Direcci") is None


def test_generic_supplier_ignores_noisy_provider_lines_from_csv_anomalies() -> None:
    text = """
    En cumplimiento de la normativa vigente es posible que el concepto esté incompleto.
    Para más información sobre el cargo, debe dirigirse a la empresa emisora del mismo.
    Información adicional Referencia
    Fecha factura: 01/04/2026
    Total factura: 16,15
    Cliente: Daniel Cuenca Moya
    NIF cliente: 48334490J
    """
    parser = GenericSupplierInvoiceParser()

    result = parser.parse(text, Path("documento_ruidoso.pdf"))

    assert result.nombre_proveedor is None
    assert result.nif_proveedor is None
    assert result.fecha_factura == "01-04-2026"
    assert result.total == 16.15


def test_base_parser_noise_detector_flags_reversed_or_fragmented_names() -> None:
    parser = GenericSupplierInvoiceParser()

    assert parser.is_probable_noise_name(")otnemucod") is True
    assert parser.is_probable_noise_name(".F.I.N") is True
    assert parser.is_probable_noise_name("Información adicional Referencia") is True
    assert parser.is_probable_noise_name("FRANCISCO AMADOR GARCIA") is False


def test_generic_base_rechaza_proveedor_ocr_basura() -> None:
    """Proveedor basura OCR filtrado."""
    parser = GenericSupplierInvoiceParser()
    text = """
otnemucod
ajoh 
OILOF 
.F.I.N
Cliente: Cliente Prueba SL
    """
    result = parser.parse(text, Path("ocr_proveedor_basura.pdf"))
    assert result.nombre_proveedor is None


def test_generic_base_nif_proveedor_no_coge_cliente() -> None:
    """NIF proveedor excluye correctamente NIF cliente."""
    text = """
PROVEEDOR XYZ SL
NIF B12345678

Cliente Prueba SL
NIF cliente 48334490J
    """
    parser = GenericSupplierInvoiceParser()
    result = parser.parse(text, Path("nif_cliente.pdf"))
    assert result.nif_proveedor == "B12345678"


def test_generic_base_numero_factura_filtra_ocr() -> None:
    """Numero_factura rechaza basura OCR."""
    assert GenericInvoiceParser().clean_invoice_number_candidate("direcci") is None
    assert GenericInvoiceParser().clean_invoice_number_candidate("aeiouprueba") is None
    assert GenericInvoiceParser().clean_invoice_number_candidate("F123") == "F123"
    assert GenericInvoiceParser().clean_invoice_number_candidate("2026-001") == "2026-001"


def test_generic_base_iva_cuota_no_porcentaje() -> None:
    """IVA extrae cuota real, no tipo %."""
    text = """
Base imponible 100,00
IVA (21%) 21,00 
Total factura 121,00
    """
    parser = GenericInvoiceParser()
    result = parser.parse(text, Path("iva_test.pdf"))
    assert result.iva == 21.0


def test_generic_base_prioriza_bloque_final() -> None:
    """Prioriza bloque final coherente Base+IVA=Total."""
    text = """
...líneas intermedias...
Base 80.00
IVA 16.80
Subtotal parcial 96.80

*** RESUMEN FINAL ***
Base imponible..... 118.00
IVA 21%............ 24.78
TOTAL FACTURA...... 142.78
    """
    parser = GenericSupplierInvoiceParser()
    result = parser.parse(text, Path("bloque_final.pdf"))
    assert result.subtotal == 118.0
    assert result.iva == 24.78
    assert result.total == 142.78


def test_generic_supplier_uses_folder_alias_for_levantia_when_ocr_name_is_noisy() -> None:
    text = """
    77410930B
    OILOF
    Fecha factura: 20/03/2026
    Total factura: 1576,63
    Cliente: Daniel Cuenca Moya
    NIF cliente: 48334490J
    """
    parser = GenericSupplierInvoiceParser()

    result = parser.parse(text, Path(r"C:\tmp\1T 26\LEVANTIA\0100604203149.pdf"))

    assert result.nombre_proveedor == "Aislamientos Acústicos Levante, S.L."
    assert result.total == 1576.63


def test_generic_supplier_uses_folder_alias_for_davofrio_when_top_name_is_garbage() -> None:
    text = """
    ajoH
    Fecha factura: 26/03/2026
    Base imponible 219,00
    IVA 45,99
    Total factura 264,99
    Cliente: Daniel Cuenca Moya
    NIF cliente: 48334490J
    """
    parser = GenericSupplierInvoiceParser()

    result = parser.parse(text, Path(r"C:\tmp\1T 26\DAVOFRIO\FVC26-0381.pdf"))

    assert result.nombre_proveedor == "DAVOFRIO, S.L.U."
    assert result.subtotal == 219.0
    assert result.iva == 45.99
    assert result.total == 264.99


def test_generic_supplier_marks_credit_note_amounts_as_negative() -> None:
    text = """
    ABONO
    No factura : ABV2603-10000-002221
    Fecha : 20/03/2026
    Total AI 5,49
    Impuesto 21,00 % sobre 5,49 1,15
    Total II 6,64
    NETO A PAGAR -6,64 EUR
    """
    parser = GenericSupplierInvoiceParser()

    result = parser.parse(text, Path(r"C:\tmp\1T 26\MERCALUZ\ABV2603-10000-002221.pdf"))

    assert result.subtotal == -5.49
    assert result.iva == -1.15
    assert result.total == -6.64
