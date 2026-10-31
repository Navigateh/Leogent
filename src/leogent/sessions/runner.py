import json
from collections.abc import Callable
from typing import cast
from uuid import UUID

from pydantic import JsonValue

from leogent.domain.common import DomainModel, Usage
from leogent.domain.enums import EventType, SessionStatus, TerminationReason
from leogent.domain.errors import ErrorCode, LeogentError, SessionError
from leogent.domain.event import Event, Session
from leogent.domain.model import Message, MessageRole, ModelRequest, ModelResponse
from leogent.providers.base import ModelProvider
from leogent.sessions.base import SessionStore


class TurnResult(DomainModel):
    session: Session
    request: ModelRequest
    response: ModelResponse
    text: str


def _history_messages(events: tuple[Event, ...]) -> tuple[Message, ...]:
    messages: list[Message] = []
    for event in events:
        if event.event_type is EventType.USER_MESSAGE:
            content = event.payload.get("content")
            if not isinstance(content, str):
                raise SessionError("Persisted user message content is malformed")
            messages.append(Message(role=MessageRole.USER, content=content))
        elif event.event_type is EventType.MODEL_RESPONSE:
            try:
                response = ModelResponse.model_validate_json(
                    json.dumps(event.payload, ensure_ascii=False)
                )
            except ValueError as error:
                raise SessionError("Persisted model response is malformed") from error
            if response.content is not None or response.tool_calls:
                messages.append(
                    Message(
                        role=MessageRole.ASSISTANT,
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )
    return tuple(messages)


def _stream_response(
    provider: ModelProvider,
    request: ModelRequest,
    on_text: Callable[[str], None] | None,
) -> tuple[ModelResponse, str]:
    parts: list[str] = []
    finish_reason = "stop"
    usage: Usage | None = None
    tool_calls = ()
    for chunk in provider.stream(request):
        if chunk.text_delta:
            parts.append(chunk.text_delta)
            if on_text is not None:
                on_text(chunk.text_delta)
        if chunk.finish_reason is not None:
            finish_reason = chunk.finish_reason
        if chunk.usage is not None:
            usage = chunk.usage
        if chunk.tool_calls:
            tool_calls = chunk.tool_calls
    text = "".join(parts)
    return (
        ModelResponse(
            content=text or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=Usage() if usage is None else usage,
        ),
        text,
    )


def execute_turn(
    store: SessionStore,
    provider: ModelProvider,
    prompt: str,
    *,
    session_id: UUID | str | None = None,
    stream: bool = False,
    on_text: Callable[[str], None] | None = None,
) -> TurnResult:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")

    if session_id is None:
        session = store.create_session()
        history: tuple[Message, ...] = ()
    else:
        session = store.get_session(session_id)
        history = _history_messages(store.get_events(session.id))
        if session.status is not SessionStatus.ACTIVE:
            session = store.update_session_status(session.id, SessionStatus.ACTIVE)

    store.append_event(session.id, EventType.USER_MESSAGE, {"content": prompt})
    request = ModelRequest(
        messages=(
            *history,
            Message(role=MessageRole.USER, content=prompt),
        )
    )
    store.append_event(
        session.id,
        EventType.MODEL_REQUEST,
        cast(dict[str, JsonValue], request.model_dump(mode="json")),
    )

    try:
        if stream and provider.capabilities.supports_streaming:
            response, text = _stream_response(provider, request, on_text)
        else:
            response = provider.complete(request)
            text = response.content or ""
            if text and on_text is not None:
                on_text(text)
    except Exception as error:
        code = error.code.value if isinstance(error, LeogentError) else ErrorCode.INTERNAL.value
        store.append_event(
            session.id,
            EventType.RUN_FAILED,
            {
                "error_code": code,
                "error_type": type(error).__name__,
                "message": str(error),
            },
            session_status=SessionStatus.FAILED,
        )
        raise

    store.append_event(
        session.id,
        EventType.MODEL_RESPONSE,
        cast(dict[str, JsonValue], response.model_dump(mode="json")),
    )
    store.append_event(
        session.id,
        EventType.RUN_FINISHED,
        {"reason": TerminationReason.COMPLETED.value},
        session_status=SessionStatus.COMPLETED,
    )
    return TurnResult(
        session=store.get_session(session.id),
        request=request,
        response=response,
        text=text,
    )
