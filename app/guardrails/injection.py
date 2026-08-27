"""Prompt injection detection for tool arguments.

Heuristic, pattern-based detector that flags common prompt-injection and
prompt-leakage phrasings in string arguments before they reach a model or tool.
This is a defense-in-depth guard: it is not a substitute for layered policy, but
it reliably catches the most common direct-injection attempts.

Scaled deliberately: it flags known-bad phrasing without being alarmist about
normal content. Review the pattern set below before extending it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.exceptions import PromptInjectionError

# Phrases that signal an attempt to override prior instructions or leak the
# system prompt, role confusion, or known jailbreak families.
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_prior",
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)", re.IGNORECASE),
    ),
    (
        "override",
        re.compile(
            r"(disregard|override|forget)\s+(all\s+)?(previous|prior|instructions|rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt",
        re.compile(
            r"(you\s+are\s+now|your\s+system\s+prompt|reveal\s+your\s+system\s+prompt|output\s+the\s+instructions)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_change",
        re.compile(r"act\s+as|pretend\s+to\s+be|you\s+are\s+no\s+longer", re.IGNORECASE),
    ),
    (
        "jailbreak",
        re.compile(r"\b(dan|developer\s+mode|unrestricted\s+mode|jailbreak)\b", re.IGNORECASE),
    ),
    (
        "instruction_leak",
        re.compile(
            r"repeat\s+(your|the)\s+(instructions|system\s+prompt|prompt)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_confusion",
        re.compile(
            r"(forget|ignore).{0,30}(being\s+an?\s+ai|your\s+instructions)",
            re.IGNORECASE,
        ),
    ),
)

# Tags that are always safe to bypass the detector (e.g. one's own curated lists).
_SAFE_SUBSTRINGS: tuple[str, ...] = ("ignore prior instructions from the user",)


def _already_sanitized(text: str) -> bool:
    low = text.lower()
    return any(s in low for s in _SAFE_SUBSTRINGS)


@dataclass(frozen=True, slots=True)
class InjectionScanResult:
    """Outcome of a prompt-injection scan."""

    flagged: bool
    argument: str
    matched: tuple[str, ...] = field(default_factory=tuple)


class PromptInjectionDetector:
    """Detects prompt-injection phrasing in tool arguments."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def scan(self, argument: str) -> InjectionScanResult:
        """Scan a single string argument. Raises on the first blocking flag."""
        if not self.enabled or not argument or _already_sanitized(argument):
            return InjectionScanResult(flagged=False, argument=argument)
        matched: list[str] = []
        for name, pattern in _INJECTION_PATTERNS:
            if pattern.search(argument):
                matched.append(name)
        if matched:
            return InjectionScanResult(flagged=True, argument=argument, matched=tuple(matched))
        return InjectionScanResult(flagged=False, argument=argument)

    def scan_all(self, args: dict[str, object]) -> list[InjectionScanResult]:
        """Scan all string values in a call's arguments."""
        results: list[InjectionScanResult] = []
        for value in args.values():
            if isinstance(value, str):
                results.append(self.scan(value))
        return results

    def assert_safe(self, args: dict[str, object]) -> None:
        """Raise PromptInjectionError if any string argument looks injected."""
        for result in self.scan_all(args):
            if result.flagged:
                raise PromptInjectionError(
                    argument=result.argument,
                    patterns=list(result.matched),
                )
