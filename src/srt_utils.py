"""SRT/TXT parsing, manipulation, and segment writing helpers."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


def _parse_srt_time_to_ms(value: str) -> int:
    hhmmss, ms_part = value.split(",")
    hh, mm, ss = hhmmss.split(":")
    return (int(hh) * 3600 + int(mm) * 60 + int(ss)) * 1000 + int(ms_part)


def _format_ms_to_srt(ms: int) -> str:
    ms = max(ms, 0)
    hh = ms // 3_600_000
    ms %= 3_600_000
    mm = ms // 60_000
    ms %= 60_000
    ss = ms // 1_000
    ms %= 1_000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _split_text_on_punctuation(text: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for i, ch in enumerate(text):
        current += ch

        should_split = False
        prev_ch = text[i - 1] if i > 0 else ""
        next_ch = text[i + 1] if i + 1 < len(text) else ""

        if ch in "，。！？；：":
            should_split = True
        elif ch in "!?;:":
            should_split = True
        elif ch == ",":
            # Keep numeric groups intact: 1,000 / 2024,12
            should_split = not (prev_ch.isdigit() and next_ch.isdigit())
        elif ch == ".":
            # Do not split decimals or dot-connected tokens: 1.0 / e.g. / U.S.
            is_decimal = prev_ch.isdigit() and next_ch.isdigit()
            is_dot_token = prev_ch.isalpha() and next_ch.isalpha()
            should_split = not (is_decimal or is_dot_token)

        if should_split:
            piece = current.strip()
            if piece:
                chunks.append(piece)
            current = ""
    tail = current.strip()
    if tail:
        chunks.append(tail)
    return chunks if chunks else [text.strip()]


def _strip_trailing_punctuation(text: str) -> str:
    """Remove trailing punctuation marks from a subtitle line."""
    return re.sub(r"[，。！？；：,.!?;:]+$", "", text).strip()


def _rewrite_txt_from_lines(txt_path: Path, lines: list[str]) -> None:
    """Rewrite TXT as one line per subtitle segment to keep 1:1 mapping with SRT."""
    if not lines:
        return
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sync_srt_text_from_txt(srt_path: Path, txt_path: Path) -> None:
    """Overwrite SRT text lines from TXT lines with strict 1:1 alignment checks."""
    if not srt_path.exists() or not txt_path.exists():
        raise FileNotFoundError(f"SRT/TXT not found for sync: {srt_path} {txt_path}")

    txt_lines = [
        line.strip()
        for line in txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    raw = srt_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return

    blocks = raw.split("\n\n")
    valid_block_indices: list[int] = []
    for i, block in enumerate(blocks):
        block_lines = [line for line in block.splitlines() if line.strip()]
        if len(block_lines) >= 3 and " --> " in block_lines[1]:
            valid_block_indices.append(i)

    if len(txt_lines) != len(valid_block_indices):
        srt_text_lines = _extract_srt_text_lines(srt_path)
        detail = _format_line_mismatch_detail(srt_text_lines=srt_text_lines, txt_lines=txt_lines)
        raise RuntimeError(
            "Cannot sync TXT -> SRT: line count mismatch "
            f"(txt={len(txt_lines)} srt={len(valid_block_indices)}). {detail}"
        )

    for idx, block_idx in enumerate(valid_block_indices):
        block_lines = [line for line in blocks[block_idx].splitlines() if line.strip()]
        blocks[block_idx] = "\n".join(block_lines[:2] + [txt_lines[idx]])

    srt_path.write_text("\n\n".join(blocks), encoding="utf-8")


def _extract_srt_text_lines(srt_path: Path) -> list[str]:
    raw = srt_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return []
    lines: list[str] = []
    blocks = raw.split("\n\n")
    for block in blocks:
        block_lines = [line for line in block.splitlines() if line.strip()]
        if len(block_lines) >= 3 and " --> " in block_lines[1]:
            lines.append(" ".join(block_lines[2:]).strip())
    return lines


def _extract_txt_text_lines(txt_path: Path) -> list[str]:
    return [
        line.strip()
        for line in txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def _format_line_mismatch_detail(srt_text_lines: list[str], txt_lines: list[str]) -> str:
    first_mismatch = min(len(srt_text_lines), len(txt_lines))
    for idx in range(first_mismatch):
        if srt_text_lines[idx] != txt_lines[idx]:
            first_mismatch = idx
            break
    line_no = first_mismatch + 1
    srt_preview = srt_text_lines[first_mismatch] if first_mismatch < len(srt_text_lines) else "<missing>"
    txt_preview = txt_lines[first_mismatch] if first_mismatch < len(txt_lines) else "<missing>"
    return f"first mismatch line={line_no} srt='{srt_preview}' txt='{txt_preview}'"


def _validate_srt_txt_line_alignment(srt_path: Path, txt_path: Path) -> None:
    srt_lines = _extract_srt_text_lines(srt_path)
    txt_lines = _extract_txt_text_lines(txt_path)
    if len(srt_lines) != len(txt_lines):
        detail = _format_line_mismatch_detail(srt_text_lines=srt_lines, txt_lines=txt_lines)
        raise RuntimeError(
            "SRT/TXT line count mismatch before postprocess step: "
            f"srt={len(srt_lines)} txt={len(txt_lines)}. "
            f"{detail}. Please sync files first, or regenerate a consistent pair."
        )


def _split_srt_on_punctuation(srt_path: Path) -> list[str]:
    """Split each SRT segment by punctuation and redistribute timestamps."""
    if not srt_path.exists():
        return []

    raw = srt_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return []

    blocks = raw.split("\n\n")
    out_entries: list[tuple[str, str]] = []

    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            continue

        timing_line = lines[1].strip()
        if " --> " not in timing_line:
            continue
        start_str, end_str = timing_line.split(" --> ")
        start_ms = _parse_srt_time_to_ms(start_str)
        end_ms = _parse_srt_time_to_ms(end_str)
        if end_ms <= start_ms:
            continue

        text = " ".join(line.strip() for line in lines[2:]).strip()
        if not text:
            continue

        raw_pieces = _split_text_on_punctuation(text)
        pieces = [p for p in (_strip_trailing_punctuation(x) for x in raw_pieces) if p]
        if len(pieces) == 1:
            single = pieces[0]
            if single:
                out_entries.append((timing_line, single))
            continue

        weights = [max(1, len(piece.replace(" ", ""))) for piece in pieces]
        total = sum(weights)
        span = end_ms - start_ms
        cumulative = 0
        for i, piece in enumerate(pieces):
            piece_start = start_ms + (span * cumulative) // total
            cumulative += weights[i]
            piece_end = start_ms + (span * cumulative) // total
            if i == len(pieces) - 1:
                piece_end = end_ms
            if piece_end <= piece_start:
                continue
            out_entries.append(
                (
                    f"{_format_ms_to_srt(piece_start)} --> {_format_ms_to_srt(piece_end)}",
                    piece,
                )
            )

    # Merge adjacent duplicate text entries when they overlap/touch.
    deduped: list[tuple[str, str]] = []
    for timing, text in out_entries:
        if not deduped:
            deduped.append((timing, text))
            continue

        prev_timing, prev_text = deduped[-1]
        prev_start_s, prev_end_s = prev_timing.split(" --> ")
        cur_start_s, cur_end_s = timing.split(" --> ")
        prev_end_ms = _parse_srt_time_to_ms(prev_end_s)
        cur_start_ms = _parse_srt_time_to_ms(cur_start_s)
        cur_end_ms = _parse_srt_time_to_ms(cur_end_s)

        if prev_text == text and cur_start_ms <= prev_end_ms + 80:
            merged_timing = f"{prev_start_s} --> {_format_ms_to_srt(max(prev_end_ms, cur_end_ms))}"
            deduped[-1] = (merged_timing, prev_text)
        else:
            deduped.append((timing, text))

    rendered: list[str] = []
    for idx, (timing, text) in enumerate(deduped, start=1):
        rendered.append(str(idx))
        rendered.append(timing)
        rendered.append(text)
        rendered.append("")

    if rendered:
        srt_path.write_text("\n".join(rendered), encoding="utf-8")
    return [text for _, text in deduped]


def _normalize_segment_text(segment: dict[str, Any]) -> str:
    text = str(segment.get("text", "")).strip()
    return re.sub(r"\s+", " ", text)


def write_srt_txt_from_segments(output_base: Path, segments: list[dict[str, Any]]) -> None:
    """Write SRT and TXT files from transcription segments."""
    if not segments:
        raise ValueError("No transcription segments available to render outputs.")

    srt_lines: list[str] = []
    txt_lines: list[str] = []
    segment_index = 1

    for segment in segments:
        text = _normalize_segment_text(segment)
        if not text:
            continue

        start_s = float(segment.get("start", 0.0))
        end_s = float(segment.get("end", start_s))
        start_ms = max(0, int(round(start_s * 1000)))
        end_ms = max(start_ms + 1, int(round(end_s * 1000)))

        srt_lines.append(str(segment_index))
        srt_lines.append(f"{_format_ms_to_srt(start_ms)} --> {_format_ms_to_srt(end_ms)}")
        srt_lines.append(text)
        srt_lines.append("")
        txt_lines.append(text)
        segment_index += 1

    if not txt_lines:
        raise ValueError("Transcription segments were present but contained no usable text.")

    output_base.with_suffix(".srt").write_text("\n".join(srt_lines), encoding="utf-8")
    output_base.with_suffix(".txt").write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
