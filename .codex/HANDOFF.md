# HANDOFF.md

## Current Baseline
- Active baseline branch: `main`
- Current `main` head when this handoff was written: `bcc8ec7`
- Pre-merge checkpoint tag: `pre-merge-main-2026-03-07`
- Post-merge checkpoint tag: `post-merge-llm-diff-2026-03-07`

## What Landed
- `feat/llm-correct-diff-based` was treated as the best candidate branch and merged back into `main` through `integration/2026-03-merge-main-verification`.
- The repo now includes:
  - standalone `postprocess`
  - diff-based `llm-correct`
  - resumable postprocess state machine
  - verification helper scripts such as `run.sh` and `scripts/video_trim_ffmpeg.py`
- The agent-native task system under `.codex/` is the canonical project memory.

## Verified Flows
- Fixed verification input:
  - `usage/geekshootjack/连接音乐Wi-Fi-杨海崧/source/杨海崧-音频_first30m.mp3`
- Verification output root:
  - `usage/geekshootjack/连接音乐Wi-Fi-杨海崧/output/whisper_workbench/merge_main_verification`
- The following were run against the integration candidate before merging to `main`:
  - `oneshot_full`: `transcribe + split-on-punc + llm-correct + autocorrect`
  - `transcribe_only`: upstream Whisper only
  - `postprocess_only`: downstream-only postprocess on copied artifacts
- Result summary:
  - all three flows produced artifacts
  - `oneshot_full` and `postprocess_only` both ended with aligned `txt/srt` line counts
  - `gemini` timed out in large-batch postprocess during verification
  - `codex` completed the downstream correction path successfully

## Current Open Problems
- Canonical open issues are tracked in `.codex/ISSUES.md`.
- Highest-value current issues:
  - `I-006`: punctuation can reappear after `split-on-punc` because later postprocess steps reintroduce it
  - `I-007`: silence gaps can disappear because timing gets redistributed too aggressively
  - `I-008`: year expressions need normalization such as `8年 -> 2008年`, `9几年 -> 199几年`
- Issue IDs are stable and may be non-contiguous by design.

## Current Priority
- Primary in-progress task: `T-011`
  - redesign correction toward a Glossary-First pipeline
  - use deterministic terminology/homophone normalization before LLM
  - reduce LLM workload and instability
- Next useful follow-ups:
  - `T-012` reliability report artifact for postprocess runs
  - `T-002` glossary A/B evaluation helper
  - `T-003` punctuation split regression fixtures

## Do Not Forget
- Use `.codex/AGENTS.md`, `.codex/TASKS.md`, `.codex/TODO.md`, and `.codex/ISSUES.md` as the real handoff system.
- Do not rely on old `tasks/...` paths from historical instructions; `.codex/...` is the live system.
- `run.sh` is the practical verification entrypoint for the currently accepted merge baseline.
- Some old feature branches are now behind `main`; do not continue new work on them unless there is a specific archival/recovery reason.
