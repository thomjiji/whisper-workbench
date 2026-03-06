# whisper-workbench

Python wrapper scripts for local [whisper.cpp](https://github.com/ggerganov/whisper.cpp) and Groq Whisper API transcription workflows.

## Features

- Batch transcription of audio files using local whisper.cpp
- Optional remote transcription backend via Groq Whisper API
- Automatic audio conversion to 16kHz mono WAV (required by whisper.cpp)
- SRT and TXT subtitle output
- Optional initial prompt injection (`--prompt-file`) for whisper-cli
- Automatic autocorrect post-processing for generated `.txt` and `.srt` files

## Agent-Native Workflow

This repository uses an agent-native document workflow to keep multi-agent coding aligned.

Document graph:

```text
.codex/AGENTS.md  ->  .codex/TASKS.md  ->  .codex/TODO.md
          \                                   |
           \-------------------------------> .codex/ISSUES.md
```

Responsibilities:

- `.codex/AGENTS.md`: root collaboration protocol, quality gates, and workflow rules.
- `.codex/TASKS.md`: medium/long-horizon task backlog with acceptance criteria.
- `.codex/TODO.md`: short-horizon execution board (`Now/Next/Later/Blocked`).
- `.codex/ISSUES.md`: known problems, repro steps, and workarounds.

Default collaboration loop:

1. Read `.codex/AGENTS.md`.
2. Pick or update one task in `.codex/TASKS.md`.
3. Move active work into `.codex/TODO.md` `Now`.
4. Implement and verify.
5. Update status in `.codex/TASKS.md`/`.codex/TODO.md` and log new problems in `.codex/ISSUES.md`.

Cross-vendor context mapping:

- OpenAI/Codex: `AGENTS.md` style project instruction file (stored here as `.codex/AGENTS.md`).
- Anthropic/Claude: `CLAUDE.md` memory pattern is mapped to this repo's `.codex/AGENTS.md`.
- Google/Gemini: `GEMINI.md` context pattern is mapped to this repo's `.codex/AGENTS.md`.

Official references:

- OpenAI: [Introducing Codex](https://openai.com/index/introducing-codex/)
- OpenAI: [Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
- Anthropic: [How Claude remembers your project](https://code.claude.com/docs/en/memory)
- Anthropic: [Todo tracking in Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/todo-tracking)
- Google: [Introducing Gemini CLI (official blog)](https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemini-cli-open-source-ai-agent/)
- Google: [GEMINI.md context file docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md)
- Google: [Gemini CLI todos tool docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/todos.md)

## Prerequisites

- **Python 3.12+**
- **uv** - Python package/env manager
- **ffmpeg** - for audio conversion
- **whisper.cpp** - local transcription engine (setup script provided)
- **CMake** - for building whisper.cpp
- **Groq API key** - required only for `--backend groq`

## Setup

### 1. Clone this repository

```bash
git clone https://github.com/your-username/whisper-workbench.git
cd whisper-workbench
```

### 2. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Run the setup script

Setup uses one cross-platform entry command through `uv`:

This will clone whisper.cpp, build it, download a Whisper model (default: `large-v3`), and download a VAD model (default: `silero-v5.1.2`):

```bash
uv run wb-setup

# Optional: use large-v3-turbo for faster transcription
uv run wb-setup --model large-v3-turbo

# Optional: use smaller models
uv run wb-setup --model medium
uv run wb-setup --model small

# Optional: select a VAD model
uv run wb-setup --vad-model silero-v6.2.0

# Optional: skip VAD model download
uv run wb-setup --skip-vad

# Short form
uv run wb-setup -m turbo
```

### 4. Install Python dependencies

```bash
uv sync
```

## Usage

### Basic Transcription

Transcribe audio files to SRT/TXT:

```bash
uv run python main.py --help

# Single file
uv run python main.py transcribe -i audio.wav -o ./output -l en

# Multiple files
uv run python main.py transcribe -i file1.wav file2.wav -o ./output -l ja

# Use an initial prompt from a text file
uv run python main.py transcribe -i audio.wav -o ./output -l en --prompt-file ./prompt.txt

# Disable autocorrect post-processing
uv run python main.py transcribe -i audio.wav -o ./output -l en --no-autocorrect

# Use local backend with a model variant shortcut
uv run python main.py transcribe -i audio.wav -o ./output -l en --backend local --local-model turbo

# Or use an explicit local model path
uv run python main.py transcribe -i audio.wav -o ./output -l en --backend local --local-model-path /path/to/ggml-large-v3-turbo.bin

# High-accuracy decode preset (slower)
uv run python main.py transcribe -i audio.wav -o ./output -l zh --backend local --local-model turbo --decode-profile accuracy

# Legacy preset (backward-compatible with previous default knobs)
uv run python main.py transcribe -i audio.wav -o ./output -l zh --decode-profile legacy

# Split subtitle lines on punctuation (useful for Chinese readability)
uv run python main.py transcribe -i audio.wav -o ./output -l zh --split-on-punc

# Use Groq backend (requires GROQ_API_KEY; default model is whisper-large-v3)
uv run python main.py transcribe -i audio.wav -o ./output -l zh --backend groq

# Diagnose backend setup
uv run python main.py doctor
uv run python main.py doctor --backend groq
```

`transcribe` also accepts non-WAV inputs (for example `.mp3`, `.m4a`, `.mp4`).  
With `--backend local`, files are converted to temporary 16kHz mono WAV for whisper-cli and cleaned up after transcription.  
With `--backend groq`, the original input file is uploaded directly to Groq.
By default, generated `.txt` and `.srt` are post-processed with `autocorrect-py`.

### Post-Processing Pipeline

Post-processing runs in a fixed order after transcription files are written.

```text
[Backend transcription done]
            |
            v
[Write initial .srt and .txt]
            |
            v
      [--split-on-punc?]
        /            \
      Yes            No
      |               |
      v               v
[Split SRT lines]   [Keep original SRT/TXT]
[Redistribute timestamps]
[Rewrite TXT from split SRT]
        \            /
         v          v
       [--llm-correct?]
         /          \
       Yes          No
       |             |
       v             v
[LLM correct TXT]  [Skip LLM correction]
[LLM correct SRT]          |
        \                 /
         v               v
       [--no-autocorrect?]
         /              \
       No               Yes
       |                 |
       v                 v
[Autocorrect TXT]    [Skip autocorrect]
[Autocorrect SRT]           |
        \                  /
         v                v
            [Final outputs]
```

Order and behavior details:

- Step 1: Backend generates raw transcript segments and writes initial `.srt` and `.txt`.
- Step 2 (`--split-on-punc`): split SRT lines on punctuation and redistribute timestamps.
- Step 3 (`--split-on-punc`): rewrite TXT from split SRT lines so TXT and SRT stay line-aligned.
- Step 4 (`--llm-correct`): run LLM correction on TXT first, then on SRT.
- Step 5 (default): run autocorrect on TXT and SRT unless `--no-autocorrect` is set.
- Output: final `.srt` and `.txt` are the result of this ordered pipeline.

### LLM Correction Notes

- `--llm-correct` applies line-by-line correction while preserving line count and order.
- Chinese text is normalized to Simplified Chinese in the LLM correction stage.
- If `--glossary-file` is provided, glossary forms are treated as hard constraints and must be followed exactly.

### Glossary File Spec

Use a plain UTF-8 text file. Current parser behavior is "raw text prompt injection", so keep the format simple and explicit:

- One glossary entry per line.
- Each line is a canonical target form you want in final output.
- Blank lines are allowed for visual grouping.
- Do not use `:` / `->` / CSV alias syntax in the file.
- Do not add numbering, markdown, or comments.

Recommended content scope:

- Proper nouns only: people, brands, organizations, product names, works/titles.
- Include high-risk variants as separate canonical lines when needed (example: both `P.K.14` and `PK14`).
- Keep the list compact and high-confidence to reduce over-correction.

Example:

```txt
DeepMind
OpenAI
P.K.14
PK14
Dear Eloise
李高特四重奏
兵马司
```

Not recommended:

```txt
DeepMind: deep mind, deepmind
1. OpenAI
# comments
```

### Decoding Notes

- `--decode-profile balanced` (default local profile): practical speed/quality.
- `--decode-profile accuracy` (local): slower settings for difficult proper nouns.
- `--decode-profile legacy` (local): old compatible knobs (`-t 8 -sow --beam-size 5 --entropy-thold 2.8 --max-context 64`).
- `--split-on-punc`: split generated SRT lines by punctuation, re-assign timings, and rewrite TXT to one line per SRT segment (for easy 1:1 mapping).
- `balanced`/`accuracy` now also apply a bounded context window to reduce long-range repetition.

### Convert Audio to 16kHz

whisper.cpp requires 16kHz mono audio. Convert a directory of WAV files:

```bash
uv run python main.py convert --dir /path/to/wav/files
```

### Full Batch Workflow

Convert episode audio, then run batch transcription (`en` + `ja`) for all `.wav` files under `audio/<episode>`:

```bash
uv run python main.py batch --episode EP01 --base-dir ./usage
```

## Environment Variables

Override default paths with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | (unset) | API key used when `--backend groq` |
| `WHISPER_CLI_PATH` | Auto-detect from PATH or `vendor/whisper.cpp/build/bin` | Path to whisper-cli executable |
| `WHISPER_CPP_DIR` | `vendor/whisper.cpp` | Path to whisper.cpp installation |
| `WHISPER_MODEL_PATH` | `vendor/whisper.cpp/models/ggml-large-v3.bin` (falls back to turbo if v3 missing) | Path to GGML model file |
| `WHISPER_VAD_MODEL_PATH` | `vendor/whisper.cpp/models/ggml-silero-v5.1.2.bin` | Path to whisper.cpp VAD model file |

Example:

```bash
export WHISPER_CPP_DIR=/opt/whisper.cpp
export WHISPER_CLI_PATH=/opt/whisper.cpp/build/bin/whisper-cli
export WHISPER_MODEL_PATH=/opt/models/ggml-large-v3-turbo.bin
export WHISPER_VAD_MODEL_PATH=/opt/models/ggml-silero-v5.1.2.bin
export GROQ_API_KEY=your_groq_api_key
uv run python main.py transcribe -i audio.wav -o ./output --backend groq
```

## Project Structure

```
whisper-workbench/
├── .codex/
│   ├── AGENTS.md              # Root agent collaboration protocol
│   ├── TASKS.md               # Backlog with acceptance criteria
│   ├── TODO.md                # Near-term execution board
│   └── ISSUES.md              # Known issues and workarounds
├── main.py                     # Unified CLI entry point
├── scripts/
│   ├── setup_whisper_cpp.py            # Cross-platform whisper.cpp setup implementation
│   ├── audio_trim_silence.py           # Trim silence from an audio file via ffmpeg
│   ├── sync_srt_to_txt.py              # Sync SRT text lines into TXT (with line-count check)
│   ├── sync_txt_to_srt.py              # Sync TXT corrected lines back into SRT (with line-count check)
├── src/
│   ├── whisper_utils.py        # Shared whisper.cpp helpers
│   ├── transcription_backends.py # Local/Groq backend implementations
├── vendor/                     # whisper.cpp (created by setup scripts)
├── pyproject.toml
├── uv.lock
└── README.md
```

## License

MIT
