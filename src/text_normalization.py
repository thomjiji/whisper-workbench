"""Deterministic text normalization helpers."""

from __future__ import annotations

import re
from pathlib import Path

_YEAR_SUFFIX_PATTERN = re.compile(
    r"(?<!\d)(?P<yy>\d{2})(?P<suffix>年(?:初|中|末|底|前|后)?)"
)


def _expand_two_digit_year(two_digit_year: str) -> str:
    value = int(two_digit_year)
    century = 2000 if value <= 29 else 1900
    return str(century + value)


def normalize_year_expressions(text: str) -> str:
    """Expand high-confidence Arabic numeral year abbreviations."""

    def replace(match: re.Match[str]) -> str:
        return f"{_expand_two_digit_year(match.group('yy'))}{match.group('suffix')}"

    return _YEAR_SUFFIX_PATTERN.sub(replace, text)


def normalize_year_expressions_in_txt_file(file_path: Path) -> bool:
    """Normalize year expressions in a TXT file in place."""
    original = file_path.read_text(encoding="utf-8")
    normalized = "\n".join(
        normalize_year_expressions(line) for line in original.splitlines()
    )
    if original.endswith("\n"):
        normalized += "\n"
    if normalized == original:
        return False
    file_path.write_text(normalized, encoding="utf-8")
    return True
