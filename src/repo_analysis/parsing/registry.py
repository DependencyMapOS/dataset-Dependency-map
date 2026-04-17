from __future__ import annotations

from functools import lru_cache

from tree_sitter import Parser

from repo_analysis.discovery.language_detect import tree_sitter_language_name


@lru_cache(maxsize=32)
def get_parser_for_language(language: str) -> Parser:
    """Return a tree-sitter Parser for the logical language id."""
    from tree_sitter_language_pack import get_parser as language_pack_get_parser

    ts_name = tree_sitter_language_name(language)
    return language_pack_get_parser(ts_name)  # type: ignore[arg-type]


def supported_language(language: str) -> bool:
    try:
        get_parser_for_language(language)
        return True
    except Exception:
        return False
