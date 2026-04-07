#!/usr/bin/env bash

set -euo pipefail

DEFAULT_GLOSSARY="usage/geekshootjack/连接音乐Wi-Fi/杨海崧/docs/glossary.txt"

usage() {
  cat <<'EOF'
Usage:
  ./run.sh oneshot_full <input> <output_path> [glossary]
  ./run.sh transcribe_only <input> <output_path>
  ./run.sh postprocess_only <srt> <txt> [glossary]
EOF
}

MODE="${1:-}"

if [[ -z "$MODE" ]]; then
  usage
  exit 1
fi

case "$MODE" in
  oneshot_full)
    if [[ $# -lt 3 || $# -gt 4 ]]; then
      usage
      exit 1
    fi
    INPUT="$2"
    OUTPUT_PATH="$3"
    GLOSSARY="${4:-$DEFAULT_GLOSSARY}"
    uv run main transcribe \
      -i "$INPUT" \
      -o "$OUTPUT_PATH" \
      -l zh \
      --backend local \
      --local-model large-v3 \
      --llm-correct \
      --llm-backend codex \
      --llm-timeout-sec 600 \
      --glossary-file "$GLOSSARY" \
      --no-autocorrect
    ;;
  transcribe_only)
    if [[ $# -ne 3 ]]; then
      usage
      exit 1
    fi
    INPUT="$2"
    OUTPUT_PATH="$3"
    uv run main transcribe \
      -i "$INPUT" \
      -o "$OUTPUT_PATH" \
      -l zh \
      --backend local \
      --skip-postprocess
    ;;
  postprocess_only)
    if [[ $# -lt 3 || $# -gt 4 ]]; then
      usage
      exit 1
    fi
    SRT_PATH="$2"
    TXT_PATH="$3"
    GLOSSARY="${4:-$DEFAULT_GLOSSARY}"
    uv run main postprocess \
      --srt "$SRT_PATH" \
      --txt "$TXT_PATH" \
      --llm-correct \
      --llm-backend codex \
      --llm-timeout-sec 600 \
      --glossary-file "$GLOSSARY"
    ;;
  *)
    usage
    exit 1
    ;;
esac
