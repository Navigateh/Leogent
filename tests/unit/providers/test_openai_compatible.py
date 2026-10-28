import json
from collections.abc import Callable

import httpx
import pytest

from leogent.config.models import OpenAICompatibleProviderConfig
from leogent.domain.common import GenerationParameters
from leogent.domain.errors import ProviderError
from leogent.domain.model import Message, MessageRole, ModelRequest, ToolCall, ToolDefinition
from leogent.providers.base import ModelCapabilities
from leogent.providers.openai_compatible import OpenAICompatibleProvider


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str | None = "secret-key",
) -> OpenAICompatibleProvider:
    config = OpenAICompatibleProviderConfig(
        type="openai-compatible",
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key_env="TEST_API_KEY",
        context_window=8192,
    )
    return OpenAICompatibleProvider(
        config,
        api_key=api_key,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _request() -> ModelRequest:
    return ModelRequest(
        messages=(
            Message(role=MessageRole.SYSTEM, content="Be concise."),
            Message(role=MessageRole.USER, content="Read README.md"),
        ),
        tools=(
            ToolDefinition(
                name="filesystem__read_file",
                description="Read a file",
                input_schema={"type": "object"},
            ),
        ),
        parameters=GenerationParameters(temperature=0.2, top_p=0.9, max_output_tokens=128),
    )


def test_complete_normalizes_text_tool_calls_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://api.example.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret-key"
        assert payload["model"] == "test-model"
        assert payload["messages"][1] == {"role": "user", "content": "Read README.md"}
        assert payload["tools"][0]["function"]["name"] == "filesystem__read_file"
        assert payload["max_tokens"] == 128
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Checking.",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "filesystem__read_file",
                                        "arguments": '{"path": "README.md"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
        )

    provider = _provider(handler)

    response = provider.complete(_request())

    assert response.content == "Checking."
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0].arguments == {"path": "README.md"}
    assert response.usage.total_tokens == 13


def test_complete_preserves_assistant_tool_calls_in_history() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assistant = payload["messages"][0]
        assert assistant["content"] is None
        arguments = json.loads(assistant["tool_calls"][0]["function"]["arguments"])
        assert arguments == {"path": "README.md"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "Done"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    provider = _provider(handler)
    request = ModelRequest(
        messages=(
            Message(
                role=MessageRole.ASSISTANT,
                tool_calls=(
                    ToolCall(
                        id="call_1",
                        name="filesystem__read_file",
                        arguments={"path": "README.md"},
                    ),
                ),
            ),
            Message(
                role=MessageRole.TOOL,
                content="file contents",
                tool_call_id="call_1",
            ),
        )
    )

    provider.complete(request)


def test_stream_concatenates_text_and_fragmented_tool_arguments() -> None:
    events = [
        'data: {"choices":[{"delta":{"content":"Read"}}]}\n\n',
        (
            'data: {"choices":[{"delta":{"content":"ing.","tool_calls":['
            '{"index":0,"id":"call_1","function":'
            '{"name":"filesystem__read_file","arguments":"{\\"path\\":"}}]}}]}\n\n'
        ),
        (
            'data: {"choices":[{"delta":{"tool_calls":['
            '{"index":0,"function":{"arguments":"\\"README.md\\"}"}}]},'
            '"finish_reason":"tool_calls"}]}\n\n'
        ),
        "data: [DONE]\n\n",
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content="".join(events),
            headers={"content-type": "text/event-stream"},
        )

    provider = _provider(handler)
    chunks = list(provider.stream(_request()))

    assert "".join(chunk.text_delta for chunk in chunks) == "Reading."
    assert chunks[-1].finish_reason == "tool_calls"
    assert chunks[-1].tool_calls[0].arguments == {"path": "README.md"}


def test_http_error_is_retryable_and_does_not_echo_api_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            text="rate limited; supplied Authorization: Bearer secret-key",
        )

    provider = _provider(handler)

    with pytest.raises(ProviderError) as error:
        provider.complete(_request())

    assert error.value.retryable is True
    assert error.value.status_code == 429
    assert "secret-key" not in str(error.value)


def test_invalid_tool_arguments_raise_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "filesystem__read_file",
                                        "arguments": "{invalid",
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    provider = _provider(handler)

    with pytest.raises(ProviderError, match="tool arguments"):
        provider.complete(_request())


def test_openai_capabilities_reflect_configuration() -> None:
    provider = _provider(lambda _: httpx.Response(200, json={}))

    assert provider.capabilities == ModelCapabilities(
        context_window=8192,
        supports_native_tools=True,
        supports_streaming=True,
        supports_structured_output=False,
    )
