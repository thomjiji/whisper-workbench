"""Transcription backend implementations for local whisper.cpp and Groq API."""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.postprocess import postprocess_transcription_outputs
from src.srt_utils import write_srt_txt_from_segments
from src.whisper_utils import remove_16khz_suffix, run_whisper_command

GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


@dataclass(slots=True)
class TranscribeRequest:
    """Unified transcription request for all backends."""

    audio_file: Path
    output_dir: Path
    lang: str
    initial_prompt: str | None
    autocorrect: bool
    split_on_punc: bool
    llm_correct: bool
    llm_backend: str
    llm_model: str | None
    llm_timeout_sec: int
    llm_glossary: str | None
    skip_postprocess: bool = False
    local_model_path: str | None = None
    decode_options: dict[str, int | float | bool] | None = None
    groq_model: str = "whisper-large-v3"
    groq_timeout_sec: int = 300


class LocalWhisperCppBackend:
    """Local transcription backend powered by whisper.cpp CLI."""

    name = "local"

    def transcribe(self, request: TranscribeRequest) -> None:
        decode_options = request.decode_options or {}
        run_whisper_command(
            audio_file=str(request.audio_file),
            lang=request.lang,
            output_dir=str(request.output_dir),
            initial_prompt=request.initial_prompt,
            autocorrect=request.autocorrect,
            model_path=request.local_model_path,
            split_on_punc=request.split_on_punc,
            llm_correct=request.llm_correct,
            llm_backend=request.llm_backend,
            llm_model=request.llm_model,
            llm_timeout_sec=request.llm_timeout_sec,
            llm_glossary=request.llm_glossary,
            skip_postprocess=request.skip_postprocess,
            **decode_options,
        )


def _build_multipart_form_data(
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
) -> tuple[bytes, str]:
    boundary = f"----WhisperWorkbench{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
        )
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_path.name}"\r\n'
        ).encode("utf-8")
    )
    chunks.append(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    chunks.append(file_path.read_bytes())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    return body, boundary


def _parse_groq_error(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        raw = ""
    details: list[str] = []
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                if isinstance(err.get("message"), str):
                    details.append(f"message={err['message']}")
                if isinstance(err.get("type"), str):
                    details.append(f"type={err['type']}")
                if isinstance(err.get("code"), str):
                    details.append(f"code={err['code']}")
            elif isinstance(payload.get("message"), str):
                details.append(f"message={payload['message']}")

    if exc.code == 413:
        base = "Groq rejected the file as too large (413). Prepare a smaller audio file."
    elif exc.code in {401, 403}:
        base = f"Groq auth/permission error ({exc.code}). Verify GROQ_API_KEY and model access."
    else:
        base = f"Groq API error {exc.code}: {exc.reason}"

    if details:
        return f"{base} Details: " + "; ".join(details)
    if raw:
        return f"{base} Raw: {raw.strip()}"
    return base


def _call_groq_transcriptions_api(
    audio_file: Path,
    model: str,
    timeout_sec: int,
    lang: str | None,
    prompt: str | None,
) -> dict[str, Any]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for --backend groq.")

    fields = {"model": model, "response_format": "verbose_json"}
    if lang:
        fields["language"] = lang
    if prompt:
        fields["prompt"] = prompt

    body, boundary = _build_multipart_form_data(fields, "file", audio_file)
    request = urllib.request.Request(
        GROQ_TRANSCRIPTIONS_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "whisper-workbench/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_parse_groq_error(exc)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Groq network error: {exc.reason}. "
            "Check connectivity or increase --groq-timeout-sec."
        ) from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Groq returned a non-JSON response.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Groq returned an unexpected JSON structure.")
    return data


class GroqWhisperBackend:
    """Remote transcription backend using Groq's OpenAI-compatible endpoint."""

    name = "groq"

    def transcribe(self, request: TranscribeRequest) -> None:
        payload = _call_groq_transcriptions_api(
            audio_file=request.audio_file,
            model=request.groq_model,
            timeout_sec=request.groq_timeout_sec,
            lang=request.lang,
            prompt=request.initial_prompt,
        )

        segments = payload.get("segments")
        if not isinstance(segments, list):
            raise RuntimeError(
                "Groq response did not include 'segments'. "
                "Use a supported model and response format."
            )

        file_name = remove_16khz_suffix(str(request.audio_file.resolve()))
        output_base = request.output_dir / f"{file_name}_{request.lang}"
        write_srt_txt_from_segments(output_base=output_base, segments=segments)
        if not request.skip_postprocess:
            postprocess_transcription_outputs(
                output_base=output_base,
                split_on_punc=request.split_on_punc,
                llm_correct=request.llm_correct,
                llm_backend=request.llm_backend,
                llm_model=request.llm_model,
                llm_timeout_sec=request.llm_timeout_sec,
                llm_glossary=request.llm_glossary,
                autocorrect=request.autocorrect,
            )
