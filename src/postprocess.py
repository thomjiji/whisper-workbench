"""Postprocessing pipeline for SRT/TXT transcript pairs."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from src.llm_correct import llm_correct_file_in_place
from src.srt_utils import (
    _rewrite_txt_from_lines,
    _split_srt_on_punctuation,
    _sync_srt_text_from_txt,
    _validate_srt_txt_line_alignment,
)

LOG = logging.getLogger(__name__)


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
    from src.whisper_utils import autocorrect_file_in_place

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
