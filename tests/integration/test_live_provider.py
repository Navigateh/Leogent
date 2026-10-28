from pathlib import Path

import pytest

from leogent.config.loader import load_config_from_search
from leogent.domain.errors import ConfigurationError
from leogent.domain.model import Message, MessageRole, ModelRequest
from leogent.providers.factory import create_provider


@pytest.mark.live
def test_configured_live_provider_returns_a_model_result() -> None:
    try:
        config = load_config_from_search(Path.cwd())
        provider = create_provider(config)
    except ConfigurationError as error:
        pytest.skip(str(error))

    try:
        response = provider.complete(
            ModelRequest(
                messages=(
                    Message(
                        role=MessageRole.USER,
                        content="Reply with exactly: Leogent ready",
                    ),
                )
            )
        )
    finally:
        provider.close()

    assert response.content or response.tool_calls
