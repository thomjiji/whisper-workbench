#!/usr/bin/env python3
"""Extract subtitle text lines from an SRT file into a plain TXT file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TIMECODE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$"
)


def extract_text_lines(srt_path: Path) -> list[str]:
    lines = srt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isdigit():
            continue
        if TIMECODE_RE.match(stripped):
            continue
        out.append(stripped)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract non-timecode subtitle text lines from an SRT file."
    )
    parser.add_argument("-i", "--input", required=True, help="Input .srt file path")
    parser.add_argument(
        "-o",
        "--output",
        help="Output .txt path (default: <input_stem>_llm_lines.txt)",
    )
    args = parser.parse_args()

    srt_path = Path(args.input).expanduser().resolve()
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else srt_path.with_name(f"{srt_path.stem}_llm_lines.txt")
    )

    lines = extract_text_lines(srt_path)
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"Extracted {len(lines)} text lines to: {output_path}")


if __name__ == "__main__":
    main()
