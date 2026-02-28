# whisper-workbench

Python wrapper scripts for [whisper.cpp](https://github.com/ggerganov/whisper.cpp) that streamline audio transcription workflows.

## Features

- Batch transcription of audio files using whisper.cpp
- Automatic audio conversion to 16kHz mono WAV (required by whisper.cpp)
- SRT and TXT subtitle output
- Optional initial prompt injection (`--prompt-file`) for whisper-cli
- Automatic autocorrect post-processing for generated `.txt` and `.srt` files

## Prerequisites

- **Python 3.12+**
- **uv** - Python package/env manager
- **ffmpeg** - for audio conversion
- **whisper.cpp** - the transcription engine (setup script provided)
- **CMake** - for building whisper.cpp

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

This will clone whisper.cpp, build it, and download a model (default: `large-v3`):

```bash
chmod +x setup.sh
./setup.sh

# Optional: use large-v3-turbo for faster transcription
./setup.sh --model large-v3-turbo

# Short form
./setup.sh -m turbo
```

On Windows (PowerShell):

```powershell
.\setup.ps1

# Optional: use large-v3-turbo for faster transcription
.\setup.ps1 --model large-v3-turbo

# Short form
.\setup.ps1 -m turbo
```

On Windows (`cmd.exe`):

```bat
setup.bat
setup.bat --model large-v3-turbo
setup.bat -m turbo
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

# Select model variant shortcut
uv run python main.py transcribe -i audio.wav -o ./output -l en --model turbo

# Or use an explicit model path (overrides --model)
uv run python main.py transcribe -i audio.wav -o ./output -l en --model-path /path/to/ggml-large-v3-turbo.bin
```

`transcribe` also accepts non-WAV inputs (for example `.mp3`, `.m4a`, `.mp4`).  
The tool automatically converts them to temporary 16kHz mono WAV files for whisper-cli, then deletes the temporary WAV files after transcription.
By default, generated `.txt` and `.srt` are post-processed with `autocorrect-py`.

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
| `WHISPER_CPP_DIR` | `vendor/whisper.cpp` | Path to whisper.cpp installation |
| `WHISPER_MODEL_PATH` | `vendor/whisper.cpp/models/ggml-large-v3.bin` | Path to GGML model file |

Example:

```bash
export WHISPER_CPP_DIR=/opt/whisper.cpp
export WHISPER_MODEL_PATH=/opt/models/ggml-large-v3-turbo.bin
uv run python main.py transcribe -i audio.wav -o ./output
```

## Project Structure

```
whisper-workbench/
├── main.py                     # Unified CLI entry point
├── setup.sh                    # Setup whisper.cpp and download model
├── setup.ps1                   # Windows PowerShell setup script
├── setup.bat                   # Windows cmd wrapper for setup.ps1
├── src/
│   ├── whisper_utils.py        # Shared whisper.cpp helpers
├── vendor/                     # whisper.cpp (created by setup scripts)
├── pyproject.toml
├── uv.lock
└── README.md
```

## License

MIT
