import sqlite3
from contextlib import contextmanager


def get_connection(sqlite_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(sqlite_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def connect(sqlite_path: str):
    conn = get_connection(sqlite_path)
    try:
        yield conn
    finally:
        conn.close()