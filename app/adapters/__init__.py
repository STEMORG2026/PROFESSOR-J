"""API adapters — the FastAPI surface the frontend / clients talk to."""

from app.adapters.api import create_app

__all__ = ["create_app"]
