"""LLM-based transcript correction helpers."""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)
LLM_CORRECT_CHUNK_SIZE = 400
LLM_CORRECT_MAX_RETRIES = 1
LLM_CORRECT_MIN_CHUNK_SIZE = 50
LLM_CORRECT_MAX_WORKERS = 4
LLM_CORRECT_LARGE_CHUNK_WORKERS = 2


def _summarize_cli_error(stderr: bytes | str | None) -> str:
    from src.whisper_utils import _decode_stderr

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
        "You are a transcript correction assistant for Chinese transcripts.\n\n"
        "GOAL:\n"
        "Review each line. Return ONLY the lines that need correction.\n"
        "If a line is already correct, do NOT include it in your response.\n"
        "Return an empty corrections list if nothing needs changing.\n\n"
        "OUTPUT FORMAT (必须严格遵守):\n"
        '{"corrections":[{"id":<int>,"text":"<corrected_text>"}]}\n'
        "- Return ONLY valid JSON. No markdown, no explanation.\n"
        "- Return ONLY lines you are changing.\n"
        "- The \"id\" must be one of the input line IDs.\n"
        "- Do NOT invent new IDs. Do NOT merge lines. Do NOT split lines.\n\n"
        "CORRECTION RULES:\n"
        "- Fix homophones and misrecognition errors (同音字与误识别纠错).\n"
        "- Normalize proper nouns (e.g. deep mind -> DeepMind, open ai -> OpenAI).\n"
        "- When Arabic numeral years or decades are clearly abbreviated, expand them to the full form (for example 08年 -> 2008年, 9几年 -> 199几年).\n"
        "- Do not rewrite ambiguous spoken Chinese year phrases such as 八九年 unless the context is explicit.\n"
        "- Convert Traditional Chinese to Simplified Chinese (繁体→简体).\n"
        "- Keep numbers, punctuation, non-Chinese tokens unless clearly wrong.\n\n"
    ]
    if glossary:
        prompt_parts.append(
            "GLOSSARY OVERRIDE (最高优先级):\n"
            "Match any glossary term and normalize to the exact listed form.\n"
            "Glossary rules override all other normalization choices.\n\n"
            f"Glossary:\n{glossary}\n\n"
        )
    prompt_parts.append("INPUT:\n")
    prompt_parts.append(json.dumps(payload, ensure_ascii=False))
    return "".join(prompt_parts)


def _apply_llm_corrections_patch(
    raw: str,
    input_lines: list[str],
    line_offset: int,
) -> list[str]:
    """Parse LLM response as a patch, apply to originals.

    Returns corrected lines. Never raises on missing/extra lines.
    """
    payload = _extract_json_payload(raw)
    corrections = payload.get("corrections", [])
    if not isinstance(corrections, list):
        raise ValueError("LLM response JSON missing `corrections` array.")

    valid_ids = set(range(line_offset, line_offset + len(input_lines)))
    result = list(input_lines)

    seen_ids: set[int] = set()
    for item in corrections:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        item_text = item.get("text")
        if not isinstance(item_id, int) or not isinstance(item_text, str):
            continue
        if item_id not in valid_ids:
            LOG.warning(
                "LLM returned invalid id %s (valid range %d-%d), skipping",
                item_id,
                line_offset,
                line_offset + len(input_lines) - 1,
            )
            continue
        if item_id in seen_ids:
            LOG.warning("LLM returned duplicate id %s, skipping", item_id)
            continue
        seen_ids.add(item_id)
        result[item_id - line_offset] = item_text.strip()

    LOG.info("LLM applied %d corrections out of %d lines", len(seen_ids), len(input_lines))
    return result


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
    return _apply_llm_corrections_patch(raw, input_lines=lines, line_offset=line_offset)


def _llm_correct_lines_chunked(
    lines: list[str],
    backend: str,
    model: str | None,
    timeout_sec: int,
    glossary: str | None = None,
    chunk_size: int = LLM_CORRECT_CHUNK_SIZE,
) -> tuple[list[str], int]:
    total = len(lines)
    chunk_size = max(1, chunk_size)
    chunk_list = [
        (start, min(start + chunk_size, total), lines[start : min(start + chunk_size, total)])
        for start in range(0, total, chunk_size)
    ]
    total_chunks = len(chunk_list)
    max_workers = min(
        total_chunks,
        LLM_CORRECT_LARGE_CHUNK_WORKERS
        if chunk_size >= 400
        else LLM_CORRECT_MAX_WORKERS,
    ) or 1
    LOG.info(
        "LLM correction scheduling: chunk_size=%d total_chunks=%d max_workers=%d",
        chunk_size,
        total_chunks,
        max_workers,
    )

    def degrade_chunk(
        start: int,
        chunk: list[str],
        exc: Exception,
    ) -> list[str] | None:
        if len(chunk) <= LLM_CORRECT_MIN_CHUNK_SIZE:
            return None
        split_size = max(LLM_CORRECT_MIN_CHUNK_SIZE, len(chunk) // 2)
        LOG.warning(
            "LLM chunk degrade (%s lines %d-%d -> subchunks of %d): %s",
            backend,
            start + 1,
            start + len(chunk),
            split_size,
            exc,
        )
        corrected, failures = _llm_correct_lines_chunked(
            lines=chunk,
            backend=backend,
            model=model,
            timeout_sec=timeout_sec,
            glossary=glossary,
            chunk_size=split_size,
        )
        if failures == len(range(0, len(chunk), split_size)):
            return None
        return corrected

    def process_chunk(args: tuple[int, tuple[int, int, list[str]]]) -> tuple[int, list[str] | None]:
        chunk_idx, (start, end, chunk) = args
        LOG.info(
            "LLM correction batch %d/%d: lines %d-%d",
            chunk_idx,
            total_chunks,
            start + 1,
            end,
        )
        chunk_corrected: list[str] | None = None
        for attempt in range(1, LLM_CORRECT_MAX_RETRIES + 2):
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
            except RuntimeError as exc:
                LOG.warning(
                    "LLM chunk backend error (%s attempt %d/2 lines %d-%d): %s",
                    backend,
                    attempt,
                    start + 1,
                    end,
                    exc,
                )
                chunk_corrected = degrade_chunk(start, chunk, exc)
                break
            except (ValueError, json.JSONDecodeError) as exc:
                LOG.warning(
                    "LLM chunk JSON parse failed (%s attempt %d/2 lines %d-%d): %s",
                    backend,
                    attempt,
                    start + 1,
                    end,
                    exc,
                )
                chunk_corrected = degrade_chunk(start, chunk, exc)
        return start, chunk_corrected

    results: dict[int, list[str] | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for start, result in executor.map(process_chunk, enumerate(chunk_list, start=1)):
            results[start] = result

    corrected: list[str] = []
    failures = 0
    for start, end, chunk in chunk_list:
        result = results[start]
        if result is None:
            failures += 1
            corrected.extend(chunk)
        else:
            corrected.extend(result)
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

    total_chunks = (len(lines) + LLM_CORRECT_CHUNK_SIZE - 1) // LLM_CORRECT_CHUNK_SIZE

    for backend_name in _ordered_llm_backends(backend):
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
        if failures < max(1, total_chunks):
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
