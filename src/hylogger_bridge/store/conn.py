# Purpose: open one SQLite transaction and wake SSE readers only after it commits.
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def transaction(path: Path, changed: threading.Condition) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=10)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
        if connection.total_changes:
            with changed:
                changed.notify_all()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
