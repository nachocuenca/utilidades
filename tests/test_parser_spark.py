from pathlib import Path
from src.parsers.spark import SparkInvoiceParser

def test_spark_parser_minimal(load_sample_text):
    text = load_sample_text("FACT 220224 DE SPARK A BENIOFFI.txt")
    parser = SparkInvoiceParser()
    result = parser.parse(text, Path("FACT 220224 DE SPARK A BENIOFFI.pdf"))
    assert result.parser_usado == "spark"
    assert result.nombre_proveedor == "SPARK ENERGIA SL"
    # El resto de asserts se pueden ajustar según layout real y Excel
