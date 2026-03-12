# Architecture

## Entry Points

- `main.py`: unified CLI entry point
- `wb-setup`: setup helper exposed from `scripts/setup_whisper_cpp.py`

The main CLI exposes five subcommands:

- `transcribe`
- `postprocess`
- `convert`
- `batch`
- `doctor`

## Core Modules

### `src/transcription_backends.py`

Defines the local `whisper.cpp` backend and the Groq backend behind a shared request model.

- Local backend shells out to `whisper-cli`
- Groq backend uses stdlib HTTP calls
- Both return timed transcript segments that feed downstream rendering and postprocess

### `src/whisper_utils.py`

Shared environment and execution helpers:

- resolve binary and model paths
- convert media to 16 kHz mono WAV
- run local whisper commands
- run autocorrect helpers

### `src/srt_utils.py`

Subtitle text and timing helpers:

- parse and write SRT/TXT pairs
- split subtitle lines on punctuation
- redistribute timestamps after splitting
- preserve 1:1 TXT-to-SRT alignment where required

### `src/postprocess.py`

Owns the ordered postprocess pipeline and any step orchestration between subtitle text files.

### `src/llm_correct.py`

Runs optional line-preserving correction through external LLM CLIs such as Gemini, Claude, or Codex.

## Pipeline

High-level flow:

1. Load media input and backend configuration
2. Transcribe via local `whisper.cpp` or Groq
3. Write initial `.srt` and `.txt`
4. Optionally run postprocess steps
5. Emit final subtitle artifacts

## Postprocess Order

The order is intentional and should not be casually changed:

1. `split` via `--split-on-punc`
2. `llm_correct_txt` via `--llm-correct`
3. `sync_txt_to_srt`
4. `autocorrect`

Key invariant:

- TXT and SRT must stay line-aligned whenever a text-sync step expects 1:1 correspondence

## Backend Notes

Local backend:

- optimized for offline or private workflows
- depends on `whisper.cpp`, model files, and optionally VAD models
- can disable VAD for more faithful subtitle timing

Groq backend:

- avoids local model setup
- requires `GROQ_API_KEY`
- sends the original input file to the Groq API

## Repository Layout

```text
whisper-workbench/
├── AGENTS.md
├── README.md
├── docs/
│   ├── README.md
│   ├── agent-workflow.md
│   ├── architecture.md
│   └── cli.md
├── main.py
├── scripts/
├── src/
├── tests/
├── usage/
└── tasks/
    └── lessons.md
```

## Documentation Ownership

- Root `README.md`: short human-facing TLDR only
- `docs/cli.md`: operational usage details and flags
- `docs/architecture.md`: implementation map and invariants
- `docs/agent-workflow.md`: collaboration process for humans and agents
