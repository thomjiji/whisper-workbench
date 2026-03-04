#!/usr/bin/env python3
"""Trim silence from an audio file using ffmpeg silenceremove."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_nosilence{input_path.suffix}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trim silence from an audio file with ffmpeg."
    )
    parser.add_argument("-i", "--input", required=True, help="Input audio file path")
    parser.add_argument(
        "-o",
        "--output",
        help="Output audio file path (default: <input_stem>_nosilence.<ext>)",
    )
    parser.add_argument(
        "--start-duration",
        type=float,
        default=0.3,
        help="Minimum non-silent duration at start to keep (default: 0.3)",
    )
    parser.add_argument(
        "--stop-duration",
        type=float,
        default=0.5,
        help="Minimum silence duration to trim in body/tail (default: 0.5)",
    )
    parser.add_argument(
        "--threshold-db",
        type=float,
        default=-40.0,
        help="Silence threshold in dB (default: -40.0)",
    )
    parser.add_argument(
        "--audio-codec",
        default="libmp3lame",
        help="Output audio codec (default: libmp3lame)",
    )
    parser.add_argument(
        "--audio-bitrate",
        default="128k",
        help="Output audio bitrate (default: 128k)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found in PATH")

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input audio file not found: {input_path}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_output_path(input_path)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    threshold = f"{args.threshold_db:g}dB"
    filter_str = (
        "silenceremove="
        f"start_periods=1:start_duration={args.start_duration:g}:start_threshold={threshold}:"
        f"stop_periods=-1:stop_duration={args.stop_duration:g}:stop_threshold={threshold}"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-af",
        filter_str,
        "-c:a",
        args.audio_codec,
        "-b:a",
        args.audio_bitrate,
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
