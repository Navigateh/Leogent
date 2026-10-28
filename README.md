# Leogent

**A small agent runtime you can read, run, and reshape.**

Leogent is an open-source Python project for learning how agents work. The
first stage focuses on a complete, readable execution path from a model request
through tools, session state, memory, context compaction, and skills. The second
stage will grow the same runtime into a practical coding agent.

The project is currently implementing Milestone 0 and Milestone 1: repository
foundations, domain models, and layered configuration. Providers, MCP tools,
Agent Loop, sessions, memory storage, compaction, and TUI behavior are not part
of this milestone.

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
```

The complete offline quality gate is:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest -q
uv run python -m build
```

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

## License

MIT
