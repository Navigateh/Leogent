# Contributing to Leogent

Leogent is in an early teaching-oriented development phase. Keep changes small,
readable, and covered by behavior-focused tests.

## Local setup

```bash
uv sync --extra dev
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run pyright
```

## Change guidelines

- Keep the `domain` package independent from infrastructure.
- Do not store API keys in JSON, fixtures, source code, or logs.
- Add tests before behavior changes.
- Keep Milestone status in `todolist.md` accurate.
- Explain user-visible behavior and test coverage in pull requests.
