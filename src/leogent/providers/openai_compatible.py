import json
from collections.abc import Iterator
from typing import cast

import httpx
from pydantic import BaseModel, Field, JsonValue, ValidationError

from leogent.config.models import OpenAICompatibleProviderConfig
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


class _OpenAIFunction(BaseModel):
    name: str
    arguments: str = ""


class _OpenAIToolCall(BaseModel):
    id: str | None = None
    function: _OpenAIFunction


def _tool_call_list() -> list[_OpenAIToolCall]:
    return []


class _OpenAIMessage(BaseModel):
    content: str | None = None
    tool_calls: list[_OpenAIToolCall] = Field(default_factory=_tool_call_list)


class _OpenAIChoice(BaseModel):
    message: _OpenAIMessage = Field(default_factory=_OpenAIMessage)
    finish_reason: str = "stop"


class _OpenAIUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _choice_list() -> list[_OpenAIChoice]:
    return []


class _OpenAIEnvelope(BaseModel):
    choices: list[_OpenAIChoice] = Field(default_factory=_choice_list)
    usage: _OpenAIUsage = Field(default_factory=_OpenAIUsage)


class _OpenAIStreamFunction(BaseModel):
    name: str | None = None
    arguments: str | None = None


class _OpenAIStreamToolCall(BaseModel):
    index: int = 0
    id: str | None = None
    function: _OpenAIStreamFunction = Field(default_factory=_OpenAIStreamFunction)


def _stream_tool_call_list() -> list[_OpenAIStreamToolCall]:
    return []


class _OpenAIStreamDelta(BaseModel):
    content: str | None = None
    tool_calls: list[_OpenAIStreamToolCall] = Field(default_factory=_stream_tool_call_list)


class _OpenAIStreamChoice(BaseModel):
    delta: _OpenAIStreamDelta = Field(default_factory=_OpenAIStreamDelta)
    finish_reason: str | None = None


def _stream_choice_list() -> list[_OpenAIStreamChoice]:
    return []


class _OpenAIStreamEnvelope(BaseModel):
    choices: list[_OpenAIStreamChoice] = Field(default_factory=_stream_choice_list)
    usage: _OpenAIUsage | None = None


def _parse_tool_arguments(value: str) -> dict[str, JsonValue]:
    if not value.strip():
        return {}
    try:
        parsed: object = json.loads(value)
    except json.JSONDecodeError as error:
        raise ProviderError("OpenAI-compatible tool arguments must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise ProviderError("OpenAI-compatible tool arguments must be a JSON object")
    return cast(dict[str, JsonValue], parsed)


def _message_payload(message: Message) -> dict[str, object]:
    payload: dict[str, object] = {"role": message.role.value}
    if message.content is not None or message.role is MessageRole.ASSISTANT:
        payload["content"] = message.content
    if message.name is not None:
        payload["name"] = message.name
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, separators=(",", ":")),
                },
            }
            for call in message.tool_calls
        ]
    return payload


def _tool_payload(tool: ToolDefinition) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


class OpenAICompatibleProvider:
    def __init__(
        self,
        config: OpenAICompatibleProviderConfig,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=config.timeout_seconds)
        self._owns_client = client is None

    @property
    def provider_id(self) -> str:
        return "openai-compatible"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            context_window=self._config.context_window,
            supports_native_tools=True,
            supports_streaming=True,
            supports_structured_output=False,
        )

    def build_payload(self, request: ModelRequest, *, stream: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._config.model,
            "messages": [_message_payload(message) for message in request.messages],
            "temperature": request.parameters.temperature,
            "top_p": request.parameters.top_p,
            "max_tokens": request.parameters.max_output_tokens,
            "stream": stream,
        }
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
        if request.parameters.stop:
            payload["stop"] = list(request.parameters.stop)
        return payload

    def complete(self, request: ModelRequest) -> ModelResponse:
        validate_request(request, self.capabilities)
        try:
            response = self._client.post(
                f"{self._config.base_url}/chat/completions",
                headers=self._headers(),
                json=self.build_payload(request),
            )
        except httpx.HTTPError as error:
            raise ProviderError("OpenAI-compatible request failed", retryable=True) from error
        if response.is_error:
            raise error_from_response("OpenAI-compatible provider", response, self._api_key)
        try:
            envelope = _OpenAIEnvelope.model_validate_json(response.content)
        except ValidationError as error:
            raise ProviderError("OpenAI-compatible returned an invalid response") from error
        if not envelope.choices:
            raise ProviderError("OpenAI-compatible response did not contain a choice")
        choice = envelope.choices[0]
        return ModelResponse(
            content=choice.message.content,
            tool_calls=tuple(self._normalize_tool_call(call) for call in choice.message.tool_calls),
            finish_reason=choice.finish_reason,
            usage=Usage(
                input_tokens=envelope.usage.prompt_tokens,
                output_tokens=envelope.usage.completion_tokens,
            ),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        validate_request(request, self.capabilities)
        fragments: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None
        usage: Usage | None = None
        try:
            with self._client.stream(
                "POST",
                f"{self._config.base_url}/chat/completions",
                headers=self._headers(),
                json=self.build_payload(request, stream=True),
            ) as response:
                if response.is_error:
                    response.read()
                    raise error_from_response(
                        "OpenAI-compatible provider",
                        response,
                        self._api_key,
                    )
                for data in iter_sse_data(response):
                    try:
                        event = _OpenAIStreamEnvelope.model_validate_json(data)
                    except ValidationError as error:
                        raise ProviderError(
                            "OpenAI-compatible returned an invalid stream event"
                        ) from error
                    if event.usage is not None:
                        usage = Usage(
                            input_tokens=event.usage.prompt_tokens,
                            output_tokens=event.usage.completion_tokens,
                        )
                    for choice in event.choices:
                        if choice.delta.content:
                            yield ModelChunk(text_delta=choice.delta.content)
                        for tool_call in choice.delta.tool_calls:
                            fragment = fragments.setdefault(
                                tool_call.index,
                                {"id": "", "name": "", "arguments": ""},
                            )
                            if tool_call.id:
                                fragment["id"] += tool_call.id
                            if tool_call.function.name:
                                fragment["name"] += tool_call.function.name
                            if tool_call.function.arguments:
                                fragment["arguments"] += tool_call.function.arguments
                        if choice.finish_reason is not None:
                            finish_reason = choice.finish_reason
        except httpx.HTTPError as error:
            raise ProviderError("OpenAI-compatible stream failed", retryable=True) from error

        tool_calls = tuple(
            ToolCall(
                id=fragment["id"],
                name=fragment["name"],
                arguments=_parse_tool_arguments(fragment["arguments"]),
            )
            for _, fragment in sorted(fragments.items())
        )
        if any(not call.id or not call.name for call in tool_calls):
            raise ProviderError("OpenAI-compatible returned an incomplete streamed tool call")
        yield ModelChunk(
            tool_calls=tool_calls,
            finish_reason=finish_reason or "stop",
            usage=usage,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        return headers

    def _normalize_tool_call(self, call: _OpenAIToolCall) -> ToolCall:
        if not call.id:
            raise ProviderError("OpenAI-compatible tool call is missing an id")
        return ToolCall(
            id=call.id,
            name=call.function.name,
            arguments=_parse_tool_arguments(call.function.arguments),
        )
