# /Users/thom/code/whisper-workbench/vendor/whisper.cpp/build/bin/whisper-cli \
#  -m /Users/thom/code/whisper-workbench/vendor/whisper.cpp/models/ggml-large-v3.bin \
#  -f "/Users/thom/code/whisper-workbench/usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/260314/杨海崧-视频_last15m_first1m.wav" \
#  -l zh \
#  -t 8 \
#  -osrt \
#  -otxt \
#  -ojf \
#  -ocsv \
#  -of "/Users/thom/code/whisper-workbench/usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/260314/out3/杨海崧-视频_last15m" \
#  --split-on-word \
#  --max-len 1 \
#  --beam-size 5 \
#  --entropy-thold 2.8 \
#  --max-context 64 \
#  --suppress-nst \
#  --vad \
#  --vad-model "/Users/thom/code/whisper-workbench/vendor/whisper.cpp/models/ggml-silero-v5.1.2.bin" \

# /Users/thom/code/whisper-workbench/vendor/whisper.cpp/build/bin/whisper-cli \
#  -m /Users/thom/code/whisper-workbench/vendor/whisper.cpp/models/ggml-large-v3.bin \
#  -f "/Users/thom/code/whisper-workbench/usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/260314/杨海崧-视频_last15m.wav" \
#  -l zh \
#  -t 8 \
#  -osrt \
#  -otxt \
#  -of "/Users/thom/code/whisper-workbench/usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/260314/out4/杨海崧-视频_last15m.wav" \
#  --max-len 12 \
#  --beam-size 5 \
#  --entropy-thold 2.8 \
#  --max-context 64 \
#  --suppress-nst \
#  --vad \
#  --vad-model "/Users/thom/code/whisper-workbench/vendor/whisper.cpp/models/ggml-silero-v5.1.2.bin" \

# Transcript-style run for long readable TXT paragraphs instead of subtitle-width lines.
# Note: this whisper-cli build expects an audio file, so extract WAV from the MP4 first.
ffmpeg -y \
 -i "/Users/thom/code/whisper-workbench/usage/geekshootjack/张小珺/133-谢赛宁/source/133-谢赛宁.mp4" \
 -vn \
 -ac 1 \
 -ar 16000 \
 "/Users/thom/code/whisper-workbench/usage/geekshootjack/张小珺/133-谢赛宁/output/133-谢赛宁_16k.wav"

/Users/thom/code/whisper-workbench/vendor/whisper.cpp/build/bin/whisper-cli \
 -m /Users/thom/code/whisper-workbench/vendor/whisper.cpp/models/ggml-large-v3.bin \
 -f "/Users/thom/code/whisper-workbench/usage/geekshootjack/张小珺/133-谢赛宁/output/133-谢赛宁_16k.wav" \
 -l zh \
 -t 8 \
 -otxt \
 -ojf \
 -of "/Users/thom/code/whisper-workbench/usage/geekshootjack/张小珺/133-谢赛宁/output/133-谢赛宁_transcript" \
 --beam-size 5 \
 --best-of 5 \
 --entropy-thold 2.8 \
 --max-context 128 \
 --suppress-nst \
 --vad \
 --vad-model "/Users/thom/code/whisper-workbench/vendor/whisper.cpp/models/ggml-silero-v5.1.2.bin" \
 --vad-min-silence-duration-ms 1200 \
 --vad-speech-pad-ms 200 \
 --vad-max-speech-duration-s 45
