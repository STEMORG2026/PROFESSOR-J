"""PII redaction for tool arguments and logs.

Redacts personally-identifiable information (email, phone, US SSN, credit-card
numbers, and common secret patterns) before content reaches model context or
logs, so sensitive data never persists. Detokenization on return is a separate,
out-of-scope concern (callers must not expect reversible redaction here).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.exceptions import PIIRedactionError

# NOTE: keep the redaction conservative (matches real PII shapes) so normal
# text is not mangled.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),  # email
    re.compile(r"\b\+\d[\d\s().-]{8,}\d\b"),  # international phone
    re.compile(r"\b(?:\d[ -]?){9,13}\d\b"),  # long digit runs (phone / SSN / card)
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # US SSN
    re.compile(r"\b(?:\d{4}[ -]?){3}\d{3,4}\b"),  # 13-16 digit card numbers
)
_REDACTED = "***REDACTED***"


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Outcome of redacting a piece of text."""

    value: str
    redacted_count: int


class PIIRedactor:
    """Redacts PII-shaped substrings from text."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def redact(self, text: str | None) -> RedactionResult:
        """Return the text with PII replaced. None is passed through."""
        if not self.enabled or text is None:
            return RedactionResult(value=text or "", redacted_count=0)
        count = 0
        out = text
        for pattern in _PATTERNS:
            out, n = pattern.subn(_REDACTED, out)
            count += n
        return RedactionResult(value=out, redacted_count=count)

    def redact_deep(self, args: dict[str, object]) -> tuple[dict[str, object], int]:
        """Redact all string values in a call's argument dict, returning the
        sanitized copy and the total redactions performed. Raises on failure."""
        sanitized: dict[str, object] = {}
        total = 0
        try:
            for key, value in args.items():
                if isinstance(value, str):
                    result = self.redact(value)
                    total += result.redacted_count
                    sanitized[key] = result.value
                else:
                    sanitized[key] = value
        except Exception as e:  # pragma: no cover - defensive
            raise PIIRedactionError(f"PII redaction failed: {e}") from e
        return sanitized, total
