"""Database subsystem — pluggable persistence backbone (Phase 9a).

SQLite is implemented; Postgres is the Phase 9 SEAM (different engine URI).
"""

from app.db.engine import DatabaseEngine, SqliteDatabaseEngine
from app.db.repositories import MasteryRepository, TranscriptRepository

__all__ = [
    "DatabaseEngine",
    "SqliteDatabaseEngine",
    "MasteryRepository",
    "TranscriptRepository",
]
