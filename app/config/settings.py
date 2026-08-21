"""PROFESSOR-J Configuration — Pydantic Settings with Validation."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_core import PydanticCustomError


class Settings(BaseSettings):
    """Application settings loaded from environment variables with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="PROFESSOR_",
    )

    # ── Application ──────────────────────────────────────────────────
    app_name: str = "PROFESSOR-J"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # ── API ──────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    api_key: str = Field(default="changeme", description="Bearer token for API authentication")

    # ── Data Directories ─────────────────────────────────────────────
    data_dir: Path = Path("data")
    prompts_dir: Path = Path("prompts")
    exports_dir: Path = Path("LearningHubSTEM/exports")

    # ── Database ─────────────────────────────────────────────────────
    database_url: str | None = Field(
        default=None,
        description="PostgreSQL URL (e.g. postgresql://user:pass@host:5432/db). None = SQLite.",
    )
    sqlite_path: Path = Path("data/professor.db")

    # ── LearningHubSTEM ──────────────────────────────────────────────
    lhs_export_path: Path = Path("LearningHubSTEM/exports/knowledge.json")
    lhs_expected_export_version: int = 3
    lhs_expected_schema_version: int = 3

    # ── LLM Providers ────────────────────────────────────────────────
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    cerebras_api_key: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    llamacpp_base_url: str = "http://localhost:8080"

    # ── Vector Store ─────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection: str = "professor_knowledge"

    # ── Langfuse / Observability ─────────────────────────────────────
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    otel_endpoint: str = "http://localhost:4318/v1/traces"

    # ── MCP ──────────────────────────────────────────────────────────
    mcp_config_path: Path = Path("mcp_agent.config.yaml")

    # ── Sandbox ──────────────────────────────────────────────────────
    sandbox_timeout_seconds: int = 10
    sandbox_memory_mb: int = 512
    sandbox_cpu_quota: int = 50000  # 50% of one CPU core

    # ── Voice ────────────────────────────────────────────────────────
    vad_threshold: float = 0.5
    stt_model: str = "whisper-1"
    tts_model: str = "tts-1"

    @field_validator("data_dir", "prompts_dir", "exports_dir", mode="before")
    @classmethod
    def _resolve_paths(cls, v: str | Path) -> Path:
        return Path(v).resolve()

    @field_validator("api_key")
    @classmethod
    def _validate_api_key(cls, v: str, info: Any) -> str:
        if not v or v == "changeme":
            # Allow changeme in development mode
            if info.data.get("environment") == "development":
                return v
            raise ValueError("PROFESSOR_API_KEY must be set to a secure random value")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance for dependency injection."""
    return Settings()


# ── Startup Validation ───────────────────────────────────────────────

def validate_required_secrets(settings: Settings) -> None:
    """Validate that all required secrets are present at startup."""
    missing: list[str] = []

    if settings.environment == "production":
        required = [
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        ]
    else:
        required = []

    # At least one LLM provider must be configured
    provider_keys = [
        settings.openai_api_key,
        settings.anthropic_api_key,
        settings.google_api_key,
        settings.groq_api_key,
        settings.cerebras_api_key,
        settings.openrouter_api_key,
    ]
    if not any(provider_keys):
        missing.append("At least one LLM provider API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)")

    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")
