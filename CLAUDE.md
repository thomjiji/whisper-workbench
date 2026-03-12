# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent collaboration

This repo uses GitHub Issues and the GitHub Project as the only task-tracking system. Read these files before starting work:

1. `AGENTS.md`
2. `docs/agent-workflow.md`
3. `docs/architecture.md`
4. `docs/cli.md`

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

Detailed architecture and pipeline notes now live in `docs/architecture.md`.

## Key conventions

- **No local markdown backlog** — use GitHub Issues/Project for planning and status.
- **No test suite** — verify via import checks and `uv run main doctor`.
- **Circular import avoidance** — `postprocess.py` imports `autocorrect_file_in_place` from `whisper_utils` lazily (inside the function body) to avoid the cycle.
- **No new dependencies** — Groq backend uses stdlib `urllib` intentionally. LLM backends call external CLIs (`gemini`, `claude`, `codex`) via subprocess.
- **Output naming** — `<input_stem>_<lang>.srt` / `.txt`, placed in the specified output dir.
