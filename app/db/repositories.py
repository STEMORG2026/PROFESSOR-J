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


class SessionRepository:
    """Persist and load chat sessions with conversations."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    def create_session(
        self,
        session_id: str,
        learner_id: str,
        *,
        title: str | None = None,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        api_keys: str | None = None,
        base_url: str | None = None,
    ) -> None:
        now = utc_now().isoformat()
        self.engine.execute(
            """
            INSERT INTO sessions (session_id, learner_id, title, status, system_prompt,
                provider, model, api_keys, base_url, created_at, updated_at, last_activity_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                learner_id,
                title,
                system_prompt,
                provider,
                model,
                api_keys,
                base_url,
                now,
                now,
                now,
            ),
        )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        rows = self.engine.fetch_all(
            "SELECT session_id, learner_id, title, status, system_prompt, provider, model, "
            "api_keys, base_url, created_at, updated_at, last_activity_at FROM sessions "
            "WHERE session_id = ?",
            (session_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "session_id": row[0],
            "learner_id": row[1],
            "title": row[2],
            "status": row[3],
            "system_prompt": row[4],
            "provider": row[5],
            "model": row[6],
            "api_keys": row[7],
            "base_url": row[8],
            "created_at": row[9],
            "updated_at": row[10],
            "last_activity_at": row[11],
        }

    def list_sessions(self, learner_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.engine.fetch_all(
            "SELECT session_id, learner_id, title, status, provider, model, system_prompt, "
            "created_at, updated_at, last_activity_at FROM sessions WHERE learner_id = ? "
            "ORDER BY last_activity_at DESC LIMIT ?",
            (learner_id, limit),
        )
        return [
            {
                "session_id": row[0],
                "learner_id": row[1],
                "title": row[2],
                "status": row[3],
                "provider": row[4],
                "model": row[5],
                "system_prompt": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "last_activity_at": row[9],
            }
            for row in rows
        ]

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        api_keys: str | None = None,
        base_url: str | None = None,
    ) -> None:
        fields = []
        params = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if system_prompt is not None:
            fields.append("system_prompt = ?")
            params.append(system_prompt)
        if provider is not None:
            fields.append("provider = ?")
            params.append(provider)
        if model is not None:
            fields.append("model = ?")
            params.append(model)
        if api_keys is not None:
            fields.append("api_keys = ?")
            params.append(api_keys)
        if base_url is not None:
            fields.append("base_url = ?")
            params.append(base_url)
        if not fields:
            return
        fields.append("updated_at = ?")
        params.append(utc_now().isoformat())
        fields.append("last_activity_at = ?")
        params.append(utc_now().isoformat())
        params.append(session_id)
        self.engine.execute(
            f"UPDATE sessions SET {', '.join(fields)} WHERE session_id = ?",
            tuple(params),
        )

    def delete_session(self, session_id: str) -> None:
        self.engine.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        self.engine.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def create_conversation(
        self,
        conversation_id: str,
        session_id: str,
        title: str | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        import json

        now = utc_now().isoformat()
        self.engine.execute(
            """
            INSERT INTO conversations
                (conversation_id, session_id, title, messages, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conversation_id, session_id, title, json.dumps(messages or []), now, now),
        )

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        import json

        rows = self.engine.fetch_all(
            "SELECT conversation_id, session_id, title, messages, created_at, updated_at "
            "FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "conversation_id": row[0],
            "session_id": row[1],
            "title": row[2],
            "messages": json.loads(row[3]),
            "created_at": row[4],
            "updated_at": row[5],
        }

    def list_conversations(self, session_id: str) -> list[dict[str, Any]]:
        import json

        rows = self.engine.fetch_all(
            "SELECT conversation_id, session_id, title, messages, created_at, updated_at "
            "FROM conversations WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        )
        return [
            {
                "conversation_id": row[0],
                "session_id": row[1],
                "title": row[2],
                "messages": json.loads(row[3]),
                "created_at": row[4],
                "updated_at": row[5],
            }
            for row in rows
        ]

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: str | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        import json

        fields = []
        params = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if messages is not None:
            fields.append("messages = ?")
            params.append(json.dumps(messages))
        if not fields:
            return
        fields.append("updated_at = ?")
        params.append(utc_now().isoformat())
        params.append(conversation_id)
        self.engine.execute(
            f"UPDATE conversations SET {', '.join(fields)} WHERE conversation_id = ?",
            tuple(params),
        )

    def delete_conversation(self, conversation_id: str) -> None:
        self.engine.execute(
            "DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,)
        )

    def get_setting(self, key: str) -> str | None:
        rows = self.engine.fetch_all("SELECT value FROM user_settings WHERE key = ?", (key,))
        return rows[0][0] if rows else None

    def set_setting(self, key: str, value: str) -> None:
        now = utc_now().isoformat()
        self.engine.execute(
            """
            INSERT INTO user_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )

    def list_settings(self) -> list[tuple[str, str | None]]:
        """Return all stored user settings as (key, value) pairs."""
        rows = self.engine.fetch_all("SELECT key, value FROM user_settings ORDER BY key")
        return [(str(r[0]), str(r[1])) for r in rows]

    # Persona methods
    def create_persona(
        self, persona_id: str, name: str, system_prompt: str, description: str | None = None
    ) -> None:
        now = utc_now().isoformat()
        self.engine.execute(
            """
            INSERT INTO personas
                (persona_id, name, description, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (persona_id, name, description, system_prompt, now, now),
        )

    def get_persona(self, persona_id: str) -> dict[str, Any] | None:
        rows = self.engine.fetch_all(
            "SELECT persona_id, name, description, system_prompt, created_at, updated_at "
            "FROM personas WHERE persona_id = ?",
            (persona_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "persona_id": row[0],
            "name": row[1],
            "description": row[2],
            "system_prompt": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def list_personas(self) -> list[dict[str, Any]]:
        rows = self.engine.fetch_all(
            "SELECT persona_id, name, description, system_prompt, created_at, updated_at "
            "FROM personas ORDER BY name"
        )
        return [
            {
                "persona_id": row[0],
                "name": row[1],
                "description": row[2],
                "system_prompt": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }
            for row in rows
        ]

    def update_persona(self, persona_id: str, **kwargs: Any) -> None:
        fields = []
        params = []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                params.append(value)
        if not fields:
            return
        fields.append("updated_at = ?")
        params.append(utc_now().isoformat())
        params.append(persona_id)
        self.engine.execute(
            f"UPDATE personas SET {', '.join(fields)} WHERE persona_id = ?",
            tuple(params),
        )

    def delete_persona(self, persona_id: str) -> None:
        self.engine.execute("DELETE FROM personas WHERE persona_id = ?", (persona_id,))

    # Global defaults methods
    def get_default(self, key: str) -> str | None:
        """Get a global default setting (e.g. default_provider/default_model)."""
        return self.get_setting(f"default_{key}")

    def set_default(self, key: str, value: str) -> None:
        """Set a global default setting"""
        self.set_setting(f"default_{key}", value)
