from __future__ import annotations

from pathlib import Path

from src.parsers.registry import resolve_parser, resolve_parser_with_trace
from src.parsers.obramat import ObramatInvoiceParser


def test_generic_ticket_no_longer_intercepts_maria() -> None:
    """Maria debe ganar con sus clues específicos vs generic_ticket bajado."""
    maria_text = """
    María González Arranz
    energyinmotion.es
    Factura 2024-001
    Cliente: ACME SL
    Subtotal: 100€
    IVA 21%: 21€
    Total: 121€
    """

    parser = resolve_parser(maria_text)
    assert parser.parser_name == "maria", f"Esperado maria, obtenido {parser.parser_name}"


def test_generic_ticket_no_longer_intercepts_agus() -> None:
    """Agus gana sus casos específicos."""
    agus_text = """
    Clinica Almendros
    Centro de Fisioterapia Agus
    Factura Nº: AG-2024-018
    Titular: Cliente Ejemplo
    Subtotal 85€
    Total 85€
    """

    parser = resolve_parser(agus_text)
    assert parser.parser_name == "agus", f"Esperado agus, obtenido {parser.parser_name}"


def test_repsol_simplificada_still_goes_to_generic_ticket() -> None:
    """Repsol simplificada debe ir a generic_ticket."""
    repsol_ticket = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: 998877
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """

    resolution = resolve_parser_with_trace(repsol_ticket)
    assert resolution.selected_parser.parser_name == "generic_ticket"
    assert "repsol" not in resolution.matched_parsers
    assert "generic_ticket" in resolution.matched_parsers


def test_obramat_still_beats_generic_ticket() -> None:
    """Obramat alta priority gana."""
    obramat_text = """
    BRICOLAJE BRICOMAN S.L.U.
    Factura normal estructura fiscal completa
    Base imponible, Cuota IVA 21%, Total
    """

    parser = resolve_parser(obramat_text, file_path=Path("data/obramat/factura.pdf"))
    assert parser.parser_name == "obramat"


def test_generic_ticket_path_forcing() -> None:
    """Path /tickets/ fuerza generic_ticket incluso sin strong signals."""
    weak_text = """
    PROVEEDOR XYZ
    Factura 001
    Total 100€
    """

    resolution = resolve_parser_with_trace(weak_text, file_path=Path("data/tickets/ticket.pdf"))
    assert resolution.selected_parser.parser_name == "generic_ticket"


def test_generic_ticket_rejects_long_invoice() -> None:
    """Stricter: largo documento fiscal NO va a generic_ticket."""
    long_invoice = "Base imponible\n" * 60 + "Cuota IVA\nTotal factura\n"

    parser = resolve_parser(long_invoice)
    assert parser.parser_name != "generic_ticket"