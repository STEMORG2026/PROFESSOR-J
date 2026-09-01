"""DatabaseEngine — pluggable persistence backbone (Phase 9a).

An engine-agnostic surface (connect, create tables, dispose) with a SQLite
implementation for local/dev. Postgres is the Phase 9 SEAM: the same
repositories run against a different engine URI (URL scheme ``postgresql+psycopg``)
without changing caller code.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# SQL schema is engine-agnostic SQLAlchemy Core DDL plus tolerance for engines
SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS mastery_records (
        learner_id   TEXT NOT NULL,
        concept_id   TEXT NOT NULL,
        score        REAL NOT NULL,
        confidence   REAL NOT NULL,
        practice_count INTEGER NOT NULL DEFAULT 0,
        correct_count  INTEGER NOT NULL DEFAULT 0,
        updated_at   TEXT NOT NULL,
        PRIMARY KEY (learner_id, concept_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transcripts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  TEXT NOT NULL,
        learner_id  TEXT NOT NULL,
        role        TEXT NOT NULL,
        content     TEXT NOT NULL,
        grounded    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id     TEXT PRIMARY KEY,
        learner_id     TEXT NOT NULL,
        title          TEXT,
        status         TEXT NOT NULL DEFAULT 'active',
        system_prompt  TEXT,
        provider       TEXT,
        model          TEXT,
        api_keys       TEXT,  -- JSON
        base_url       TEXT,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        last_activity_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        conversation_id  TEXT PRIMARY KEY,
        session_id       TEXT NOT NULL,
        title            TEXT,
        messages         TEXT NOT NULL,  -- JSON array
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        key          TEXT PRIMARY KEY,
        value        TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS personas (
        persona_id      TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        description     TEXT,
        system_prompt   TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )
    """,
)


class DatabaseEngine(ABC):
    """Pluggable persistence engine."""

    uri: str

    @abstractmethod
    def create_schema(self) -> None:
        """Create tables if absent."""

    @abstractmethod
    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        """Run a write statement with parameters."""

    @abstractmethod
    def fetch_all(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
        """Run a read statement and return rows."""

    @abstractmethod
    def dispose(self) -> None:
        """Close the underlying connection."""


class SqliteDatabaseEngine(DatabaseEngine):
    """SQLite-backed engine (local/dev)."""

    def __init__(self, path: str | Path = "data/professor.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.uri = f"sqlite:///{self.path}"
        import sqlite3

        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def create_schema(self) -> None:
        for statement in SCHEMA:
            self.conn.execute(statement)
        self.conn.commit()

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.conn.execute(sql, params)
        self.conn.commit()

    def fetch_all(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self.conn.execute(sql, params)]

    def dispose(self) -> None:
        self.conn.close()


__all__ = ["DatabaseEngine", "SqliteDatabaseEngine"]
