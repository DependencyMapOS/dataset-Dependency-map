from __future__ import annotations

from pathlib import Path

from repo_analysis.export.schema_version import PARSER_ID_PREFIX
from repo_analysis.parsing.backends.base import ParseResult
from repo_analysis.parsing.registry import get_parser_for_language


class TreeSitterBackend:
    def __init__(self, language: str) -> None:
        self._language = language
        self._parser = get_parser_for_language(language)
        self.parser_id = f"{PARSER_ID_PREFIX}:{language}"

    def parse_file(self, path: Path, source: bytes) -> ParseResult:
        tree = self._parser.parse(source)
        return ParseResult(tree=tree, language=self._language, parser_id=self.parser_id)
