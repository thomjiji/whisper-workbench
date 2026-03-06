#!/usr/bin/env python3
"""Detect candidate audio segments by RMS dB level using ffmpeg astats metadata."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

PTS_RE = re.compile(r"pts_time:([0-9.]+)")
RMS_RE = re.compile(r"RMS_level=(-inf|[-0-9.]+)")


@dataclass
class Sample:
    start: float
    end: float
    db: float


@dataclass
class Segment:
    start: float
    end: float
    avg_db: float
    peak_db: float
    points: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Detect high/low level audio segments from media using ffmpeg "
            "(based on 1-second RMS windows by default)."
        )
    )
    parser.add_argument("-i", "--input", required=True, help="Input media/audio path")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output report path (.txt). Prints to stdout regardless.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Analysis sample rate (default: 16000)",
    )
    parser.add_argument(
        "--window-sec",
        type=float,
        default=1.0,
        help="RMS analysis window size in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--min-db",
        type=float,
        default=-16.0,
        help="Keep samples with RMS >= this dB value (default: -16.0)",
    )
    parser.add_argument(
        "--max-db",
        type=float,
        help="Keep samples with RMS <= this dB value (optional)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=8.0,
        help="Minimum segment duration in seconds (default: 8.0)",
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=1.0,
        help="Merge nearby segments if gap <= this many seconds (default: 1.0)",
    )
    parser.add_argument(
        "--ffmpeg-bin",
        default="ffmpeg",
        help="ffmpeg executable name/path (default: ffmpeg)",
    )
    return parser


def run_ffmpeg_analysis(
    ffmpeg_bin: str,
    input_path: Path,
    sample_rate: int,
    window_sec: float,
    metadata_path: Path,
) -> None:
    if shutil.which(ffmpeg_bin) is None:
        raise RuntimeError(f"ffmpeg not found: {ffmpeg_bin}")

    samples_per_win = max(int(sample_rate * window_sec), 1)
    filter_str = (
        f"aresample={sample_rate},"
        f"asetnsamples=n={samples_per_win}:p=0,"
        "astats=metadata=1:reset=1,"
        f"ametadata=print:key=lavfi.astats.Overall.RMS_level:file={metadata_path}"
    )
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-af",
        filter_str,
        "-f",
        "null",
        "-",
    ]
    subprocess.run(cmd, check=True)


def parse_samples(metadata_path: Path, window_sec: float) -> list[Sample]:
    samples: list[Sample] = []
    pending_start: float | None = None
    for line in metadata_path.read_text(encoding="utf-8", errors="replace").splitlines():
        pts_match = PTS_RE.search(line)
        if pts_match:
            pending_start = float(pts_match.group(1))
            continue

        rms_match = RMS_RE.search(line)
        if rms_match and pending_start is not None:
            token = rms_match.group(1)
            pending_start, start = None, pending_start
            if token == "-inf":
                continue
            db = float(token)
            samples.append(Sample(start=start, end=start + window_sec, db=db))
    return samples


def in_threshold(sample_db: float, min_db: float | None, max_db: float | None) -> bool:
    if min_db is not None and sample_db < min_db:
        return False
    if max_db is not None and sample_db > max_db:
        return False
    return True


def samples_to_segments(
    samples: list[Sample],
    min_db: float | None,
    max_db: float | None,
    min_duration: float,
    merge_gap: float,
) -> list[Segment]:
    raw: list[Segment] = []
    current: list[Sample] = []

    for sample in samples:
        if in_threshold(sample.db, min_db=min_db, max_db=max_db):
            current.append(sample)
            continue

        if current:
            start = current[0].start
            end = current[-1].end
            if end - start >= min_duration:
                db_vals = [s.db for s in current]
                raw.append(
                    Segment(
                        start=start,
                        end=end,
                        avg_db=sum(db_vals) / len(db_vals),
                        peak_db=max(db_vals),
                        points=len(db_vals),
                    )
                )
            current = []

    if current:
        start = current[0].start
        end = current[-1].end
        if end - start >= min_duration:
            db_vals = [s.db for s in current]
            raw.append(
                Segment(
                    start=start,
                    end=end,
                    avg_db=sum(db_vals) / len(db_vals),
                    peak_db=max(db_vals),
                    points=len(db_vals),
                )
            )

    if not raw:
        return []

    merged: list[Segment] = [raw[0]]
    for seg in raw[1:]:
        prev = merged[-1]
        if seg.start - prev.end <= merge_gap:
            span_points = prev.points + seg.points
            weighted_avg = ((prev.avg_db * prev.points) + (seg.avg_db * seg.points)) / span_points
            merged[-1] = Segment(
                start=prev.start,
                end=seg.end,
                avg_db=weighted_avg,
                peak_db=max(prev.peak_db, seg.peak_db),
                points=span_points,
            )
            continue
        merged.append(seg)
    return merged


def sec_to_hms(sec: float) -> str:
    total = int(sec)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def render_report(segments: list[Segment]) -> str:
    lines = ["#\tstart\tend\tduration_s\tavg_db\tpeak_db"]
    for idx, seg in enumerate(segments, start=1):
        lines.append(
            f"{idx}\t{sec_to_hms(seg.start)}\t{sec_to_hms(seg.end)}\t"
            f"{seg.end - seg.start:.1f}\t{seg.avg_db:.2f}\t{seg.peak_db:.2f}"
        )
    if len(lines) == 1:
        lines.append("(no matching segments)")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if args.min_db is None and args.max_db is None:
        raise ValueError("At least one threshold is required: --min-db and/or --max-db")
    if args.window_sec <= 0:
        raise ValueError("--window-sec must be > 0")
    if args.min_duration < 0:
        raise ValueError("--min-duration must be >= 0")
    if args.merge_gap < 0:
        raise ValueError("--merge-gap must be >= 0")

    with tempfile.NamedTemporaryFile(
        prefix="ffmpeg_rms_", suffix=".txt", delete=False
    ) as temp_file:
        metadata_path = Path(temp_file.name)

    try:
        run_ffmpeg_analysis(
            ffmpeg_bin=args.ffmpeg_bin,
            input_path=input_path,
            sample_rate=args.sample_rate,
            window_sec=args.window_sec,
            metadata_path=metadata_path,
        )
        samples = parse_samples(metadata_path=metadata_path, window_sec=args.window_sec)
    finally:
        metadata_path.unlink(missing_ok=True)

    segments = samples_to_segments(
        samples=samples,
        min_db=args.min_db,
        max_db=args.max_db,
        min_duration=args.min_duration,
        merge_gap=args.merge_gap,
    )
    report = render_report(segments)

    print(report, end="")
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Saved report: {output_path}")


if __name__ == "__main__":
    main()
