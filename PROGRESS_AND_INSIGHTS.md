# Archived: PROGRESS_AND_INSIGHTS

This file is kept for historical context only.  
Active agent collaboration now uses:

- `.codex/AGENTS.md` (root protocol)
- `.codex/TASKS.md` (backlog and acceptance)
- `.codex/TODO.md` (near-term execution board)
- `.codex/ISSUES.md` (known problems and workarounds)

Historical sections below may mention deprecated setup wrappers (`setup.sh`/`setup.ps1`/`setup.bat`).

---

# Agent Handoff: Whisper Workbench

## 1) Mission
Keep `whisper-workbench` stable for real-world transcription workflows:
- Local backend: `whisper.cpp`
- Remote backend: `Groq`
- Output quality pipeline: `split-on-punc` -> `llm-correct` -> `autocorrect`

This file is the operational handoff for multiple agents (not a changelog).

## 2) Current Snapshot
- Branch: `feat/groq-backend-integration`
- CLI commands: `transcribe`, `convert`, `batch`, `doctor`
- `transcribe --backend` options on this branch: `local`, `groq`
- Decode profiles: `balanced`, `accuracy`, `legacy`
- Default local profile includes VAD + suppress-nst behavior from `main.py` decode presets

## 3) Source Of Truth Files
- CLI orchestration: `main.py`
- Backends: `src/transcription_backends.py`
- whisper.cpp runtime helpers + postprocessing pipeline: `src/whisper_utils.py`
- Setup implementation (cross-platform): `scripts/setup_whisper_cpp.py`
- Setup wrappers: `setup.sh`, `setup.ps1`, `setup.bat`
- User docs: `README.md`

## 4) Non-Negotiable Behavior
- Do not break existing `local/groq` CLI flags.
- Keep postprocessing order fixed:
  1. optional `--split-on-punc`
  2. optional `--llm-correct`
  3. optional autocorrect (default on, disabled by `--no-autocorrect`)
- `--split-on-punc` must preserve 1:1 line mapping between final SRT segments and TXT lines.
- `--llm-correct` must preserve line count/order.
- Glossary terms (if provided) are hard constraints in LLM correction.

## 5) Execution Workflow For Agents
1. Plan work in a short checklist before editing.
2. Make smallest viable patch.
3. Run targeted verification commands.
4. Update this file sections 2/7/8 if behavior changed.

## 6) Verification Commands
Run these after any substantial change:

```bash
python3 -m py_compile main.py src/whisper_utils.py src/transcription_backends.py scripts/setup_whisper_cpp.py
python3 main.py --help
python3 main.py transcribe --help
python3 main.py doctor --help
```

Recommended runtime sanity checks:

```bash
# Local backend check
uv run python main.py doctor --backend local

# Groq backend check
uv run python main.py doctor --backend groq
```

## 7) Open Work Queue
- [ ] Add robust SRT merge strategy for over-fragmented subtitle lines (configurable threshold).
- [ ] Add automated A/B evaluation helper for glossary impact (term hit-rate + diff report).
- [ ] Add regression fixture set for punctuation split edge cases (`1.0`, abbreviations, zero-length guards).
- [ ] Add backend-focused smoke test script under `scripts/`.

## 8) Known Risks / Watchouts
- GPU/Metal instability can still occur on some macOS runs in `whisper.cpp`.
- Large media files can trigger backend/model/provider limits.
- Subtitle readability regressions often come from interplay of VAD + punctuation split.
- Documentation drift risk is high: update `README.md` when changing CLI behavior.

## 9) Definition Of Done (Agent Level)
A task is done only when:
- Code changed minimally and intentionally.
- Relevant commands in section 6 pass.
- README is updated if user-facing behavior changed.
- This file reflects new reality (snapshot/open queue/risks) when applicable.
