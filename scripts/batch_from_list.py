#!/usr/bin/env python3
"""Batch-analyze repositories listed in a text file (one Git URL per line).

Equivalent to: python -m repo_analysis batch-from-list <file> [options]

Examples::

  python scripts/batch_from_list.py repos.txt --dry-run
  python scripts/batch_from_list.py repos.txt --continue-on-error
"""
from __future__ import annotations

import sys

from repo_analysis.cli.main import app


def main() -> None:
    sys.argv = ["repo_analysis", "batch-from-list", *sys.argv[1:]]
    app()


if __name__ == "__main__":
    main()
