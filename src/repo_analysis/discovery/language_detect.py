from __future__ import annotations

from pathlib import Path

_EXTENSION_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rs": "rust",
}


def detect_language(path: Path) -> str | None:
    ext = path.suffix.lower()
    return _EXTENSION_TO_LANG.get(ext)


def tree_sitter_language_name(language: str) -> str:
    """Map logical language id to tree-sitter-language-pack name."""
    if language == "typescript":
        return "typescript"
    if language == "javascript":
        return "javascript"
    if language == "csharp":
        return "csharp"
    return language
