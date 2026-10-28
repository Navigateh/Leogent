from pathlib import Path
from typing import Annotated, Literal, Self, TypeAlias
from urllib.parse import urlparse

from pydantic import AfterValidator, Field, model_validator

from leogent.domain.common import DomainModel

ENVIRONMENT_NAME_PATTERN = r"^[A-Z_][A-Z0-9_]*$"


def _validate_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP or HTTPS URL")
    return value.rstrip("/")


BaseUrl = Annotated[str, AfterValidator(_validate_base_url)]


class OpenAICompatibleProviderConfig(DomainModel):
    type: Literal["openai-compatible"] = "openai-compatible"
    base_url: BaseUrl
    model: str = Field(min_length=1)
    api_key_env: str | None = Field(default=None, pattern=ENVIRONMENT_NAME_PATTERN)
    context_window: int | None = Field(default=None, gt=0)
    timeout_seconds: float = Field(default=60.0, gt=0)


class AnthropicProviderConfig(DomainModel):
    type: Literal["anthropic"] = "anthropic"
    base_url: BaseUrl = "https://api.anthropic.com/v1"
    model: str = Field(min_length=1)
    api_key_env: str = Field(pattern=ENVIRONMENT_NAME_PATTERN)
    context_window: int | None = Field(default=None, gt=0)
    timeout_seconds: float = Field(default=60.0, gt=0)


class TransformersProviderConfig(DomainModel):
    type: Literal["transformers"] = "transformers"
    model_path: Path
    device: str = Field(default="auto", min_length=1)
    dtype: str = Field(default="auto", min_length=1)
    context_window: int | None = Field(default=None, gt=0)
    trust_remote_code: bool = False


ProviderConfig: TypeAlias = Annotated[
    OpenAICompatibleProviderConfig | AnthropicProviderConfig | TransformersProviderConfig,
    Field(discriminator="type"),
]


class AppConfig(DomainModel):
    default_provider: str = Field(min_length=1)
    providers: dict[str, ProviderConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_default_provider(self) -> Self:
        if self.default_provider not in self.providers:
            raise ValueError("default_provider must name a configured provider")
        return self
