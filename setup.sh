#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_PY="$PROJECT_ROOT/scripts/setup_whisper.py"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "error: python3/python not found in PATH" >&2
    exit 1
fi

exec "$PYTHON_BIN" "$SETUP_PY" "$@"
