# Issue I-001 Plan

## Background

GitHub issue `#1` reports that `uv run wb-setup` can fail after the repository is moved or cloned into a different absolute path while reusing an existing `vendor/whisper.cpp/build` directory.

The likely root cause is a stale `build/CMakeCache.txt` that still points at the previous source or build directory.

## Goal

Make `wb-setup` recover automatically from a stale CMake cache caused by repository relocation.

## Non-Goals

- redesign the overall `wb-setup` flow
- change model download behavior
- add general-purpose CMake cache management flags

## Current Code Findings

- `scripts/setup_whisper_cpp.py` currently runs `cmake -B build` and `cmake --build build` directly.
- There is no preflight check for `build/CMakeCache.txt`.
- There is no targeted retry path when CMake metadata references an old absolute path.

## Proposed Implementation

1. Add a helper that inspects `vendor/whisper.cpp/build/CMakeCache.txt`.
2. Parse the cache for source/build directory values that can become stale after relocation.
3. If the cached paths do not match the current `whisper.cpp` source/build directories, treat the build tree as stale.
4. Remove the stale `build` directory before invoking CMake, with a clear console message explaining why.
5. Keep normal setup behavior unchanged when the cache matches the current location.

## Risks And Tradeoffs

- Removing the build directory discards previous build artifacts, but that is already the current manual workaround and is safer than continuing with a broken cache.
- Cache parsing should stay conservative and only trigger rebuilds on clear path mismatches.

## Verification Plan

1. Add targeted unit tests for stale cache detection using temporary directories.
2. Verify that matching cache paths do not trigger cleanup.
3. Verify that mismatched source/build paths do trigger cleanup.
4. Run the relevant test file plus a lightweight CLI/help check if needed.
