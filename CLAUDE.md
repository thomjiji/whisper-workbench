# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent collaboration

This repo uses `.codex/AGENTS.md` as the canonical agent context file (shared across Claude, Codex, and Gemini). Read it before starting any task. The doc graph is:

```
.codex/AGENTS.md  →  .codex/TASKS.md  →  .codex/TODO.md
                                      →  .codex/ISSUES.md
```

## Commands

```bash
# Run the CLI
uv run main transcribe -i <audio> -o <output_dir> -l zh --backend local
uv run main postprocess --srt <file.srt> --txt <file.txt> --llm-correct
uv run main doctor

# Lint
uv run ruff check .
uv run ruff format .

# Quick import/compile check (no test suite exists)
uv run python -m py_compile main.py src/whisper_utils.py src/transcription_backends.py
uv run python -c "from src.llm_correct import llm_correct_file_in_place"
uv run python -c "from src.srt_utils import write_srt_txt_from_segments"
uv run python -c "from src.postprocess import postprocess_srt_txt_files"

# Setup whisper.cpp (builds from vendor/whisper.cpp)
uv run wb-setup
```

## Architecture

The entry point is `main.py`, which defines three subcommands (`transcribe`, `postprocess`, `convert`, `doctor`, `batch`). It delegates to:

**`src/transcription_backends.py`** — `LocalWhisperCppBackend` and `GroqWhisperBackend`, both accepting a `TranscribeRequest` dataclass. The local backend shells out to `whisper-cli`; the Groq backend uses `urllib` (no extra deps) to POST to the Groq API.

**`src/whisper_utils.py`** — Whisper environment resolution (`get_whisper_cli_path`, `get_model_path`, `get_vad_model_path`), audio conversion via ffmpeg, autocorrect helpers, and `run_whisper_command` / `batch_run_whisper_command`. Binary/model search order: `build/bin/` → `vendor/whisper.cpp/build/bin/`, and `models/` → `vendor/whisper.cpp/models/`. Override with `WHISPER_CLI_PATH`, `WHISPER_MODEL_PATH`, `WHISPER_VAD_MODEL_PATH`.

**`src/srt_utils.py`** — SRT/TXT parsing, punctuation-based splitting (`_split_srt_on_punctuation`), timestamp redistribution, and `write_srt_txt_from_segments` used by both backends.

**`src/llm_correct.py`** — LLM correction via gemini/claude/codex CLI subprocesses. Chunks input into 150-line batches (`LLM_CORRECT_CHUNK_SIZE`) processed in parallel (`LLM_CORRECT_MAX_WORKERS=4`). Backends are tried in order on failure. Each chunk prompt includes the full glossary, so the glossary substitutes for global context across chunks.

**`src/postprocess.py`** — Orchestrates the postprocess pipeline: `split` → `llm_correct_txt` → `sync_txt_to_srt` → `autocorrect`. Writes a `.postprocess_state.json` sidecar for resumable runs (`--resume`, `--from-step`, `--to-step`). Calls into `srt_utils`, `llm_correct`, and `whisper_utils.autocorrect_file_in_place`.

## Postprocess pipeline order

Fixed order — do not reorder:
1. `split` (`--split-on-punc`) — splits SRT on Chinese/English punctuation, rewrites TXT to match
2. `llm_correct_txt` (`--llm-correct`) — corrects TXT lines via LLM
3. `sync_txt_to_srt` — overwrites SRT text from corrected TXT (strict 1:1 line count enforced)
4. `autocorrect` — runs `autocorrect-py` on both TXT and SRT

The SRT and TXT files must stay in 1:1 alignment (one TXT line per SRT block). `_validate_srt_txt_line_alignment` enforces this before steps 2, 3, and 4.

## Key conventions

- **No test suite** — verify via import checks and `uv run main doctor`.
- **Circular import avoidance** — `postprocess.py` imports `autocorrect_file_in_place` from `whisper_utils` lazily (inside the function body) to avoid the cycle.
- **No new dependencies** — Groq backend uses stdlib `urllib` intentionally. LLM backends call external CLIs (`gemini`, `claude`, `codex`) via subprocess.
- **Output naming** — `<input_stem>_<lang>.srt` / `.txt`, placed in the specified output dir.
