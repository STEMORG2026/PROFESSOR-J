"""Persistence repositories for mastery and transcripts (Phase 9a).

Thin data-access objects over the :class:`DatabaseEngine`. They let the
cognitive/brain layers persist learner mastery (so the EvaluatorAgent and
ProfessorAgent can resume mastery across restarts) and session transcripts.
Swapping SQLite for Postgres only changes the engine URI.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.engine import DatabaseEngine
from app.domain.learner import MasteryScore
from app.domain.time import utc_now

logger = logging.getLogger(__name__)

_MASTERY_UPSERT = """
    INSERT INTO mastery_records
        (learner_id, concept_id, score, confidence, practice_count, correct_count, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(learner_id, concept_id) DO UPDATE SET
        score = excluded.score,
        confidence = excluded.confidence,
        practice_count = excluded.practice_count,
        correct_count = excluded.correct_count,
        updated_at = excluded.updated_at
"""

_INSERT_TRANSCRIPT = """
    INSERT INTO transcripts (session_id, learner_id, role, content, grounded, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
"""


class MasteryRepository:
    """Persist and load mastery scores."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    def upsert(self, learner_id: str, mastery: MasteryScore) -> None:
        self.engine.execute(
            _MASTERY_UPSERT,
            (
                learner_id,
                mastery.concept_id,
                mastery.score,
                mastery.confidence,
                mastery.practice_count,
                mastery.correct_count,
                utc_now().isoformat(),
            ),
        )

    def load_for(self, learner_id: str) -> dict[str, MasteryScore]:
        rows = self.engine.fetch_all(
            "SELECT concept_id, score, confidence, practice_count, correct_count "
            "FROM mastery_records WHERE learner_id = ?",
            (learner_id,),
        )
        result: dict[str, MasteryScore] = {}
        for row in rows:
            concept = str(row[0])
            result[concept] = MasteryScore(
                concept_id=concept,
                score=float(row[1]),
                confidence=float(row[2]),
                practice_count=int(row[3]),
                correct_count=int(row[4]),
            )
        return result


class TranscriptRepository:
    """Persist and load session transcript messages."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    def append(
        self,
        session_id: str,
        learner_id: str,
        role: str,
        content: str,
        *,
        grounded: bool = False,
    ) -> None:
        self.engine.execute(
            _INSERT_TRANSCRIPT,
            (
                session_id,
                learner_id,
                role,
                content,
                1 if grounded else 0,
                utc_now().isoformat(),
            ),
        )

    def history(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.engine.fetch_all(
            "SELECT role, content, grounded FROM transcripts "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        return [
            {"role": str(role), "content": str(content), "grounded": bool(grounded)}
            for role, content, grounded in rows
        ]


__all__ = ["MasteryRepository", "TranscriptRepository"]
