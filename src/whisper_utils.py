"""Shared helpers for whisper.cpp transcription workflows."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

LOG = logging.getLogger(__name__)


def get_whisper_cli_path() -> Path:
    """Get path to whisper-cli binary from env or default."""
    whisper_cpp_dir = os.environ.get(
        "WHISPER_CPP_DIR",
        Path(__file__).resolve().parent.parent / "vendor" / "whisper.cpp",
    )
    return Path(whisper_cpp_dir) / "build" / "bin" / "whisper-cli"


def get_model_path() -> Path:
    """Get path to whisper model from env or default."""
    model_path = os.environ.get("WHISPER_MODEL_PATH")
    if model_path:
        return Path(model_path)
    whisper_cpp_dir = os.environ.get(
        "WHISPER_CPP_DIR",
        Path(__file__).resolve().parent.parent / "vendor" / "whisper.cpp",
    )
    return Path(whisper_cpp_dir) / "models" / "ggml-large-v3.bin"


def get_model_path_by_variant(model_variant: str) -> Path:
    """Resolve model path by variant using WHISPER_CPP_DIR or default vendor path."""
    whisper_cpp_dir = os.environ.get(
        "WHISPER_CPP_DIR",
        Path(__file__).resolve().parent.parent / "vendor" / "whisper.cpp",
    )
    normalized = model_variant.strip().lower()
    if normalized in {"large-v3", "v3"}:
        model_name = "ggml-large-v3.bin"
    elif normalized in {"large-v3-turbo", "turbo"}:
        model_name = "ggml-large-v3-turbo.bin"
    else:
        raise ValueError(
            f"Unsupported model variant: {model_variant}. "
            "Use large-v3/v3 or large-v3-turbo/turbo."
        )
    return Path(whisper_cpp_dir) / "models" / model_name


def remove_16khz_suffix(audio_file: str) -> str:
    """Extract the file name and remove the '_16khz' suffix."""
    base_file = os.path.splitext(audio_file)[0]
    file_name = os.path.basename(base_file)
    return file_name.replace("_16khz", "")


def _convert_to_temp_16khz_wav(input_file: Path) -> Path:
    """Convert an input media file to a temporary 16khz mono WAV file."""
    fd, temp_path = tempfile.mkstemp(suffix="_16khz.wav")
    os.close(fd)
    temp_wav_path = Path(temp_path)
    temp_wav_path.unlink(missing_ok=True)

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(input_file),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(temp_wav_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if not temp_wav_path.exists() or temp_wav_path.stat().st_size == 0:
            raise RuntimeError(
                f"ffmpeg reported success but produced empty wav: {temp_wav_path}"
            )
    except subprocess.CalledProcessError as exc:
        if temp_wav_path.exists():
            temp_wav_path.unlink()
        LOG.error("Failed to convert %s to wav: %s", input_file, exc.stderr.strip())
        raise
    except RuntimeError:
        if temp_wav_path.exists():
            temp_wav_path.unlink()
        LOG.error(
            "Failed to convert %s to wav: %s",
            input_file,
            (result.stderr.strip() if "result" in locals() else "unknown ffmpeg error"),
        )
        raise

    return temp_wav_path


def _run_autocorrect_python_api(file_path: Path) -> bool:
    """Attempt autocorrect via autocorrect-py Python API."""
    try:
        import autocorrect_py  # type: ignore[import]
    except ImportError:
        return False

    original = file_path.read_text(encoding="utf-8")
    corrected = autocorrect_py.format(original)
    file_path.write_text(corrected, encoding="utf-8")
    LOG.info("Applied autocorrect via autocorrect_py.format: %s", file_path)
    return True


def _run_autocorrect_cli(file_path: Path) -> bool:
    """Attempt autocorrect via CLI command names and argument conventions."""
    command_variants = [
        ["autocorrect-py", str(file_path)],
        ["autocorrect-py", "--in-place", str(file_path)],
        ["autocorrect-py", "-i", str(file_path)],
        ["autocorrect_py", str(file_path)],
        ["autocorrect", str(file_path)],
    ]

    for cmd in command_variants:
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            LOG.info("Applied autocorrect via CLI: %s", file_path)
            return True
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError as exc:
            LOG.debug("Autocorrect CLI variant failed (%s): %s", cmd, exc.stderr)
            continue

    return False


def autocorrect_file_in_place(file_path: Path) -> None:
    """Run autocorrect in-place for a single file if tooling is available."""
    if not file_path.exists():
        LOG.warning("Autocorrect skipped; output file not found: %s", file_path)
        return

    if _run_autocorrect_python_api(file_path):
        return

    if _run_autocorrect_cli(file_path):
        return

    LOG.warning(
        "Autocorrect requested but no supported API/CLI was available for: %s",
        file_path,
    )


def convert_audio_to_16khz(audio_path: Path) -> None:
    """Convert all .wav files in directory to 16khz sampling rate using ffmpeg."""
    audio_directory = audio_path.resolve()

    wav_files = [
        f
        for f in os.listdir(audio_directory)
        if f.endswith(".wav") and "16khz" not in f
    ]
    if not wav_files:
        LOG.warning("No .wav files found or all already converted to 16khz.")
        return

    for file in wav_files:
        input_file = audio_directory / file
        output_file = audio_directory / (Path(file).stem + "_16khz.wav")

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    str(input_file),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(output_file),
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            LOG.error("ffmpeg command failed for %s", input_file)
            raise

        if output_file.exists():
            input_file.unlink()


def run_whisper_command(
    audio_file: str,
    lang: str,
    output_dir: str,
    initial_prompt: str | None = None,
    autocorrect: bool = True,
    model_path: str | None = None,
) -> None:
    """Run whisper command with dynamic output paths."""
    original_input_path = Path(audio_file).resolve()
    file_name = remove_16khz_suffix(str(original_input_path))
    input_for_whisper = original_input_path
    cleanup_temp_wav = False

    if original_input_path.suffix.lower() != ".wav":
        input_for_whisper = _convert_to_temp_16khz_wav(original_input_path)
        cleanup_temp_wav = True
        LOG.info("Converted %s to temporary WAV for transcription", original_input_path)

    whisper_cli = get_whisper_cli_path()
    resolved_model_path = Path(model_path) if model_path else get_model_path()

    cmd = [
        str(whisper_cli),
        "-t",
        "8",
        "-m",
        str(resolved_model_path),
        "-f",
        str(input_for_whisper),
        "--language",
        lang,
        "-sow",
        "--beam-size",
        "5",
        "--entropy-thold",
        "2.8",
        "--max-context",
        "64",
    ]
    if initial_prompt:
        cmd.extend(["--prompt", initial_prompt])

    cmd.extend(
        [
            "--output-srt",
            "--output-file",
            f"{output_dir}/{file_name}_{lang}",
            "--output-txt",
            "--output-file",
            f"{output_dir}/{file_name}_{lang}",
        ]
    )

    try:
        subprocess.run(cmd, check=True)
        if autocorrect:
            output_base = Path(output_dir) / f"{file_name}_{lang}"
            autocorrect_file_in_place(output_base.with_suffix(".txt"))
            autocorrect_file_in_place(output_base.with_suffix(".srt"))
    finally:
        if cleanup_temp_wav and input_for_whisper.exists():
            input_for_whisper.unlink()
            LOG.info("Deleted temporary WAV: %s", input_for_whisper)


def batch_run_whisper_command(audio_file_paths: list[str], base_output_dir: Path) -> None:
    """Run whisper command for each audio file in both English and Japanese."""
    os.makedirs(base_output_dir / "en", exist_ok=True)
    os.makedirs(base_output_dir / "ja", exist_ok=True)

    for audio_file in audio_file_paths:
        run_whisper_command(audio_file, "en", str(base_output_dir / "en"))
        run_whisper_command(audio_file, "ja", str(base_output_dir / "ja"))


def list_audio_files(base_audio_dir: Path) -> list[str]:
    """Return all .wav files in the given directory (sorted)."""
    audio_files = sorted(base_audio_dir.glob("*.wav"))
    return [str(path.resolve()) for path in audio_files]
