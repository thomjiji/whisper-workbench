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
