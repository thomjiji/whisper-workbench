# TODO.md

## Now
- [T-011] Design Glossary-First correction pipeline (deterministic terminology/homophone normalization before LLM), define interfaces and rollout plan.

## Next
- [T-012] Add postprocess reliability report artifact (`*.postprocess_report.json`) with fallback/chunk stats.
- [T-002] Add glossary A/B evaluation helper.
- [T-004] Add backend smoke-test script under `scripts/`.
- [T-003] Add punctuation split regression fixtures.

## Later
- [T-001] Add robust SRT merge strategy for over-fragmented subtitle lines.
- [T-006] Add glossary-driven homophone normalization without manual alias mapping.

## Blocked
- (empty)

## Recently Completed
- [T-009] Hardened LLM correction with structured parsing + backend fallback + chunk degradation.
- [T-010] Added resumable postprocess execution (`--resume`, `--from-step`, `--to-step`) with state persistence.

## Usage Rules
- Keep only near-term execution items here (roughly 1-2 weeks).
- Every line must reference a task ID from `.codex/TASKS.md`.
- Allow only one main `in_progress` task in `Now`.
