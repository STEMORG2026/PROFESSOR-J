"""PROFESSOR-J — Server Entry Point.

FastAPI application with HTTP + WebSocket endpoints.
Serves as the foundation for the orchestration plane.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.acp import create_acp_server
from app.bootstrap import build_root
from app.orchestration import (
    create_agent_router,
    create_hooks_system,
    create_plugin_registry,
    create_subagent_manager,
)
from app.routers.chat import chat_router
from app.routers.lh_integration import lh_router

logger = logging.getLogger(__name__)

_VERSION = "0.9.0"

# Orchestration singletons
_acp_server = create_acp_server()
_subagent_manager = create_subagent_manager()
_plugin_registry = create_plugin_registry()
_agent_router = create_agent_router()
_hooks_system = create_hooks_system()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle manager."""
    # Configure structured logging before anything else runs, so startup is recorded.
    from app.logging_config import setup_logging

    setup_logging()
    build_root()
    logger.info("PROFESSOR-J server starting (version=%s)", _VERSION)
    yield
    logger.info("PROFESSOR-J server shutting down")


app = FastAPI(
    title="PROFESSOR-J",
    version=_VERSION,
    lifespan=lifespan,
)

# Include routers
app.include_router(lh_router)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": _VERSION}


@app.get("/ready")
async def ready() -> dict[str, str]:
    """Readiness probe."""
    return {"status": "ready", "version": _VERSION}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time streaming."""
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        await websocket.send_json({"echo": data})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


@app.get("/api/v1/status")
async def status() -> JSONResponse:
    """Platform status."""
    return JSONResponse(
        {
            "status": "running",
            "version": _VERSION,
            "capabilities": ["chat", "orchestration"],
        }
    )


@app.post("/api/v1/acp")
async def acp_endpoint(request: dict[str, Any]) -> JSONResponse:
    """ACP JSON-RPC endpoint."""
    import json

    response = await _acp_server.handle_message(json.dumps(request))
    return JSONResponse(json.loads(response))


@app.get("/api/v1/agents")
async def list_agents() -> JSONResponse:
    """List managed subagents."""
    return JSONResponse({"agents": []})


@app.post("/api/v1/route")
async def route_task(request: dict[str, Any]) -> JSONResponse:
    """Route a task to the appropriate subagent."""
    task = request.get("task", "")
    agent = _agent_router.get_agent_for_task(task)
    return JSONResponse({"agent": agent, "task": task})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
