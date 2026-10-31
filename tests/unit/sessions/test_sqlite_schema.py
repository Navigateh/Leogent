import sqlite3
from pathlib import Path

from leogent.domain.enums import EventType
from leogent.sessions.sqlite import SQLiteSessionStore, default_database_path


def test_initialize_is_idempotent_and_records_schema_version(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(database_path)
    assert store.schema_version() == 2
    store.close()

    reopened = SQLiteSessionStore(database_path)
    try:
        assert reopened.schema_version() == 2
    finally:
        reopened.close()


def test_event_table_rejects_update_and_delete(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(database_path)
    session = store.create_session()
    event = store.append_event(
        session.id,
        EventType.USER_MESSAGE,
        {"content": "immutable"},
    )
    store.close()

    connection = sqlite3.connect(database_path)
    try:
        try:
            connection.execute(
                "UPDATE events SET payload_json = '{}' WHERE event_id = ?",
                (str(event.event_id),),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
        else:
            raise AssertionError("update unexpectedly succeeded")
    finally:
        connection.close()


def test_event_table_rejects_delete(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(database_path)
    session = store.create_session()
    event = store.append_event(
        session.id,
        EventType.USER_MESSAGE,
        {"content": "immutable"},
    )
    store.close()

    connection = sqlite3.connect(database_path)
    try:
        try:
            connection.execute(
                "DELETE FROM events WHERE event_id = ?",
                (str(event.event_id),),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
        else:
            raise AssertionError("delete unexpectedly succeeded")
    finally:
        connection.close()


def test_default_database_path_uses_leogent_home(tmp_path: Path) -> None:
    assert default_database_path({"LEOGENT_HOME": str(tmp_path)}) == tmp_path / "leogent.db"
