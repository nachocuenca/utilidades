from __future__ import annotations

from pathlib import Path

from config.settings import get_settings
from src.db.repositories import InvoiceRepository
from src.pdf.reader import PdfReadResult
from src.services.scanner import InvoiceScanner


def test_scanner_processes_pdf_and_persists_result(load_sample_text, monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "maria_01.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)
    sample_text = load_sample_text("maria_01.txt")

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=sample_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    summary = scanner.scan()

    assert summary.total_encontrados == 1
    assert summary.procesados == 1
    assert summary.creados == 1
    assert summary.actualizados == 0
    assert summary.fallidos == 0
    assert repository.count() == 1

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].nombre_proveedor == "María González Arranz"
    assert stored[0].nombre_cliente == "ACME CONSULTING SL"

    second_summary = scanner.scan(skip_known=True)

    assert second_summary.total_encontrados == 1
    assert second_summary.omitidos == 1
    assert second_summary.procesados == 0
    assert repository.count() == 1


def test_scanner_marks_ticket_type_from_resolved_parser_and_skips_default_customer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS", "true")
    monkeypatch.setenv("DEFAULT_CUSTOMER_NAME", "Daniel Cuenca Moya")
    monkeypatch.setenv("DEFAULT_CUSTOMER_TAX_ID", "48334490J")
    monkeypatch.setenv("DEFAULT_CUSTOMER_POSTAL_CODE", "03501")
    get_settings.cache_clear()

    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "gasolina"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "ticket_repsol.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    ticket_text = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: TK-2026-77
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=ticket_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    scanner.scan(recursive=True)

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].parser_usado == "generic_ticket"
    assert stored[0].tipo_documento == "ticket"
    assert stored[0].nombre_cliente is None
    assert stored[0].nif_cliente is None
    assert stored[0].cp_cliente is None


def test_scanner_applies_default_customer_over_garbage_for_facturas(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS", "true")
    monkeypatch.setenv("DEFAULT_CUSTOMER_NAME", "Daniel Cuenca Moya")
    monkeypatch.setenv("DEFAULT_CUSTOMER_TAX_ID", "48334490J")
    monkeypatch.setenv("DEFAULT_CUSTOMER_POSTAL_CODE", "03501")
    get_settings.cache_clear()

    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "proveedor_x"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "factura_cliente_sucio.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    dirty_customer_text = """
    PROVEEDOR XYZ SL
    CIF B12345678
    Cliente: LCUENCAMOYA
    NIF cliente: ES84 1465 0100 9417 6430 4696
    Factura: F-2026-001
    Fecha factura: 08/04/2026
    Base imponible 100,00
    IVA 21,00
    Total factura 121,00
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=dirty_customer_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    scanner.scan(recursive=True)

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].tipo_documento == "factura"
    assert stored[0].nombre_cliente == "Daniel Cuenca Moya"
    assert stored[0].nif_cliente == "48334490J"
    assert stored[0].cp_cliente == "03501"


def test_scanner_process_file_returns_parser_trace_with_matched_parsers(monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "varios"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "ticket_fuera_de_carpeta.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    ticket_text = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: 998877
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=ticket_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    result = scanner._process_file(
        pdf_path=pdf_path.resolve(),
        file_hash="dummyhash",
        parser_name=None,
        folder_origin="varios",
    )

    assert isinstance(result["matched_parsers"], list)
    assert "generic_ticket" in result["matched_parsers"]
    assert result["document_type"] == "ticket"
    assert int(result["invoice_id"]) > 0


def test_scanner_keeps_customer_empty_when_root_scan_has_no_folder_origin(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORCE_DEFAULT_CUSTOMER_FOR_FACTURAS", "true")
    monkeypatch.setenv("DEFAULT_CUSTOMER_NAME", "Daniel Cuenca Moya")
    monkeypatch.setenv("DEFAULT_CUSTOMER_TAX_ID", "48334490J")
    monkeypatch.setenv("DEFAULT_CUSTOMER_POSTAL_CODE", "03501")
    get_settings.cache_clear()

    inbox_dir = tmp_path / "repsol"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = inbox_dir / "09_01 75,75 €.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    repsol_text = """Nº Factura: 096943/5/26/000169
Fecha: 09/01/2026
F. Operación: 09/01/2026
E.S./A.S. Lugar Suministro (*)
CRED BENIDORM
CR CV-70 P.K. 47
03500 BENIDORM (ALICANTE)
CAMPSA ESTACIONES SERVICIO SA
Adquiriente
CUENCA MOYA DANIEL
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Matrícula: 8991KBS
Datos Fiscales Adquiriente CUENCA MOYA DANIEL (CIF/NIF: 48334490J)
CALLE MARAVALL 31 SEGUNDO E
03501 BENIDORM (ALICANTE)
Datos del suministro
Fecha Productos Litros €/L Importe
09.01.2026 Diesel e+ 53,01 1,429 75,75
Importe del producto (Base Imponible) 62,60 €
IVA 21,00% de 62,60 € 13,15 €
TOTAL FACTURA EUROS........ 75,75 €
(*) Esta factura está emitida en nombre y por cuenta de Repsol Soluciones Energéticas, S.A.
Repsol Soluciones Energéticas, S.A. Méndez Alvaro, 44. Madrid 28045
Registro Mercantil de Madrid, Tomo 2530 gral, Folio 1, Hoja M-44194, incr 665 C.I.F. A-80298839"""

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=repsol_text,
            page_count=1,
            extractor="fake",
        )

    monkeypatch.setattr("src.services.scanner.read_pdf_text", fake_read_pdf_text)

    summary = scanner.scan()
    assert summary.procesados == 1

    stored = repository.list_invoices()
    assert len(stored) == 1
    assert stored[0].nombre_proveedor == "Repsol Soluciones Energéticas, S.A."
    assert stored[0].nif_proveedor == "A80298839"
    assert stored[0].nombre_cliente is None
    assert stored[0].nif_cliente is None
    assert stored[0].cp_cliente is None
    assert stored[0].subtotal == 62.6
    assert stored[0].iva == 13.15
    assert stored[0].total == 75.75


def test_scanner_extracts_minimal_fields_for_tgss_no_fiscal_receipt(monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "TGSS"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "seguros_sociales_marzo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    tgss_text = """
    TESORERIA GENERAL DE LA SEGURIDAD SOCIAL
    Recibo de liquidacion de cotizaciones
    Razon social: AUTONOMOS PRUEBA SL
    Fecha de valor: 28/03/2026
    Importe del recibo: 523,17 EUR
    Referencia: TGSS-03/2026-0001
    Numero de recibo: 011234567890
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=tgss_text,
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
    assert stored[0].nombre_proveedor == "Tesorería General de la Seguridad Social"
    assert stored[0].nombre_cliente == "AUTONOMOS PRUEBA SL"
    assert stored[0].numero_factura == "TGSS-03/2026-0001"
    assert stored[0].fecha_factura == "28-03-2026"
    assert stored[0].subtotal is None
    assert stored[0].iva is None
    assert stored[0].nif_proveedor is None
    assert stored[0].total == 523.17


def test_scanner_extracts_minimal_fields_for_bank_receipt_no_fiscal(monkeypatch, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    supplier_dir = inbox_dir / "recibos banco"
    supplier_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = supplier_dir / "agua_abril.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake file for tests")

    repository = InvoiceRepository(db_path=tmp_path / "app.db")
    scanner = InvoiceScanner(repository=repository, inbox_dir=inbox_dir)

    bank_receipt_text = """
    Adeudo por domiciliacion
    Titular de la domiciliacion
    AUTONOMO PRUEBA SL
    Entidad emisora
    SUMINISTROS AGUA MEDITERRANEO SL
    Fecha de valor: 09/04/2026
    Importe adeudado: 81,44 EUR
    Observaciones: REC-2026/0045
    Referencia del adeudo: SDD-998877
    """

    def fake_read_pdf_text(path: str | Path) -> PdfReadResult:
        resolved = Path(path).resolve()
        return PdfReadResult(
            file_path=resolved,
            text=bank_receipt_text,
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
    assert stored[0].nombre_cliente == "AUTONOMO PRUEBA SL"
    assert stored[0].nombre_proveedor == "SUMINISTROS AGUA MEDITERRANEO SL"
    assert stored[0].numero_factura == "REC-2026/0045"
    assert stored[0].fecha_factura == "09-04-2026"
    assert stored[0].subtotal is None
    assert stored[0].iva is None
    assert stored[0].total == 81.44
