from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from leogent.domain.enums import EventType, SessionStatus
from leogent.domain.event import Event, Session
from leogent.domain.state import RunState


class SessionStore(Protocol):
    def schema_version(self) -> int: ...

    def create_session(self) -> Session: ...

    def get_session(self, session_id: UUID | str) -> Session: ...

    def list_sessions(self, *, limit: int = 50) -> tuple[Session, ...]: ...

    def append_event(
        self,
        session_id: UUID | str,
        event_type: EventType,
        payload: dict[str, JsonValue] | None = None,
        *,
        event_id: UUID | None = None,
        session_status: SessionStatus | None = None,
    ) -> Event: ...

    def get_events(
        self,
        session_id: UUID | str,
        *,
        start_sequence: int = 1,
        end_sequence: int | None = None,
    ) -> tuple[Event, ...]: ...

    def update_session_status(
        self,
        session_id: UUID | str,
        status: SessionStatus,
    ) -> Session: ...

    def rebuild_run_state(self, session_id: UUID | str) -> RunState: ...

    def fork_session(self, session_id: UUID | str, at_sequence: int) -> Session: ...

    def close(self) -> None: ...
