# uv run main transcribe \
#   -i "usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/杨海崧-音频_first10m.mp3" \
#   -o "usage/geekshootjack/连接音乐Wi-Fi-杨海崧/output/full_transcribe" \
#   -l zh \
#   --backend local \
#   --local-model turbo \
#   --split-on-punc \
#   --llm-correct \
#   --llm-backend gemini \
#   --llm-timeout-sec 600 \
#   --no-autocorrect \
#   --glossary-file "usage/geekshootjack/连接音乐Wi-Fi-杨海崧/docs/glossary_full.txt"

# uv run main transcribe \
#   -i "usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/杨海崧-视频_last15m.mp4" \
#   -o "usage/geekshootjack/连接音乐Wi-Fi-杨海崧/output/whisper_workbench/full_process_1" \
#   -l zh \
#   --backend local \
#   --skip-postprocess

uv run main postprocess \
  --srt "usage/geekshootjack/连接音乐Wi-Fi-杨海崧/output/whisper_workbench/gsj-5_whisper_process/杨海崧-音频_musicmasked_zh.srt" \
  --txt "usage/geekshootjack/连接音乐Wi-Fi-杨海崧/output/whisper_workbench/gsj-5_whisper_process/杨海崧-音频_musicmasked_zh.txt" \
  --llm-correct \
  --llm-backend codex \
  --glossary-file="usage/geekshootjack/连接音乐Wi-Fi-杨海崧/docs/glossary_full.txt"
