from pathlib import Path

from src.parsers.generic_ticket import GenericTicketInvoiceParser


def test_path_ticket_with_total_date_and_strong_accepts() -> None:
    parser = GenericTicketInvoiceParser()
    text = (
        "Ticket nº 123\n"
        "Fecha: 10/04/2026\n"
        "Total: 12,50\n"
        "Pagado con tarjeta\n"
    )
    assert parser.can_handle(text, Path(r"C:\data\tickets\doc.pdf"))


def test_text_with_fiscal_markers_rejected() -> None:
    parser = GenericTicketInvoiceParser()
    text = (
        "Proveedor SA\n"
        "Base imponible 100,00\n"
        "Cuota IVA 21,00\n"
        "Total factura 121,00\n"
    )
    assert not parser.can_handle(text, None)


def test_short_weak_text_with_ticket_word_rejected() -> None:
    parser = GenericTicketInvoiceParser()
    text = (
        "ticket\n"
        "Total: 5,00\n"
    )
    assert not parser.can_handle(text, None)
