from pathlib import Path

import pytest
from typer.testing import CliRunner

import leogent.cli.run as run_module
from leogent.cli.main import app
from leogent.config.models import AppConfig, OpenAICompatibleProviderConfig
from leogent.domain.model import ModelResponse
from leogent.providers.base import ModelProvider
from leogent.providers.mock import ScriptedProvider


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


def test_run_command_prints_single_turn_non_stream_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LEOGENT_HOME", str(tmp_path))
    provider = ScriptedProvider((ModelResponse(content="Hello from Leogent"),))

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

    result = CliRunner().invoke(
        app,
        ["run", "Say hello", "--no-tui", "--no-stream"],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "Hello from Leogent"
    assert provider.requests[0].messages[0].content == "Say hello"


def test_run_command_streams_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LEOGENT_HOME", str(tmp_path))
    provider = ScriptedProvider((ModelResponse(content="Hello stream"),))

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

    result = CliRunner().invoke(
        app,
        ["run", "Say hello", "--no-tui", "--stream"],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "Hello stream"


def test_run_command_rejects_empty_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load(_: Path) -> AppConfig:
        return _config()

    monkeypatch.setattr(run_module, "load_config_from_search", fake_load)

    result = CliRunner().invoke(app, ["run", "   ", "--no-tui"])

    assert result.exit_code == 2
    assert "must not be empty" in result.output


def test_run_command_accepts_explicit_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LEOGENT_HOME", str(tmp_path))
    provider = ScriptedProvider((ModelResponse(content="ok"),))
    observed: dict[str, object] = {}

    def fake_load(_: Path) -> AppConfig:
        return _config()

    def fake_create(
        config: AppConfig,
        provider_name: str | None = None,
        **_kwargs: object,
    ) -> ModelProvider:
        observed["config"] = config
        observed["provider_name"] = provider_name
        return provider

    monkeypatch.setattr(run_module, "load_config_from_search", fake_load)
    monkeypatch.setattr(run_module, "create_provider", fake_create)

    result = CliRunner().invoke(
        app,
        ["run", "hello", "--provider", "local", "--no-tui", "--no-stream"],
    )

    assert result.exit_code == 0
    assert observed["provider_name"] == "local"
