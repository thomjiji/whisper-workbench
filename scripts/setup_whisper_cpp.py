#!/usr/bin/env python3
"""Cross-platform setup for whisper.cpp and model download."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def normalize_model(model: str) -> tuple[str, str]:
    normalized = model.strip().lower()
    aliases: dict[str, str] = {
        "large-v3": "large-v3",
        "v3": "large-v3",
        "large-v3-turbo": "large-v3-turbo",
        "turbo": "large-v3-turbo",
        "medium": "medium",
        "medium.en": "medium.en",
        "small": "small",
        "small.en": "small.en",
    }
    model_variant = aliases.get(normalized)
    if not model_variant:
        raise ValueError(
            "unsupported model "
            f"'{model}' "
            "(use large-v3/v3, large-v3-turbo/turbo, medium[/medium.en], small[/small.en])"
        )
    return model_variant, f"ggml-{model_variant}.bin"


def normalize_vad_model(vad_model: str) -> tuple[str, str]:
    normalized = vad_model.strip().lower()
    aliases: dict[str, str] = {
        "silero-v5.1.2": "silero-v5.1.2",
        "v5": "silero-v5.1.2",
        "silero-v6.2.0": "silero-v6.2.0",
        "v6": "silero-v6.2.0",
    }
    model_variant = aliases.get(normalized)
    if not model_variant:
        raise ValueError(
            "unsupported VAD model "
            f"'{vad_model}' "
            "(use silero-v5.1.2/v5 or silero-v6.2.0/v6)"
        )
    return model_variant, f"ggml-{model_variant}.bin"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    try:
        subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)
    except FileNotFoundError as exc:
        tool = cmd[0] if cmd else "<unknown>"
        raise RuntimeError(
            f"Required command not found: {tool}. "
            f"Install it and ensure it is in PATH. failed_cmd={cmd}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Command failed (exit={exc.returncode}): {cmd}. "
            "See command output above for the root cause."
        ) from exc


def has_command(name: str) -> bool:
    return shutil.which(name) is not None


def find_whisper_cli(whisper_cpp_dir: Path) -> Path:
    build_bin = whisper_cpp_dir / "build" / "bin"
    if os.name == "nt":
        candidates = [
            build_bin / "Release" / "whisper-cli.exe",
            build_bin / "RelWithDebInfo" / "whisper-cli.exe",
            build_bin / "Debug" / "whisper-cli.exe",
            build_bin / "whisper-cli.exe",
        ]
    else:
        candidates = [build_bin / "whisper-cli"]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def _load_cmake_cache_entries(cache_path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    if not cache_path.is_file():
        return entries

    for raw_line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        key_with_type, sep, value = line.partition("=")
        if not sep or ":" not in key_with_type:
            continue
        key, _, _entry_type = key_with_type.partition(":")
        entries[key] = value

    return entries


def _normalized_path_string(path: Path | str) -> str:
    return os.path.normcase(
        os.path.normpath(str(Path(path).expanduser().resolve(strict=False)))
    )


def get_stale_cmake_cache_reason(source_dir: Path, build_dir: Path) -> str | None:
    cache_path = build_dir / "CMakeCache.txt"
    entries = _load_cmake_cache_entries(cache_path)
    if not entries:
        return None

    expected_paths = {
        "CMAKE_HOME_DIRECTORY": source_dir,
        "CMAKE_CACHEFILE_DIR": build_dir,
    }
    mismatches: list[str] = []
    for key, expected_path in expected_paths.items():
        cached_value = entries.get(key)
        if not cached_value:
            continue
        if _normalized_path_string(cached_value) != _normalized_path_string(expected_path):
            mismatches.append(
                f"{key} cached={cached_value} expected={expected_path}"
            )

    if not mismatches:
        return None

    return "; ".join(mismatches)


def prepare_build_dir(whisper_cpp_dir: Path) -> None:
    build_dir = whisper_cpp_dir / "build"
    stale_reason = get_stale_cmake_cache_reason(
        source_dir=whisper_cpp_dir,
        build_dir=build_dir,
    )
    if stale_reason is None:
        return

    print("==> Detected stale CMake cache from a previous repo path.")
    print(f"==> Removing {build_dir} and rebuilding whisper.cpp...")
    print(f"==> Stale cache details: {stale_reason}")
    shutil.rmtree(build_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set up whisper.cpp (clone/update/build/download model)."
    )
    parser.add_argument(
        "--model",
        "-m",
        default="large-v3",
        help=(
            "Whisper model variant: "
            "large-v3|v3|large-v3-turbo|turbo|medium|medium.en|small|small.en"
        ),
    )
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Do not run git pull when vendor/whisper.cpp already exists.",
    )
    parser.add_argument(
        "--vad-model",
        default="silero-v5.1.2",
        help="VAD model variant: silero-v5.1.2|v5|silero-v6.2.0|v6",
    )
    parser.add_argument(
        "--skip-vad",
        action="store_true",
        help="Do not download whisper.cpp VAD model.",
    )
    args = parser.parse_args()

    required_tools = ["git", "cmake"]
    missing_tools = [tool for tool in required_tools if not has_command(tool)]
    if missing_tools:
        print(
            "error: missing required command(s): "
            + ", ".join(missing_tools)
            + ". Install them first.",
            file=sys.stderr,
        )
        return 2

    try:
        model_variant, model_name = normalize_model(args.model)
        vad_variant, vad_name = normalize_vad_model(args.vad_model)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parent.parent
    vendor_dir = project_root / "vendor"
    whisper_cpp_dir = vendor_dir / "whisper.cpp"

    print("==> Setting up whisper.cpp...")
    print(f"==> Model variant: {model_variant} ({model_name})")
    if args.skip_vad:
        print("==> VAD setup skipped")
    else:
        print(f"==> VAD model variant: {vad_variant} ({vad_name})")

    vendor_dir.mkdir(parents=True, exist_ok=True)

    if not whisper_cpp_dir.exists():
        print("==> Cloning whisper.cpp...")
        run(["git", "clone", "https://github.com/ggerganov/whisper.cpp.git", str(whisper_cpp_dir)])
    elif not args.skip_update:
        print("==> whisper.cpp already cloned, updating...")
        run(["git", "-C", str(whisper_cpp_dir), "pull"])
    else:
        print("==> whisper.cpp already cloned, skipping update")

    print("==> Building whisper.cpp...")
    prepare_build_dir(whisper_cpp_dir)
    run(["cmake", "-B", "build"], cwd=whisper_cpp_dir)
    run(["cmake", "--build", "build", "--config", "Release"], cwd=whisper_cpp_dir)

    model_path = whisper_cpp_dir / "models" / model_name
    if not model_path.exists():
        print(f"==> Downloading {model_name} model...")
        if os.name == "nt":
            download_cmd = whisper_cpp_dir / "models" / "download-ggml-model.cmd"
            run(["cmd", "/c", str(download_cmd), model_variant], cwd=whisper_cpp_dir / "models")
        else:
            download_sh = whisper_cpp_dir / "models" / "download-ggml-model.sh"
            run([str(download_sh), model_variant], cwd=whisper_cpp_dir / "models")
    else:
        print(f"==> Model {model_name} already exists")

    vad_path = whisper_cpp_dir / "models" / vad_name
    if args.skip_vad:
        print("==> Skipping VAD model download")
    elif not vad_path.exists():
        print(f"==> Downloading VAD model {vad_name}...")
        if os.name == "nt":
            download_cmd = whisper_cpp_dir / "models" / "download-vad-model.cmd"
            run(["cmd", "/c", str(download_cmd), vad_variant], cwd=whisper_cpp_dir / "models")
        else:
            download_sh = whisper_cpp_dir / "models" / "download-vad-model.sh"
            run([str(download_sh), vad_variant], cwd=whisper_cpp_dir / "models")
    else:
        print(f"==> VAD model {vad_name} already exists")

    whisper_cli = find_whisper_cli(whisper_cpp_dir)

    print("\n==> Setup complete!\n")
    print(f"whisper.cpp built at: {whisper_cli}")
    print(f"Model downloaded to:  {model_path}")
    if not args.skip_vad:
        print(f"VAD model at:         {vad_path}")
    print("\nOptional environment overrides:")
    print(f"  WHISPER_CPP_DIR={whisper_cpp_dir}")
    print(f"  WHISPER_MODEL_PATH={model_path}")
    if not args.skip_vad:
        print(f"  WHISPER_VAD_MODEL_PATH={vad_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
