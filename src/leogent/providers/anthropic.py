import json
from collections.abc import Iterator
from typing import cast

import httpx
from pydantic import BaseModel, Field, JsonValue, ValidationError

from leogent.config.models import AnthropicProviderConfig
from leogent.domain.common import Usage
from leogent.domain.errors import ProviderError
from leogent.domain.model import (
    Message,
    MessageRole,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolDefinition,
)
from leogent.providers._http import error_from_response
from leogent.providers._sse import iter_sse_data
from leogent.providers.base import ModelCapabilities, ModelChunk
from leogent.providers.validation import validate_request


class _AnthropicBlock(BaseModel):
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict[str, JsonValue] = Field(default_factory=dict)


class _AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


def _block_list() -> list[_AnthropicBlock]:
    return []


class _AnthropicResponse(BaseModel):
    content: list[_AnthropicBlock] = Field(default_factory=_block_list)
    stop_reason: str = "end_turn"
    usage: _AnthropicUsage = Field(default_factory=_AnthropicUsage)


class _AnthropicStreamDelta(BaseModel):
    type: str | None = None
    text: str | None = None
    partial_json: str | None = None
    stop_reason: str | None = None


class _AnthropicStreamMessage(BaseModel):
    usage: _AnthropicUsage = Field(default_factory=_AnthropicUsage)


class _AnthropicStreamEvent(BaseModel):
    type: str
    index: int | None = None
    delta: _AnthropicStreamDelta | None = None
    content_block: _AnthropicBlock | None = None
    message: _AnthropicStreamMessage | None = None
    usage: _AnthropicUsage | None = None


def _tool_payload(tool: ToolDefinition) -> dict[str, object]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
    }


def _assistant_content(message: Message) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    blocks.extend(
        {
            "type": "tool_use",
            "id": call.id,
            "name": call.name,
            "input": call.arguments,
        }
        for call in message.tool_calls
    )
    if not blocks:
        raise ProviderError("Anthropic assistant messages require content or tool calls")
    return blocks


def _message_payload(message: Message) -> dict[str, object] | None:
    if message.role is MessageRole.SYSTEM:
        return None
    if message.role is MessageRole.TOOL:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content or "",
                }
            ],
        }
    if message.role is MessageRole.ASSISTANT:
        return {"role": "assistant", "content": _assistant_content(message)}
    return {"role": "user", "content": message.content or ""}


def _parse_json_object(value: str) -> dict[str, JsonValue]:
    if not value.strip():
        return {}
    try:
        parsed: object = json.loads(value)
    except json.JSONDecodeError as error:
        raise ProviderError("Anthropic tool input must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise ProviderError("Anthropic tool input must be a JSON object")
    return cast(dict[str, JsonValue], parsed)


class AnthropicProvider:
    def __init__(
        self,
        config: AnthropicProviderConfig,
        *,
        api_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=config.timeout_seconds)
        self._owns_client = client is None

    @property
    def provider_id(self) -> str:
        return "anthropic"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            context_window=self._config.context_window,
            supports_native_tools=True,
            supports_streaming=True,
            supports_structured_output=False,
        )

    def build_payload(self, request: ModelRequest) -> dict[str, object]:
        system_messages = [
            message.content
            for message in request.messages
            if message.role is MessageRole.SYSTEM and message.content
        ]
        messages: list[dict[str, object]] = []
        for message in request.messages:
            message_payload = _message_payload(message)
            if message_payload is not None:
                messages.append(message_payload)
        payload: dict[str, object] = {
            "model": self._config.model,
            "max_tokens": request.parameters.max_output_tokens,
            "messages": messages,
        }
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
        if "temperature" in request.parameters.model_fields_set:
            payload["temperature"] = request.parameters.temperature
        if "top_p" in request.parameters.model_fields_set:
            payload["top_p"] = request.parameters.top_p
        if request.parameters.stop:
            payload["stop_sequences"] = list(request.parameters.stop)
        return payload

    def complete(self, request: ModelRequest) -> ModelResponse:
        validate_request(request, self.capabilities)
        try:
            response = self._client.post(
                f"{self._config.base_url}/messages",
                headers=self._headers(),
                json=self.build_payload(request),
            )
        except httpx.HTTPError as error:
            raise ProviderError("Anthropic request failed", retryable=True) from error
        if response.is_error:
            raise error_from_response("Anthropic provider", response, self.api_key)
        try:
            envelope = _AnthropicResponse.model_validate_json(response.content)
        except ValidationError as error:
            raise ProviderError("Anthropic returned an invalid response") from error
        text = "".join(block.text or "" for block in envelope.content if block.type == "text")
        tool_calls = tuple(
            ToolCall(
                id=block.id or "",
                name=block.name or "",
                arguments=block.input,
            )
            for block in envelope.content
            if block.type == "tool_use"
        )
        if any(not call.id or not call.name for call in tool_calls):
            raise ProviderError("Anthropic returned an incomplete tool call")
        return ModelResponse(
            content=text or None,
            tool_calls=tool_calls,
            finish_reason=envelope.stop_reason,
            usage=Usage(
                input_tokens=envelope.usage.input_tokens,
                output_tokens=envelope.usage.output_tokens,
            ),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        validate_request(request, self.capabilities)
        tools: dict[int, dict[str, JsonValue | str]] = {}
        finish_reason: str | None = None
        input_tokens = 0
        output_tokens = 0
        try:
            with self._client.stream(
                "POST",
                f"{self._config.base_url}/messages",
                headers=self._headers(),
                json={**self.build_payload(request), "stream": True},
            ) as response:
                if response.is_error:
                    response.read()
                    raise error_from_response("Anthropic provider", response, self.api_key)
                for data in iter_sse_data(response):
                    try:
                        event = _AnthropicStreamEvent.model_validate_json(data)
                    except ValidationError as error:
                        raise ProviderError("Anthropic returned an invalid stream event") from error
                    if event.type == "message_start" and event.message is not None:
                        input_tokens = event.message.usage.input_tokens
                    elif event.type == "content_block_start" and event.content_block is not None:
                        block = event.content_block
                        if block.type == "tool_use" and event.index is not None:
                            tools[event.index] = {
                                "id": block.id or "",
                                "name": block.name or "",
                                "arguments": "",
                            }
                    elif event.type == "content_block_delta" and event.delta is not None:
                        if event.delta.type == "text_delta" and event.delta.text:
                            yield ModelChunk(text_delta=event.delta.text)
                        elif (
                            event.delta.type == "input_json_delta"
                            and event.index is not None
                            and event.index in tools
                            and event.delta.partial_json
                        ):
                            arguments = tools[event.index]["arguments"]
                            tools[event.index]["arguments"] = (
                                str(arguments) + event.delta.partial_json
                            )
                    elif event.type == "message_delta":
                        if event.delta and event.delta.stop_reason:
                            finish_reason = event.delta.stop_reason
                        if event.usage is not None:
                            output_tokens = event.usage.output_tokens
        except httpx.HTTPError as error:
            raise ProviderError("Anthropic stream failed", retryable=True) from error

        tool_calls = tuple(
            ToolCall(
                id=str(value["id"]),
                name=str(value["name"]),
                arguments=_parse_json_object(str(value["arguments"])),
            )
            for _, value in sorted(tools.items())
        )
        yield ModelChunk(
            tool_calls=tool_calls,
            finish_reason=finish_reason or "end_turn",
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
