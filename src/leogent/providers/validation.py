from leogent.domain.errors import ContextWindowExceeded
from leogent.domain.model import ModelRequest
from leogent.providers.base import ModelCapabilities


def validate_request(request: ModelRequest, capabilities: ModelCapabilities) -> None:
    context_window = capabilities.context_window
    if context_window is None:
        return
    requested_tokens = request.estimated_input_tokens + request.parameters.max_output_tokens
    if requested_tokens > context_window:
        raise ContextWindowExceeded(
            f"Request needs {requested_tokens} tokens but context window is {context_window}"
        )
