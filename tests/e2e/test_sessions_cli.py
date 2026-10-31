import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

import leogent.cli.run as run_module
from leogent.cli.main import app
from leogent.config.models import AppConfig, OpenAICompatibleProviderConfig
from leogent.domain.enums import EventType
from leogent.domain.model import ModelResponse
from leogent.providers.base import ModelProvider
from leogent.providers.mock import ScriptedProvider
from leogent.sessions.sqlite import SQLiteSessionStore, default_database_path


def _config() -> AppConfig:
    return AppConfig(
        default_provider="local",
        providers={
            "local": OpenAICompatibleProviderConfig(
                type="openai-compatible",
                base_url="http://localhost:11434/v1",
                model="local-model",
            )
        },
    )


def test_run_persists_session_and_prints_identifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LEOGENT_HOME", str(tmp_path))
    provider = ScriptedProvider((ModelResponse(content="Hello"),))

    def fake_load(_: Path) -> AppConfig:
        return _config()

    def fake_create(
        _: AppConfig,
        provider_name: str | None = None,
        **_kwargs: object,
    ) -> ModelProvider:
        del provider_name
        return provider

    monkeypatch.setattr(run_module, "load_config_from_search", fake_load)
    monkeypatch.setattr(run_module, "create_provider", fake_create)

    result = CliRunner().invoke(app, ["run", "hello", "--no-tui", "--no-stream"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Hello"
    assert re.search(r"session [0-9a-f-]{36}", result.stderr)
    store = SQLiteSessionStore(default_database_path())
    try:
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert store.get_events(sessions[0].id)[-1].event_type is EventType.RUN_FINISHED
    finally:
        store.close()


def test_sessions_list_prints_persisted_session(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(database_path)
    session = store.create_session()
    store.close()

    result = CliRunner().invoke(
        app,
        ["sessions", "list", "--db", str(database_path)],
    )

    assert result.exit_code == 0
    assert str(session.id) in result.stdout
    assert "active" in result.stdout


def test_sessions_show_prints_events(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.db")
    session = store.create_session()
    store.append_event(session.id, EventType.USER_MESSAGE, {"content": "hello"})
    store.close()

    result = CliRunner().invoke(
        app,
        ["sessions", "show", str(session.id), "--db", str(tmp_path / "sessions.db")],
    )

    assert result.exit_code == 0
    assert str(session.id) in result.stdout
    assert "user_message" in result.stdout
    assert "hello" in result.stdout


def test_sessions_fork_creates_child(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(database_path)
    source = store.create_session()
    store.append_event(source.id, EventType.USER_MESSAGE, {"content": "hello"})
    store.close()

    result = CliRunner().invoke(
        app,
        [
            "sessions",
            "fork",
            str(source.id),
            "--at",
            "2",
            "--db",
            str(database_path),
        ],
    )

    assert result.exit_code == 0
    child_id = result.stdout.strip().splitlines()[-1]
    store = SQLiteSessionStore(database_path)
    try:
        child = store.get_session(child_id)
        assert child.parent_session_id == source.id
        assert [event.sequence for event in store.get_events(child.id)] == [1, 2]
    finally:
        store.close()
