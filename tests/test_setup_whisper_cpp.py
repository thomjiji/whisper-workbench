from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.setup_whisper_cpp import get_stale_cmake_cache_reason, prepare_build_dir


class StaleCMakeCacheTests(unittest.TestCase):
    def test_matching_cache_paths_are_not_treated_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            whisper_cpp_dir = Path(temp_dir) / "vendor" / "whisper.cpp"
            build_dir = whisper_cpp_dir / "build"
            build_dir.mkdir(parents=True)
            cache_path = build_dir / "CMakeCache.txt"
            cache_path.write_text(
                "\n".join(
                    [
                        f"CMAKE_HOME_DIRECTORY:INTERNAL={whisper_cpp_dir}",
                        f"CMAKE_CACHEFILE_DIR:INTERNAL={build_dir}",
                    ]
                ),
                encoding="utf-8",
            )

            stale_reason = get_stale_cmake_cache_reason(whisper_cpp_dir, build_dir)

            self.assertIsNone(stale_reason)

    def test_source_path_mismatch_is_treated_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            whisper_cpp_dir = Path(temp_dir) / "vendor" / "whisper.cpp"
            build_dir = whisper_cpp_dir / "build"
            build_dir.mkdir(parents=True)
            cache_path = build_dir / "CMakeCache.txt"
            cache_path.write_text(
                "\n".join(
                    [
                        "CMAKE_HOME_DIRECTORY:INTERNAL=/old/repo/vendor/whisper.cpp",
                        f"CMAKE_CACHEFILE_DIR:INTERNAL={build_dir}",
                    ]
                ),
                encoding="utf-8",
            )

            stale_reason = get_stale_cmake_cache_reason(whisper_cpp_dir, build_dir)

            self.assertIsNotNone(stale_reason)
            self.assertIn("CMAKE_HOME_DIRECTORY", stale_reason)

    def test_prepare_build_dir_removes_stale_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            whisper_cpp_dir = Path(temp_dir) / "vendor" / "whisper.cpp"
            build_dir = whisper_cpp_dir / "build"
            build_dir.mkdir(parents=True)
            cache_path = build_dir / "CMakeCache.txt"
            cache_path.write_text(
                "\n".join(
                    [
                        f"CMAKE_HOME_DIRECTORY:INTERNAL={whisper_cpp_dir}",
                        "CMAKE_CACHEFILE_DIR:INTERNAL=/old/repo/vendor/whisper.cpp/build",
                    ]
                ),
                encoding="utf-8",
            )
            (build_dir / "dummy.txt").write_text("old build artifact", encoding="utf-8")

            prepare_build_dir(whisper_cpp_dir)

            self.assertFalse(build_dir.exists())


if __name__ == "__main__":
    unittest.main()
