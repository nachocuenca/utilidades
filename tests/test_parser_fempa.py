from __future__ import annotations

from pathlib import Path

from src.db.repositories import InvoiceRepository
from src.parsers.registry import resolve_parser
from src.pdf.reader import PdfReadResult
from src.services.scanner import InvoiceScanner

FEMPA_EXEMPT_INVOICE_TEXT = """
FED. EMPRESARIOS DEL METAL
CUENCA MOYA, DANIEL
DE LA PROVINCIA DE ALICANTE
CALLE MARAVALL 31 2E
CL BENIJOFAR 4 6
BENIDORM, ALICANTE 03501
POL IND AGUA AMARGA
Espana
ALACANT/ALICANTE, Alicante/Alacant 03008
Espana
CIF/NIF G03096963
Telefono 965150300
Fax 965161000
E-mail fempa@fempa.es
Web www.fempa.es
No factura 1S261409
Fecha registro 05/01/26
CIF/NIF Cliente 48334490J
No Descripcion Cantidad Precio venta % Dto. % IVA Importe
0000366 Cuota FEMPA de 01/01/26 a 1 292,50 0 % 292,50
30/06/26
IVA exento s/Art.20 Uno 12 y Art.20 Tres de la ley 37/1992 de 28 de Dic. del Impuesto sobre el Valor Anadido
Base imponible % IVA Cuota IVA % RE Cuota RE
292,50 TOTAL FACTURA: 292,50
"""

FEMPA_BANK_RECEIPT_TEXT = """
Adeudo recibido
IBAN ES10 1465 0100 9617 4459 4754
Titular de la domiciliacion Entidad emisora
Importe euros Clausula gastos Fecha operacion Fecha valor
Referencia del adeudo
Informacion adicional
En cumplimiento de la normativa vigente es posible que el concepto este incompleto.
01/04/2026 1 de 1 DANIEL CUENCA MOYA ES10 1465 0100 9617 4459 4754
CUENCA MOYA DANIEL FEDERACION DE EMPRESARIOS DEL METAL DE L
48,76 Compartidos 12/01/2026 12/01/2026
Factura N.
1S261409 1
Id. emisor: ES83000G03096963
"""


def test_fempa_parser_extracts_exempt_invoice_with_zero_iva() -> None:
    parser = resolve_parser(
        FEMPA_EXEMPT_INVOICE_TEXT,
        file_path=Path(r"C:\tmp\1T 26\FEMPA\CUOTA 2026 292,50.pdf"),
    )

    result = parser.parse(
        FEMPA_EXEMPT_INVOICE_TEXT,
        Path(r"C:\tmp\1T 26\FEMPA\CUOTA 2026 292,50.pdf"),
    )

    assert parser.parser_name == "fempa"
    assert result.nombre_proveedor == "FED. EMPRESARIOS DEL METAL"
    assert result.nif_proveedor == "G03096963"
    assert result.numero_factura == "1S261409"
    assert result.fecha_factura == "05-01-2026"
    assert result.subtotal == 292.5
    assert result.iva == 0.0
    assert result.total == 292.5


def test_scanner_persists_fempa_exempt_invoice_as_factura(monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "FEMPA"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "CUOTA 2026 292,50.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=FEMPA_EXEMPT_INVOICE_TEXT,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    summary = scanner.scan(recursive=True)

    assert summary.procesados == 1

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].tipo_documento == "factura"
    assert stored[0].parser_usado == "fempa"
    assert stored[0].subtotal == 292.5
    assert stored[0].iva == 0.0
    assert stored[0].total == 292.5


def test_scanner_keeps_fempa_bank_receipt_as_no_fiscal(monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "FEMPA"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "ENERO 48,76.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=FEMPA_BANK_RECEIPT_TEXT,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    summary = scanner.scan(recursive=True)

    assert summary.procesados == 1
    assert summary.requieren_revision == 1

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].tipo_documento == "no_fiscal"
    assert stored[0].parser_usado == "non_fiscal_receipt"
    assert stored[0].nombre_proveedor == "Federación de Empresarios del Metal de la provincia de Alicante"
    assert stored[0].nombre_cliente == "Daniel Cuenca Moya"
    assert stored[0].numero_factura == "1S261409 1"
    assert stored[0].fecha_factura == "12-01-2026"
    assert stored[0].subtotal is None
    assert stored[0].iva is None
    assert stored[0].total == 48.76
