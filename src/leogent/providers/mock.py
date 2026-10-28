from collections.abc import Iterator, Sequence

from leogent.domain.errors import ProviderError
from leogent.domain.model import ModelRequest, ModelResponse
from leogent.providers.base import ModelCapabilities, ModelChunk


class ScriptedProvider:
    def __init__(
        self,
        responses: Sequence[ModelResponse | Exception],
        *,
        capabilities: ModelCapabilities | None = None,
    ) -> None:
        self._responses = list(responses)
        self._capabilities = capabilities or ModelCapabilities(context_window=8192)
        self.requests: list[ModelRequest] = []

    @property
    def provider_id(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> ModelCapabilities:
        return self._capabilities

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self._responses:
            raise ProviderError("Scripted provider responses are exhausted")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        response = self.complete(request)
        if response.content:
            yield ModelChunk(text_delta=response.content)
        yield ModelChunk(
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )

    def close(self) -> None:
        return None
