"""OpenTelemetry Exporter — Langfuse self-hosted via OTLP HTTP."""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace import set_tracer_provider

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Global tracer provider instance
_tracer_provider: TracerProvider | None = None


def init_tracer_provider(
    service_name: str = "professor-j",
    service_version: str = "0.1.0",
    otel_endpoint: str | None = None,
    console_export: bool = False,
) -> TracerProvider:
    """Initialize OpenTelemetry tracer provider with OTLP exporter to Langfuse."""
    global _tracer_provider

    settings = get_settings()
    endpoint = otel_endpoint or settings.otel_endpoint

    # Create resource with service metadata
    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
            "deployment.environment": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)

    # OTLP HTTP exporter to Langfuse
    otlp_exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={
            "Authorization": f"Basic {_langfuse_auth_header()}",
        }
        if _langfuse_auth_header()
        else {},
        timeout=10,
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Optional console exporter for development
    if console_export or settings.debug:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    set_tracer_provider(provider)
    _tracer_provider = provider

    logger.info(
        "OpenTelemetry tracer provider initialized",
        extra={
            "service_name": service_name,
            "endpoint": endpoint,
            "console_export": console_export,
        },
    )
    return provider


def _langfuse_auth_header() -> str | None:
    """Generate Langfuse Basic auth header from public/secret keys."""
    import base64

    settings = get_settings()
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}"
        return base64.b64encode(credentials.encode()).decode()
    return None


def get_tracer(name: str | None = None) -> Any:
    """Get a tracer instance."""
    from opentelemetry import trace

    return trace.get_tracer(name or "professor-j")


def shutdown_tracer_provider() -> None:
    """Shutdown tracer provider gracefully."""
    global _tracer_provider
    if _tracer_provider:
        _tracer_provider.shutdown()  # type: ignore[no-untyped-call]
        _tracer_provider = None
        logger.info("OpenTelemetry tracer provider shutdown")


# ── Semantic Convention Helpers ─────────────────────────────────────


def set_span_attributes(span: Any, attributes: dict[str, Any]) -> None:
    """Set multiple attributes on a span."""
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


def set_gen_ai_attributes(
    span: Any,
    operation: str,
    model: str,
    provider: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    """Set standard GenAI semantic convention attributes."""
    attrs = {
        "gen_ai.operation.name": operation,
        "gen_ai.request.model": model,
        "gen_ai.system": provider,
    }
    if prompt_tokens is not None:
        attrs["gen_ai.usage.prompt_tokens"] = str(prompt_tokens)
    if completion_tokens is not None:
        attrs["gen_ai.usage.completion_tokens"] = str(completion_tokens)
    if total_tokens is not None:
        attrs["gen_ai.usage.total_tokens"] = str(total_tokens)
    set_span_attributes(span, attrs)


def set_tool_attributes(
    span: Any,
    tool_name: str,
    tool_args: dict[str, Any] | None = None,
    tool_result: Any | None = None,
    error: Exception | None = None,
) -> None:
    """Set tool execution attributes."""
    attrs = {"tool.name": tool_name}
    if tool_args:
        # Sanitize sensitive args
        sanitized = _sanitize_args(tool_args)
        attrs["tool.args"] = str(sanitized)
    if tool_result is not None:
        attrs["tool.result"] = str(tool_result)[:1000]
    if error:
        attrs["tool.error"] = str(error)
        span.set_status(1, str(error))  # ERROR status
    set_span_attributes(span, attrs)


def set_retrieval_attributes(
    span: Any,
    query: str,
    top_k: int,
    results_count: int,
    vector_store: str,
) -> None:
    """Set retrieval/search attributes."""
    attrs = {
        "retrieval.query": query[:500],
        "retrieval.top_k": top_k,
        "retrieval.results_count": results_count,
        "retrieval.vector_store": vector_store,
    }
    set_span_attributes(span, attrs)


def set_guardrail_attributes(
    span: Any,
    tool_name: str,
    tier: str,
    allowed: bool,
    reason: str | None = None,
) -> None:
    """Set safety guardrail attributes."""
    attrs = {
        "guardrail.tool": tool_name,
        "guardrail.tier": tier,
        "guardrail.allowed": allowed,
    }
    if reason:
        attrs["guardrail.reason"] = reason
    if not allowed:
        span.set_status(1, f"Guardrail denied: {reason or 'policy'}")
    set_span_attributes(span, attrs)


def set_evaluator_attributes(
    span: Any,
    evaluator: str,
    score: float | None = None,
    passed: bool | None = None,
) -> None:
    """Set evaluator attributes."""
    attrs = {"evaluator.name": evaluator}
    if score is not None:
        attrs["evaluator.score"] = str(score)
    if passed is not None:
        attrs["evaluator.passed"] = str(passed).lower()
    set_span_attributes(span, attrs)


def _sanitize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive data from args before logging."""
    """Remove sensitive data from args before logging."""
    sensitive_keys = {
        "api_key",
        "password",
        "secret",
        "token",
        "authorization",
        "access_token",
        "refresh_token",
        "private_key",
        "credential",
    }
    sanitized = {}
    for k, v in args.items():
        if any(s in k.lower() for s in sensitive_keys):
            sanitized[k] = "***REDACTED***"
        elif isinstance(v, str) and len(v) > 1000:
            sanitized[k] = v[:1000] + "...[truncated]"
        else:
            sanitized[k] = v
    return sanitized
