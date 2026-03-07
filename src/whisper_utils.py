"""Shared helpers for whisper.cpp transcription workflows."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

LOG = logging.getLogger(__name__)


def _decode_stderr(stderr: bytes | str | None) -> str:
    """Decode subprocess stderr safely across platform code pages."""
    if stderr is None:
        return ""
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", errors="replace")
    return stderr


def _ensure_file_readable(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    try:
        with path.open("rb") as file:
            file.read(1)
    except OSError as exc:
        raise PermissionError(f"{label} is not readable: {path}") from exc


def _candidate_whisper_cli_paths(base_dir: Path) -> list[Path]:
    build_bin_dir = base_dir / "build" / "bin"
    vendor_bin_dir = base_dir / "vendor" / "whisper.cpp" / "build" / "bin"
    if os.name == "nt":
        return [
            build_bin_dir / "Release" / "whisper-cli.exe",
            build_bin_dir / "RelWithDebInfo" / "whisper-cli.exe",
            build_bin_dir / "Debug" / "whisper-cli.exe",
            build_bin_dir / "whisper-cli.exe",
            vendor_bin_dir / "Release" / "whisper-cli.exe",
            vendor_bin_dir / "RelWithDebInfo" / "whisper-cli.exe",
            vendor_bin_dir / "Debug" / "whisper-cli.exe",
            vendor_bin_dir / "whisper-cli.exe",
        ]
    return [build_bin_dir / "whisper-cli", vendor_bin_dir / "whisper-cli"]


def get_whisper_cli_path() -> Path:
    """Get path to whisper-cli binary from env, PATH, or local build."""
    env_path = os.environ.get("WHISPER_CLI_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    which_result = shutil.which("whisper-cli")
    if which_result:
        return Path(which_result)

    base_dir = Path(__file__).resolve().parent.parent
    for candidate in _candidate_whisper_cli_paths(base_dir):
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "whisper-cli not found. Set WHISPER_CLI_PATH, add it to PATH, "
        "or build whisper.cpp in the project root."
    )


def _model_search_dirs(base_dir: Path) -> list[Path]:
    return [
        base_dir / "models",
        base_dir / "vendor" / "whisper.cpp" / "models",
    ]


def get_model_path() -> Path:
    """Get the default Whisper model path."""
    env_path = os.environ.get("WHISPER_MODEL_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    base_dir = Path(__file__).resolve().parent.parent
    for models_dir in _model_search_dirs(base_dir):
        candidate = models_dir / "ggml-large-v3-turbo.bin"
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "Whisper model not found. Set WHISPER_MODEL_PATH or place model at "
        f"{base_dir / 'models' / 'ggml-large-v3-turbo.bin'}"
    )


def get_model_path_by_variant(variant: str) -> Path:
    """Get a Whisper model path by variant name (e.g. 'large-v3-turbo')."""
    env_path = os.environ.get("WHISPER_MODEL_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    base_dir = Path(__file__).resolve().parent.parent
    for models_dir in _model_search_dirs(base_dir):
        candidate = models_dir / f"ggml-{variant}.bin"
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Whisper model variant '{variant}' not found. "
        f"Expected at {base_dir / 'models' / f'ggml-{variant}.bin'}. "
        "Set WHISPER_MODEL_PATH to override."
    )


def get_vad_model_path() -> Path:
    """Get the VAD model path."""
    env_path = os.environ.get("WHISPER_VAD_MODEL_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    base_dir = Path(__file__).resolve().parent.parent
    for models_dir in _model_search_dirs(base_dir):
        for name in ("silero_vad.onnx", "ggml-silero-v5.1.2.bin", "ggml-silero-v6.2.0.bin"):
            candidate = models_dir / name
            if candidate.is_file():
                return candidate

    raise FileNotFoundError(
        "VAD model not found. Set WHISPER_VAD_MODEL_PATH or place model at "
        f"{base_dir / 'models' / 'silero_vad.onnx'}"
    )


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
        )
        if not temp_wav_path.exists() or temp_wav_path.stat().st_size == 0:
            raise RuntimeError(
                f"ffmpeg reported success but produced empty wav: {temp_wav_path}"
            )
    except subprocess.CalledProcessError as exc:
        if temp_wav_path.exists():
            temp_wav_path.unlink()
        LOG.error(
            "Failed to convert %s to wav: %s",
            input_file,
            _decode_stderr(exc.stderr).strip(),
        )
        raise
    except RuntimeError:
        if temp_wav_path.exists():
            temp_wav_path.unlink()
        LOG.error(
            "Failed to convert %s to wav: %s",
            input_file,
            (
                _decode_stderr(result.stderr).strip()
                if "result" in locals()
                else "unknown ffmpeg error"
            ),
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
            )
            LOG.info("Applied autocorrect via CLI: %s", file_path)
            return True
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError as exc:
            LOG.debug(
                "Autocorrect CLI variant failed (%s): %s",
                cmd,
                _decode_stderr(exc.stderr).strip(),
            )
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
    threads: int = 8,
    split_on_word: bool = True,
    beam_size: int = 5,
    best_of: int = 5,
    entropy_thold: float = 2.8,
    max_context: int = -1,
    max_len: int = 0,
    no_gpu: bool = False,
    no_fallback: bool = False,
    suppress_nst: bool = False,
    use_vad: bool = False,
    vad_model_path: str | None = None,
    split_on_punc: bool = False,
    llm_correct: bool = False,
    llm_backend: str = "gemini",
    llm_model: str | None = None,
    llm_timeout_sec: int = 300,
    llm_glossary: str | None = None,
    skip_postprocess: bool = False,
) -> None:
    """Run whisper command with dynamic output paths."""
    from src.postprocess import postprocess_transcription_outputs

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
    _ensure_file_readable(resolved_model_path, "Whisper model file")
    resolved_vad_model_path: Path | None = None
    if use_vad:
        resolved_vad_model_path = (
            Path(vad_model_path).expanduser().resolve()
            if vad_model_path
            else get_vad_model_path()
        )
        _ensure_file_readable(resolved_vad_model_path, "Whisper VAD model file")

    cmd = [
        str(whisper_cli),
        "-t",
        str(threads),
        "-m",
        str(resolved_model_path),
        "-f",
        str(input_for_whisper),
        "--language",
        lang,
        "--beam-size",
        str(beam_size),
        "--best-of",
        str(best_of),
        "--entropy-thold",
        str(entropy_thold),
        "--max-context",
        str(max_context),
    ]
    if split_on_word:
        cmd.append("-sow")
    if max_len > 0:
        cmd.extend(["--max-len", str(max_len)])
    if no_gpu:
        cmd.append("--no-gpu")
    if no_fallback:
        cmd.append("--no-fallback")
    if suppress_nst:
        cmd.append("--suppress-nst")
    if use_vad and resolved_vad_model_path:
        cmd.extend(["--vad", "--vad-model", str(resolved_vad_model_path)])
    if initial_prompt:
        cmd.extend(["--prompt", initial_prompt])

    output_base_str = str(Path(output_dir) / f"{file_name}_{lang}")
    cmd.extend(
        [
            "--output-srt",
            "--output-file",
            output_base_str,
            "--output-txt",
            "--output-file",
            output_base_str,
        ]
    )

    try:
        subprocess.run(cmd, check=True)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 4551:
            raise RuntimeError(
                "Windows App Control policy blocked whisper-cli. "
                "Set WHISPER_CLI_PATH to an approved whisper-cli.exe path."
            ) from exc
        raise
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "whisper-cli failed. Verify whisper-cli and model paths are valid/readable. "
            f"model={resolved_model_path} cli={whisper_cli}"
        ) from exc
    else:
        output_base = Path(output_dir) / f"{file_name}_{lang}"
        if not skip_postprocess:
            postprocess_transcription_outputs(
                output_base=output_base,
                split_on_punc=split_on_punc,
                llm_correct=llm_correct,
                llm_backend=llm_backend,
                llm_model=llm_model,
                llm_timeout_sec=llm_timeout_sec,
                llm_glossary=llm_glossary,
                autocorrect=autocorrect,
            )
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
