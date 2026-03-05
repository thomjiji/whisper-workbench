# whisper-workbench

Python wrapper scripts for local [whisper.cpp](https://github.com/ggerganov/whisper.cpp) and Groq Whisper API transcription workflows.

## Features

- Batch transcription of audio files using local whisper.cpp
- Optional remote transcription backend via Groq Whisper API
- Automatic audio conversion to 16kHz mono WAV (required by whisper.cpp)
- SRT and TXT subtitle output
- Optional initial prompt injection (`--prompt-file`) for whisper-cli
- Automatic autocorrect post-processing for generated `.txt` and `.srt` files

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

Setup is implemented by a single cross-platform Python script: `scripts/setup_whisper_cpp.py`.
Wrappers `setup.sh` / `setup.ps1` / `setup.bat` call it.

This will clone whisper.cpp, build it, download a Whisper model (default: `large-v3`), and download a VAD model (default: `silero-v5.1.2`):

```bash
chmod +x setup.sh
./setup.sh

# Optional: use large-v3-turbo for faster transcription
./setup.sh --model large-v3-turbo

# Optional: use smaller models
./setup.sh --model medium
./setup.sh --model small

# Optional: select a VAD model
./setup.sh --vad-model silero-v6.2.0

# Optional: skip VAD model download
./setup.sh --skip-vad

# Short form
./setup.sh -m turbo
```

On Windows (PowerShell):

```powershell
.\setup.ps1

# Optional: use large-v3-turbo for faster transcription
.\setup.ps1 --model large-v3-turbo

# Optional: use smaller models
.\setup.ps1 --model medium
.\setup.ps1 --model small

# Optional: select a VAD model
.\setup.ps1 --vad-model silero-v6.2.0

# Optional: skip VAD model download
.\setup.ps1 --skip-vad

# Short form
.\setup.ps1 -m turbo
```

On Windows (`cmd.exe`):

```bat
setup.bat
setup.bat --model large-v3-turbo
setup.bat --model medium
setup.bat --model small
setup.bat --vad-model silero-v6.2.0
setup.bat --skip-vad
setup.bat -m turbo
```

Direct cross-platform invocation:

```bash
python scripts/setup_whisper_cpp.py --model turbo
python scripts/setup_whisper_cpp.py --model medium
python scripts/setup_whisper_cpp.py --model small
python scripts/setup_whisper_cpp.py --vad-model silero-v6.2.0
python scripts/setup_whisper_cpp.py --skip-vad
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

### LLM Correction Notes

- `--llm-correct` applies line-by-line correction while preserving line count and order.
- Chinese text is normalized to Simplified Chinese in the LLM correction stage.
- If `--glossary-file` is provided, glossary forms are treated as hard constraints and must be followed exactly.

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
├── main.py                     # Unified CLI entry point
├── setup.sh                    # Setup whisper.cpp and download model
├── setup.ps1                   # Windows PowerShell setup script
├── setup.bat                   # Windows cmd wrapper for setup.ps1
├── scripts/
│   ├── setup_whisper_cpp.py            # Cross-platform whisper.cpp setup
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
