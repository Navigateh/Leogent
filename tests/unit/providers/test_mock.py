import pytest

from leogent.domain.errors import ProviderError
from leogent.domain.model import Message, MessageRole, ModelRequest, ModelResponse
from leogent.providers.mock import ScriptedProvider


def _request() -> ModelRequest:
    return ModelRequest(messages=(Message(role=MessageRole.USER, content="hello"),))


def test_scripted_provider_returns_responses_in_order_and_records_requests() -> None:
    provider = ScriptedProvider(
        (
            ModelResponse(content="first"),
            ModelResponse(content="second"),
        )
    )

    assert provider.complete(_request()).content == "first"
    assert provider.complete(_request()).content == "second"
    assert len(provider.requests) == 2


def test_scripted_provider_stream_yields_content_and_finish_reason() -> None:
    provider = ScriptedProvider((ModelResponse(content="streamed", finish_reason="stop"),))

    chunks = list(provider.stream(_request()))

    assert "".join(chunk.text_delta for chunk in chunks) == "streamed"
    assert chunks[-1].finish_reason == "stop"


def test_scripted_provider_raises_when_script_is_exhausted() -> None:
    provider = ScriptedProvider(())

    with pytest.raises(ProviderError, match="exhausted"):
        provider.complete(_request())
