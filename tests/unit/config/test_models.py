import pytest
from pydantic import ValidationError

from leogent.config.models import AppConfig, OpenAICompatibleProviderConfig


def test_default_provider_must_exist() -> None:
    with pytest.raises(ValidationError):
        AppConfig(default_provider="missing", providers={})


def test_api_key_reference_must_be_an_environment_name() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {
                "default_provider": "cloud",
                "providers": {
                    "cloud": {
                        "type": "openai-compatible",
                        "base_url": "https://api.example.com/v1",
                        "model": "example",
                        "api_key_env": "sk-secret-value",
                    }
                },
            }
        )


def test_local_openai_compatible_provider_does_not_require_api_key() -> None:
    config = AppConfig.model_validate(
        {
            "default_provider": "local",
            "providers": {
                "local": {
                    "type": "openai-compatible",
                    "base_url": "http://localhost:11434/v1",
                    "model": "local-model",
                }
            },
        }
    )

    profile = config.providers["local"]
    assert isinstance(profile, OpenAICompatibleProviderConfig)
    assert str(profile.base_url).rstrip("/") == "http://localhost:11434/v1"


def test_unknown_provider_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {
                "default_provider": "cloud",
                "providers": {
                    "cloud": {
                        "type": "anthropic",
                        "model": "claude-example",
                        "api_key_env": "ANTHROPIC_API_KEY",
                        "unexpected": True,
                    }
                },
            }
        )


def test_transformers_provider_requires_model_path() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {
                "default_provider": "local",
                "providers": {
                    "local": {
                        "type": "transformers",
                    }
                },
            }
        )
