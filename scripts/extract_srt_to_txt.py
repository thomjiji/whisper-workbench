#!/usr/bin/env python3
"""Extract subtitle text content lines from SRT into TXT (one subtitle block per line)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TIMECODE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$"
)


def extract_text_lines_from_srt(srt_path: Path) -> list[str]:
    """Return subtitle text lines from SRT as one merged line per subtitle block."""
    raw = srt_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return []

    blocks = re.split(r"\n\s*\n", raw)
    out: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        text_parts: list[str] = []
        for line in lines:
            if line.isdigit():
                continue
            if TIMECODE_RE.match(line):
                continue
            text_parts.append(line)

        if text_parts:
            out.append(" ".join(text_parts))

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract subtitle text lines from an SRT file to a TXT file."
    )
    parser.add_argument("--srt", required=True, help="Input .srt file path")
    parser.add_argument(
        "--txt",
        help="Output .txt file path (default: same path/stem as --srt with .txt suffix)",
    )
    args = parser.parse_args()

    srt_path = Path(args.srt).expanduser().resolve()
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    txt_path = (
        Path(args.txt).expanduser().resolve()
        if args.txt
        else srt_path.with_suffix(".txt")
    )

    lines = extract_text_lines_from_srt(srt_path)
    txt_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"Extracted {len(lines)} subtitle lines to: {txt_path}")


if __name__ == "__main__":
    main()
