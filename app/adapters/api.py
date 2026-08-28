"""FastAPI application — the HTTP surface for the frontend (Phase 7).

Exposes a small, typed API surface:

* ``GET  /api/health`` — liveness of the composition root + brain.
* ``POST /api/chat``   — send a user prompt to the cognitive brain and get a
  response (deterministic MockProvider by default, so it runs with zero config
  and no API keys; a real provider can be registered on the built-in graph).

The brain defaults to the deterministic graph (``build_brain_graph()`` falls back
to ``MockProvider``), making the API immediately testable in local dev and CI.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.bootstrap import AppRoot, build_root
from app.brain.graph import CognitiveBrain

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """A single user prompt for the brain."""

    prompt: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    """The brain's reply plus provenance."""

    response: str
    intent: str
    provider: str
    plan_steps: int
    session_id: str | None = None


class HealthResponse(BaseModel):
    """Liveness summary for the running app."""

    status: str
    subsystems: dict[str, bool]
    ready: bool


# Module-level default root (built lazily; sqlite/in-memory default).
_root: AppRoot | None = None


def _get_root() -> AppRoot:
    global _root
    if _root is None:
        _root = build_root()
    return _root


def create_app(root: AppRoot | None = None, brain: CognitiveBrain | None = None) -> FastAPI:
    """Build the FastAPI app, optionally with injected dependencies (testing)."""
    app_root = root or _get_root()
    app_brain = brain or CognitiveBrain()

    app = FastAPI(title="PROFESSOR-J", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev only; tighten for production
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        h = app_root.health()
        return HealthResponse(
            status="ok" if h["ready"] else "degraded",
            subsystems={k: bool(v) for k, v in h.items() if k != "ready"},
            ready=bool(h["ready"]),
        )

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        result: dict[str, Any] = await app_brain.run(req.prompt)
        return ChatResponse(
            response=str(result["response"]),
            intent=str(result["intent"]),
            provider=str(result["provider"]),
            plan_steps=int(result["plan_steps"]),
            session_id=req.session_id,
        )

    return app


# Uvicorn entrypoint: `uvicorn app.adapters.api:app`
app = create_app()

__all__ = ["create_app", "app", "ChatRequest", "ChatResponse", "HealthResponse"]
