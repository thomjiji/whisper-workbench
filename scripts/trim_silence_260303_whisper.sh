#!/usr/bin/env bash
set -euo pipefail

# Silence trim preset used in this project:
# - start_threshold/stop_threshold: -40dB
# - keep speech-safe pauses with start_duration=0.3s, stop_duration=0.5s

INPUT="usage/geekshootjack/260303-whisper/2026-03-03_从whisper聊开_all.m4a.mp3"
OUTPUT="usage/geekshootjack/260303-whisper/2026-03-03_从whisper聊开_all.m4a_nosilence.mp3"

ffmpeg -y -i "$INPUT" \
  -af "silenceremove=start_periods=1:start_duration=0.3:start_threshold=-40dB:stop_periods=-1:stop_duration=0.5:stop_threshold=-40dB" \
  -c:a libmp3lame -b:a 128k \
  "$OUTPUT"

echo "Done: $OUTPUT"
