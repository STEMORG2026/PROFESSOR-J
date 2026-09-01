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


def test_chat_stream_emits_meta_token_done() -> None:
    """The SSE endpoint streams meta, incremental token, and done events."""
    client = TestClient(create_app())
    with client.stream("POST", "/api/chat/stream", json={"prompt": "hello streaming"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events: dict[str, list[str]] = {}
        payloads: dict[str, list[str]] = {}
        for raw in resp.iter_lines():
            if not raw:
                continue
            if raw.startswith("event:"):
                name = raw[len("event:") :].strip()
                events.setdefault(name, [])
                payloads.setdefault(name, [])
                events[name].append(name)
            elif raw.startswith("data:"):
                # attach to the most recent event name
                for name in reversed(events):
                    payloads[name].append(raw[len("data:") :].strip())
                    break
    assert "meta" in events
    assert "token" in events
    assert "done" in events
    joined = "".join(payloads.get("token", []))
    assert joined  # non-empty streamed text
    # token deltas reassemble into something close to the mock text
    assert "mock" in joined


def test_chat_stream_meta_reports_provider() -> None:
    client = TestClient(create_app())
    with client.stream("POST", "/api/chat/stream", json={"prompt": "hi"}) as resp:
        meta_raw = next(
            (ln[len("data:") :].strip() for ln in resp.iter_lines() if ln.startswith("data:")),
            "",
        )
    import json

    meta = json.loads(meta_raw)
    assert meta["provider"]
    assert meta["model"]
