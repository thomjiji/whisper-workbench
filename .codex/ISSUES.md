# ISSUES.md

## Issue Log

| IssueID | Symptom | Impact | Repro | Workaround | Owner | Status |
|---|---|---|---|---|---|---|
| I-001 | CMake build fails after moving repo path (`CMakeCache.txt` path mismatch) | `wb-setup` cannot build `whisper.cpp` | Run setup in a relocated clone with stale `vendor/whisper.cpp/build` cache | Remove `vendor/whisper.cpp/build` and rebuild | human | open |
| I-002 | Groq backend returns auth failure (`401/403`) | Remote transcription unavailable | Run `--backend groq` with invalid/expired key | Regenerate key and verify `GROQ_API_KEY` in active shell session | human | open |
| I-003 | SenseVoice/FunASR run may not return timestamps | Cannot generate strict sentence-level SRT | Run SenseVoice combo lacking timestamp output | Use local/groq backend for timestamped subtitle workflows | agent | open |
| I-004 | `whisper.cpp` Metal/GPU instability on some macOS setups | Runtime crashes or unstable decode | Run local backend on affected macOS GPU configuration | Retry with adjusted decode settings or CPU fallback | human | open |
| I-005 | `unrecognized arguments` when reusing `transcribe` flags with `postprocess` | User confuses command scopes and sees hard stop after transcription | Run `main postprocess ... -l zh --backend local --skip-postprocess` | Use `-l/--backend/--skip-postprocess` only with `transcribe`; `postprocess` accepts only file paths + step flags | agent | open |

## Add New Issue Template
Use this format when adding entries:

```text
| I-XXX | Symptom | Impact | Repro | Workaround | Owner | Status |
```
