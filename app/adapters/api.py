"""FastAPI application — the HTTP surface for the frontend (Phase 7).

Exposes a small, typed API surface:

* ``GET  /api/health`` — liveness of the composition root + brain.
* ``POST /api/chat``   — send a user prompt to the cognitive brain and get a
  response. Accepts optional ``provider``, ``model``, ``api_key``, and
  ``base_url`` to dynamically select and configure a cloud provider per-request.

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
from app.models.catalog import ProviderCatalog
from app.models.cloud_providers import (
    GoogleAIProvider,
    NVIDIANIMProvider,
    OpenRouterProvider,
)
from app.models.providers import OpenAICompatProvider

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """A single user prompt for the brain, with optional provider selection."""

    prompt: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = None
    provider: str | None = Field(
        default=None,
        description="Provider id (e.g. 'openrouter', 'openai_compat', 'mock')",
    )
    model: str | None = Field(
        default=None,
        description="Model name to use with the selected provider",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for the selected provider",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for OpenAI-compatible providers",
    )


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


def _make_provider_for(
    provider_id: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> Any | None:
    """Dynamically construct a provider from the user's frontend selection.

    Returns None when ``provider_id`` is ``mock`` or unrecognised (so the
    brain falls back to its default router with a MockProvider).
    """
    pid = (provider_id or "mock").strip().lower()

    if pid == "mock":
        return None  # caller uses default router with MockProvider

    if pid == "openrouter":
        return OpenRouterProvider(
            name="openrouter",
            model=model or "openrouter/auto",
            api_key=api_key,
        )

    if pid == "nvidia_nim":
        return NVIDIANIMProvider(
            name="nvidia_nim",
            model=model or "nvidia/nemotron-3-ultra",
            api_key=api_key,
        )

    if pid == "google_ai":
        return GoogleAIProvider(
            name="google_ai",
            model=model or "gemini-1.5-pro",
            api_key=api_key,
        )

    if pid == "openai_compat":
        url = (base_url or "https://api.openai.com/v1").rstrip("/")
        return OpenAICompatProvider(
            name="openai_compat",
            model=model or "gpt-4o-mini",
            base_url=url,
            api_key=api_key,
        )

    # Fallback: treat as openai_compat with the provider id as a label
    logger.warning("Unknown provider_id=%r; treating as OpenAI-compatible", pid)
    url = (base_url or "https://api.openai.com/v1").rstrip("/")
    return OpenAICompatProvider(
        name=pid,
        model=model or "gpt-4o-mini",
        base_url=url,
        api_key=api_key,
    )


def create_app(root: AppRoot | None = None, brain: CognitiveBrain | None = None) -> FastAPI:
    """Build the FastAPI app, optionally with injected dependencies (testing)."""
    app_root = root or _get_root()

    def _build_brain_for(req: ChatRequest | None = None) -> CognitiveBrain:
        """Build a brain wired to the provider the user asked for."""
        if req and req.provider:
            provider = _make_provider_for(
                provider_id=req.provider,
                model=req.model or "",
                api_key=req.api_key,
                base_url=req.base_url,
            )
            if provider is not None:
                catalog = ProviderCatalog([provider])
                router = __import__("app.models.router", fromlist=["ModelRouter"]).ModelRouter(
                    catalog
                )
                return CognitiveBrain(router=router)
        return brain or CognitiveBrain()

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
        active_brain = _build_brain_for(req)
        result: dict[str, Any] = await active_brain.run(req.prompt)
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
