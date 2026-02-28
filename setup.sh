#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./setup.sh [--model <large-v3|large-v3-turbo|v3|turbo>] [-m <...>] [-h|--help]

Options:
  --model, -m
            Whisper model variant to download (default: large-v3)
            accepted: large-v3, v3, large-v3-turbo, turbo
  -h, --help
            Show this help message
EOF
}

MODEL_VARIANT="large-v3"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model|-m)
            if [[ $# -lt 2 ]]; then
                echo "error: --model requires a value" >&2
                usage
                exit 2
            fi
            MODEL_VARIANT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

case "$MODEL_VARIANT" in
    large-v3|v3)
        MODEL_VARIANT="large-v3"
        MODEL_NAME="ggml-large-v3.bin"
        ;;
    large-v3-turbo|turbo)
        MODEL_VARIANT="large-v3-turbo"
        MODEL_NAME="ggml-large-v3-turbo.bin"
        ;;
    *)
        echo "error: unsupported model '$MODEL_VARIANT' (use large-v3/v3 or large-v3-turbo/turbo)" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR_DIR="$PROJECT_ROOT/vendor"
WHISPER_CPP_DIR="$VENDOR_DIR/whisper.cpp"

echo "==> Setting up whisper.cpp..."
echo "==> Model variant: $MODEL_VARIANT ($MODEL_NAME)"

mkdir -p "$VENDOR_DIR"

if [ ! -d "$WHISPER_CPP_DIR" ]; then
    echo "==> Cloning whisper.cpp..."
    git clone https://github.com/ggerganov/whisper.cpp.git "$WHISPER_CPP_DIR"
else
    echo "==> whisper.cpp already cloned, updating..."
    git -C "$WHISPER_CPP_DIR" pull
fi

echo "==> Building whisper.cpp..."
cd "$WHISPER_CPP_DIR"
cmake -B build
cmake --build build --config Release

MODEL_PATH="$WHISPER_CPP_DIR/models/$MODEL_NAME"
if [ ! -f "$MODEL_PATH" ]; then
    echo "==> Downloading $MODEL_NAME model..."
    ./models/download-ggml-model.sh "$MODEL_VARIANT"
else
    echo "==> Model $MODEL_NAME already exists"
fi

echo ""
echo "==> Setup complete!"
echo ""
echo "whisper.cpp built at: $WHISPER_CPP_DIR/build/bin/whisper-cli"
echo "Model downloaded to:  $MODEL_PATH"
echo ""
echo "Optional environment overrides:"
echo "  export WHISPER_CPP_DIR=$WHISPER_CPP_DIR"
echo "  export WHISPER_MODEL_PATH=$MODEL_PATH"
