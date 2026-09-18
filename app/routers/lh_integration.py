"""API router for LearningHub frontend integration."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

lh_router = APIRouter(prefix="/api/v1/lh", tags=["learninghub"])


@lh_router.get("/health")
async def lh_health() -> dict[str, str]:
    """Health check for LearningHub frontend integration."""
    return {"status": "ok", "service": "professor-j-lh-bridge"}


@lh_router.get("/ecosystem-info")
async def ecosystem_info() -> dict[str, Any]:
    """Return ecosystem topology for LearningHub information head."""
    return {
        "services": {
            "learninghub": {
                "role": "information-head",
                "responsibilities": ["knowledge", "governance", "content", "pedagogy"],
                "status": "active",
            },
            "professor-j": {
                "role": "worker",
                "responsibilities": ["ai-execution", "orchestration", "model-routing"],
                "status": "active",
            },
        },
        "integration": {
            "protocol": "http+json",
            "auth": "api-key",
            "endpoints": {
                "chat": "/api/v1/lh/chat",
                "stream": "/api/v1/lh/stream",
                "status": "/api/v1/status",
            },
        },
    }
