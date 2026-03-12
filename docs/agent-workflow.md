# Agent Workflow

## Source of Truth

This repository does not maintain a local markdown backlog anymore.

- GitHub Issues are the canonical task records
- The GitHub Project is the canonical planning board
- Milestones and labels define release scope and priority

Do not recreate `.codex/TASKS.md`, `.codex/TODO.md`, or `.codex/ISSUES.md`.

## Local Context Files

- `AGENTS.md`: short entry point for agent tooling
- `.codex/AGENTS.md`: compatibility pointer for tools that already look there
- `CLAUDE.md`: Claude-specific entry pointing back into this doc set
- `tasks/lessons.md`: lessons learned from user corrections
- `.codex/HANDOFF.md`: optional temporary handoff context

These files provide guidance. They are not project management artifacts.

## Expected Work Loop

1. Read `AGENTS.md` and this document.
2. Identify the active GitHub issue, milestone, or project item.
3. Inspect the relevant code before changing anything.
4. Implement the smallest clean fix that satisfies the issue.
5. Run verification appropriate to the scope.
6. Update docs when behavior or operator workflow changes.
7. Report results back with verification evidence.

## Documentation Rules

- `README.md` should stay short and human-readable
- Detailed setup, flags, architecture, and workflow notes belong in `docs/`
- If a behavior change affects users, update the matching `docs/*.md` page in the same change

## Verification Baseline

After meaningful code changes, prefer running:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m py_compile main.py src/whisper_utils.py src/transcription_backends.py scripts/setup_whisper_cpp.py
UV_CACHE_DIR=/tmp/uv-cache uv run main --help
UV_CACHE_DIR=/tmp/uv-cache uv run main transcribe --help
UV_CACHE_DIR=/tmp/uv-cache uv run main doctor --help
```

When backend setup is relevant, also run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run main doctor --backend local
UV_CACHE_DIR=/tmp/uv-cache uv run main doctor --backend groq
```

## Decision Rules

- Preserve CLI compatibility unless the issue explicitly changes it
- Prefer simple, contained patches
- Keep implementation and docs aligned
- Use GitHub metadata instead of local markdown for status tracking
