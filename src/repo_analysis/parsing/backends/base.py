from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tree_sitter import Tree


@dataclass
class ParseResult:
    tree: Tree
    language: str
    parser_id: str


class ParserBackend(Protocol):
    def parse_file(self, path: Path, source: bytes) -> ParseResult: ...
