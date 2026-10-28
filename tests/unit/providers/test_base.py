import pytest

from leogent.domain.common import GenerationParameters
from leogent.domain.errors import ContextWindowExceeded
from leogent.domain.model import Message, MessageRole, ModelRequest
from leogent.providers.base import ModelCapabilities, ModelChunk
from leogent.providers.validation import validate_request


def test_capabilities_support_unknown_context_window() -> None:
    capabilities = ModelCapabilities(context_window=None)

    assert capabilities.context_window is None
    assert capabilities.supports_native_tools is True
    assert capabilities.supports_streaming is True


def test_stream_chunk_round_trip_preserves_finish_reason() -> None:
    chunk = ModelChunk(text_delta="Done", finish_reason="stop")

    assert ModelChunk.model_validate_json(chunk.model_dump_json()) == chunk


def test_request_rejects_input_and_output_over_context_window() -> None:
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content="hello"),),
        parameters=GenerationParameters(max_output_tokens=100),
        estimated_input_tokens=20,
    )
    capabilities = ModelCapabilities(context_window=100)

    with pytest.raises(ContextWindowExceeded, match="120.*100"):
        validate_request(request, capabilities)


def test_request_accepts_exact_context_window_limit() -> None:
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content="hello"),),
        parameters=GenerationParameters(max_output_tokens=80),
        estimated_input_tokens=20,
    )

    validate_request(request, ModelCapabilities(context_window=100))
