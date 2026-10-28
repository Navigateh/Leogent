import json
from pathlib import Path

import pytest

from leogent.config.loader import load_config, resolve_api_key
from leogent.config.models import (
    AppConfig,
    OpenAICompatibleProviderConfig,
    TransformersProviderConfig,
)
from leogent.domain.errors import ConfigurationError


def _write_config(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_project_config_deep_merges_over_global_config(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    _write_config(
        global_path,
        {
            "default_provider": "cloud",
            "providers": {
                "cloud": {
                    "type": "openai-compatible",
                    "base_url": "https://api.example.com/v1",
                    "model": "global-model",
                    "api_key_env": "CLOUD_API_KEY",
                }
            },
        },
    )
    _write_config(project_path, {"providers": {"cloud": {"model": "project-model"}}})

    config = load_config(global_path, project_path)

    provider = config.providers["cloud"]
    assert isinstance(provider, OpenAICompatibleProviderConfig)
    assert provider.model == "project-model"
    assert str(provider.base_url).rstrip("/") == "https://api.example.com/v1"


def test_environment_can_override_default_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "default_provider": "cloud",
            "providers": {
                "cloud": {
                    "type": "openai-compatible",
                    "base_url": "https://api.example.com/v1",
                    "model": "cloud-model",
                },
                "local": {
                    "type": "openai-compatible",
                    "base_url": "http://localhost:11434/v1",
                    "model": "local-model",
                },
            },
        },
    )

    config = load_config(None, config_path, {"LEOGENT_DEFAULT_PROVIDER": "local"})

    assert config.default_provider == "local"


def test_missing_config_files_raise_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="No Leogent configuration"):
        load_config(tmp_path / "missing-global.json", tmp_path / "missing-project.json")


def test_invalid_json_raises_configuration_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="valid JSON"):
        load_config(None, config_path)


def test_validation_error_does_not_echo_secret_reference(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "default_provider": "cloud",
            "providers": {
                "cloud": {
                    "type": "openai-compatible",
                    "base_url": "https://api.example.com/v1",
                    "model": "model",
                    "api_key_env": "sk-live-secret",
                }
            },
        },
    )

    with pytest.raises(ConfigurationError) as error:
        load_config(None, config_path)

    assert "sk-live-secret" not in str(error.value)


def test_resolve_api_key_reads_only_the_referenced_environment_name() -> None:
    profile = OpenAICompatibleProviderConfig(
        type="openai-compatible",
        base_url="https://api.example.com/v1",
        model="model",
        api_key_env="CLOUD_API_KEY",
    )

    assert resolve_api_key(profile, {"CLOUD_API_KEY": "secret"}) == "secret"
    assert resolve_api_key(profile, {"OTHER_KEY": "secret"}) is None


def test_transformers_provider_has_no_api_key() -> None:
    profile = TransformersProviderConfig(type="transformers", model_path=Path("/models/example"))

    assert resolve_api_key(profile, {"LEOGENT_API_KEY": "secret"}) is None


def test_loaded_config_uses_provider_union(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "default_provider": "cloud",
            "providers": {
                "cloud": {
                    "type": "anthropic",
                    "model": "claude-example",
                    "api_key_env": "ANTHROPIC_API_KEY",
                }
            },
        },
    )

    config: AppConfig = load_config(None, config_path)

    assert config.providers["cloud"].type == "anthropic"


def test_project_relative_transformers_path_resolves_from_config_directory(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "project" / ".leogent" / "config.json"
    _write_config(
        config_path,
        {
            "default_provider": "local",
            "providers": {
                "local": {
                    "type": "transformers",
                    "model_path": "models/qwen",
                }
            },
        },
    )

    config = load_config(None, config_path)

    provider = config.providers["local"]
    assert isinstance(provider, TransformersProviderConfig)
    assert provider.model_path == config_path.parent / "models" / "qwen"
