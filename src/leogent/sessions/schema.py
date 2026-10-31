import sqlite3
from datetime import UTC, datetime

SCHEMA_VERSION = 2

MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (
        1,
        (
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                parent_session_id TEXT,
                fork_event_sequence INTEGER,
                FOREIGN KEY (parent_session_id) REFERENCES sessions(id),
                CHECK (
                    (parent_session_id IS NULL AND fork_event_sequence IS NULL)
                    OR
                    (parent_session_id IS NOT NULL AND fork_event_sequence IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK (sequence > 0),
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE (session_id, sequence),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """,
        ),
    ),
    (
        2,
        (
            "CREATE INDEX sessions_updated_at ON sessions(updated_at DESC)",
            "CREATE INDEX events_session_sequence ON events(session_id, sequence)",
            """
            CREATE TRIGGER events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END
            """,
            """
            CREATE TRIGGER events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END
            """,
        ),
    ),
)


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    current = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_versions").fetchone()
    current_version = 0 if current is None else int(current[0])
    for version, statements in MIGRATIONS:
        if version <= current_version:
            continue
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(tz=UTC).isoformat()),
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
