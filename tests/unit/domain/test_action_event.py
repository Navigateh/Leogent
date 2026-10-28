from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from leogent.domain.action import Action, FinishAction, SearchMemoryAction, ToolCallAction
from leogent.domain.event import Event, EventType, Session, SessionStatus
from leogent.domain.model import ToolCall, ToolResult


def test_action_union_round_trips_tool_call() -> None:
    action = ToolCallAction(
        call=ToolCall(id="call_1", name="filesystem__read_file", arguments={"path": "README.md"})
    )
    adapter = TypeAdapter(Action)

    restored = adapter.validate_json(adapter.dump_json(action))

    assert restored == action


def test_action_union_parses_finish_action() -> None:
    action = TypeAdapter(Action).validate_python({"type": "finish", "answer": "Done."})

    assert action == FinishAction(answer="Done.")


def test_search_memory_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SearchMemoryAction(query="project", limit=0)


def test_event_converts_naive_timestamp_to_utc() -> None:
    event = Event(
        session_id=UUID("00000000-0000-0000-0000-000000000001"),
        sequence=1,
        event_type=EventType.USER_MESSAGE,
        occurred_at=datetime(2026, 10, 28, 12, 0),
        payload={"content": "hello"},
    )

    assert event.occurred_at == datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def test_fork_event_requires_parent_session() -> None:
    with pytest.raises(ValidationError):
        Session(status=SessionStatus.ACTIVE, fork_event_sequence=3)


def test_updated_time_cannot_precede_created_time() -> None:
    with pytest.raises(ValidationError):
        Session(
            created_at=datetime(2026, 10, 28, 12, 1, tzinfo=UTC),
            updated_at=datetime(2026, 10, 28, 12, 0, tzinfo=UTC),
        )


def test_tool_result_round_trip_preserves_failure_metadata() -> None:
    result = ToolResult(
        call_id="call_1",
        tool_name="filesystem__read_file",
        success=False,
        content="permission denied",
        error="permission denied",
        duration_ms=12.5,
        truncated=True,
    )

    assert ToolResult.model_validate_json(result.model_dump_json()) == result
