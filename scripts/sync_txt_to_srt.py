#!/usr/bin/env python3
"""Sync corrected TXT lines back into SRT subtitle text lines."""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

TIMECODE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$"
)


def _is_srt_text_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.isdigit():
        return False
    if TIMECODE_RE.match(stripped):
        return False
    return True


def collect_srt_text_line_indexes(srt_lines: list[str]) -> list[int]:
    return [idx for idx, line in enumerate(srt_lines) if _is_srt_text_line(line)]


def collect_txt_text_lines(txt_lines: list[str]) -> list[str]:
    return [line.strip() for line in txt_lines if line.strip()]


def _line_preview(lines: list[str], start: int, end: int, limit: int = 2) -> str:
    if start >= end:
        return "<none>"
    preview = lines[start : min(end, start + limit)]
    return " | ".join(preview)


def _build_count_mismatch_message(
    srt_text_lines: list[str], txt_text_lines: list[str]
) -> str:
    matcher = difflib.SequenceMatcher(a=srt_text_lines, b=txt_text_lines, autojunk=False)
    details = (
        "Line count mismatch between SRT/TXT text content: "
        f"srt={len(srt_text_lines)} txt={len(txt_text_lines)}."
    )
    non_equal_ops = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    chosen = next((op for op in non_equal_ops if op[0] != "replace"), None)
    if chosen is None and non_equal_ops:
        chosen = non_equal_ops[0]
    if chosen is not None:
        tag, i1, i2, j1, j2 = chosen
        details += (
            f"\nFirst mismatch block ({tag}):"
            f"\n- srt lines {i1 + 1}-{i2}: {_line_preview(srt_text_lines, i1, i2)}"
            f"\n- txt lines {j1 + 1}-{j2}: {_line_preview(txt_text_lines, j1, j2)}"
            "\nAborting without writing output."
        )
        return details
    details += "\nAborting without writing output."
    return details


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sync corrected TXT lines into SRT subtitle text lines. "
            "The script first validates line counts."
        )
    )
    parser.add_argument("--srt", required=True, help="Input .srt file path")
    parser.add_argument("--txt", required=True, help="Input corrected .txt file path")
    parser.add_argument(
        "-o",
        "--output",
        help="Output .srt path (default: overwrite --srt file in place)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    srt_path = Path(args.srt).expanduser().resolve()
    txt_path = Path(args.txt).expanduser().resolve()
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")
    if not txt_path.is_file():
        raise FileNotFoundError(f"TXT file not found: {txt_path}")

    output_path = (
        Path(args.output).expanduser().resolve() if args.output else srt_path
    )

    srt_lines = srt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    txt_lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()

    srt_indexes = collect_srt_text_line_indexes(srt_lines)
    txt_text_lines = collect_txt_text_lines(txt_lines)

    if len(srt_indexes) != len(txt_text_lines):
        srt_text_lines = [srt_lines[idx].strip() for idx in srt_indexes]
        raise ValueError(_build_count_mismatch_message(srt_text_lines, txt_text_lines))

    merged = list(srt_lines)
    for i, srt_idx in enumerate(srt_indexes):
        merged[srt_idx] = txt_text_lines[i]

    rendered = "\n".join(merged)
    if srt_path.read_text(encoding="utf-8", errors="replace").endswith("\n"):
        rendered += "\n"
    output_path.write_text(rendered, encoding="utf-8")

    print(
        "Synced TXT -> SRT successfully: "
        f"{len(txt_text_lines)} lines written to {output_path}"
    )


if __name__ == "__main__":
    main()
