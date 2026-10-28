from typing import Self

from pydantic import Field, JsonValue, model_validator

from leogent.domain.common import DomainModel, GenerationParameters, Usage
from leogent.domain.enums import MessageRole


class ToolDefinition(DomainModel):
    name: str = Field(min_length=1)
    description: str = ""
    input_schema: dict[str, JsonValue] = Field(default_factory=dict)


class ToolCall(DomainModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class Message(DomainModel):
    role: MessageRole
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    @model_validator(mode="after")
    def validate_tool_fields(self) -> Self:
        if self.role is MessageRole.TOOL and not self.tool_call_id:
            raise ValueError("tool messages require tool_call_id")
        if self.role is not MessageRole.TOOL and self.tool_call_id is not None:
            raise ValueError("tool_call_id is only valid for tool messages")
        if self.tool_calls and self.role is not MessageRole.ASSISTANT:
            raise ValueError("tool_calls are only valid for assistant messages")
        return self


class ModelRequest(DomainModel):
    messages: tuple[Message, ...] = Field(min_length=1)
    tools: tuple[ToolDefinition, ...] = ()
    parameters: GenerationParameters = Field(default_factory=GenerationParameters)
    estimated_input_tokens: int = Field(default=0, ge=0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ModelResponse(DomainModel):
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str = Field(default="stop", min_length=1)
    usage: Usage = Field(default_factory=Usage)
    provider_metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ToolResult(DomainModel):
    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    success: bool
    content: str = ""
    error: str | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    truncated: bool = False
