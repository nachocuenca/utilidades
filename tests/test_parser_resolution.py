from __future__ import annotations

from pathlib import Path

from src.parsers.registry import resolve_parser, resolve_parser_with_trace


def test_path_hint_alone_does_not_force_specific_parser() -> None:
    text = """
    FACTURA
    Proveedor: ACME SUMINISTROS SL
    CIF proveedor: B12345678
    Número de factura: AC-2026-001
    Fecha factura: 08/04/2026
    Base imponible: 100,00
    Cuota IVA: 21,00
    Total factura: 121,00
    """

    parser = resolve_parser(text, file_path=Path(r"C:\temp\saltoki\mezcla\factura.pdf"))

    assert parser.parser_name == "generic_supplier"


def test_generic_ticket_requires_strong_evidence_outside_ticket_folder() -> None:
    text = """
    FACTURA
    Proveedor: SUMINISTROS BENIDORM SL
    Identificador: DOC-44
    Número de factura: SB-2026-014
    Fecha factura: 08/04/2026
    Base imponible: 50,00
    Cuota IVA: 10,50
    Total factura: 60,50
    """

    parser = resolve_parser(text, file_path=Path(r"C:\temp\proveedores\suministros\factura.pdf"))

    assert parser.parser_name == "generic_supplier"


def test_generic_ticket_matches_when_ticket_signals_are_clear() -> None:
    text = """
    REPSOL ESTACION DE SERVICIO
    FACTURA SIMPLIFICADA
    N° OP: 998877
    FECHA: 08/04/2026
    TOTAL: 54,20
    EFECTIVO: 60,00
    CAMBIO: 5,80
    """

    resolution = resolve_parser_with_trace(text, file_path=Path(r"C:\temp\varios\ticket_fuera_de_carpeta.pdf"))

    assert resolution.selected_parser.parser_name == "generic_ticket"
    assert "generic_ticket" in resolution.matched_parsers


def test_specific_parser_needs_textual_confirmation_even_with_supplier_folder() -> None:
    text = """
    FACTURA
    Proveedor: FERRETERIA COSTA SL
    CIF proveedor: B76543210
    Número de factura: FC-2026-200
    Fecha factura: 08/04/2026
    Base imponible: 80,00
    Cuota IVA: 16,80
    Total factura: 96,80
    """

    parser = resolve_parser(text, file_path=Path(r"C:\temp\mercaluz\mezcla\factura.pdf"))

    assert parser.parser_name == "generic_supplier"


def test_mercaluz_selected_with_text_nif_abv() -> None:
    text = """
    MERCALUZ S.A.
    NIF A03204864
    FACTURA ABV2024-00123-456789
    """
    
    parser = resolve_parser(text, file_path=Path(r"C:\temp\mercaluz\ABV2024-00123-456789.pdf"))
    
    assert parser.parser_name == "mercaluz"

