# Whisper Workbench Progress And Insights

## Scope
This document summarizes the cross-platform setup/transcription improvements, subtitle segmentation experiments, and decoding-profile tuning performed during this session.

## Timeline Of Main Changes
1. Added Windows-compatible setup support:
   - `setup.ps1` + `setup.bat`
   - README usage updates for Windows.
2. Reverted two earlier Windows hotfix commits on request, then performed a broader cross-platform refactor:
   - Unified setup implementation through `scripts/setup_whisper_cpp.py`.
   - `setup.sh` / `setup.ps1` became wrappers.
   - Added `doctor` command for environment checks.
3. Added and iterated decoding controls:
   - Introduced decode profiles (`balanced`, `accuracy`).
   - Later added `legacy` profile for backward compatibility with original stable params.
4. Prompt feature direction changed several times by request:
   - Added markdown/OpenAI prompt generation and A/B tooling.
   - Later removed OpenAI-related functionality.
   - Restored `--prompt-file` only (local file prompt, no API dependency).
5. Subtitle segmentation improvements:
   - Added optional `--split-on-punc` post-processing for SRT.
   - Implemented time-span redistribution when one SRT line is split into multiple lines.
   - Added trailing punctuation trimming for split outputs.
   - Fixed decimal splitting bug (`1.0` should not become `1` + `0`).
   - Fixed repeated/zero-duration segment issue caused by allocation/rounding edge cases.

## Current Decode Profiles
Defined in `main.py`:

- `balanced` (default):
  - `threads=8`
  - `split_on_word=True`
  - `beam_size=5`
  - `best_of=5`
  - `entropy_thold=2.8`
  - `max_context=64`
  - `no_gpu=False`
  - `no_fallback=False`

- `accuracy`:
  - `threads=8`
  - `split_on_word=True`
  - `beam_size=8`
  - `best_of=8`
  - `entropy_thold=2.6`
  - `max_context=96`
  - `max_len=80`
  - `no_gpu=False`
  - `no_fallback=False`

- `legacy` (backward compatibility):
  - `threads=8`
  - `split_on_word=True`
  - `beam_size=5`
  - `best_of=5`
  - `entropy_thold=2.8`
  - `max_context=64`
  - `no_gpu=False`
  - `no_fallback=False`

## Key Insights
1. Repetition/hallucination is mainly a decoding behavior problem, not a punctuation post-processing problem.
2. `max-context` is a primary anti-repetition knob:
   - Bounding context (`64`/`96`) tends to reduce long-range self-repetition vs unlimited context.
3. `split-on-word` tradeoff for CJK:
   - With `-sow`: can produce long lines.
   - Without `-sow`: can produce fragmented tokens.
   - Current design keeps `-sow` and makes punctuation split optional (`--split-on-punc`).
4. Punctuation splitting must be context-aware:
   - Never split decimal numbers (`1.0`).
   - Be careful with dot/comma semantics and timestamp redistribution precision.
5. OpenAI-based prompt generation is not required to improve robustness; local decode/profile tuning already gives meaningful control.

## Issues Encountered And Resolved
1. Windows subprocess decode error (`gbk`/UnicodeDecodeError) during ffmpeg stderr capture.
2. Windows App Control block (`WinError 4551`) for `whisper-cli.exe`.
3. Model path/readability failures.
4. GPU/Metal instability on macOS in some runs (`--no-gpu` workaround used in tests).
5. `--split-on-punc` early implementation bugs:
   - Invalid UTF-8 read crash -> switched to `errors="replace"`.
   - Decimal split bug (`AI 1.0`) -> split logic refined.
   - Duplicate/0ms segments -> improved time allocation + dedupe merge.

## Current CLI State
- Main commands:
  - `transcribe`
  - `convert`
  - `batch`
  - `doctor`
- `transcribe` includes:
  - `--prompt-file` (local prompt only)
  - `--decode-profile {balanced,accuracy,legacy}`
  - `--split-on-punc` (optional SRT split pass)

## Recommended Usage
1. Backward-compatible behavior (closest to original stable setup):
   - `--decode-profile legacy`
2. Default practical behavior:
   - `--decode-profile balanced`
3. Better precision with higher cost:
   - `--decode-profile accuracy`
4. If subtitle readability is more important than raw ASR segmentation:
   - Add `--split-on-punc`

## Suggested Next Validation
1. Run the same audio through all three profiles and compare:
   - repeated-line rate
   - long-line count
   - proper noun correctness
2. Compare `--split-on-punc` on/off for Chinese subtitle readability and timing acceptability.
3. If needed, add a small regression test fixture for SRT split edge cases (`1.0`, abbreviations, zero-length guard).
