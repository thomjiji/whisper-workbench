#!/usr/bin/env python3
"""Unified CLI entry point for whisper.cpp transcription workflows."""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

from src.whisper_utils import (
    batch_run_whisper_command,
    convert_audio_to_16khz,
    get_model_path,
    get_model_path_by_variant,
    get_whisper_cli_path,
    list_audio_files,
    run_whisper_command,
)

LOG = logging.getLogger(__name__)


def _add_llm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--llm-correct",
        action="store_true",
        help="Run Codex CLI post-correction to fix homophones and proper nouns.",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="haiku",
        help="Claude model alias or full ID for LLM correction (default: haiku).",
    )
    parser.add_argument(
        "--glossary-file",
        type=str,
        help="Path to a UTF-8 file with one proper noun per line for LLM correction.",
    )


def _add_decode_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--decode-profile",
        type=str,
        choices=["balanced", "accuracy", "legacy"],
        default="balanced",
        help="Decode preset: balanced|accuracy|legacy(backward-compatible old params).",
    )
    parser.add_argument(
        "--split-on-punc",
        action="store_true",
        help="Split generated SRT lines on punctuation and redistribute timestamps.",
    )


def _resolve_decode_options(args: argparse.Namespace) -> dict[str, int | float | bool]:
    presets: dict[str, dict[str, int | float | bool]] = {
        "balanced": {
            "threads": 8,
            "split_on_word": True,
            "beam_size": 5,
            "best_of": 5,
            "entropy_thold": 2.8,
            # Borrow anti-repetition behavior from legacy profile.
            "max_context": 64,
            # "max_len": 0,
            "no_gpu": False,
            "no_fallback": False,
        },
        "accuracy": {
            "threads": 8,
            "split_on_word": True,
            "beam_size": 8,
            "best_of": 8,
            # Keep accuracy-oriented decoding, but reduce long-context repetition.
            "entropy_thold": 2.6,
            "max_context": 96,
            "max_len": 80,
            "no_gpu": False,
            "no_fallback": False,
        },
        "legacy": {
            "threads": 8,
            "split_on_word": True,
            "beam_size": 5,
            "best_of": 5,
            "entropy_thold": 2.8,
            "max_context": 64,
            "no_gpu": False,
            "no_fallback": False,
        },
    }
    return dict(presets[args.decode_profile])


def cmd_transcribe(args: argparse.Namespace) -> None:
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    decode_options = _resolve_decode_options(args)
    initial_prompt: str | None = None

    if args.prompt_file:
        prompt_file = Path(args.prompt_file).resolve()
        if not prompt_file.is_file():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
        initial_prompt = prompt_file.read_text(encoding="utf-8").strip()
        if not initial_prompt:
            raise ValueError(f"Prompt file is empty: {prompt_file}")

    selected_model_path: str | None = None
    if args.model_path:
        candidate = Path(args.model_path).resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Model file not found: {candidate}")
        selected_model_path = str(candidate)
    elif args.model:
        selected_model_path = str(get_model_path_by_variant(args.model))

    llm_glossary: str | None = None
    if args.llm_correct and args.glossary_file:
        glossary_path = Path(args.glossary_file).resolve()
        if not glossary_path.is_file():
            raise FileNotFoundError(f"Glossary file not found: {glossary_path}")
        llm_glossary = glossary_path.read_text(encoding="utf-8")

    for audio_file in args.input:
        audio_path = Path(audio_file).resolve()
        run_whisper_command(
            str(audio_path),
            args.lang,
            str(output_dir),
            initial_prompt=initial_prompt,
            autocorrect=not args.no_autocorrect,
            model_path=selected_model_path,
            split_on_punc=args.split_on_punc,
            llm_correct=args.llm_correct,
            llm_model=args.llm_model,
            llm_glossary=llm_glossary,
            **decode_options,
        )


def cmd_convert(args: argparse.Namespace) -> None:
    convert_audio_to_16khz(Path(args.dir))


def cmd_batch(args: argparse.Namespace) -> None:
    base_dir = Path(args.base_dir).resolve()
    episode_title = args.episode

    base_output_dir = base_dir / "output" / episode_title
    base_audio_dir = base_dir / "audio" / episode_title

    convert_audio_to_16khz(base_audio_dir)
    audio_file_paths = list_audio_files(base_audio_dir)
    if not audio_file_paths:
        raise FileNotFoundError(f"No .wav files found in: {base_audio_dir}")
    batch_run_whisper_command(audio_file_paths, base_output_dir)


def cmd_doctor(_args: argparse.Namespace) -> None:
    ffmpeg_path = shutil.which("ffmpeg")
    print(f"[doctor] ffmpeg: {ffmpeg_path or 'NOT FOUND'}")

    try:
        whisper_cli_path = get_whisper_cli_path()
        print(f"[doctor] whisper-cli: {whisper_cli_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"[doctor] whisper-cli: ERROR ({exc})")

    try:
        model_path = get_model_path()
        print(f"[doctor] model: {model_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"[doctor] model: ERROR ({exc})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified whisper.cpp transcription workflow CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe_parser = subparsers.add_parser(
        "transcribe", description="Run whisper.cpp on audio files"
    )
    transcribe_parser.add_argument(
        "-i",
        "--input",
        type=str,
        nargs="+",
        required=True,
        help="Path to audio file(s) to process.",
    )
    transcribe_parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Output directory for transcription files.",
    )
    transcribe_parser.add_argument(
        "-l",
        "--lang",
        type=str,
        default="en",
        help="Language code (default: en).",
    )
    transcribe_parser.add_argument(
        "--prompt-file",
        type=str,
        help="Path to a UTF-8 text file used as the whisper initial prompt.",
    )
    transcribe_parser.add_argument(
        "--no-autocorrect",
        action="store_true",
        help="Skip autocorrect post-processing for generated .txt/.srt files.",
    )
    transcribe_parser.add_argument(
        "--model",
        type=str,
        choices=["large-v3", "v3", "large-v3-turbo", "turbo"],
        help="Model variant shortcut (default uses WHISPER_MODEL_PATH or large-v3).",
    )
    transcribe_parser.add_argument(
        "--model-path",
        type=str,
        help="Absolute/relative path to a GGML model file (overrides --model).",
    )
    _add_decode_args(transcribe_parser)
    _add_llm_args(transcribe_parser)
    transcribe_parser.set_defaults(func=cmd_transcribe)

    convert_parser = subparsers.add_parser(
        "convert", description="Batch convert .wav files to 16khz mono PCM"
    )
    convert_parser.add_argument(
        "--dir",
        type=str,
        required=True,
        help="Directory containing .wav files",
    )
    convert_parser.set_defaults(func=cmd_convert)

    batch_parser = subparsers.add_parser(
        "batch",
        description="Convert + transcribe (en/ja)",
    )
    batch_parser.add_argument(
        "-e", "--episode", type=str, required=True, help="Episode title"
    )
    batch_parser.add_argument(
        "-d",
        "--base-dir",
        type=str,
        required=True,
        help="Base directory containing audio/ and output/ subdirectories",
    )
    batch_parser.set_defaults(func=cmd_batch)

    doctor_parser = subparsers.add_parser(
        "doctor",
        description="Check required binaries and model path resolution",
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s %(levelname)s %(asctime)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
