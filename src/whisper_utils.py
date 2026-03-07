"""Shared helpers for whisper.cpp transcription workflows."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import json
import hashlib
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)
LLM_CORRECT_CHUNK_SIZE = 400
LLM_CORRECT_MAX_RETRIES = 2
LLM_CORRECT_MIN_CHUNK_SIZE = 50


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
    elif normalized == "medium":
        model_name = "ggml-medium.bin"
    elif normalized == "medium.en":
        model_name = "ggml-medium.en.bin"
    elif normalized == "small":
        model_name = "ggml-small.bin"
    elif normalized == "small.en":
        model_name = "ggml-small.en.bin"
    else:
        raise ValueError(
            f"Unsupported model variant: {model_variant}. "
            "Use large-v3/v3, large-v3-turbo/turbo, medium[/medium.en], or small[/small.en]."
        )
    resolved = Path(whisper_cpp_dir).expanduser().resolve() / "models" / model_name
    _ensure_file_readable(resolved, f"Whisper model file for variant '{model_variant}'")
    return resolved


def get_vad_model_path() -> Path:
    """Get path to whisper.cpp VAD model from env or local default."""
    vad_model_path = os.environ.get("WHISPER_VAD_MODEL_PATH")
    if vad_model_path:
        resolved = Path(vad_model_path).expanduser().resolve()
        _ensure_file_readable(resolved, "Whisper VAD model file")
        return resolved

    whisper_cpp_dir = os.environ.get(
        "WHISPER_CPP_DIR",
        Path(__file__).resolve().parent.parent / "vendor" / "whisper.cpp",
    )
    candidate = (
        Path(whisper_cpp_dir).expanduser().resolve() / "models" / "ggml-silero-v5.1.2.bin"
    )
    _ensure_file_readable(candidate, "Whisper VAD model file")
    return candidate


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


def _default_llm_model_for_backend(backend: str) -> str | None:
    if backend == "claude":
        return "haiku"
    return None


def _run_llm_subprocess(
    cmd: list[str],
    prompt: str | None,
    timeout_sec: int,
    backend: str,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            cmd,
            input=prompt.encode("utf-8") if prompt is not None else None,
            capture_output=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"{backend} CLI not found in PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{backend} request timed out after {timeout_sec} seconds."
        ) from exc


def _summarize_cli_error(stderr: bytes | str | None) -> str:
    raw = _decode_stderr(stderr).strip()
    if not raw:
        return "(no stderr output)"
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return "(no stderr output)"
    preview = "\n".join(lines[:8])
    if len(lines) > 8:
        preview += "\n..."
    return preview


def _call_gemini(prompt: str, model: str | None, timeout_sec: int) -> str:
    """Call gemini CLI in non-interactive mode."""
    cmd = ["gemini", "--prompt", "", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])
    result = _run_llm_subprocess(cmd, prompt, timeout_sec, backend="gemini")
    if result.returncode != 0:
        raise RuntimeError(f"gemini failed: {_summarize_cli_error(result.stderr)}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def _call_claude(prompt: str, model: str | None, timeout_sec: int) -> str:
    """Call claude non-interactively (stdin -> stdout)."""
    cmd = ["claude", "--print", "--no-session-persistence"]
    if model:
        cmd.extend(["--model", model])
    result = _run_llm_subprocess(cmd, prompt, timeout_sec, backend="claude")
    if result.returncode != 0:
        raise RuntimeError(f"claude failed: {_summarize_cli_error(result.stderr)}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def _call_codex(prompt: str, model: str | None, timeout_sec: int) -> str:
    """Call codex exec non-interactively and return the final message."""
    with tempfile.NamedTemporaryFile(prefix="codex_last_", suffix=".txt", delete=False) as f:
        output_path = Path(f.name)

    cmd = [
        "codex",
        "exec",
        "-",
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
    ]
    if model:
        cmd.extend(["--model", model])

    try:
        result = _run_llm_subprocess(cmd, prompt, timeout_sec, backend="codex")
        if result.returncode != 0:
            raise RuntimeError(f"codex failed: {_summarize_cli_error(result.stderr)}")
        if output_path.exists():
            output = output_path.read_text(encoding="utf-8", errors="replace").strip()
            if output:
                return output
        return result.stdout.decode("utf-8", errors="replace").strip()
    finally:
        output_path.unlink(missing_ok=True)


def _call_llm_cli(
    prompt: str,
    backend: str,
    model: str | None,
    timeout_sec: int,
) -> str:
    effective_model = model or _default_llm_model_for_backend(backend)
    if backend == "gemini":
        return _call_gemini(prompt, effective_model, timeout_sec)
    if backend == "claude":
        return _call_claude(prompt, effective_model, timeout_sec)
    if backend == "codex":
        return _call_codex(prompt, effective_model, timeout_sec)
    raise ValueError(f"Unsupported llm backend: {backend}")


def _ordered_llm_backends(primary_backend: str) -> list[str]:
    all_backends = ["gemini", "codex", "claude"]
    ordered = [primary_backend]
    ordered.extend(backend for backend in all_backends if backend != primary_backend)
    return ordered


def _extract_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return json.loads(text[start : end + 1])


def _build_llm_correct_prompt(
    lines: list[str],
    glossary: str | None = None,
    line_offset: int = 1,
) -> str:
    payload = {
        "lines": [{"id": i + line_offset, "text": line} for i, line in enumerate(lines)],
    }
    prompt_parts = [
        "ROLE:\n"
        "You are a transcript correction assistant for Chinese interview transcripts.\n\n"
        "GOAL:\n"
        "Correct each line while preserving meaning and sentence boundaries.\n\n"
        "HARD CONSTRAINTS (必须严格遵守):\n"
        "1) Return ONLY valid JSON in this exact schema:\n"
        '{"lines":[{"id":<int>,"text":"<corrected_text>"}]}\n'
        "2) Keep EXACTLY the same number of items and same ids.\n"
        "3) Do NOT merge or split lines.\n"
        "4) No extra keys, no markdown, no explanations.\n\n"
        "NORMALIZATION RULES:\n"
        "- Fix obvious homophone/misrecognition errors (同音字与误识别纠错).\n"
        "- Normalize proper nouns/brand names to official casing and spacing.\n"
        "  Example: deep mind -> DeepMind, open ai -> OpenAI.\n"
        "- Convert Traditional Chinese to Simplified Chinese for all Chinese text (繁体统一转简体).\n"
        "- Keep numbers, punctuation, and non-Chinese tokens unless correction is clearly needed.\n"
        "- If a line is already correct, keep it unchanged.\n\n"
    ]
    if glossary:
        prompt_parts.append(
            "GLOSSARY OVERRIDE (最高优先级):\n"
            "If any glossary term or alias appears in a line, you MUST normalize it to the\n"
            "exact glossary form. Glossary rules override other stylistic choices.\n"
            "Do not invent alternatives when glossary specifies a form.\n\n"
            f"Glossary 词汇表 (use these exact forms):\n{glossary}\n\n"
        )
    prompt_parts.append("INPUT JSON:\n")
    prompt_parts.append(json.dumps(payload, ensure_ascii=False))
    return "".join(prompt_parts)


def _parse_llm_corrected_lines(
    raw: str,
    expected_ids: list[int],
    original_by_id: dict[int, str],
) -> list[str]:
    data = _extract_json_payload(raw)
    items = data.get("lines") if isinstance(data, dict) else None
    if isinstance(data, list):
        items = data
    if not isinstance(items, list):
        raise ValueError("LLM response JSON missing `lines` array.")

    parsed: dict[int, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("LLM response line item is not an object.")
        line_id = item.get("id")
        text = item.get("text")
        if not isinstance(line_id, int):
            raise ValueError("LLM response line id is not int.")
        if not isinstance(text, str):
            raise ValueError("LLM response line text is not string.")
        if line_id in parsed:
            raise ValueError(f"LLM response has duplicate id: {line_id}")
        parsed[line_id] = text.strip()

    if set(parsed.keys()) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(parsed.keys()))
        extra = sorted(set(parsed.keys()) - set(expected_ids))
        raise ValueError(
            "LLM response ids mismatch. "
            f"missing={missing[:5]} extra={extra[:5]}"
        )

    return [parsed.get(line_id, original_by_id[line_id]) for line_id in expected_ids]


def _llm_correct_lines_once(
    lines: list[str],
    backend: str,
    model: str | None,
    timeout_sec: int,
    glossary: str | None = None,
    line_offset: int = 1,
) -> list[str]:
    if not lines:
        return []
    prompt = _build_llm_correct_prompt(lines, glossary=glossary, line_offset=line_offset)
    raw = _call_llm_cli(
        prompt=prompt,
        backend=backend,
        model=model,
        timeout_sec=timeout_sec,
    )
    expected_ids = [line_offset + i for i in range(len(lines))]
    original_by_id = {line_offset + i: line for i, line in enumerate(lines)}
    return _parse_llm_corrected_lines(raw, expected_ids=expected_ids, original_by_id=original_by_id)


def _llm_correct_lines_chunked(
    lines: list[str],
    backend: str,
    model: str | None,
    timeout_sec: int,
    glossary: str | None = None,
    chunk_size: int = LLM_CORRECT_CHUNK_SIZE,
) -> tuple[list[str], int]:
    corrected: list[str] = []
    failures = 0
    total = len(lines)
    chunk_size = max(1, chunk_size)
    total_chunks = (total + chunk_size - 1) // chunk_size

    for chunk_idx, start in enumerate(range(0, total, chunk_size), start=1):
        end = min(start + chunk_size, total)
        chunk = lines[start:end]
        LOG.info(
            "LLM correction batch %d/%d: lines %d-%d",
            chunk_idx,
            total_chunks,
            start + 1,
            end,
        )
        chunk_corrected: list[str] | None = None
        for attempt in range(1, LLM_CORRECT_MAX_RETRIES + 1):
            try:
                chunk_corrected = _llm_correct_lines_once(
                    lines=chunk,
                    backend=backend,
                    model=model,
                    timeout_sec=timeout_sec,
                    glossary=glossary,
                    line_offset=start + 1,
                )
                break
            except Exception as exc:  # noqa: BLE001
                LOG.warning(
                    "LLM chunk failed (%s attempt %d/%d lines %d-%d): %s",
                    backend,
                    attempt,
                    LLM_CORRECT_MAX_RETRIES,
                    start + 1,
                    end,
                    exc,
                )
        if chunk_corrected is None:
            failures += 1
            corrected.extend(chunk)
            continue
        corrected.extend(chunk_corrected)
    return corrected, failures


def _llm_correct_lines(
    lines: list[str],
    backend: str,
    model: str | None,
    timeout_sec: int,
    glossary: str | None = None,
) -> tuple[list[str], str]:
    """Return corrected lines and status: applied|partial_applied|fallback_kept_original."""
    if not lines:
        return [], "applied"

    for backend_name in _ordered_llm_backends(backend):
        try:
            corrected = _llm_correct_lines_once(
                lines=lines,
                backend=backend_name,
                model=model,
                timeout_sec=timeout_sec,
                glossary=glossary,
                line_offset=1,
            )
            LOG.info("LLM correction applied via %s in single request.", backend_name)
            return corrected, "applied"
        except Exception as exc:  # noqa: BLE001
            LOG.warning(
                "LLM single request failed (%s): %s; falling back to chunked mode.",
                backend_name,
                exc,
            )
            corrected_chunked, failures = _llm_correct_lines_chunked(
                lines=lines,
                backend=backend_name,
                model=model,
                timeout_sec=timeout_sec,
                glossary=glossary,
            )
            if failures == 0:
                LOG.info("LLM correction applied via %s in chunked mode.", backend_name)
                return corrected_chunked, "applied"
            if failures < max(1, (len(lines) + LLM_CORRECT_CHUNK_SIZE - 1) // LLM_CORRECT_CHUNK_SIZE):
                LOG.warning(
                    "LLM correction partially applied via %s; %d chunk(s) kept original.",
                    backend_name,
                    failures,
                )
                return corrected_chunked, "partial_applied"
            LOG.warning(
                "LLM chunked mode failed for backend %s; trying next backend.",
                backend_name,
            )

    LOG.warning("LLM correction fallback_kept_original: all backends failed.")
    return lines, "fallback_kept_original"


def llm_correct_file_in_place(
    file_path: Path,
    backend: str,
    model: str | None,
    timeout_sec: int,
    glossary: str | None = None,
) -> None:
    """Apply LLM correction in-place to a .txt or .srt file."""
    if not file_path.exists():
        LOG.warning("LLM correct skipped; file not found: %s", file_path)
        return

    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        all_lines = file_path.read_text(encoding="utf-8").splitlines()
        original_lines = list(all_lines)
        non_empty_indices = [i for i, line in enumerate(all_lines) if line.strip()]
        if not non_empty_indices:
            return
        content_lines = [all_lines[i] for i in non_empty_indices]
        corrected_lines, status = _llm_correct_lines(
            content_lines,
            backend=backend,
            model=model,
            timeout_sec=timeout_sec,
            glossary=glossary,
        )
        for idx, corrected in zip(non_empty_indices, corrected_lines):
            all_lines[idx] = corrected
        file_path.write_text("\n".join(all_lines), encoding="utf-8")
        if all_lines == original_lines:
            LOG.info("LLM correction %s with no text changes: %s", status, file_path)
        else:
            LOG.info("LLM correction %s: %s", status, file_path)

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
        corrected_texts, status = _llm_correct_lines(
            texts,
            backend=backend,
            model=model,
            timeout_sec=timeout_sec,
            glossary=glossary,
        )
        for block_idx, corrected_text in zip(valid_block_indices, corrected_texts):
            block_lines = blocks[block_idx].splitlines()
            blocks[block_idx] = "\n".join(block_lines[:2] + [corrected_text])
        file_path.write_text("\n\n".join(blocks), encoding="utf-8")
        LOG.info("LLM correction %s: %s", status, file_path)

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


def _default_postprocess_state_path(srt_path: Path) -> Path:
    return srt_path.with_suffix(".postprocess_state.json")


def _compute_postprocess_pair_hash(srt_path: Path, txt_path: Path) -> str:
    hasher = hashlib.sha256()
    hasher.update(srt_path.read_bytes())
    hasher.update(b"\n--PAIR-SEP--\n")
    hasher.update(txt_path.read_bytes())
    return hasher.hexdigest()


def _read_postprocess_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _write_postprocess_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _selected_postprocess_steps(
    split_on_punc: bool,
    llm_correct: bool,
    autocorrect: bool,
) -> list[str]:
    steps: list[str] = []
    if split_on_punc:
        steps.append("split")
    if llm_correct:
        steps.append("llm_correct_txt")
        steps.append("sync_txt_to_srt")
    if autocorrect:
        steps.append("autocorrect")
    return steps


def postprocess_transcription_outputs(
    output_base: Path,
    split_on_punc: bool,
    llm_correct: bool,
    llm_backend: str,
    llm_model: str | None,
    llm_timeout_sec: int,
    llm_glossary: str | None,
    autocorrect: bool,
    resume: bool = False,
    from_step: str | None = None,
    to_step: str | None = None,
) -> None:
    """Apply optional post-processing steps for generated transcript files."""
    postprocess_srt_txt_files(
        srt_path=output_base.with_suffix(".srt"),
        txt_path=output_base.with_suffix(".txt"),
        split_on_punc=split_on_punc,
        llm_correct=llm_correct,
        llm_backend=llm_backend,
        llm_model=llm_model,
        llm_timeout_sec=llm_timeout_sec,
        llm_glossary=llm_glossary,
        autocorrect=autocorrect,
        resume=resume,
        from_step=from_step,
        to_step=to_step,
    )


def postprocess_srt_txt_files(
    srt_path: Path,
    txt_path: Path,
    split_on_punc: bool,
    llm_correct: bool,
    llm_backend: str,
    llm_model: str | None,
    llm_timeout_sec: int,
    llm_glossary: str | None,
    autocorrect: bool,
    resume: bool = False,
    from_step: str | None = None,
    to_step: str | None = None,
) -> None:
    """Apply optional post-processing steps to an existing SRT/TXT pair."""
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")
    if not txt_path.is_file():
        raise FileNotFoundError(f"TXT file not found: {txt_path}")

    steps = _selected_postprocess_steps(
        split_on_punc=split_on_punc,
        llm_correct=llm_correct,
        autocorrect=autocorrect,
    )
    if not steps:
        return

    state_path = _default_postprocess_state_path(srt_path)
    pair_hash = _compute_postprocess_pair_hash(srt_path, txt_path)
    state = _read_postprocess_state(state_path) if resume else {}
    completed_steps = [str(x) for x in state.get("completed_steps", [])]

    if resume and state and state.get("pair_hash") not in {None, pair_hash}:
        LOG.warning(
            "Resume requested but state hash differs from current files; starting fresh state."
        )
        completed_steps = []

    selected_steps = steps
    if from_step:
        if from_step not in selected_steps:
            raise ValueError(f"--from-step '{from_step}' is not part of selected postprocess steps.")
        selected_steps = selected_steps[selected_steps.index(from_step) :]
    if to_step:
        if to_step not in selected_steps:
            raise ValueError(f"--to-step '{to_step}' is not part of selected postprocess steps.")
        selected_steps = selected_steps[: selected_steps.index(to_step) + 1]

    if resume:
        selected_steps = [step for step in selected_steps if step not in completed_steps]

    state = {
        "pair_hash": pair_hash,
        "completed_steps": completed_steps,
        "selected_steps": selected_steps,
        "status": "running",
        "last_step": completed_steps[-1] if completed_steps else None,
    }
    _write_postprocess_state(state_path, state)

    try:
        for step in selected_steps:
            LOG.info("Postprocess step: %s", step)
            if step == "split":
                split_lines = _split_srt_on_punctuation(srt_path)
                _rewrite_txt_from_lines(txt_path, split_lines)
            elif step == "llm_correct_txt":
                _validate_srt_txt_line_alignment(srt_path, txt_path)
                llm_correct_file_in_place(
                    txt_path,
                    backend=llm_backend,
                    model=llm_model,
                    timeout_sec=llm_timeout_sec,
                    glossary=llm_glossary,
                )
            elif step == "sync_txt_to_srt":
                _validate_srt_txt_line_alignment(srt_path, txt_path)
                _sync_srt_text_from_txt(srt_path=srt_path, txt_path=txt_path)
            elif step == "autocorrect":
                _validate_srt_txt_line_alignment(srt_path, txt_path)
                autocorrect_file_in_place(txt_path)
                autocorrect_file_in_place(srt_path)
            else:
                raise ValueError(f"Unknown postprocess step: {step}")

            state["completed_steps"] = [*state.get("completed_steps", []), step]
            state["last_step"] = step
            state["pair_hash"] = _compute_postprocess_pair_hash(srt_path, txt_path)
            _write_postprocess_state(state_path, state)
    except Exception:  # noqa: BLE001
        state["status"] = "failed"
        _write_postprocess_state(state_path, state)
        raise

    state["status"] = "done"
    state["pair_hash"] = _compute_postprocess_pair_hash(srt_path, txt_path)
    _write_postprocess_state(state_path, state)


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
