from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from leogent.domain.enums import EventType, SessionStatus
from leogent.domain.errors import DuplicateEvent, SessionNotFound
from leogent.sessions.sqlite import SQLiteSessionStore


def test_create_and_append_events_assign_contiguous_sequences(
    store: SQLiteSessionStore,
) -> None:
    session = store.create_session()

    user = store.append_event(
        session.id,
        EventType.USER_MESSAGE,
        {"content": "hello"},
    )
    answer = store.append_event(
        session.id,
        EventType.MODEL_RESPONSE,
        {"content": "hi"},
    )

    events = store.get_events(session.id)
    assert [event.event_type for event in events] == [
        EventType.SESSION_STARTED,
        EventType.USER_MESSAGE,
        EventType.MODEL_RESPONSE,
    ]
    assert [user.sequence, answer.sequence] == [2, 3]
    assert [event.sequence for event in events] == [1, 2, 3]


def test_event_payload_round_trips_through_sqlite(store: SQLiteSessionStore) -> None:
    session = store.create_session()
    payload: dict[str, JsonValue] = {
        "content": "hello",
        "nested": {"values": [1, 2, 3]},
        "enabled": True,
    }

    event = store.append_event(session.id, EventType.USER_MESSAGE, payload)

    assert store.get_events(session.id)[-1] == event


def test_duplicate_event_id_is_rejected_without_changing_event_count(
    store: SQLiteSessionStore,
) -> None:
    session = store.create_session()
    event_id = uuid4()
    store.append_event(
        session.id,
        EventType.USER_MESSAGE,
        {"content": "first"},
        event_id=event_id,
    )

    with pytest.raises(DuplicateEvent):
        store.append_event(
            session.id,
            EventType.USER_MESSAGE,
            {"content": "second"},
            event_id=event_id,
        )

    assert len(store.get_events(session.id)) == 2


def test_unknown_session_raises_session_not_found(store: SQLiteSessionStore) -> None:
    missing = UUID("00000000-0000-0000-0000-000000000001")

    with pytest.raises(SessionNotFound):
        store.get_session(missing)


def test_event_and_status_update_are_visible_together(
    store: SQLiteSessionStore,
) -> None:
    session = store.create_session()

    store.append_event(
        session.id,
        EventType.RUN_FINISHED,
        {"reason": "completed"},
        session_status=SessionStatus.COMPLETED,
    )

    assert store.get_session(session.id).status is SessionStatus.COMPLETED
    assert store.get_events(session.id)[-1].event_type is EventType.RUN_FINISHED


def test_session_status_update_refreshes_updated_time(
    store: SQLiteSessionStore,
) -> None:
    session = store.create_session()

    updated = store.update_session_status(session.id, SessionStatus.CANCELLED)

    assert updated.status is SessionStatus.CANCELLED
    assert updated.updated_at >= session.updated_at


def test_list_sessions_returns_newest_update_first(store: SQLiteSessionStore) -> None:
    first = store.create_session()
    second = store.create_session()
    store.append_event(first.id, EventType.USER_MESSAGE, {"content": "newer"})

    sessions = store.list_sessions()

    assert [session.id for session in sessions][:2] == [first.id, second.id]


def test_get_events_supports_sequence_ranges(store: SQLiteSessionStore) -> None:
    session = store.create_session()
    for sequence in range(2, 6):
        store.append_event(
            session.id,
            EventType.USER_MESSAGE,
            {"content": str(sequence)},
        )

    events = store.get_events(session.id, start_sequence=2, end_sequence=4)

    assert [event.sequence for event in events] == [2, 3, 4]
