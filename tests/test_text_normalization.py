from __future__ import annotations

import unittest

from src.text_normalization import normalize_year_expressions


class NormalizeYearExpressionsTests(unittest.TestCase):
    def test_expands_two_digit_year(self) -> None:
        self.assertEqual(normalize_year_expressions("08年"), "2008年")

    def test_expands_year_with_trailing_text(self) -> None:
        self.assertEqual(normalize_year_expressions("应该是18年吧"), "应该是2018年吧")

    def test_expands_year_suffix_variant(self) -> None:
        self.assertEqual(normalize_year_expressions("98年底"), "1998年底")

    def test_keeps_full_year(self) -> None:
        self.assertEqual(normalize_year_expressions("2008年"), "2008年")

    def test_keeps_ambiguous_spoken_year(self) -> None:
        self.assertEqual(normalize_year_expressions("八九年"), "八九年")

    def test_keeps_relative_time_phrase(self) -> None:
        self.assertEqual(normalize_year_expressions("七年前"), "七年前")


if __name__ == "__main__":
    unittest.main()
