# AGENTS.md

## Source Of Truth

This repository uses GitHub Issues and the GitHub Project as the only task-tracking system.

- GitHub Issues define what we are building or fixing.
- Labels and milestones define priority and release scope.
- The GitHub Project is the planning board.
- Local markdown files must not become a second backlog.

Do not recreate `.codex/TASKS.md`, `.codex/TODO.md`, `.codex/ISSUES.md`, or any local todo board.

## Read Order

1. `AGENTS.md`
2. the active GitHub issue or pull request
3. `docs/architecture.md` and `docs/cli.md` as needed
4. `docs/plans/*.md` when a reviewed implementation plan exists

## Agentic Dev Process

### Default Loop

1. Read the target GitHub issue and confirm the acceptance criteria.
2. Inspect the relevant code before proposing a solution.
3. Decide whether the task is small enough to implement directly or needs a reviewed plan first.
4. For non-trivial work, write a plan doc under `docs/plans/`.
5. Review and refine that plan before implementation.
6. Implement according to the approved plan.
7. Run verification appropriate to the scope.
8. Update user-facing docs when behavior, setup, or workflow changes.
9. Report the result and verification evidence back on GitHub, then close the issue when done.

### When To Write A Plan First

Write a plan doc for work that:

- spans multiple files or modules
- changes architecture
- changes CLI, UI, or operator workflow
- carries meaningful regression risk
- benefits from explicit scope review before coding

Small, obvious fixes do not need a separate plan doc.

### Plan Review Rules

Plan docs live under `docs/plans/` and are for review, not tracking.

A good plan doc should include:

- background
- goal
- non-goals
- current code findings
- proposed implementation
- risks and tradeoffs
- verification plan
- open questions, if any

If implementation reveals the plan is wrong, update the plan before continuing with major changes.

## Documentation Rules

- `README.md` stays short and human-facing.
- Detailed setup, flags, architecture notes, and process detail belong in `docs/`.
- `docs/plans/` is only for reviewable plans tied to active GitHub issues.
- Do not mirror issue state inside docs.

## Local Context Files

- `CLAUDE.md` should be a symlink to `AGENTS.md` so tool-specific entry points stay aligned.
- `tasks/lessons.md` stores reusable lessons from past corrections.

These files provide guidance. They are not project management artifacts.

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

- Preserve CLI compatibility unless the issue explicitly changes it.
- Prefer simple, contained patches.
- Keep implementation and docs aligned in the same change.
- Use GitHub metadata instead of local markdown for status tracking.
