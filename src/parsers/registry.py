from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.parsers.agus import AgusInvoiceParser
from src.parsers.base import BaseInvoiceParser
from src.parsers.cementos_benidorm import CementosBenidormInvoiceParser
from src.parsers.davofrio import DavofrioInvoiceParser
from src.parsers.edieuropa import EdieuropaInvoiceParser
from src.parsers.eseaforms import EseaformsInvoiceParser
from src.parsers.fempa import FempaInvoiceParser
from src.parsers.generic import GenericInvoiceParser
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.parsers.generic_ticket import GenericTicketInvoiceParser
from src.parsers.legal_quality import LegalQualityInvoiceParser
from src.parsers.levantia import LevantiaInvoiceParser
from src.parsers.leroy_merlin import LeroyMerlinInvoiceParser
from src.parsers.maria import MariaInvoiceParser
from src.parsers.mercaluz import MercaluzInvoiceParser
from src.parsers.obramat import ObramatInvoiceParser
from src.parsers.repsol import RepsolInvoiceParser
from src.parsers.rhef import RhefInvoiceParser
from src.parsers.saltoki import SaltokiInvoiceParser
from src.parsers.versotel import VersotelInvoiceParser
from src.parsers.wurth import WurthInvoiceParser
from src.parsers.spark import SparkInvoiceParser
from src.parsers.beroil import BeroilInvoiceParser
from src.parsers.daniel_fernandez import DanielFernandezInvoiceParser


@dataclass(slots=True)
class ParserResolution:
    selected_parser: BaseInvoiceParser
    matched_parsers: list[str]


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, BaseInvoiceParser] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        # Específicos alta prioridad
        self.register(LeroyMerlinInvoiceParser())
        self.register(ObramatInvoiceParser())
        self.register(SaltokiInvoiceParser())
        self.register(RepsolInvoiceParser())
        self.register(DavofrioInvoiceParser())
        self.register(EseaformsInvoiceParser())
        self.register(EdieuropaInvoiceParser())
        self.register(FempaInvoiceParser())
        self.register(CementosBenidormInvoiceParser())
        self.register(RhefInvoiceParser())
        self.register(LegalQualityInvoiceParser())
        self.register(MercaluzInvoiceParser())
        self.register(LevantiaInvoiceParser())
        self.register(WurthInvoiceParser())
        self.register(VersotelInvoiceParser())
        self.register(SparkInvoiceParser())
        self.register(BeroilInvoiceParser())
        self.register(DanielFernandezInvoiceParser())
        from src.parsers.enruta_logistic import EnrutaLogisticInvoiceParser
        self.register(EnrutaLogisticInvoiceParser())
        from src.parsers.rpg_carvin import RpgCarvinInvoiceParser
        self.register(RpgCarvinInvoiceParser())

        # Ticket genérico
        self.register(GenericTicketInvoiceParser())

        # Específicos secundarios
        self.register(MariaInvoiceParser())
        self.register(AgusInvoiceParser())

        # Fallbacks
        self.register(GenericSupplierInvoiceParser())
        self.register(GenericInvoiceParser())

    def register(self, parser: BaseInvoiceParser) -> None:
        self._parsers[parser.parser_name] = parser

    def get(self, parser_name: str) -> BaseInvoiceParser:
        normalized = parser_name.strip().lower()
        if normalized not in self._parsers:
            raise KeyError(f"Parser no registrado: {parser_name}")
        return self._parsers[normalized]

    def list_names(self) -> list[str]:
        return sorted(self._parsers.keys())

    def evaluate(
        self,
        text: str,
        file_path: str | Path | None = None,
        parser_name: str | None = None,
    ) -> ParserResolution:
        if parser_name:
            parser = self.get(parser_name)
            return ParserResolution(
                selected_parser=parser,
                matched_parsers=[parser.parser_name],
            )

        ordered_parsers = sorted(
            self._parsers.values(),
            key=lambda parser: parser.priority,
            reverse=True,
        )

        matched_parsers: list[str] = []
        selected_parser: BaseInvoiceParser | None = None

        for parser in ordered_parsers:
            if not parser.can_handle(text, file_path=file_path):
                continue

            matched_parsers.append(parser.parser_name)
            if selected_parser is None:
                selected_parser = parser

        if selected_parser is None:
            selected_parser = self.get("generic")
            if not matched_parsers:
                matched_parsers.append(selected_parser.parser_name)
        # Tie-break: if both generic_ticket and generic matched, prefer generic_ticket
        try:
            if selected_parser and selected_parser.parser_name == "generic":
                if "generic_ticket" in matched_parsers:
                    selected_parser = self.get("generic_ticket")
        except Exception:
            # defensive: if registry missing names, keep previous selection
            pass
        return ParserResolution(
            selected_parser=selected_parser,
            matched_parsers=matched_parsers,
        )

    def resolve(
        self,
        text: str,
        file_path: str | Path | None = None,
        parser_name: str | None = None,
    ) -> BaseInvoiceParser:
        return self.evaluate(
            text=text,
            file_path=file_path,
            parser_name=parser_name,
        ).selected_parser


_registry: ParserRegistry | None = None


def get_parser_registry() -> ParserRegistry:
    global _registry

    if _registry is None:
        _registry = ParserRegistry()

    return _registry


def resolve_parser(
    text: str,
    file_path: str | Path | None = None,
    parser_name: str | None = None,
) -> BaseInvoiceParser:
    return get_parser_registry().resolve(
        text=text,
        file_path=file_path,
        parser_name=parser_name,
    )


def resolve_parser_with_trace(
    text: str,
    file_path: str | Path | None = None,
    parser_name: str | None = None,
) -> ParserResolution:
    return get_parser_registry().evaluate(
        text=text,
        file_path=file_path,
        parser_name=parser_name,
    )
