"""Safety & guardrails — tiered tool gating, prompt-injection, and PII redaction.

Entry points:

- ``safety_gate`` decorator + ``SafetyPolicy``: while every tool a cognitive
  agent may run must be wrapped with ``@safety_gate``.
- ``PromptInjectionDetector``: flags injection phrasings in string arguments.
- ``PIIRedactor``: strips PII-shaped substrings before content reaches context
  or logs.
"""

from app.guardrails.injection import (  # noqa: F401
    PromptInjectionDetector,
)
from app.guardrails.pii import PIIRedactor  # noqa: F401
from app.guardrails.policy import (  # noqa: F401
    SafetyPolicy,
    reset_default_policy,
    safety_gate,
    set_default_policy,
)

__all__ = [
    "PromptInjectionDetector",
    "PIIRedactor",
    "SafetyPolicy",
    "safety_gate",
    "set_default_policy",
    "reset_default_policy",
]
