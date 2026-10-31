import subprocess
import sys
from pathlib import Path

import pytest

from leogent.domain.enums import EventType, SessionStatus
from leogent.sessions.sqlite import SQLiteSessionStore


@pytest.mark.integration
def test_session_survives_abnormal_process_exit(tmp_path: Path) -> None:
    database_path = tmp_path / "recovery.db"
    script = """
import os
import sys
from leogent.domain.enums import EventType
from leogent.sessions.sqlite import SQLiteSessionStore

store = SQLiteSessionStore(sys.argv[1])
session = store.create_session()
store.append_event(session.id, EventType.USER_MESSAGE, {"content": "pending"})
print(session.id)
sys.stdout.flush()
os._exit(23)
"""

    result = subprocess.run(
        [sys.executable, "-c", script, str(database_path)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 23
    session_id = result.stdout.strip()
    store = SQLiteSessionStore(database_path)
    try:
        session = store.get_session(session_id)
        events = store.get_events(session.id)
        state = store.rebuild_run_state(session.id)
    finally:
        store.close()

    assert session.status is SessionStatus.ACTIVE
    assert [event.event_type for event in events] == [
        EventType.SESSION_STARTED,
        EventType.USER_MESSAGE,
    ]
    assert state.current_step == 0
    assert state.termination_reason is None
