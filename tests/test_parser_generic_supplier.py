from pathlib import Path

from src.parsers.generic_supplier import GenericSupplierInvoiceParser


def test_folder_alias_plus_weak_evidence_rejected() -> None:
    parser = GenericSupplierInvoiceParser()
    text = (
        "Some random header\n"
        "Total factura: 50,00\n"
    )
    # simulate folder alias by passing a path containing 'mercaluz'
    assert not parser.can_handle(text, Path(r"C:\tmp\MERCA\MERCALUZ\doc.pdf"))


def test_nif_and_amounts_accepted() -> None:
    parser = GenericSupplierInvoiceParser()
    text = (
        "COMPONENTES ELECTRICOS MERCALUZ S.A.\n"
        "CIF A03204864\n"
        "Fecha factura: 10/04/2026\n"
        "Base imponible 100,00\n"
        "Total factura 121,00\n"
    )
    assert parser.can_handle(text, None)


def test_noisy_provider_rejected() -> None:
    parser = GenericSupplierInvoiceParser()
    text = (
        "ajoh\n"
        "oiloF\n"
        "Fecha factura: 10/04/2026\n"
        "Total factura 50,00\n"
    )
    assert not parser.can_handle(text, None)
