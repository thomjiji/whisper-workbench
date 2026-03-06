#!/usr/bin/env python3
"""Bidirectional sync between SRT subtitle text lines and TXT lines."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
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


def _collect_srt_text_line_indexes(srt_lines: list[str]) -> list[int]:
    return [idx for idx, line in enumerate(srt_lines) if _is_srt_text_line(line)]


def _collect_txt_text_lines(txt_lines: list[str]) -> list[str]:
    return [line.strip() for line in txt_lines if line.strip()]


def _line_preview(lines: list[str], start: int, end: int, limit: int = 2) -> str:
    if start >= end:
        return "<none>"
    return " | ".join(lines[start : min(end, start + limit)])


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
        )
    return details


def _confirm_continue(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _sync_srt_to_txt(srt_path: Path, output_txt_path: Path) -> int:
    srt_lines = srt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    srt_indexes = _collect_srt_text_line_indexes(srt_lines)
    srt_text_lines = [srt_lines[idx].strip() for idx in srt_indexes]
    output_txt_path.write_text(
        "\n".join(srt_text_lines) + ("\n" if srt_text_lines else ""),
        encoding="utf-8",
    )
    return len(srt_text_lines)


def _sync_txt_to_srt(srt_path: Path, txt_path: Path, output_srt_path: Path, force: bool) -> int:
    srt_lines = srt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    txt_lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    srt_indexes = _collect_srt_text_line_indexes(srt_lines)
    txt_text_lines = _collect_txt_text_lines(txt_lines)

    if len(srt_indexes) != len(txt_text_lines):
        srt_text_lines = [srt_lines[idx].strip() for idx in srt_indexes]
        mismatch = _build_count_mismatch_message(srt_text_lines, txt_text_lines)
        if not force:
            print(mismatch)
            if not _confirm_continue("Line count mismatch detected. Continue with best-effort sync?"):
                raise RuntimeError(
                    "Aborted due to line-count mismatch. Use --force to continue non-interactively."
                )
        else:
            print(mismatch)
            print("Proceeding with --force (best-effort sync).")

    merged = list(srt_lines)
    replaced = min(len(srt_indexes), len(txt_text_lines))
    for i in range(replaced):
        merged[srt_indexes[i]] = txt_text_lines[i]

    output_srt_path.write_text(
        "\n".join(merged) + ("\n" if srt_path.read_text(encoding="utf-8", errors="replace").endswith("\n") else ""),
        encoding="utf-8",
    )
    return replaced


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bidirectional sync between subtitle SRT text lines and TXT lines. "
            "On line-count mismatch, asks before proceeding unless --force is set."
        )
    )
    parser.add_argument(
        "--direction",
        required=True,
        choices=["srt-to-txt", "txt-to-srt"],
        help="Sync direction.",
    )
    parser.add_argument("--srt", required=True, help="Input .srt file path")
    parser.add_argument("--txt", required=True, help="Input .txt file path")
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Optional output path. "
            "Defaults to overwriting destination in selected direction "
            "(TXT for srt-to-txt, SRT for txt-to-srt)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed on line-count mismatch without confirmation (best-effort sync).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    srt_path = Path(args.srt).expanduser().resolve()
    txt_path = Path(args.txt).expanduser().resolve()
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    if args.direction == "srt-to-txt":
        output_txt_path = Path(args.output).expanduser().resolve() if args.output else txt_path
        output_txt_path.parent.mkdir(parents=True, exist_ok=True)
        count = _sync_srt_to_txt(srt_path, output_txt_path)
        print(f"Synced SRT -> TXT: {count} lines written to {output_txt_path}")
        return

    if not txt_path.is_file():
        raise FileNotFoundError(f"TXT file not found: {txt_path}")

    output_srt_path = Path(args.output).expanduser().resolve() if args.output else srt_path
    count = _sync_txt_to_srt(srt_path, txt_path, output_srt_path, force=args.force)
    print(f"Synced TXT -> SRT: {count} lines written to {output_srt_path}")


if __name__ == "__main__":
    main()
