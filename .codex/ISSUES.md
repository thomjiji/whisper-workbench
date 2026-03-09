# ISSUES.md

## Issue Log

| IssueID | Symptom | Impact | Repro | Workaround | Owner | Status |
|---|---|---|---|---|---|---|
| I-001 | CMake build fails after moving repo path (`CMakeCache.txt` path mismatch) | `wb-setup` cannot build `whisper.cpp` | Run setup in a relocated clone with stale `vendor/whisper.cpp/build` cache | Remove `vendor/whisper.cpp/build` and rebuild | human | open |
| I-003 | SenseVoice/FunASR run may not return timestamps | Cannot generate strict sentence-level SRT | Run SenseVoice combo lacking timestamp output | Use local/groq backend for timestamped subtitle workflows | agent | open |
| I-006 | `--split-on-punc` result still contains punctuation in final SRT after full postprocess | User expectation mismatch; final subtitle punctuation style is unstable across runs | Run oneshot full flow (`split -> llm-correct -> sync -> autocorrect`) and inspect lines like `对，你做，你存在，谁做谁存在` | Current behavior is expected because LLM/autocorrect can reintroduce punctuation after split; requires a final punctuation-normalize pass if punctuation-free output is desired | agent | open |
| I-007 | Subtitle timing can get "filled in" across silence, pulling later subtitle start times earlier so pauses disappear | Timeline quality degrades; real no-speech gaps are lost and subtitle pacing becomes unnatural | Inspect generated SRT on long-form interview material where speakers pause; timeline appears densely packed with little or no silence | Use local `--no-vad` for timing-sensitive subtitle runs; default local behavior still keeps VAD on for silence trimming / anti-hallucination | agent | open |
| I-008 | Year expressions are not normalized consistently (`8年` vs `2008年`, `9几年` vs `199几年`) | Transcript readability and factual clarity suffer, especially for temporal references | Inspect corrected TXT/SRT on interview content with year mentions | Fixed via minimal deterministic TXT postprocess + TXT->SRT sync; larger canonical timed-transcript postprocess refactor remains tracked as T-013 | agent | resolved |

## Add New Issue Template
Use this format when adding entries:

```text
| I-XXX | Symptom | Impact | Repro | Workaround | Owner | Status |
```
