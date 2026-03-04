"""Shared helpers for whisper.cpp transcription workflows."""

from __future__ import annotations

import logging
import os
import re
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
    if os.name == "nt":
        return [
            build_bin_dir / "Release" / "whisper-cli.exe",
            build_bin_dir / "RelWithDebInfo" / "whisper-cli.exe",
            build_bin_dir / "Debug" / "whisper-cli.exe",
            build_bin_dir / "whisper-cli.exe",
        ]
    return [build_bin_dir / "whisper-cli"]


def get_whisper_cli_path() -> Path:
    """Get path to whisper-cli binary from env, PATH, or local build."""
    whisper_cli_path = os.environ.get("WHISPER_CLI_PATH")
    if whisper_cli_path:
        path = Path(whisper_cli_path).expanduser().resolve()
        _ensure_file_readable(path, "whisper-cli executable")
        return path

    whisper_cli_in_path = shutil.which("whisper-cli")
    if whisper_cli_in_path:
        return Path(whisper_cli_in_path).resolve()

    whisper_cpp_dir = os.environ.get(
        "WHISPER_CPP_DIR",
        Path(__file__).resolve().parent.parent / "vendor" / "whisper.cpp",
    )
    base_dir = Path(whisper_cpp_dir).expanduser().resolve()
    cli_candidates = _candidate_whisper_cli_paths(base_dir)
    for candidate in cli_candidates:
        if candidate.exists():
            _ensure_file_readable(candidate, "whisper-cli executable")
            return candidate

    raise FileNotFoundError(
        "whisper-cli executable not found. Tried:\n"
        + "\n".join(str(p) for p in cli_candidates)
        + "\nRun setup first or set WHISPER_CLI_PATH."
    )


def get_model_path() -> Path:
    """Get path to whisper model from env or local defaults."""
    model_path = os.environ.get("WHISPER_MODEL_PATH")
    if model_path:
        resolved = Path(model_path).expanduser().resolve()
        _ensure_file_readable(resolved, "Whisper model file")
        return resolved

    whisper_cpp_dir = os.environ.get(
        "WHISPER_CPP_DIR",
        Path(__file__).resolve().parent.parent / "vendor" / "whisper.cpp",
    )
    models_dir = Path(whisper_cpp_dir).expanduser().resolve() / "models"
    candidates = [
        models_dir / "ggml-large-v3.bin",
        models_dir / "ggml-large-v3-turbo.bin",
    ]
    for candidate in candidates:
        if candidate.exists():
            _ensure_file_readable(candidate, "Whisper model file")
            return candidate

    raise FileNotFoundError(
        "No default Whisper model found. Expected one of:\n"
        + "\n".join(str(path) for path in candidates)
        + "\nRun setup first, or provide --model/--model-path, or set WHISPER_MODEL_PATH."
    )


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
    resolved = Path(whisper_cpp_dir).expanduser().resolve() / "models" / model_name
    _ensure_file_readable(resolved, f"Whisper model file for variant '{model_variant}'")
    return resolved


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


def _call_claude(prompt: str, model: str = "haiku") -> str:
    """Call claude -p non-interactively (stdin → stdout) and return the response."""
    cmd = [
        "claude", "--print",
        "--model", model,
        "--no-session-persistence",
    ]
    try:
        result = subprocess.run(
            cmd,
            input=prompt.encode("utf-8"),
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("claude CLI not found.") from exc
    if result.returncode != 0:
        raise RuntimeError(f"claude failed: {_decode_stderr(result.stderr).strip()}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def _llm_correct_lines(
    lines: list[str],
    model: str,
    glossary: str | None = None,
) -> list[str]:
    """Use an LLM to fix homophone errors and proper noun inconsistencies."""
    numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    prompt_parts = [
        "You are a transcript correction assistant.\n"
        "Fix: (1) homophone errors 同音字错误 e.g. 之瞎→之下, 在→再\n"
        "     (2) proper noun forms per glossary 专名统一\n"
        "Rules 规则:\n"
        "- Return EXACTLY the same number of lines in the same order"
        " 返回行数必须与输入完全一致\n"
        "- Output ONLY the numbered list, no explanations 只输出编号列表，不要解释\n"
        "- Format: N. corrected text\n"
        "- Do NOT merge or split lines 不要合并或拆分行\n"
        "- If a line needs no correction, return it unchanged\n"
        "- No tool use needed, just output the corrected list directly\n",
    ]
    if glossary:
        prompt_parts.append(f"\nGlossary 词汇表 (use these exact forms):\n{glossary}\n\n---\n\n")
    prompt_parts.append(numbered)
    prompt = "".join(prompt_parts)

    raw = _call_claude(prompt, model)

    corrected: dict[int, str] = {}
    for line in raw.splitlines():
        m = re.match(r"^(\d+)\.\s*(.*)", line)
        if m:
            corrected[int(m.group(1))] = m.group(2)

    if len(corrected) != len(lines):
        LOG.warning(
            "LLM returned %d lines but expected %d; falling back to original",
            len(corrected),
            len(lines),
        )
        return lines

    return [corrected.get(i + 1, lines[i]) for i in range(len(lines))]


def llm_correct_file_in_place(
    file_path: Path,
    model: str,
    glossary: str | None = None,
) -> None:
    """Apply LLM correction in-place to a .txt or .srt file."""
    if not file_path.exists():
        LOG.warning("LLM correct skipped; file not found: %s", file_path)
        return

    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        all_lines = file_path.read_text(encoding="utf-8").splitlines()
        non_empty_indices = [i for i, line in enumerate(all_lines) if line.strip()]
        if not non_empty_indices:
            return
        content_lines = [all_lines[i] for i in non_empty_indices]
        corrected_lines = _llm_correct_lines(content_lines, model, glossary)
        for idx, corrected in zip(non_empty_indices, corrected_lines):
            all_lines[idx] = corrected
        file_path.write_text("\n".join(all_lines), encoding="utf-8")
        LOG.info("LLM correction applied to %s", file_path)

    elif suffix == ".srt":
        raw = file_path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            return
        blocks = raw.split("\n\n")
        texts: list[str] = []
        valid_block_indices: list[int] = []
        for i, block in enumerate(blocks):
            block_lines = block.splitlines()
            if len(block_lines) < 3 or " --> " not in block_lines[1]:
                continue
            text = " ".join(line.strip() for line in block_lines[2:]).strip()
            if text:
                texts.append(text)
                valid_block_indices.append(i)
        if not texts:
            return
        corrected_texts = _llm_correct_lines(texts, model, glossary)
        for block_idx, corrected_text in zip(valid_block_indices, corrected_texts):
            block_lines = blocks[block_idx].splitlines()
            blocks[block_idx] = "\n".join(block_lines[:2] + [corrected_text])
        file_path.write_text("\n\n".join(blocks), encoding="utf-8")
        LOG.info("LLM correction applied to %s", file_path)

    else:
        LOG.warning("LLM correct: unsupported file type %s, skipping", file_path.suffix)


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
    split_on_punc: bool = False,
    llm_correct: bool = False,
    llm_model: str = "haiku",
    llm_glossary: str | None = None,
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
    _ensure_file_readable(resolved_model_path, "Whisper model file")

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
        if split_on_punc:
            split_lines = _split_srt_on_punctuation(output_base.with_suffix(".srt"))
            _rewrite_txt_from_lines(output_base.with_suffix(".txt"), split_lines)
        if llm_correct:
            llm_correct_file_in_place(output_base.with_suffix(".txt"), llm_model, llm_glossary)
            llm_correct_file_in_place(output_base.with_suffix(".srt"), llm_model, llm_glossary)
        if autocorrect:
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
