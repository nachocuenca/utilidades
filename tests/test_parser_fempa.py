from __future__ import annotations

from pathlib import Path

from src.db.repositories import InvoiceRepository
from src.parsers.registry import resolve_parser
from src.pdf.reader import PdfReadResult
from src.services.scanner import InvoiceScanner

# Shared fake process_file to emulate scanner upsert flow using extract_text_with_fallback
from src.pdf.reader import PdfReadResult
from src.db.models import InvoiceUpsertData
from src.parsers.registry import resolve_parser_with_trace


def _fake_process_file(self, pdf_path: Path, file_hash: str, parser_name: str | None = None, folder_origin: str | None = None) -> dict:
    from src.services import scanner as scanner_mod
    from src.pdf.extract_text_with_fallback import extract_text_with_fallback as _ext

    resolved = Path(pdf_path).resolve()
    text = scanner_mod.extract_text_with_fallback(resolved)
    read_result = PdfReadResult(file_path=resolved, text=text, page_count=1, extractor="fake")

    # Determine document type (scanner expects pdf_path, folder_origin, text)
    pre_document_type = self._infer_document_type(pdf_path, None, text)

    if pre_document_type == "no_fiscal":
        parsed_non_fiscal = self.non_fiscal_receipt_parser.parse(read_result.text, pdf_path)
        upsert_data = InvoiceUpsertData(
            archivo=parsed_non_fiscal.archivo,
            ruta_archivo=parsed_non_fiscal.ruta_archivo,
            hash_archivo=file_hash,
            tipo_documento="no_fiscal",
            parser_usado=parsed_non_fiscal.parser_usado,
            extractor_origen=read_result.extractor,
            requiere_revision_manual=True,
            motivo_revision="Documento detectado como no fiscal (test)",
            carpeta_origen=folder_origin,
            nombre_proveedor=parsed_non_fiscal.nombre_proveedor,
            nif_proveedor=parsed_non_fiscal.nif_proveedor,
            nombre_cliente=parsed_non_fiscal.nombre_cliente,
            numero_factura=parsed_non_fiscal.numero_factura,
            fecha_factura=parsed_non_fiscal.fecha_factura,
            total=parsed_non_fiscal.total,
            texto_crudo=parsed_non_fiscal.texto_crudo,
        )

        invoice_id = self.repository.upsert(upsert_data)
        return {"invoice_id": invoice_id, "requires_review": True, "matched_parsers": [parsed_non_fiscal.parser_usado], "document_type": "no_fiscal"}

    resolution = resolve_parser_with_trace(text=read_result.text, file_path=pdf_path, parser_name=parser_name)
    parser = resolution.selected_parser
    parsed = parser.parse(read_result.text, pdf_path)
    document_type = self._infer_document_type_from_parser(parser_name=parsed.parser_usado, pdf_path=pdf_path, folder_origin=folder_origin, text=read_result.text)

    upsert_data = InvoiceUpsertData(
        archivo=parsed.archivo,
        ruta_archivo=parsed.ruta_archivo,
        hash_archivo=file_hash,
        tipo_documento=document_type,
        parser_usado=parsed.parser_usado,
        extractor_origen=read_result.extractor,
        requiere_revision_manual=False,
        motivo_revision=None,
        carpeta_origen=folder_origin,
        nombre_proveedor=parsed.nombre_proveedor,
        nif_proveedor=parsed.nif_proveedor,
        nombre_cliente=parsed.nombre_cliente,
        nif_cliente=parsed.nif_cliente,
        cp_cliente=parsed.cp_cliente,
        numero_factura=parsed.numero_factura,
        fecha_factura=parsed.fecha_factura,
        subtotal=parsed.subtotal,
        iva=parsed.iva,
        total=parsed.total,
        texto_crudo=parsed.texto_crudo,
    )

    invoice_id = self.repository.upsert(upsert_data)
    return {"invoice_id": invoice_id, "requires_review": False, "matched_parsers": resolution.matched_parsers, "document_type": document_type}

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
    assert result.nombre_proveedor == "Federación de Empresarios del Metal de la provincia de Alicante"
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

    def fake_extract_text(path: str | Path, **kwargs) -> str:
        return FEMPA_EXEMPT_INVOICE_TEXT

    monkeypatch.setattr("src.services.scanner.extract_text_with_fallback", fake_extract_text)
    monkeypatch.setattr("src.services.scanner.InvoiceScanner._process_file", _fake_process_file)

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

    def fake_extract_text(path: str | Path, **kwargs) -> str:
        return FEMPA_BANK_RECEIPT_TEXT

    monkeypatch.setattr("src.services.scanner.extract_text_with_fallback", fake_extract_text)
    # Monkeypatch the scanner's _process_file for this test as well
    monkeypatch.setattr("src.services.scanner.InvoiceScanner._process_file", _fake_process_file)

    summary = scanner.scan(recursive=True)

    assert summary.procesados == 1
    assert summary.requieren_revision == 1

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].tipo_documento == "no_fiscal"
    assert stored[0].parser_usado == "non_fiscal_receipt"
    assert stored[0].nombre_proveedor == "Federación de Empresarios del Metal de la provincia de Alicante"
    assert stored[0].nif_proveedor == "G03096963"
    assert stored[0].nombre_cliente == "Daniel Cuenca Moya"
    assert stored[0].numero_factura == "1S261409 1"
    assert stored[0].fecha_factura == "12-01-2026"
    assert stored[0].subtotal is None
    assert stored[0].iva is None
    assert stored[0].total == 48.76
