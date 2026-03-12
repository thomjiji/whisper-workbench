# whisper-workbench

`whisper-workbench` is a subtitle-oriented transcription toolkit that wraps local `whisper.cpp` and the Groq Whisper API behind one CLI.

It is built for practical media workflows:

- transcribe audio or video into `.srt` and `.txt`
- switch between local and Groq backends
- run optional punctuation splitting, LLM correction, and autocorrect
- keep setup and operator commands simple enough for repeated editorial use

## TL;DR

Install dependencies:

```bash
uv sync
uv run wb-setup
```

Run a local transcription:

```bash
uv run main transcribe -i input.mp4 -o ./output -l zh
```

Use Groq instead:

```bash
uv run main transcribe -i input.mp4 -o ./output -l zh --backend groq
```

If subtitle timing matters more than silence trimming:

```bash
uv run main transcribe -i input.mp4 -o ./output -l zh --backend local --no-vad
```

## Docs

- [Docs Index](./docs/README.md)
- [CLI Guide](./docs/cli.md)
- [Architecture](./docs/architecture.md)
- [Agent Workflow](./docs/agent-workflow.md)

## Project Tracking

Planning now lives in GitHub Issues, Milestones, and the `whisper-workbench` GitHub Project. Local markdown backlogs were intentionally removed.

## License

MIT
