#!/usr/bin/env python3
"""Unified CLI entry point for local/Groq transcription workflows."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
from pathlib import Path

from src.transcription_backends import (
    GroqWhisperBackend,
    LocalWhisperCppBackend,
    TranscribeRequest,
)
from src.whisper_utils import (
    batch_run_whisper_command,
    convert_audio_to_16khz,
    get_model_path,
    get_model_path_by_variant,
    get_whisper_cli_path,
    list_audio_files,
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


def _add_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        choices=["local", "groq"],
        default="local",
        help="Transcription backend to use (default: local).",
    )


def _add_common_transcribe_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--split-on-punc",
        action="store_true",
        help="Split generated SRT lines on punctuation and redistribute timestamps.",
    )


def _add_local_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--local-model",
        type=str,
        choices=[
            "large-v3",
            "v3",
            "large-v3-turbo",
            "turbo",
            "medium",
            "medium.en",
            "small",
            "small.en",
        ],
        default=None,
        help="Local whisper.cpp model variant shortcut.",
    )
    parser.add_argument(
        "--local-model-path",
        type=str,
        default=None,
        help="Absolute/relative path to a local GGML model file.",
    )
    parser.add_argument(
        "--decode-profile",
        type=str,
        choices=["balanced", "accuracy", "legacy"],
        default=None,
        help="Decode preset for local backend: balanced|accuracy|legacy.",
    )


def _add_groq_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--groq-model",
        type=str,
        default=None,
        help="Groq model name (default: whisper-large-v3-turbo).",
    )
    parser.add_argument(
        "--groq-timeout-sec",
        type=int,
        default=None,
        help="Groq request timeout in seconds (default: 300).",
    )


def _resolve_decode_options(decode_profile: str) -> dict[str, int | float | bool]:
    presets: dict[str, dict[str, int | float | bool]] = {
        "balanced": {
            "threads": 8,
            "split_on_word": True,
            "beam_size": 5,
            "best_of": 5,
            "entropy_thold": 2.8,
            "max_context": 64,
            "no_gpu": False,
            "no_fallback": False,
        },
        "accuracy": {
            "threads": 8,
            "split_on_word": True,
            "beam_size": 8,
            "best_of": 8,
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
    return dict(presets[decode_profile])


def _validate_backend_args(args: argparse.Namespace) -> None:
    if args.backend == "groq":
        if args.local_model is not None or args.local_model_path is not None:
            raise ValueError(
                "--local-model/--local-model-path are only valid with --backend local."
            )
        if args.decode_profile is not None:
            raise ValueError("--decode-profile is only valid with --backend local.")
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is required when using --backend groq.")
    elif args.backend == "local":
        if args.groq_model is not None or args.groq_timeout_sec is not None:
            raise ValueError(
                "--groq-model/--groq-timeout-sec are only valid with --backend groq."
            )


def cmd_transcribe(args: argparse.Namespace) -> None:
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _validate_backend_args(args)

    initial_prompt: str | None = None
    if args.prompt_file:
        prompt_file = Path(args.prompt_file).resolve()
        if not prompt_file.is_file():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
        initial_prompt = prompt_file.read_text(encoding="utf-8").strip()
        if not initial_prompt:
            raise ValueError(f"Prompt file is empty: {prompt_file}")

    llm_glossary: str | None = None
    if args.llm_correct and args.glossary_file:
        glossary_path = Path(args.glossary_file).resolve()
        if not glossary_path.is_file():
            raise FileNotFoundError(f"Glossary file not found: {glossary_path}")
        llm_glossary = glossary_path.read_text(encoding="utf-8")

    backend = LocalWhisperCppBackend() if args.backend == "local" else GroqWhisperBackend()

    selected_model_path: str | None = None
    decode_options: dict[str, int | float | bool] | None = None
    groq_model = args.groq_model or "whisper-large-v3-turbo"
    groq_timeout_sec = args.groq_timeout_sec or 300

    if args.backend == "local":
        if args.local_model_path:
            candidate = Path(args.local_model_path).resolve()
            if not candidate.is_file():
                raise FileNotFoundError(f"Model file not found: {candidate}")
            selected_model_path = str(candidate)
        elif args.local_model:
            selected_model_path = str(get_model_path_by_variant(args.local_model))

        decode_profile = args.decode_profile or "balanced"
        decode_options = _resolve_decode_options(decode_profile)

    for audio_file in args.input:
        audio_path = Path(audio_file).resolve()
        if not audio_path.is_file():
            raise FileNotFoundError(f"Input file not found: {audio_path}")

        backend.transcribe(
            TranscribeRequest(
                audio_file=audio_path,
                output_dir=output_dir,
                lang=args.lang,
                initial_prompt=initial_prompt,
                autocorrect=not args.no_autocorrect,
                split_on_punc=args.split_on_punc,
                llm_correct=args.llm_correct,
                llm_model=args.llm_model,
                llm_glossary=llm_glossary,
                local_model_path=selected_model_path,
                decode_options=decode_options,
                groq_model=groq_model,
                groq_timeout_sec=groq_timeout_sec,
            )
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


def cmd_doctor(args: argparse.Namespace) -> None:
    ffmpeg_path = shutil.which("ffmpeg")
    print(f"[doctor] ffmpeg: {ffmpeg_path or 'NOT FOUND'}")

    if args.backend in {"local", "all"}:
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

    if args.backend in {"groq", "all"}:
        print(
            "[doctor] GROQ_API_KEY: "
            + ("SET" if os.environ.get("GROQ_API_KEY") else "NOT SET")
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified transcription workflow CLI (local whisper.cpp + Groq)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe_parser = subparsers.add_parser(
        "transcribe",
        description="Transcribe audio files via local whisper.cpp or Groq backend",
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
        help="Path to a UTF-8 text file used as the initial prompt.",
    )
    transcribe_parser.add_argument(
        "--no-autocorrect",
        action="store_true",
        help="Skip autocorrect post-processing for generated .txt/.srt files.",
    )
    _add_backend_args(transcribe_parser)
    _add_local_backend_args(transcribe_parser)
    _add_groq_backend_args(transcribe_parser)
    _add_common_transcribe_args(transcribe_parser)
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
        description="Convert + transcribe (en/ja) using local backend",
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
        description="Check backend prerequisites (ffmpeg/local/groq)",
    )
    doctor_parser.add_argument(
        "--backend",
        choices=["all", "local", "groq"],
        default="all",
        help="Select which backend checks to run (default: all).",
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
