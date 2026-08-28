"""Tests for the FastAPI adapter (Phase 7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.adapters.api import create_app


def test_health_ready() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["status"] == "ok"
    assert body["subsystems"]["db"] is True


def test_chat_returns_brain_response() -> None:
    client = TestClient(create_app())
    resp = client.post("/api/chat", json={"prompt": "hello", "session_id": "s1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "s1"
    assert body["provider"]  # mock provider present
    assert body["response"]
    assert "plan_steps" in body


def test_chat_classifies_tutorial_intent() -> None:
    client = TestClient(create_app())
    resp = client.post("/api/chat", json={"prompt": "teach me socratic physics"})
    assert resp.json()["intent"] == "tutorial"
