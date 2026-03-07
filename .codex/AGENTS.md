# AGENTS.md

## Purpose
This repository uses an agent-native collaboration model for coding tasks.  
This file is the root instruction and navigation point for human + agent workflows.

## Canonical Docs (Read Order)
1. `.codex/AGENTS.md` (this file): rules, workflow, quality bar.
2. `.codex/TASKS.md`: medium/long-horizon task backlog and acceptance criteria.
3. `.codex/TODO.md`: near-term execution board (`Now/Next/Later/Blocked`).
4. `.codex/ISSUES.md`: known problems, repro steps, workarounds, owner/status.

## Project Snapshot
- Product: `whisper-workbench`
- Core entrypoint: `main.py`
- Primary command: `uv run python main.py transcribe ...`
- Backends: local `whisper.cpp`, remote `Groq Whisper`
- Post-process pipeline order (must stay stable):
  1. `--split-on-punc` (optional)
  2. `--llm-correct` (optional)
  3. autocorrect (default on, disabled by `--no-autocorrect`)

## Collaboration Protocol
1. Before coding: read `.codex/TASKS.md` and move one item into `.codex/TODO.md` `Now`.
2. During coding: keep one main `in_progress` task at a time.
3. After coding: update task status, acceptance evidence, and any new issue in `.codex/ISSUES.md`.
4. If user-facing behavior changes: update `README.md` in the same change.

## Quality Gates
Run after meaningful code changes:

```bash
python3 -m py_compile main.py src/whisper_utils.py src/transcription_backends.py scripts/setup_whisper_cpp.py
python3 main.py --help
python3 main.py transcribe --help
python3 main.py doctor --help
```

Recommended runtime checks:

```bash
uv run python main.py doctor --backend local
uv run python main.py doctor --backend groq
```

## Decision Rules
- Preserve existing CLI compatibility unless task explicitly says otherwise.
- Prefer smallest safe patch.
- Keep docs and implementation aligned in one PR/commit set.
- Do not repurpose `.codex/TODO.md` as a changelog.

## Cross-Vendor Mapping
- OpenAI/Codex style memory file -> `.codex/AGENTS.md`
- Anthropic/Claude style memory file (`CLAUDE.md`) -> mapped to `.codex/AGENTS.md`
- Google/Gemini style context file (`GEMINI.md`) -> mapped to `.codex/AGENTS.md`

This repo standardizes on `.codex/AGENTS.md` as the canonical context file.
