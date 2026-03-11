from __future__ import annotations

import unittest
from unittest.mock import patch

import src.llm_correct as llm_correct


class LlmCorrectChunkingTests(unittest.TestCase):
    def test_large_chunk_degrades_into_smaller_subchunks(self) -> None:
        lines = [f"line {i}" for i in range(1, 401)]

        def fake_once(
            lines: list[str],
            backend: str,
            model: str | None,
            timeout_sec: int,
            glossary: str | None = None,
            line_offset: int = 1,
        ) -> list[str]:
            if len(lines) > 200:
                raise RuntimeError("payload too large")
            return [f"{line} [ok]" for line in lines]

        with patch.object(llm_correct, "_llm_correct_lines_once", side_effect=fake_once):
            corrected, failures = llm_correct._llm_correct_lines_chunked(
                lines=lines,
                backend="codex",
                model=None,
                timeout_sec=60,
                chunk_size=400,
            )

        self.assertEqual(failures, 0)
        self.assertEqual(len(corrected), 400)
        self.assertTrue(all(line.endswith("[ok]") for line in corrected))

    def test_small_chunk_failure_keeps_original(self) -> None:
        lines = [f"line {i}" for i in range(1, 51)]

        def always_fail(
            lines: list[str],
            backend: str,
            model: str | None,
            timeout_sec: int,
            glossary: str | None = None,
            line_offset: int = 1,
        ) -> list[str]:
            raise RuntimeError("backend down")

        with patch.object(llm_correct, "_llm_correct_lines_once", side_effect=always_fail):
            corrected, failures = llm_correct._llm_correct_lines_chunked(
                lines=lines,
                backend="codex",
                model=None,
                timeout_sec=60,
                chunk_size=50,
            )

        self.assertEqual(failures, 1)
        self.assertEqual(corrected, lines)


if __name__ == "__main__":
    unittest.main()
