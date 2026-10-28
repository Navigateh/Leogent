import os
from collections.abc import Mapping

from leogent.config.loader import resolve_api_key
from leogent.config.models import (
    AnthropicProviderConfig,
    AppConfig,
    OpenAICompatibleProviderConfig,
)
from leogent.domain.errors import ConfigurationError
from leogent.providers.anthropic import AnthropicProvider
from leogent.providers.base import ModelProvider
from leogent.providers.openai_compatible import OpenAICompatibleProvider


def create_provider(
    config: AppConfig,
    provider_name: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ModelProvider:
    selected_name = provider_name or config.default_provider
    try:
        profile = config.providers[selected_name]
    except KeyError:
        raise ConfigurationError(f"Provider '{selected_name}' is not configured") from None
    environment = os.environ if environ is None else environ
    api_key = resolve_api_key(profile, environment)
    if isinstance(profile, OpenAICompatibleProviderConfig):
        return OpenAICompatibleProvider(profile, api_key=api_key)
    if isinstance(profile, AnthropicProviderConfig):
        if api_key is None:
            raise ConfigurationError(
                f"Environment variable {profile.api_key_env} is required for Anthropic"
            )
        return AnthropicProvider(profile, api_key=api_key)
    raise ConfigurationError(
        "Transformers providers are implemented in Milestone 10; use an "
        "OpenAI-compatible local server for now"
    )
