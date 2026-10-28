from collections.abc import Iterator
from typing import Protocol

from pydantic import Field

from leogent.domain.common import DomainModel, Usage
from leogent.domain.model import ModelRequest, ModelResponse, ToolCall


class ModelCapabilities(DomainModel):
    context_window: int | None = Field(default=None, gt=0)
    supports_native_tools: bool = True
    supports_streaming: bool = True
    supports_structured_output: bool = False
    supports_prompt_cache: bool = False
    tokenizer: str | None = None


class ModelChunk(DomainModel):
    text_delta: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None
    usage: Usage | None = None


class ModelProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> ModelCapabilities: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]: ...

    def close(self) -> None: ...
