#!/usr/bin/env python3
"""Sync SRT subtitle text lines into a TXT file with count validation."""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

TIMECODE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$"
)


def _extract_srt_text_lines(srt_lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in srt_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isdigit():
            continue
        if TIMECODE_RE.match(stripped):
            continue
        out.append(stripped)
    return out


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sync SRT text lines into TXT. "
            "The script first validates SRT/TXT text-line counts."
        )
    )
    parser.add_argument("--srt", required=True, help="Input .srt file path")
    parser.add_argument("--txt", required=True, help="Input .txt file path to compare/sync")
    parser.add_argument(
        "-o",
        "--output",
        help="Output .txt path (default: overwrite --txt file in place)",
    )
    args = parser.parse_args()

    srt_path = Path(args.srt).expanduser().resolve()
    txt_path = Path(args.txt).expanduser().resolve()
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")
    if not txt_path.is_file():
        raise FileNotFoundError(f"TXT file not found: {txt_path}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else txt_path
    )

    srt_raw_lines = srt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    txt_raw_lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()

    srt_text_lines = _extract_srt_text_lines(srt_raw_lines)
    txt_text_lines = [line.strip() for line in txt_raw_lines if line.strip()]

    if len(srt_text_lines) != len(txt_text_lines):
        raise ValueError(_build_count_mismatch_message(srt_text_lines, txt_text_lines))

    output_path.write_text(
        "\n".join(srt_text_lines) + ("\n" if srt_text_lines else ""),
        encoding="utf-8",
    )
    print(f"Synced SRT -> TXT successfully: {len(srt_text_lines)} lines written to {output_path}")


if __name__ == "__main__":
    main()
