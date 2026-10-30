# Leogent

**A small agent runtime you can read, run, and reshape.**

Leogent is an open-source Python project for learning how agents work. The
first stage focuses on a complete, readable execution path from a model request
through tools, session state, memory, context compaction, and skills. The second
stage will grow the same runtime into a practical coding agent.

Milestones 0 through 2 currently provide repository foundations, domain models,
layered configuration, OpenAI-compatible and Anthropic providers, streaming
responses, and the single-turn `leogent run --no-tui` command. MCP tools, the
Agent Loop, sessions, memory storage, compaction, and TUI behavior remain future
milestones.

> [!WARNING]
> Leogent does not yet provide a sandbox or a security boundary. Models and MCP
> servers will run with the permissions of the current process. Only use
> trusted configuration and tools.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

## Development

```bash
uv sync --extra dev
uv run leogent version
uv run pytest
uv run ruff check .
uv run pyright
uv run leogent run "Explain an agent loop" --no-tui
```

The complete offline quality gate is:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest -q
uv run python -m build
```

## Documentation

The tutorial site uses MkDocs Material:

```bash
uv sync --extra docs
uv run mkdocs serve
uv run mkdocs build --strict
```

Open `http://127.0.0.1:8000` after starting the development server.

## Configuration

Leogent reads a global JSON configuration and may override it with
`.leogent/config.json` in the current project. API keys are referenced by
environment variable name:

```json
{
  "default_provider": "local",
  "providers": {
    "local": {
      "type": "openai-compatible",
      "base_url": "http://localhost:11434/v1",
      "model": "qwen2.5-coder:7b"
    }
  }
}
```

Never put an actual secret in a configuration file. The data directory can be
overridden with `LEOGENT_HOME`, and `LEOGENT_DEFAULT_PROVIDER` selects a
provider after configuration merging. Relative Transformers model paths are
resolved from the configuration file that supplied the path.

## Providers

Milestone 2 supports OpenAI-compatible HTTP services and the native Anthropic
Messages API. Select a provider with `--provider`; otherwise the configured
`default_provider` is used.

```bash
leogent run "What is an agent loop?" --no-tui
leogent run "What is an agent loop?" --no-tui --no-stream
leogent run "hello" --provider local --no-tui
```

Provider tests use HTTPX mock transports and make no network calls by default.
Run the optional live acceptance test after configuring a real model:

```bash
uv run pytest -m live tests/integration/test_live_provider.py -v
```

Read the detailed [Milestone 2 provider tutorial](docs/tutorials/milestone-2.md)
for the request/response code path, streaming parser, Anthropic content blocks,
and CLI wiring.

## License

MIT
