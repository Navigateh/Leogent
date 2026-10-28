import json
from collections.abc import Callable
from typing import cast

import httpx

from leogent.config.models import AnthropicProviderConfig
from leogent.domain.model import Message, MessageRole, ModelRequest, ToolCall, ToolDefinition
from leogent.providers.anthropic import AnthropicProvider


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
) -> AnthropicProvider:
    config = AnthropicProviderConfig(
        type="anthropic",
        model="claude-test",
        api_key_env="ANTHROPIC_API_KEY",
        context_window=200000,
    )
    return AnthropicProvider(
        config,
        api_key="anthropic-secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_request_extracts_system_messages_and_tool_results() -> None:
    provider = _provider(lambda _: httpx.Response(200, json={}))
    request = ModelRequest(
        messages=(
            Message(role=MessageRole.SYSTEM, content="Be concise."),
            Message(role=MessageRole.USER, content="Read README"),
            Message(role=MessageRole.TOOL, content="contents", tool_call_id="tool_1"),
        ),
        tools=(
            ToolDefinition(
                name="filesystem__read_file",
                description="Read a file",
                input_schema={"type": "object"},
            ),
        ),
    )

    payload = provider.build_payload(request)
    messages = cast(list[dict[str, object]], payload["messages"])
    blocks = cast(list[dict[str, object]], messages[-1]["content"])
    tools = cast(list[dict[str, object]], payload["tools"])

    assert payload["system"] == "Be concise."
    assert blocks[0] == {
        "type": "tool_result",
        "tool_use_id": "tool_1",
        "content": "contents",
    }
    assert tools[0]["input_schema"] == {"type": "object"}


def test_complete_normalizes_text_tool_use_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "anthropic-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        payload = json.loads(request.content)
        assert payload["model"] == "claude-test"
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "Reading."},
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "filesystem__read_file",
                        "input": {"path": "README.md"},
                    },
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 8, "output_tokens": 4},
            },
        )

    provider = _provider(handler)
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content="Read README"),),
        tools=(ToolDefinition(name="filesystem__read_file"),),
    )

    response = provider.complete(request)

    assert response.content == "Reading."
    assert response.finish_reason == "tool_use"
    assert response.tool_calls[0].arguments == {"path": "README.md"}
    assert response.usage.total_tokens == 12


def test_stream_normalizes_text_and_tool_input_deltas() -> None:
    events = [
        (
            'data: {"type":"content_block_delta","index":0,'
            '"delta":{"type":"text_delta","text":"Reading"}}\n\n'
        ),
        (
            'data: {"type":"content_block_start","index":1,'
            '"content_block":{"type":"tool_use","id":"tool_1",'
            '"name":"filesystem__read_file","input":{}}}\n\n'
        ),
        (
            'data: {"type":"content_block_delta","index":1,'
            '"delta":{"type":"input_json_delta","partial_json":"{\\"path\\":"}}\n\n'
        ),
        (
            'data: {"type":"content_block_delta","index":1,'
            '"delta":{"type":"input_json_delta","partial_json":"\\"README.md\\"}"}}\n\n'
        ),
        (
            'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},'
            '"usage":{"output_tokens":4}}\n\n'
        ),
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content="".join(events),
            headers={"content-type": "text/event-stream"},
        )

    provider = _provider(handler)
    chunks = list(
        provider.stream(ModelRequest(messages=(Message(role=MessageRole.USER, content="Read"),)))
    )

    assert "".join(chunk.text_delta for chunk in chunks) == "Reading"
    assert chunks[-1].finish_reason == "tool_use"
    assert chunks[-1].tool_calls[0] == ToolCall(
        id="tool_1",
        name="filesystem__read_file",
        arguments={"path": "README.md"},
    )


def test_assistant_tool_calls_become_tool_use_blocks() -> None:
    provider = _provider(lambda _: httpx.Response(200, json={}))
    request = ModelRequest(
        messages=(
            Message(
                role=MessageRole.ASSISTANT,
                content="Checking.",
                tool_calls=(
                    ToolCall(
                        id="tool_1",
                        name="filesystem__read_file",
                        arguments={"path": "README.md"},
                    ),
                ),
            ),
        )
    )

    payload = provider.build_payload(request)
    messages = cast(list[dict[str, object]], payload["messages"])

    assert messages[0]["content"] == [
        {"type": "text", "text": "Checking."},
        {
            "type": "tool_use",
            "id": "tool_1",
            "name": "filesystem__read_file",
            "input": {"path": "README.md"},
        },
    ]
