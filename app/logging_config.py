"""Structured Logging Configuration — JSON output, correlation IDs, OTel-ready."""

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any

# Context variable for correlation ID propagation across async boundaries
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    """Inject correlation ID into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get() or "none"
        return True


class JSONFormatter(logging.Formatter):
    """JSON log formatter with standard fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "none"),
        }

        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "correlation_id",
            }:
                log_data[key] = value

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class SecretRedactingFilter(logging.Filter):
    """Redact credential-shaped values from every log record before it is rendered.

    Added after the audit (S2-16) established that the log path had no redaction at
    all and that ``extra=`` keys were written verbatim. The existing redactor in
    ``app/telemetry/exporter.py`` matches on key *names*; this filter matches on value
    *shape* as well, because a credential can arrive in a message string, a URL, or a
    traceback rather than under a key called ``api_key``.

    Redaction is applied to the rendered message and to string values in ``extra``,
    in place, so both the JSON and the plain formatter are covered.
    """

    #: Key-name fragments that always cause their value to be redacted.
    _SENSITIVE_KEY_PARTS: tuple[str, ...] = (
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "passwd",
        "credential",
        "authorization",
        "bearer",
        "private_key",
    )

    #: Value shapes that are redacted wherever they appear.
    _VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
        # Query-string credentials, e.g. ?key=AIza... or &api_key=sk-...
        re.compile(r"([?&](?:key|api_key|apikey|token|access_token)=)[^&\s\"']+", re.I),
        # Authorization headers
        re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.I),
        # Provider-prefixed keys
        re.compile(r"\b(sk-[A-Za-z0-9._\-]{12,})"),
        re.compile(r"\b(AIza[0-9A-Za-z._\-]{20,})"),
        re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})"),
    )

    REDACTED = "***REDACTED***"

    @classmethod
    def _redact_text(cls, text: str) -> str:
        for pattern in cls._VALUE_PATTERNS:
            if pattern.groups:
                text = pattern.sub(lambda m: m.group(1) + cls.REDACTED, text)
            else:
                text = pattern.sub(cls.REDACTED, text)
        return text

    @classmethod
    def _key_is_sensitive(cls, key: str) -> bool:
        lowered = key.lower()
        return any(part in lowered for part in cls._SENSITIVE_KEY_PARTS)

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact the pre-rendered message, then re-render args so getMessage() is safe.
        try:
            record.msg = self._redact_text(record.getMessage())
            record.args = ()
        except Exception:  # pragma: no cover - never let logging break the request
            return True

        for key, value in list(record.__dict__.items()):
            if self._key_is_sensitive(key):
                record.__dict__[key] = self.REDACTED
            elif isinstance(value, str):
                record.__dict__[key] = self._redact_text(value)

        if record.exc_text:
            record.exc_text = self._redact_text(record.exc_text)
        return True


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    include_correlation: bool = True,
) -> None:
    """Configure application-wide logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Redaction first, so no formatter can render an unredacted record.
    handler.addFilter(SecretRedactingFilter())

    if include_correlation:
        handler.addFilter(CorrelationIdFilter())

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(correlation_id)s | %(name)s | %(message)s"
            )
        )

    root_logger.addHandler(handler)

    # Reduce noise from third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set correlation ID for current context; returns the ID."""
    cid = correlation_id or str(uuid.uuid4())[:8]
    correlation_id_var.set(cid)
    return cid


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    correlation_id_var.set(None)
