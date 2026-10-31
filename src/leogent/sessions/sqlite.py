import json
import sqlite3
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from pydantic import JsonValue, ValidationError

from leogent.config.paths import data_directory
from leogent.domain.common import Usage, utc_now
from leogent.domain.enums import EventType, SessionStatus, TerminationReason
from leogent.domain.errors import (
    DuplicateEvent,
    SessionError,
    SessionNotFound,
)
from leogent.domain.event import Event, Session
from leogent.domain.state import RunState
from leogent.sessions.schema import migrate


def default_database_path(environ: Mapping[str, str] | None = None) -> Path:
    return data_directory(environ) / "leogent.db"


def _row_mapping(row: sqlite3.Row) -> dict[str, object]:
    return {key: cast(object, row[key]) for key in row.keys()}  # noqa: SIM118


class SQLiteSessionStore:
    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self._database_path = str(database_path)
        if self._database_path != ":memory:":
            Path(self._database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._database_path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if self._database_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        migrate(self._connection)

    def schema_version(self) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_versions"
        ).fetchone()
        return 0 if row is None else int(row[0])

    def create_session(self) -> Session:
        now = utc_now()
        session = Session(created_at=now, updated_at=now)
        with self._transaction():
            self._insert_session(session)
            self._insert_event(
                session_id=session.id,
                event_type=EventType.SESSION_STARTED,
                payload={"status": SessionStatus.ACTIVE.value},
            )
        return self.get_session(session.id)

    def get_session(self, session_id: UUID | str) -> Session:
        return self._session_from_row(self._require_session_row(session_id))

    def list_sessions(self, *, limit: int = 50) -> tuple[Session, ...]:
        if limit < 1:
            raise SessionError("Session list limit must be positive")
        rows = self._connection.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return tuple(self._session_from_row(row) for row in rows)

    def append_event(
        self,
        session_id: UUID | str,
        event_type: EventType,
        payload: dict[str, JsonValue] | None = None,
        *,
        event_id: UUID | None = None,
        session_status: SessionStatus | None = None,
    ) -> Event:
        resolved_id = self._resolve_session_id(session_id)
        try:
            with self._transaction():
                self._require_session_row(resolved_id)
                event = self._insert_event(
                    session_id=resolved_id,
                    event_type=event_type,
                    payload={} if payload is None else payload,
                    event_id=event_id,
                    session_status=session_status,
                )
        except sqlite3.IntegrityError as error:
            if "events.event_id" in str(error):
                raise DuplicateEvent(f"Event {event_id} already exists") from error
            raise SessionError("Unable to append session event") from error
        return event

    def get_events(
        self,
        session_id: UUID | str,
        *,
        start_sequence: int = 1,
        end_sequence: int | None = None,
    ) -> tuple[Event, ...]:
        resolved_id = self._resolve_session_id(session_id)
        self._require_session_row(resolved_id)
        if start_sequence < 1:
            raise SessionError("Event sequence must be positive")
        if end_sequence is not None and end_sequence < start_sequence:
            return ()
        rows = self._connection.execute(
            """
            SELECT * FROM events
            WHERE session_id = ?
              AND sequence >= ?
              AND (? IS NULL OR sequence <= ?)
            ORDER BY sequence ASC
            """,
            (str(resolved_id), start_sequence, end_sequence, end_sequence),
        ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    def update_session_status(
        self,
        session_id: UUID | str,
        status: SessionStatus,
    ) -> Session:
        resolved_id = self._resolve_session_id(session_id)
        with self._transaction():
            self._require_session_row(resolved_id)
            self._connection.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, utc_now().isoformat(), str(resolved_id)),
            )
        return self.get_session(resolved_id)

    def rebuild_run_state(self, session_id: UUID | str) -> RunState:
        resolved_id = self._resolve_session_id(session_id)
        events = self.get_events(resolved_id)
        current_step = 0
        context_tokens = 0
        input_tokens = 0
        output_tokens = 0
        termination_reason: TerminationReason | None = None

        for event in events:
            if event.event_type is EventType.MODEL_REQUEST:
                current_step += 1
            elif event.event_type is EventType.MODEL_RESPONSE:
                usage = event.payload.get("usage")
                if usage is not None:
                    try:
                        usage_data = cast(dict[str, object], usage)
                        input_tokens += int(cast(int, usage_data.get("input_tokens", 0)))
                        output_tokens += int(cast(int, usage_data.get("output_tokens", 0)))
                    except (AttributeError, TypeError, ValueError) as error:
                        raise SessionError("Persisted model usage is malformed") from error
            elif event.event_type is EventType.CONTEXT_COMPACTED:
                value = event.payload.get("estimated_tokens", event.payload.get("context_tokens"))
                if value is not None:
                    try:
                        context_tokens = int(cast(int, value))
                    except (TypeError, ValueError) as error:
                        raise SessionError("Persisted context token count is malformed") from error
            elif event.event_type is EventType.RUN_FINISHED:
                reason = event.payload.get("reason", TerminationReason.COMPLETED.value)
                try:
                    termination_reason = TerminationReason(str(reason))
                except ValueError as error:
                    raise SessionError("Persisted termination reason is malformed") from error
            elif event.event_type is EventType.RUN_FAILED:
                termination_reason = TerminationReason.ERROR

        return RunState(
            session_id=resolved_id,
            current_step=current_step,
            context_tokens=context_tokens,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
            termination_reason=termination_reason,
        )

    def fork_session(self, session_id: UUID | str, at_sequence: int) -> Session:
        if at_sequence < 1:
            raise SessionError("Fork sequence must be positive")
        source_id = self._resolve_session_id(session_id)
        source_events = self.get_events(source_id, end_sequence=at_sequence)
        if not source_events or source_events[-1].sequence != at_sequence:
            raise SessionError(f"Fork sequence {at_sequence} does not exist in session {source_id}")
        now = utc_now()
        child = Session(
            created_at=now,
            updated_at=now,
            parent_session_id=source_id,
            fork_event_sequence=at_sequence,
        )
        with self._transaction():
            self._insert_session(child)
            for event in source_events:
                self._connection.execute(
                    """
                    INSERT INTO events(
                        event_id, session_id, sequence, event_type, occurred_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        str(child.id),
                        event.sequence,
                        event.event_type.value,
                        event.occurred_at.isoformat(),
                        json.dumps(event.payload, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
            self._connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now.isoformat(), str(child.id)),
            )
        return self.get_session(child.id)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteSessionStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Generator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def _insert_session(self, session: Session) -> None:
        self._connection.execute(
            """
            INSERT INTO sessions(
                id, status, created_at, updated_at, parent_session_id, fork_event_sequence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(session.id),
                session.status.value,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                None if session.parent_session_id is None else str(session.parent_session_id),
                session.fork_event_sequence,
            ),
        )

    def _insert_event(
        self,
        *,
        session_id: UUID,
        event_type: EventType,
        payload: dict[str, JsonValue],
        event_id: UUID | None = None,
        session_status: SessionStatus | None = None,
    ) -> Event:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE session_id = ?",
            (str(session_id),),
        ).fetchone()
        sequence = 1 if row is None else int(row[0])
        event = Event(
            event_id=uuid4() if event_id is None else event_id,
            session_id=session_id,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
        )
        self._connection.execute(
            """
            INSERT INTO events(
                event_id, session_id, sequence, event_type, occurred_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(event.event_id),
                str(event.session_id),
                event.sequence,
                event.event_type.value,
                event.occurred_at.isoformat(),
                json.dumps(event.payload, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        updated_at = event.occurred_at.isoformat()
        if session_status is None:
            self._connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (updated_at, str(session_id)),
            )
        else:
            self._connection.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                (session_status.value, updated_at, str(session_id)),
            )
        return event

    def _resolve_session_id(self, session_id: UUID | str) -> UUID:
        if isinstance(session_id, UUID):
            return session_id
        try:
            return UUID(session_id)
        except ValueError as error:
            raise SessionNotFound(f"Invalid session id: {session_id}") from error

    def _require_session_row(self, session_id: UUID | str) -> sqlite3.Row:
        resolved_id = self._resolve_session_id(session_id)
        row = self._connection.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (str(resolved_id),),
        ).fetchone()
        if row is None:
            raise SessionNotFound(f"Session {resolved_id} was not found")
        return row

    def _session_from_row(self, row: sqlite3.Row) -> Session:
        try:
            return Session.model_validate_json(json.dumps(_row_mapping(row)))
        except ValidationError as error:
            raise SessionError("Persisted session row is invalid") from error

    def _event_from_row(self, row: sqlite3.Row) -> Event:
        data = _row_mapping(row)
        payload_json = data.pop("payload_json")
        if not isinstance(payload_json, str):
            raise SessionError("Persisted event payload is invalid")
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as error:
            raise SessionError("Persisted event payload is not valid JSON") from error
        if not isinstance(payload, dict):
            raise SessionError("Persisted event payload must be a JSON object")
        data["payload"] = cast(dict[str, JsonValue], payload)
        try:
            return Event.model_validate_json(json.dumps(data))
        except ValidationError as error:
            raise SessionError("Persisted event row is invalid") from error
