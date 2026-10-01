"""PROFESSOR-J Configuration — Pydantic Settings with Validation."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # 0.0.0.0 is the default bind for local/dev/container access, overridable
    # via PROFESSOR_API_HOST; the server binds inside the sandbox/container.
    api_host: str = "0.0.0.0"  # nosec B104 - dev/container bind, overridable via env
    api_port: int = 8000
    api_workers: int = 1
    api_key: str = Field(default="changeme", description="Bearer token for API authentication")

    # ── Data Directories ─────────────────────────────────────────────
    data_dir: Path = Path("data")
    prompts_dir: Path = Path("prompts")
    exports_dir: Path = Path("STEMMA/exports")

    # ── Database ─────────────────────────────────────────────────────
    database_url: str | None = Field(
        default=None,
        description="PostgreSQL URL (e.g. postgresql://user:pass@host:5432/db). None = SQLite.",
    )
    sqlite_path: Path = Path("data/professor.db")

    # ── STEMMA ──────────────────────────────────────────────
    lhs_export_path: Path = Path("STEMMA/exports/knowledge.json")

    # ── LLM Providers ────────────────────────────────────────────────
    # Each key accepts the bare env name (workspace practice, e.g. the keys
    # migrated from JARVIS's .env) as well as the PROFESSOR_-prefixed variant.
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "PROFESSOR_OPENAI_API_KEY"),
    )
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "PROFESSOR_ANTHROPIC_API_KEY"),
    )
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "PROFESSOR_GOOGLE_API_KEY"),
    )
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "PROFESSOR_GROQ_API_KEY"),
    )
    cerebras_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CEREBRAS_API_KEY", "PROFESSOR_CEREBRAS_API_KEY"),
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "PROFESSOR_OPENROUTER_API_KEY"),
    )
    # New provider keys
    nvidia_nim_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NVIDIA_NIM_API_KEY", "PROFESSOR_NVIDIA_NIM_API_KEY"),
    )
    google_ai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_AI_API_KEY", "PROFESSOR_GOOGLE_AI_API_KEY"),
    )
    ollama_base_url: str = "http://localhost:11434"
    llamacpp_base_url: str = "http://localhost:8080"

    # ── Singularity (OpenAI-compatible) ──────────────────────────────
    # The workspace's primary LLM endpoint. The key lives in the repo's
    # gitignored `.env` as SINGULARITY_API_KEY (workspace practice); a
    # PROFESSOR_-prefixed override is also accepted.
    singularity_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SINGULARITY_API_KEY", "PROFESSOR_SINGULARITY_API_KEY"),
    )
    singularity_base_url: str = Field(
        default="https://api.singularityapi.dev/v1",
        validation_alias=AliasChoices("SINGULARITY_BASE_URL", "PROFESSOR_SINGULARITY_BASE_URL"),
    )
    # ── Bluesmind (OpenAI-compatible) ────────────────────────────────
    # These were missing while `_make_provider_for` already read them and `.env`
    # already declared BLUESMIND_API_KEY, so selecting the provider raised
    # AttributeError (audit S2-17). Declared here to complete the contract.
    bluesmind_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BLUESMIND_API_KEY", "PROFESSOR_BLUESMIND_API_KEY"),
    )
    bluesmind_base_url: str = Field(
        default="https://api.bluesmind.ai/v1",
        validation_alias=AliasChoices("BLUESMIND_BASE_URL", "PROFESSOR_BLUESMIND_BASE_URL"),
    )

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


# ── Provider env names → Settings field names ─────────────────────────
# These are read from the repo-root .env *first* (source of truth), so the
# ambient shell environment cannot shadow them with a different key.
_PROVIDER_ENV_KEYS: dict[str, str] = {
    "OPENAI_API_KEY": "openai_api_key",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "GOOGLE_API_KEY": "google_api_key",
    "GROQ_API_KEY": "groq_api_key",
    "CEREBRAS_API_KEY": "cerebras_api_key",
    "OPENROUTER_API_KEY": "openrouter_api_key",
    "NVIDIA_NIM_API_KEY": "nvidia_nim_api_key",
    "GOOGLE_AI_API_KEY": "google_ai_api_key",
    "SINGULARITY_API_KEY": "singularity_api_key",
    "SINGULARITY_BASE_URL": "singularity_base_url",
}


def _repo_env() -> dict[str, str]:
    """Load the repo-root ``.env`` file.

    Workspace practice keeps secrets in the repo's gitignored ``.env``; the
    shell may export a *different* key (e.g. the global SINGULARITY_API_KEY in
    ~/.bashrc intended for other tools), which must not shadow the repo's own.
    """
    from dotenv import dotenv_values

    dotenv_path = Path(__file__).resolve().parents[2] / ".env"
    raw: dict[str, str | None] = dotenv_values(str(dotenv_path))
    return {k: v for k, v in raw.items() if v is not None}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance.

    The repo ``.env`` wins over the process environment for provider
    credentials: load the normal settings (defaults + ``PROFESSOR_``-prefixed
    env surface + ``.env`` aliases), then force the repo ``.env`` values on
    top, so an unrelated shell export (e.g. ~/.bashrc) cannot shadow the
    repo's own keys.
    """
    settings = Settings()
    repo = _repo_env()
    overrides: dict[str, str] = {
        field: repo[env_name]
        for env_name, field in _PROVIDER_ENV_KEYS.items()
        if repo.get(env_name) is not None
    }
    return settings.model_copy(update=overrides)


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

    # In production, the named provider keys are mandatory.
    for name, value in required:
        if not value:
            missing.append(name)

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
        missing.append(
            "At least one LLM provider API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)"
        )

    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")
