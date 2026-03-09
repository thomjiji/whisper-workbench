#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: ./play.sh <media> <subtitle>" >&2
  exit 1
fi

mpv "$1" --sub-file="$2" --sub-font="Noto Sans"
