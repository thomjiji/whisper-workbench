from __future__ import annotations

import unittest

import main


class LocalVadArgTests(unittest.TestCase):
    def test_local_vad_defaults_off(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(
            ["transcribe", "-i", "audio.wav", "-o", "out", "--backend", "local"]
        )
        self.assertFalse(main._resolve_local_vad_setting(args))

    def test_local_vad_can_be_enabled(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(
            ["transcribe", "-i", "audio.wav", "-o", "out", "--backend", "local", "--vad"]
        )
        self.assertTrue(main._resolve_local_vad_setting(args))

    def test_local_vad_can_be_explicitly_disabled(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(
            ["transcribe", "-i", "audio.wav", "-o", "out", "--backend", "local", "--no-vad"]
        )
        self.assertFalse(main._resolve_local_vad_setting(args))

    def test_local_vad_flags_are_mutually_exclusive(self) -> None:
        parser = main.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "transcribe",
                    "-i",
                    "audio.wav",
                    "-o",
                    "out",
                    "--backend",
                    "local",
                    "--vad",
                    "--no-vad",
                ]
            )

    def test_groq_rejects_local_vad_flags(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(
            ["transcribe", "-i", "audio.wav", "-o", "out", "--backend", "groq", "--vad"]
        )
        with self.assertRaisesRegex(ValueError, "--vad/--no-vad are only valid"):
            main._validate_backend_args(args)


if __name__ == "__main__":
    unittest.main()
