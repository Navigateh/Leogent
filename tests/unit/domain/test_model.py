import pytest
from pydantic import ValidationError

from leogent.domain.model import Message, MessageRole, ModelRequest, ModelResponse, ToolDefinition


def test_model_response_round_trip_preserves_tool_call_arguments() -> None:
    response = ModelResponse.model_validate(
        {
            "content": None,
            "finish_reason": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "filesystem__read_file",
                    "arguments": {"path": "README.md"},
                }
            ],
            "usage": {"input_tokens": 12, "output_tokens": 4},
        }
    )

    assert ModelResponse.model_validate_json(response.model_dump_json()) == response
    assert response.tool_calls[0].arguments["path"] == "README.md"


def test_message_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        Message(role="unknown", content="hello")  # type: ignore[arg-type]


def test_tool_message_requires_tool_call_id() -> None:
    with pytest.raises(ValidationError):
        Message(role=MessageRole.TOOL, content="result")


def test_model_request_round_trip_preserves_tool_definition() -> None:
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content="Read the README"),),
        tools=(
            ToolDefinition(
                name="filesystem__read_file",
                description="Read a file",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            ),
        ),
    )

    assert ModelRequest.model_validate_json(request.model_dump_json()) == request
