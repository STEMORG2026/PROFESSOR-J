"""Error Taxonomy — Typed exceptions, retry policies, circuit breaker hooks."""

from __future__ import annotations

from typing import Any


class ProfessorError(Exception):
    """Base exception for all PROFESSOR-J errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool = False,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code or self.__class__.__name__
        self.retryable = retryable
        self.context = context or {}


# ── Configuration & Startup ────────────────────────────────────────


class ConfigurationError(ProfessorError):
    """Raised when configuration is invalid or missing."""

    pass


class SecretValidationError(ConfigurationError):
    """Raised when required secrets are missing or invalid."""

    pass


# ── LLM Provider Errors ────────────────────────────────────────────


class ProviderError(ProfessorError):
    """Base class for LLM provider errors."""

    pass


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is temporarily unavailable (503, connection error)."""

    def __init__(self, provider: str, message: str = "", **kwargs: Any) -> None:
        super().__init__(
            f"Provider '{provider}' unavailable: {message}",
            code="PROVIDER_UNAVAILABLE",
            retryable=True,
            context={"provider": provider, **kwargs},
        )


class ProviderRateLimitError(ProviderError):
    """Raised when provider returns 429 (rate limit)."""

    def __init__(
        self, provider: str, retry_after: int | None = None, **kwargs: Any
    ) -> None:
        super().__init__(
            f"Provider '{provider}' rate limited",
            code="PROVIDER_RATE_LIMIT",
            retryable=True,
            context={"provider": provider, "retry_after": retry_after, **kwargs},
        )


class ProviderAuthError(ProviderError):
    """Raised when provider authentication fails (401, 403)."""

    def __init__(self, provider: str, **kwargs: Any) -> None:
        super().__init__(
            f"Provider '{provider}' authentication failed",
            code="PROVIDER_AUTH_FAILED",
            retryable=False,
            context={"provider": provider, **kwargs},
        )


class ProviderTimeoutError(ProviderError):
    """Raised when provider request times out."""

    def __init__(self, provider: str, timeout: float, **kwargs: Any) -> None:
        super().__init__(
            f"Provider '{provider}' timed out after {timeout}s",
            code="PROVIDER_TIMEOUT",
            retryable=True,
            context={"provider": provider, "timeout": timeout, **kwargs},
        )


class NoHealthyProvidersError(ProviderError):
    """Raised when all providers in the pool are unhealthy."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            "No healthy LLM providers available in failover pool",
            code="NO_HEALTHY_PROVIDERS",
            retryable=False,
            context=kwargs,
        )


# ── Circuit Breaker ────────────────────────────────────────────────


class CircuitBreakerError(ProfessorError):
    """Base class for circuit breaker errors."""

    pass


class CircuitOpenError(CircuitBreakerError):
    """Raised when circuit breaker is OPEN and rejecting requests."""

    def __init__(self, provider: str, opened_at: float, **kwargs: Any) -> None:
        super().__init__(
            f"Circuit breaker OPEN for provider '{provider}'",
            code="CIRCUIT_OPEN",
            retryable=True,
            context={"provider": provider, "opened_at": opened_at, **kwargs},
        )


class CircuitHalfOpenError(CircuitBreakerError):
    """Raised when circuit breaker is HALF_OPEN (testing recovery)."""

    pass


# ── Model Router ───────────────────────────────────────────────────


class RoutingError(ProfessorError):
    """Raised when model routing fails."""

    pass


class TaskClassificationError(RoutingError):
    """Raised when intent/task classification fails."""

    pass


# ── Knowledge & Grounding ──────────────────────────────────────────


class KnowledgeError(ProfessorError):
    """Base class for knowledge/grounding errors."""

    pass


class LHSAdapterError(KnowledgeError):
    """Raised when LearningHubSTEM adapter fails."""

    pass


class LHSSchemaDriftError(LHSAdapterError):
    """Raised when LHS export schema version mismatches."""

    def __init__(self, expected: str, found: str, **kwargs: Any) -> None:
        super().__init__(
            f"LHS schema drift: expected version {expected}, found {found}",
            code="LHS_SCHEMA_DRIFT",
            retryable=False,
            context={"expected_version": expected, "found_version": found, **kwargs},
        )


class EntityNotFoundError(LHSAdapterError):
    """Raised when a canonical entity is not found."""

    def __init__(self, entity_id: str, **kwargs: Any) -> None:
        super().__init__(
            f"Canonical entity not found: {entity_id}",
            code="ENTITY_NOT_FOUND",
            retryable=False,
            context={"entity_id": entity_id, **kwargs},
        )


class PrerequisiteMappingError(LHSAdapterError):
    """Raised when prerequisite graph traversal fails."""

    pass


class UngroundedContentError(KnowledgeError):
    """Raised when content cannot be grounded and must be labeled ungrounded."""

    pass


# ── Memory & Storage ───────────────────────────────────────────────


class MemoryError(ProfessorError):
    """Base class for memory/storage errors."""

    pass


class VectorStoreError(MemoryError):
    """Raised when vector store operations fail."""

    pass


class MemoryBackendError(MemoryError):
    """Raised when memory backend operations fail."""

    pass


class MigrationError(MemoryError):
    """Raised when database migration fails."""

    pass


# ── Safety & Guardrails ────────────────────────────────────────────


class GuardrailError(ProfessorError):
    """Base class for guardrail/safety errors."""

    pass


class SafetyGateError(GuardrailError):
    """Raised when @safety_gate denies a tool call."""

    def __init__(self, tool: str, tier: str, reason: str, **kwargs: Any) -> None:
        super().__init__(
            f"Safety gate ({tier}) denied tool '{tool}': {reason}",
            code="SAFETY_GATE_DENIED",
            retryable=False,
            context={"tool": tool, "tier": tier, "reason": reason, **kwargs},
        )


class HITLRequiredError(GuardrailError):
    """Raised when DESTRUCTIVE operation requires human approval."""

    def __init__(self, tool: str, description: str, **kwargs: Any) -> None:
        super().__init__(
            f"HITL approval required for destructive tool '{tool}': {description}",
            code="HITL_REQUIRED",
            retryable=False,
            context={"tool": tool, "description": description, **kwargs},
        )


class PromptInjectionError(GuardrailError):
    """Raised when prompt injection is detected."""

    def __init__(self, argument: str, patterns: list[str], **kwargs: Any) -> None:
        super().__init__(
            f"Prompt injection detected in argument '{argument}': {patterns}",
            code="PROMPT_INJECTION",
            retryable=False,
            context={"argument": argument, "patterns": patterns, **kwargs},
        )


class PIIRedactionError(GuardrailError):
    """Raised when PII redaction fails."""

    pass


# ── Sandbox & Tool Execution ──────────────────────────────────────


class SandboxError(ProfessorError):
    """Base class for sandbox/tool execution errors."""

    pass


class SandboxTimeoutError(SandboxError):
    """Raised when sandbox execution times out."""

    def __init__(self, timeout: int, **kwargs: Any) -> None:
        super().__init__(
            f"Sandbox execution timed out after {timeout}s",
            code="SANDBOX_TIMEOUT",
            retryable=True,
            context={"timeout": timeout, **kwargs},
        )


class SandboxMemoryError(SandboxError):
    """Raised when sandbox exceeds memory limit."""

    def __init__(self, limit_mb: int, **kwargs: Any) -> None:
        super().__init__(
            f"Sandbox exceeded memory limit of {limit_mb}MB",
            code="SANDBOX_MEMORY_LIMIT",
            retryable=False,
            context={"limit_mb": limit_mb, **kwargs},
        )


class SandboxSecurityError(SandboxError):
    """Raised when sandbox detects security violation."""

    def __init__(self, violation: str, **kwargs: Any) -> None:
        super().__init__(
            f"Sandbox security violation: {violation}",
            code="SANDBOX_SECURITY_VIOLATION",
            retryable=False,
            context={"violation": violation, **kwargs},
        )


class ToolExecutionError(SandboxError):
    """Raised when tool execution fails."""

    pass


class ToolNotFoundError(SandboxError):
    """Raised when requested tool is not registered."""

    def __init__(self, tool: str, **kwargs: Any) -> None:
        super().__init__(
            f"Tool not found: {tool}",
            code="TOOL_NOT_FOUND",
            retryable=False,
            context={"tool": tool, **kwargs},
        )


# ── MCP ────────────────────────────────────────────────────────────


class MCPError(ProfessorError):
    """Base class for MCP errors."""

    pass


class MCPConnectionError(MCPError):
    """Raised when MCP server connection fails."""

    def __init__(self, server: str, transport: str, **kwargs: Any) -> None:
        super().__init__(
            f"MCP connection failed to '{server}' via {transport}",
            code="MCP_CONNECTION_FAILED",
            retryable=True,
            context={"server": server, "transport": transport, **kwargs},
        )


class MCPToolError(MCPError):
    """Raised when MCP tool invocation fails."""

    pass


class MCPToolNotFoundError(MCPError):
    """Raised when MCP tool is not found."""

    pass


# ── Session & Workspace ────────────────────────────────────────────


class SessionError(ProfessorError):
    """Base class for session errors."""

    pass


class SessionNotFoundError(SessionError):
    """Raised when session is not found."""

    pass


class SessionExpiredError(SessionError):
    """Raised when session has expired."""

    pass


class WorkspaceError(ProfessorError):
    """Base class for workspace errors."""

    pass


# ── Evaluation & Testing ───────────────────────────────────────────


class EvaluationError(ProfessorError):
    """Base class for evaluation errors."""

    pass


class DatasetError(EvaluationError):
    """Raised when dataset operations fail."""

    pass


class EvaluatorError(EvaluationError):
    """Raised when evaluator fails."""

    pass


# ── Retry Policy Helpers ──────────────────────────────────────────

RETRYABLE_CODES = {
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_RATE_LIMIT",
    "PROVIDER_TIMEOUT",
    "CIRCUIT_OPEN",
    "SANDBOX_TIMEOUT",
    "MCP_CONNECTION_FAILED",
}

NON_RETRYABLE_CODES = {
    "PROVIDER_AUTH_FAILED",
    "LHS_SCHEMA_DRIFT",
    "ENTITY_NOT_FOUND",
    "SAFETY_GATE_DENIED",
    "HITL_REQUIRED",
    "PROMPT_INJECTION",
    "SANDBOX_MEMORY_LIMIT",
    "SANDBOX_SECURITY_VIOLATION",
    "TOOL_NOT_FOUND",
    "SESSION_NOT_FOUND",
    "SESSION_EXPIRED",
}


def is_retryable(error: Exception) -> bool:
    """Check if an error is retryable based on its code or type."""
    if isinstance(error, ProfessorError):
        if error.code in RETRYABLE_CODES:
            return True
        if error.code in NON_RETRYABLE_CODES:
            return False
        return error.retryable
    # Default: retry on connection/timeout errors
    return isinstance(error, (ConnectionError, TimeoutError))


def get_retry_delay(
    attempt: int, base_delay: float = 1.0, max_delay: float = 60.0
) -> float:
    """Calculate exponential backoff delay with jitter."""
    import random

    delay = min(base_delay * (2**attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)
    return float(delay + jitter)
