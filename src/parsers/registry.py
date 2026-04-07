from __future__ import annotations

from pathlib import Path

from src.parsers.agus import AgusInvoiceParser
from src.parsers.base import BaseInvoiceParser
from src.parsers.edieuropa import EdieuropaInvoiceParser
from src.parsers.eseaforms import EseaformsInvoiceParser
from src.parsers.generic import GenericInvoiceParser
from src.parsers.generic_supplier import GenericSupplierInvoiceParser
from src.parsers.maria import MariaInvoiceParser
from src.parsers.mercaluz import MercaluzInvoiceParser
from src.parsers.obramat import ObramatInvoiceParser
from src.parsers.repsol import RepsolInvoiceParser
from src.parsers.saltoki import SaltokiInvoiceParser


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, BaseInvoiceParser] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(ObramatInvoiceParser())
        self.register(SaltokiInvoiceParser())
        self.register(MercaluzInvoiceParser())
        self.register(RepsolInvoiceParser())
        self.register(EseaformsInvoiceParser())
        self.register(EdieuropaInvoiceParser())
        self.register(MariaInvoiceParser())
        self.register(AgusInvoiceParser())
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

    def resolve(
        self,
        text: str,
        file_path: str | Path | None = None,
        parser_name: str | None = None,
    ) -> BaseInvoiceParser:
        if parser_name:
            return self.get(parser_name)

        ordered_parsers = sorted(
            self._parsers.values(),
            key=lambda parser: parser.priority,
            reverse=True,
        )

        for parser in ordered_parsers:
            if parser.can_handle(text, file_path=file_path):
                return parser

        return self.get("generic")


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