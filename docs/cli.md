# CLI Guide

## What This Tool Does

`whisper-workbench` wraps local `whisper.cpp` and the Groq Whisper API into one subtitle-oriented workflow. It can transcribe media files, emit `.srt` + `.txt`, and optionally run a postprocess pipeline for punctuation splitting, LLM correction, and autocorrect.

## Prerequisites

- Python 3.12+
- `uv`
- `ffmpeg`
- `CMake`
- `whisper.cpp` assets installed via `uv run wb-setup`
- `GROQ_API_KEY` only when using `--backend groq`

## Setup

Install dependencies and local models:

```bash
uv sync
uv run wb-setup
```

Useful setup variants:

```bash
uv run wb-setup --model large-v3-turbo
uv run wb-setup --model medium
uv run wb-setup --vad-model silero-v6.2.0
uv run wb-setup --skip-vad
uv run wb-setup -m turbo
```

## Main Commands

Show top-level help:

```bash
uv run main --help
```

Transcribe one file:

```bash
uv run main transcribe -i audio.wav -o ./output -l zh
```

Use Groq instead of local `whisper.cpp`:

```bash
uv run main transcribe -i audio.wav -o ./output -l zh --backend groq
```

Run local transcription with a model shortcut:

```bash
uv run main transcribe -i audio.wav -o ./output -l zh --backend local --local-model turbo
```

Disable VAD for timing-sensitive subtitle work:

```bash
uv run main transcribe -i audio.wav -o ./output -l zh --backend local --no-vad
```

Split subtitle lines on punctuation:

```bash
uv run main transcribe -i audio.wav -o ./output -l zh --split-on-punc
```

Stop after raw transcription output:

```bash
uv run main transcribe -i audio.wav -o ./output -l zh --skip-postprocess
```

Run postprocess later on an existing pair:

```bash
uv run main postprocess --srt ./output/audio_zh.srt --txt ./output/audio_zh.txt --llm-correct --autocorrect
```

Run diagnostics:

```bash
uv run main doctor
uv run main doctor --backend groq
```

Batch process an episode directory:

```bash
uv run main batch --episode EP01 --base-dir ./usage
```

Convert a directory of WAV files:

```bash
uv run main convert --dir /path/to/wav/files
```

## `transcribe` Flags

Core inputs:

- `-i, --input`: one or more audio/video files
- `-o, --output`: output directory
- `-l, --lang`: language code, default `en`

Backend selection:

- `--backend {local,groq}`
- `--local-model {large-v3,v3,large-v3-turbo,turbo,medium,medium.en,small,small.en}`
- `--local-model-path PATH`
- `--decode-profile {balanced,accuracy,legacy}`
- `--no-vad`
- `--groq-model MODEL`
- `--groq-timeout-sec SECONDS`

Postprocess controls:

- `--prompt-file FILE`
- `--split-on-punc`
- `--no-autocorrect`
- `--skip-postprocess`

LLM correction:

- `--llm-correct`
- `--llm-backend {gemini,claude,codex}`
- `--llm-model MODEL`
- `--llm-timeout-sec SECONDS`
- `--glossary-file FILE`

## Postprocess Behavior

When postprocess is enabled, the pipeline order is fixed:

1. Optional punctuation split (`--split-on-punc`)
2. Optional LLM correction (`--llm-correct`)
3. Autocorrect unless disabled (`--no-autocorrect`)

You can also run `postprocess` separately. In that mode, steps are opt-in.

## Decode Profiles

- `balanced`: default local profile for practical speed and quality
- `accuracy`: slower profile for harder proper nouns and cleaner decoding
- `legacy`: older compatible knob set

If subtitle timing matters more than silence trimming, prefer `--no-vad`.

## Input and Output Notes

- `transcribe` accepts media inputs such as `.wav`, `.mp3`, `.m4a`, and `.mp4`
- Local backend converts inputs to temporary 16 kHz mono WAV as needed
- Groq backend uploads the original input directly
- Output files are written as `<input_stem>_<lang>.srt` and `.txt`

## Glossary File Format

Use a UTF-8 text file with one canonical term per line.

Recommended:

```txt
DeepMind
OpenAI
PK14
Dear Eloise
```

Avoid alias syntax, numbering, or inline comments:

```txt
DeepMind: deep mind, deepmind
1. OpenAI
# comments
```

The glossary is meant for high-confidence proper nouns and title forms.

## Environment Variables

- `GROQ_API_KEY`: required for `--backend groq`
- `WHISPER_CLI_PATH`: override `whisper-cli` path
- `WHISPER_CPP_DIR`: override `whisper.cpp` root
- `WHISPER_MODEL_PATH`: override local GGML model path
- `WHISPER_VAD_MODEL_PATH`: override VAD model path

Example:

```bash
export WHISPER_CPP_DIR=/opt/whisper.cpp
export WHISPER_CLI_PATH=/opt/whisper.cpp/build/bin/whisper-cli
export WHISPER_MODEL_PATH=/opt/models/ggml-large-v3-turbo.bin
export WHISPER_VAD_MODEL_PATH=/opt/models/ggml-silero-v5.1.2.bin
export GROQ_API_KEY=your_groq_api_key
uv run main transcribe -i audio.wav -o ./output --backend groq
```
