import pytest

from leogent.domain.enums import EventType, SessionStatus
from leogent.domain.errors import ProviderError
from leogent.domain.model import MessageRole, ModelResponse
from leogent.providers.mock import ScriptedProvider
from leogent.sessions.runner import TurnResult, execute_turn
from leogent.sessions.sqlite import SQLiteSessionStore


def test_single_turn_persists_complete_event_sequence(store: SQLiteSessionStore) -> None:
    provider = ScriptedProvider((ModelResponse(content="Hello", finish_reason="stop"),))
    output: list[str] = []

    result = execute_turn(store, provider, "Say hello", on_text=output.append)
    events = store.get_events(result.session.id)

    assert isinstance(result, TurnResult)
    assert result.text == "Hello"
    assert output == ["Hello"]
    assert [event.event_type for event in events] == [
        EventType.SESSION_STARTED,
        EventType.USER_MESSAGE,
        EventType.MODEL_REQUEST,
        EventType.MODEL_RESPONSE,
        EventType.RUN_FINISHED,
    ]
    assert store.get_session(result.session.id).status is SessionStatus.COMPLETED


def test_resume_includes_prior_user_and_assistant_messages(
    store: SQLiteSessionStore,
) -> None:
    provider = ScriptedProvider(
        (
            ModelResponse(content="First answer"),
            ModelResponse(content="Second answer"),
        )
    )
    first = execute_turn(store, provider, "First question")

    second = execute_turn(
        store,
        provider,
        "Second question",
        session_id=first.session.id,
    )

    request = provider.requests[-1]
    assert [message.role for message in request.messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
        MessageRole.USER,
    ]
    assert [message.content for message in request.messages] == [
        "First question",
        "First answer",
        "Second question",
    ]
    assert second.session.id == first.session.id
    assert len(store.get_events(first.session.id)) == 9


def test_streaming_turn_accumulates_text_and_persists_response(
    store: SQLiteSessionStore,
) -> None:
    provider = ScriptedProvider((ModelResponse(content="streamed"),))
    output: list[str] = []

    result = execute_turn(
        store,
        provider,
        "stream",
        stream=True,
        on_text=output.append,
    )
    response_event = store.get_events(result.session.id)[-2]

    assert result.text == "streamed"
    assert output == ["streamed"]
    assert response_event.payload["content"] == "streamed"


def test_provider_failure_marks_session_failed_and_records_error(
    store: SQLiteSessionStore,
) -> None:
    provider = ScriptedProvider((ProviderError("model unavailable"),))

    with pytest.raises(ProviderError, match="model unavailable"):
        execute_turn(store, provider, "fail")

    session = store.list_sessions()[0]
    events = store.get_events(session.id)
    assert session.status is SessionStatus.FAILED
    assert events[-1].event_type is EventType.RUN_FAILED
    assert events[-1].payload["message"] == "model unavailable"


def test_runner_rejects_empty_prompt(store: SQLiteSessionStore) -> None:
    provider = ScriptedProvider(())

    with pytest.raises(ValueError, match="must not be empty"):
        execute_turn(store, provider, "  ")
