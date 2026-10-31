from uuid import UUID

import pytest

from leogent.domain.enums import EventType, SessionStatus, TerminationReason
from leogent.domain.errors import SessionError
from leogent.sessions.sqlite import SQLiteSessionStore


def test_rebuild_run_state_folds_requests_usage_context_and_completion(
    store: SQLiteSessionStore,
) -> None:
    session = store.create_session()
    store.append_event(session.id, EventType.USER_MESSAGE, {"content": "first"})
    store.append_event(session.id, EventType.MODEL_REQUEST, {})
    store.append_event(
        session.id,
        EventType.MODEL_RESPONSE,
        {"content": "one", "usage": {"input_tokens": 10, "output_tokens": 5}},
    )
    store.append_event(
        session.id,
        EventType.CONTEXT_COMPACTED,
        {"estimated_tokens": 512},
    )
    store.append_event(session.id, EventType.USER_MESSAGE, {"content": "second"})
    store.append_event(session.id, EventType.MODEL_REQUEST, {})
    store.append_event(
        session.id,
        EventType.MODEL_RESPONSE,
        {"content": "two", "usage": {"input_tokens": 20, "output_tokens": 7}},
    )
    store.append_event(
        session.id,
        EventType.RUN_FINISHED,
        {"reason": "completed"},
    )

    state = store.rebuild_run_state(session.id)

    assert state.session_id == session.id
    assert state.current_step == 2
    assert state.usage.input_tokens == 30
    assert state.usage.output_tokens == 12
    assert state.usage.total_tokens == 42
    assert state.context_tokens == 512
    assert state.termination_reason is TerminationReason.COMPLETED


def test_rebuild_run_state_keeps_incomplete_run_open(
    store: SQLiteSessionStore,
) -> None:
    session = store.create_session()
    store.append_event(session.id, EventType.USER_MESSAGE, {"content": "pending"})

    state = store.rebuild_run_state(session.id)

    assert state.termination_reason is None
    assert state.current_step == 0


def test_rebuild_run_state_rejects_malformed_usage(
    store: SQLiteSessionStore,
) -> None:
    session = store.create_session()
    store.append_event(
        session.id,
        EventType.MODEL_RESPONSE,
        {"usage": {"input_tokens": "many"}},
    )

    with pytest.raises(SessionError, match="usage"):
        store.rebuild_run_state(session.id)


def test_fork_copies_prefix_with_new_event_ids(
    store: SQLiteSessionStore,
) -> None:
    source = store.create_session()
    store.append_event(source.id, EventType.USER_MESSAGE, {"content": "kept"})
    store.append_event(source.id, EventType.MODEL_RESPONSE, {"content": "later"})
    original_events = store.get_events(source.id)

    child = store.fork_session(source.id, at_sequence=2)
    copied_events = store.get_events(child.id)

    assert child.id != source.id
    assert child.status is SessionStatus.ACTIVE
    assert child.parent_session_id == source.id
    assert child.fork_event_sequence == 2
    assert [event.payload for event in copied_events] == [
        original_events[0].payload,
        original_events[1].payload,
    ]
    assert [event.event_id for event in copied_events] != [
        event.event_id for event in original_events[:2]
    ]
    assert store.get_events(source.id) == original_events


def test_fork_rejects_sequence_past_session_end(store: SQLiteSessionStore) -> None:
    session = store.create_session()

    with pytest.raises(SessionError, match="sequence"):
        store.fork_session(session.id, at_sequence=2)


def test_fork_rejects_unknown_parent(
    store: SQLiteSessionStore,
) -> None:
    with pytest.raises(SessionError):
        store.fork_session(
            UUID("00000000-0000-0000-0000-000000000001"),
            at_sequence=1,
        )
