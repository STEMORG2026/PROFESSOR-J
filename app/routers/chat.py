"""Chat endpoint for LearningHub frontend — routes through orchestration plane."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

chat_router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "google/gemini-3.7-flash"
    max_tokens: int = 800
    system_prompt: str | None = None


class ChatResponse(BaseModel):
    message: str
    model: str
    agent: str = "professor-j"


@chat_router.post("/")
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat endpoint for LearningHub frontend.
    
    Routes messages through the orchestration plane:
    1. Agent router selects best model for the task
    2. Model provider generates response
    3. Response returned to LH frontend
    """
    last_message = request.messages[-1].content if request.messages else ""
    
    # Route through orchestration plane
    # For now, echo back with model info
    # In production: call model router → provider → stream response
    response = f"PROFESSOR-J orchestration response: {last_message}"
    
    return ChatResponse(
        message=response,
        model=request.model,
        agent="professor-j",
    )
