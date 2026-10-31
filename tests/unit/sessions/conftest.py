from collections.abc import Iterator

import pytest

from leogent.sessions.sqlite import SQLiteSessionStore


@pytest.fixture
def store() -> Iterator[SQLiteSessionStore]:
    session_store = SQLiteSessionStore(":memory:")
    try:
        yield session_store
    finally:
        session_store.close()
