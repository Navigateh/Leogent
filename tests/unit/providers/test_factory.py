from pathlib import Path

import pytest

from leogent.config.models import (
    AnthropicProviderConfig,
    AppConfig,
    OpenAICompatibleProviderConfig,
    TransformersProviderConfig,
)
from leogent.domain.errors import ConfigurationError
from leogent.providers.anthropic import AnthropicProvider
from leogent.providers.factory import create_provider
from leogent.providers.openai_compatible import OpenAICompatibleProvider


def test_factory_creates_openai_compatible_provider() -> None:
    config = AppConfig(
        default_provider="local",
        providers={
            "local": OpenAICompatibleProviderConfig(
                type="openai-compatible",
                base_url="http://localhost:11434/v1",
                model="local-model",
            )
        },
    )

    provider = create_provider(config, environ={})

    assert isinstance(provider, OpenAICompatibleProvider)


def test_factory_creates_anthropic_provider_with_resolved_key() -> None:
    config = AppConfig(
        default_provider="cloud",
        providers={
            "cloud": AnthropicProviderConfig(
                type="anthropic",
                model="claude-test",
                api_key_env="ANTHROPIC_API_KEY",
            )
        },
    )

    provider = create_provider(
        config,
        environ={"ANTHROPIC_API_KEY": "secret"},
    )

    assert isinstance(provider, AnthropicProvider)
    assert provider.api_key == "secret"


def test_factory_rejects_missing_anthropic_key() -> None:
    config = AppConfig(
        default_provider="cloud",
        providers={
            "cloud": AnthropicProviderConfig(
                type="anthropic",
                model="claude-test",
                api_key_env="ANTHROPIC_API_KEY",
            )
        },
    )

    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        create_provider(config, environ={})


def test_factory_explains_that_transformers_is_milestone_ten() -> None:
    config = AppConfig(
        default_provider="local",
        providers={
            "local": TransformersProviderConfig(
                type="transformers",
                model_path=Path("models/example"),
            )
        },
    )

    with pytest.raises(ConfigurationError, match="Milestone 10"):
        create_provider(config, environ={})
