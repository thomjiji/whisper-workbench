#!/usr/bin/env bash

# Integration verification fixtures
INPUT="usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/260309/clips/杨海崧-音频-260309_00_00_58_to_00_01_45.mp3"
VERIFY_ROOT="usage/geekshootjack/连接音乐Wi-Fi-杨海崧/output/whisper_workbench/260309/test_2"
GLOSSARY="usage/geekshootjack/连接音乐Wi-Fi-杨海崧/docs/glossary_full.txt"

# 1) oneshot_full: whisper + all postprocess in one run
uv run main transcribe \
  -i "$INPUT" \
  -o "$VERIFY_ROOT/oneshot_full" \
  -l zh \
  --backend local \
  --llm-correct \
  --llm-backend codex \
  --llm-timeout-sec 600 \
  --glossary-file "$GLOSSARY" \
  --no-autocorrect \
  --no-vad

# 2) transcribe_only: whisper upstream only
# uv run main transcribe \
#   -i "$INPUT" \
#   -o "$VERIFY_ROOT/transcribe_only" \
#   -l zh \
#   --backend local \
#   --skip-postprocess

# 3) postprocess_only: downstream only on transcribe_only artifacts
# mkdir -p "$VERIFY_ROOT/postprocess_only"
# cp "$VERIFY_ROOT/transcribe_only/杨海崧-音频-260309_zh.srt" "$VERIFY_ROOT/postprocess_only/杨海崧-音频-260309_zh.srt"
# cp "$VERIFY_ROOT/transcribe_only/杨海崧-音频-260309_zh.txt" "$VERIFY_ROOT/postprocess_only/杨海崧-音频-260309_zh.txt"
# uv run main postprocess \
#   --srt "$VERIFY_ROOT/postprocess_only/杨海崧-音频-260309_zh.srt" \
#   --txt "$VERIFY_ROOT/postprocess_only/杨海崧-音频-260309_zh.txt" \
#   --llm-correct \
#   --llm-backend codex \
#   --llm-timeout-sec 600 \
#   --glossary-file "$GLOSSARY"
