#!/usr/bin/env python3
"""Trim a video with ffmpeg by first/last minutes or explicit time range."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Trim input video with ffmpeg. Choose exactly one mode: "
            "--first-minutes, --last-minutes, or --start/--end."
        )
    )
    parser.add_argument("-i", "--input", required=True, help="Input video path")
    parser.add_argument("-o", "--output", required=True, help="Output video path")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "-fc",
        "--first-minutes",
        type=float,
        help="Keep first N minutes",
    )
    mode.add_argument(
        "-lm",
        "--last-minutes",
        type=float,
        help="Keep last N minutes",
    )
    mode.add_argument(
        "--start",
        type=str,
        help="Start timestamp, e.g. 00:10:00 or 615.5 (seconds). Requires --end or --duration.",
    )

    parser.add_argument("--end", type=str, help="End timestamp, e.g. 00:25:00 or 1500")
    parser.add_argument("--duration", type=float, help="Duration in seconds (used with --start)")
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Re-encode for accurate cuts (slower). Default uses stream copy.",
    )

    return parser.parse_args()


def _ensure_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} not found in PATH")


def _ffprobe_duration_seconds(input_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(input_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    return float(payload["format"]["duration"])


def _parse_time_to_seconds(value: str) -> float:
    if ":" not in value:
        return float(value)
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid timestamp format: {value}")
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def _build_trim_range(args: argparse.Namespace, input_path: Path) -> tuple[float, float]:
    if args.first_minutes is not None:
        if args.first_minutes <= 0:
            raise ValueError("--first-minutes must be > 0")
        return 0.0, args.first_minutes * 60.0

    if args.last_minutes is not None:
        if args.last_minutes <= 0:
            raise ValueError("--last-minutes must be > 0")
        duration = _ffprobe_duration_seconds(input_path)
        keep = args.last_minutes * 60.0
        start = max(0.0, duration - keep)
        end = duration
        return start, end

    # --start mode
    start = _parse_time_to_seconds(args.start)
    if start < 0:
        raise ValueError("--start must be >= 0")
    if args.end is None and args.duration is None:
        raise ValueError("When using --start, provide --end or --duration")
    if args.end is not None and args.duration is not None:
        raise ValueError("Use either --end or --duration, not both")

    if args.end is not None:
        end = _parse_time_to_seconds(args.end)
    else:
        if args.duration is None or args.duration <= 0:
            raise ValueError("--duration must be > 0")
        end = start + args.duration

    if end <= start:
        raise ValueError("End time must be greater than start time")

    return start, end


def _run_ffmpeg(input_path: Path, output_path: Path, start: float, end: float, reencode: bool) -> None:
    duration = end - start

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{duration:.3f}",
    ]

    if reencode:
        cmd.extend(["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.extend(["-c", "copy"])

    cmd.append(str(output_path))
    subprocess.run(cmd, check=True)


def main() -> int:
    args = _parse_args()
    _ensure_tools()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input video not found: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start, end = _build_trim_range(args, input_path)
    _run_ffmpeg(input_path, output_path, start=start, end=end, reencode=args.reencode)
    print(f"Trimmed video: {output_path}")
    print(f"Range: start={start:.3f}s end={end:.3f}s duration={end-start:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
