# TASKS.md

## Status Legend
- `pending`: not started
- `in_progress`: actively being implemented
- `blocked`: cannot proceed due to dependency or external constraint
- `done`: accepted and completed

## Task Backlog

| ID | Title | Status | Owner | DependsOn | Acceptance |
|---|---|---|---|---|---|
| T-001 | Add robust SRT merge strategy for over-fragmented subtitle lines | pending | agent | - | Configurable merge threshold works on Chinese short-line cases and preserves timeline consistency |
| T-002 | Add glossary A/B evaluation helper | pending | agent | - | Script reports term hit-rate and diff summary between baseline and glossary-enabled runs |
| T-003 | Add punctuation split regression fixtures | pending | agent | - | Fixture set covers decimals (`1.0`), abbreviations, and zero-length guards; tests are reproducible |
| T-004 | Add backend smoke-test script under `scripts/` | pending | agent | - | One command validates local/groq preflight and emits actionable diagnostics |
| T-005 | Establish agent-native doc system (`.codex/AGENTS/.codex/TASKS/.codex/TODO/.codex/ISSUES`) | done | agent | - | Four docs exist under `.codex/`, README has workflow section, legacy progress file archived |
| T-006 | Add glossary-driven homophone normalization without manual alias mapping | pending | agent | - | Given only canonical glossary terms, pipeline can auto-normalize common Chinese homophone ASR errors (for example `宾马斯` -> `兵马司`) with measurable precision/recall guardrails |
| T-007 | Add FFmpeg music-segment detector script with configurable dB thresholds | done | agent | - | Script accepts media input, supports `>=`/`<=` dB threshold filtering, and outputs timestamped candidate segments with duration |
| T-008 | Decouple post-processing from transcription and add standalone postprocess command | done | agent | - | `transcribe --skip-postprocess` stops at upstream outputs, and `postprocess` can rerun selected downstream steps (`split/llm/autocorrect`) on existing SRT/TXT |
| T-009 | Harden LLM correction pipeline with structured parsing, backend fallback, and chunk degradation | done | agent | T-008 | LLM correction no longer depends on fragile numbered-line parsing; failures become `applied/partial_applied/fallback_kept_original` with deterministic sync TXT->SRT |
| T-010 | Add resumable postprocess state machine (`--resume/--from-step/--to-step`) | done | agent | T-008 | Postprocess writes persistent step state and supports resume/re-entry without rerunning completed steps |
| T-011 | Redesign correction architecture to Glossary-First (rule engine first, LLM second) | in_progress | agent | T-009,T-010 | Most terminology fixes are handled deterministically before LLM; LLM scope shrinks to hard cases and runtime/instability drops materially |
| T-012 | Add reliability report artifacts for postprocess runs | pending | agent | T-009 | Each run emits machine-readable report (failed chunks, fallback reasons, changed-lines count, glossary hit stats) for handoff/debug |
| T-013 | Unify postprocess around a single timed transcript representation | pending | agent | T-008,T-010 | Postprocess maintains one canonical `{start,end,text}` transcript model; split/text-normalize/llm/autocorrect all operate on it; TXT and SRT are rendered only at pipeline end |
| T-014 | Make local VAD explicit with timing-sensitive opt-out | done | agent | - | Local CLI exposes `--no-vad`; default behavior remains VAD-on for silence trimming, and timing-sensitive runs can opt out with verified improvement on the known `非常欢迎大家` segment |
