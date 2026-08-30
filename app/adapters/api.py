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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.bootstrap import AppRoot, build_root
from app.brain.graph import CognitiveBrain
from app.brain.intents import Intent
from app.config.settings import get_settings
from app.domain.plan import ExecutionPlan
from app.models.catalog import ProviderCatalog
from app.models.cloud_providers import (
    GoogleAIProvider,
    NVIDIANIMProvider,
    OpenRouterProvider,
)
from app.models.providers import OpenAICompatProvider
from app.voice.routes import router as voice_router

logger = logging.getLogger(__name__)

# ── Default provider route ───────────────────────────────────────────
# When nothing is configured (fresh DB, direct API call), the app falls back
# to the workspace's Singularity OpenAI-compatible endpoint, keyed from the
# repo `.env` (SINGULARITY_API_KEY). Model ids are sent to Singularity
# verbatim (no vendor prefix), matching the verified working surface.
_DEFAULTS = get_settings()
DEFAULT_PROVIDER = "singularity"
DEFAULT_MODEL = "deepseek-v4-flash-0731"
DEFAULT_BASE_URL = _DEFAULTS.singularity_base_url
DEFAULT_API_KEY = _DEFAULTS.singularity_api_key


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
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt to override the default persona",
    )


class SessionCreateRequest(BaseModel):
    learner_id: str = "default"
    title: str | None = None
    provider: str | None = None
    model: str | None = None
    api_keys: dict[str, str] | None = None
    base_url: str | None = None
    system_prompt: str | None = None


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    provider: str | None = None
    model: str | None = None
    api_keys: dict[str, str] | None = None
    base_url: str | None = None
    system_prompt: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    learner_id: str
    title: str | None
    status: str
    provider: str | None
    model: str | None
    system_prompt: str | None
    created_at: str
    updated_at: str
    last_activity_at: str

    class Config:
        from_attributes = True


class ConversationCreateRequest(BaseModel):
    session_id: str
    title: str | None = None
    messages: list[dict[str, Any]] | None = None


class ConversationResponse(BaseModel):
    conversation_id: str
    session_id: str
    title: str | None
    messages: list[dict[str, Any]]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SettingsRequest(BaseModel):
    key: str
    value: str


class PersonaCreateRequest(BaseModel):
    persona_id: str | None = None
    name: str
    system_prompt: str
    description: str | None = None


class PersonaUpdateRequest(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    description: str | None = None


class PersonaResponse(BaseModel):
    persona_id: str
    name: str
    description: str | None
    system_prompt: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DefaultSetRequest(BaseModel):
    key: str
    value: str


class DefaultResponse(BaseModel):
    key: str
    value: str | None


class SkillExecuteRequest(BaseModel):
    skill_name: str
    params: dict[str, Any] = {}


class SkillExecuteResponse(BaseModel):
    status: str  # success, failed
    data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = {}


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
            api_key=api_key or _DEFAULTS.openrouter_api_key,
        )

    if pid == "nvidia_nim":
        return NVIDIANIMProvider(
            name="nvidia_nim",
            model=model or "nvidia/nemotron-3-ultra",
            api_key=api_key or _DEFAULTS.nvidia_nim_api_key,
        )

    if pid == "google_ai":
        return GoogleAIProvider(
            name="google_ai",
            model=model or "gemini-1.5-pro",
            api_key=api_key or _DEFAULTS.google_ai_api_key or _DEFAULTS.google_api_key,
        )

    if pid == "openai_compat":
        url = (base_url or "https://api.openai.com/v1").rstrip("/")
        return OpenAICompatProvider(
            name="openai_compat",
            model=model or "gpt-4o-mini",
            base_url=url,
            api_key=api_key,
        )

    if pid == "singularity":
        # OpenAI-compatible Singularity endpoint; the key is read server-side
        # from the repo .env unless the client supplies one explicitly.
        url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        return OpenAICompatProvider(
            name="singularity",
            model=model or DEFAULT_MODEL,
            base_url=url,
            api_key=api_key or DEFAULT_API_KEY,
        )

    if pid == "bluesmind":
        # OpenAI-compatible Bluesmind endpoint; the key is read server-side
        # from the repo .env unless the client supplies one explicitly.
        settings = get_settings()
        url = (base_url or settings.bluesmind_base_url).rstrip("/")
        return OpenAICompatProvider(
            name="bluesmind",
            model=model or "kimi-k2.5",
            base_url=url,
            api_key=api_key or settings.bluesmind_api_key,
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

    def _build_brain_for(
        req: ChatRequest | None = None,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> CognitiveBrain:
        """Build a brain wired to the provider the user asked for."""
        import json

        # Explicit args win over request fields: the chat handler resolves
        # session/global values and passes them here as kwargs, while request
        # fields arrive unset on a bare call.
        provider_id = provider or (req.provider if req else None)
        model_name = model or (req.model if req else None) or ""
        resolved_url = base_url or (req.base_url if req else None)
        resolved_key = api_key or (req.api_key if req else None)

        # Existing session: fill gaps from the session, then the built-in
        # Singularity defaults, so a bare session works out of the box.
        if req and req.session_id:
            session = app_root.session_repo.get_session(req.session_id)
            if session:
                provider_id = provider_id or session.get("provider") or DEFAULT_PROVIDER
                model_name = model_name or session.get("model") or DEFAULT_MODEL
                resolved_url = resolved_url or session.get("base_url") or DEFAULT_BASE_URL
                if not resolved_key and session.get("api_keys"):
                    try:
                        session_keys = json.loads(session["api_keys"])
                        resolved_key = next(iter(session_keys.values()), None)
                    except (TypeError, ValueError):
                        pass

        if provider_id:
            provider_obj = _make_provider_for(
                provider_id=provider_id,
                model=model_name,
                api_key=resolved_key,
                base_url=resolved_url,
            )
            if provider_obj is not None:
                # Include MockProvider as fallback so the request never fully fails
                from app.models.providers import MockProvider

                fallback = MockProvider(name="mock", model="mock-model")
                catalog = ProviderCatalog([provider_obj, fallback])
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

    # Include voice routes
    app.include_router(voice_router)

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
        # If session_id provided but no system_prompt, try to get from session
        system_prompt = req.system_prompt
        provider = req.provider
        model = req.model
        base_url = req.base_url
        api_key = req.api_key

        if req.session_id:
            session = app_root.session_repo.get_session(req.session_id)
            if session:
                # Check session first, then global defaults, then built-ins
                system_prompt = (
                    system_prompt
                    or session.get("system_prompt")
                    or app_root.session_repo.get_default("system_prompt")
                )
                provider = (
                    provider
                    or session.get("provider")
                    or app_root.session_repo.get_default("provider")
                    or DEFAULT_PROVIDER
                )
                model = (
                    model
                    or session.get("model")
                    or app_root.session_repo.get_default("model")
                    or DEFAULT_MODEL
                )
                base_url = (
                    base_url
                    or session.get("base_url")
                    or app_root.session_repo.get_default("base_url")
                    or DEFAULT_BASE_URL
                )
                if not api_key and session.get("api_keys"):
                    import json

                    try:
                        api_keys = json.loads(session["api_keys"])
                        # Get the first available API key
                        api_key = api_key or next(iter(api_keys.values()), None)
                    except (TypeError, ValueError):
                        pass

        active_brain = _build_brain_for(
            req,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
        out = await active_brain.graph.ainvoke(
            {
                "prompt": req.prompt,
                "system_prompt": system_prompt,
            }
        )
        return ChatResponse(
            response=str(out.get("response", "")),
            intent=str((out.get("intent") or Intent.DIRECT_CHAT).value),
            provider=str(out.get("provider_used", "unknown")),
            plan_steps=len(out.get("plan", ExecutionPlan()).steps),
            session_id=req.session_id,
        )

    # Session endpoints
    @app.post("/api/sessions", response_model=SessionResponse)
    async def create_session(req: SessionCreateRequest) -> SessionResponse:
        import json
        import uuid

        session_id = f"sess-{uuid.uuid4().hex[:8]}"

        # Apply defaults for missing fields (global defaults, then built-ins)
        provider = req.provider or app_root.session_repo.get_default("provider") or DEFAULT_PROVIDER
        model = req.model or app_root.session_repo.get_default("model") or DEFAULT_MODEL
        system_prompt = req.system_prompt or app_root.session_repo.get_default("system_prompt")
        base_url = req.base_url or app_root.session_repo.get_default("base_url") or DEFAULT_BASE_URL

        app_root.session_repo.create_session(
            session_id=session_id,
            learner_id=req.learner_id,
            title=req.title,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
            api_keys=json.dumps(req.api_keys) if req.api_keys else None,
            base_url=base_url,
        )
        session = app_root.session_repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(**session)

    @app.get("/api/sessions", response_model=list[SessionResponse])
    async def list_sessions(learner_id: str = "default", limit: int = 50) -> list[SessionResponse]:
        sessions = app_root.session_repo.list_sessions(learner_id, limit)
        return [SessionResponse(**s) for s in sessions]

    @app.get("/api/sessions/{session_id}", response_model=SessionResponse)
    async def get_session(session_id: str) -> SessionResponse:
        session = app_root.session_repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(**session)

    @app.patch("/api/sessions/{session_id}", response_model=SessionResponse)
    async def update_session(session_id: str, req: SessionUpdateRequest) -> SessionResponse:
        import json

        update_data = req.model_dump(exclude_unset=True)
        if "api_keys" in update_data and update_data["api_keys"] is not None:
            update_data["api_keys"] = json.dumps(update_data["api_keys"])
        app_root.session_repo.update_session(session_id, **update_data)
        session = app_root.session_repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(**session)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, str]:
        app_root.session_repo.delete_session(session_id)
        return {"status": "deleted"}

    # Conversation endpoints
    @app.post("/api/conversations", response_model=ConversationResponse)
    async def create_conversation(req: ConversationCreateRequest) -> ConversationResponse:
        import uuid

        conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
        app_root.session_repo.create_conversation(
            conversation_id=conversation_id,
            session_id=req.session_id,
            title=req.title,
            messages=req.messages,
        )
        conv = app_root.session_repo.get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse(**conv)

    @app.get("/api/sessions/{session_id}/conversations", response_model=list[ConversationResponse])
    async def list_conversations(session_id: str) -> list[ConversationResponse]:
        convs = app_root.session_repo.list_conversations(session_id)
        return [ConversationResponse(**c) for c in convs]

    @app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
    async def get_conversation(conversation_id: str) -> ConversationResponse:
        conv = app_root.session_repo.get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse(**conv)

    @app.patch("/api/conversations/{conversation_id}", response_model=ConversationResponse)
    async def update_conversation(
        conversation_id: str, req: ConversationCreateRequest
    ) -> ConversationResponse:
        app_root.session_repo.update_conversation(
            conversation_id, title=req.title, messages=req.messages
        )
        conv = app_root.session_repo.get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse(**conv)

    @app.delete("/api/conversations/{conversation_id}")
    async def delete_conversation(conversation_id: str) -> dict[str, str]:
        app_root.session_repo.delete_conversation(conversation_id)
        return {"status": "deleted"}

    # Settings endpoints
    @app.post("/api/settings")
    async def set_setting(req: SettingsRequest) -> dict[str, str]:
        app_root.session_repo.set_setting(req.key, req.value)
        return {"status": "saved"}

    @app.get("/api/settings", response_model=list[DefaultResponse])
    async def list_settings() -> list[DefaultResponse]:
        """All stored user settings as {key, value} pairs (settings UI)."""
        return [DefaultResponse(key=k, value=v) for k, v in app_root.session_repo.list_settings()]

    @app.get("/api/settings/{key}")
    async def get_setting(key: str) -> dict[str, str | None]:
        value = app_root.session_repo.get_setting(key)
        return {"key": key, "value": value}

    # File upload endpoints
    @app.post("/api/upload")
    async def upload_file(
        session_id: str = Form(...),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        import os
        import uuid

        # Validate session exists
        session = app_root.session_repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Create uploads directory
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)

        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
        stored_name = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(upload_dir, stored_name)

        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Store file metadata in session as conversation or attachment
        file_info = {
            "original_name": file.filename,
            "stored_name": stored_name,
            "path": file_path,
            "size": len(content),
            "content_type": file.content_type,
        }

        # Add to session as a system message or attachment
        # For now, return the file info
        return {
            "status": "uploaded",
            "file": file_info,
        }

    @app.post("/api/chat/upload")
    async def chat_with_upload(
        prompt: str = Form(""),
        session_id: str = Form(...),
        provider: str | None = Form(None),
        model: str | None = Form(None),
        system_prompt: str | None = Form(None),
        file: UploadFile | None = File(None),
    ) -> ChatResponse:
        """Chat endpoint that accepts an optional file upload."""
        import os
        import uuid

        file_info = None
        if file:
            # Save uploaded file
            upload_dir = "data/uploads"
            os.makedirs(upload_dir, exist_ok=True)
            file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
            stored_name = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(upload_dir, stored_name)

            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            file_info = {
                "original_name": file.filename,
                "stored_name": stored_name,
                "path": file_path,
                "size": len(content),
                "content_type": file.content_type,
            }

        # Build prompt with file context
        full_prompt = prompt
        if file_info:
            full_prompt = (
                f"[File attached: {file_info['original_name']} "
                f"({file_info['content_type']}, {file_info['size']} bytes)]\n{prompt}"
            )

        # Use existing chat logic
        req = ChatRequest(
            prompt=full_prompt,
            session_id=session_id,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
        )
        return await chat(req)

    # Persona endpoints
    @app.post("/api/personas", response_model=PersonaResponse)
    async def create_persona(req: PersonaCreateRequest) -> PersonaResponse:
        import uuid

        persona_id = req.persona_id or f"persona-{uuid.uuid4().hex[:8]}"
        app_root.session_repo.create_persona(
            persona_id=persona_id,
            name=req.name,
            system_prompt=req.system_prompt,
            description=req.description,
        )
        persona = app_root.session_repo.get_persona(persona_id)
        if not persona:
            raise HTTPException(status_code=500, detail="Failed to create persona")
        return PersonaResponse(
            persona_id=persona["persona_id"],
            name=persona["name"],
            description=persona["description"],
            system_prompt=persona["system_prompt"],
            created_at=persona["created_at"],
            updated_at=persona["updated_at"],
        )

    @app.get("/api/personas", response_model=list[PersonaResponse])
    async def list_personas() -> list[PersonaResponse]:
        personas = app_root.session_repo.list_personas()
        return [PersonaResponse(**p) for p in personas]

    @app.get("/api/personas/{persona_id}", response_model=PersonaResponse)
    async def get_persona(persona_id: str) -> PersonaResponse:
        persona = app_root.session_repo.get_persona(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return PersonaResponse(**persona)

    @app.patch("/api/personas/{persona_id}", response_model=PersonaResponse)
    async def update_persona(persona_id: str, req: PersonaUpdateRequest) -> PersonaResponse:
        update_data = req.model_dump(exclude_unset=True)
        app_root.session_repo.update_persona(persona_id, **update_data)
        persona = app_root.session_repo.get_persona(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return PersonaResponse(**persona)

    @app.delete("/api/personas/{persona_id}")
    async def delete_persona(persona_id: str) -> dict[str, str]:
        app_root.session_repo.delete_persona(persona_id)
        return {"status": "deleted"}

    # Global defaults endpoints
    @app.post("/api/defaults", response_model=DefaultResponse)
    async def set_default(req: DefaultSetRequest) -> DefaultResponse:
        app_root.session_repo.set_default(req.key, req.value)
        return DefaultResponse(key=req.key, value=req.value)

    @app.patch("/api/defaults", response_model=DefaultResponse)
    async def patch_default(req: DefaultSetRequest) -> DefaultResponse:
        # Settings UI uses PATCH; same semantics as POST /api/defaults.
        app_root.session_repo.set_default(req.key, req.value)
        return DefaultResponse(key=req.key, value=req.value)

    @app.get("/api/defaults/{key}", response_model=DefaultResponse)
    async def get_default(key: str) -> DefaultResponse:
        value = app_root.session_repo.get_default(key)
        return DefaultResponse(key=key, value=value)

    @app.get("/api/defaults", response_model=list[DefaultResponse])
    async def list_defaults() -> list[DefaultResponse]:
        # Return known defaults
        default_keys = ["provider", "model", "system_prompt", "base_url"]
        return [
            DefaultResponse(key=k, value=app_root.session_repo.get_default(k)) for k in default_keys
        ]

    # Skill execution endpoints
    @app.post("/api/skills/execute", response_model=SkillExecuteResponse)
    async def execute_skill(req: SkillExecuteRequest) -> SkillExecuteResponse:
        from app.skills.builtin import register_builtin_skills
        from app.skills.registry import SkillRegistry

        # Create a fresh registry and register built-in skills
        registry = SkillRegistry()
        register_builtin_skills(registry)

        skill = registry.get(req.skill_name)
        if not skill:
            return SkillExecuteResponse(
                status="failed",
                error=f"Skill '{req.skill_name}' not found",
            )

        try:
            result = await skill(**req.params)
            return SkillExecuteResponse(
                status=result.status.value,
                data=result.data,
                error=result.error,
                metadata=result.metadata,
            )
        except Exception as e:
            return SkillExecuteResponse(
                status="failed",
                error=str(e),
            )

    @app.get("/api/skills")
    async def list_skills() -> dict[str, list[dict[str, Any]]]:
        from app.skills.builtin import register_builtin_skills
        from app.skills.registry import SkillRegistry

        registry = SkillRegistry()
        register_builtin_skills(registry)

        skills = []
        for meta in registry.list_skills():
            skills.append(
                {
                    "name": meta.name,
                    "description": meta.description,
                    "version": meta.version,
                    "category": meta.category,
                    "tags": meta.tags,
                    "timeout_seconds": meta.timeout_seconds,
                    "parameters_schema": meta.parameters_schema,
                    "returns_schema": meta.returns_schema,
                }
            )

        return {"skills": skills}

    return app


# Uvicorn entrypoint: `uvicorn app.adapters.api:app`
app = create_app()

__all__ = [
    "create_app",
    "app",
    "ChatRequest",
    "ChatResponse",
    "HealthResponse",
    "SessionCreateRequest",
    "SessionUpdateRequest",
    "SessionResponse",
    "ConversationCreateRequest",
    "ConversationResponse",
    "SettingsRequest",
    "SkillExecuteRequest",
    "SkillExecuteResponse",
]
