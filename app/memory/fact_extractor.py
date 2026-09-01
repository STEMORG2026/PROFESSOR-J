"""Rule-based fact extraction from conversation text.

Pattern-inherited from JARVIS ``app/memory/fact_extractor.py``. Uses
:data:`~app.memory.rules.RULES` to turn user statements like "I prefer physics"
into structured fact dicts that :class:`~app.memory.manager.MemoryManager.store`
understands. The interface is stable so an LLM-based extractor can replace the
rule-based one later without changing callers.
"""

from __future__ import annotations

from typing import Any

from app.memory.rules import RULES
from app.memory.schema import SOURCE_USER

# Coordinates / boundaries where extraction of a value should stop.
VALUE_BOUNDARIES = [
    ", but",
    ", and",
    ", or",
    ", yet",
    ", so",
    " and ",
    " but ",
    " or ",
    " yet ",
    " so ",
    " because ",
    " although ",
    " though ",
    " while ",
    " whereas ",
    " if ",
    " when ",
    " since ",
    " unless ",
    " until ",
    ". ",
    "! ",
    "? ",
]

_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ave", "etc"}


def _split_into_sentences(message: str) -> list[str]:
    sentences: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(message):
        current.append(message[i])
        if message[i] in ".!?":
            word_start = len(current) - 2
            while word_start >= 0 and current[word_start].isalpha():
                word_start -= 1
            word = "".join(current[word_start + 1 : -1]).lower().rstrip(".")
            if word not in _ABBREVIATIONS:
                sentence = "".join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []
        i += 1
    if current:
        leftover = "".join(current).strip()
        if leftover:
            sentences.append(leftover)
    return sentences


def _extract_value(text: str, trigger: str) -> str:
    idx = text.find(trigger)
    if idx == -1:
        return ""
    start = idx + len(trigger)
    value = text[start:].strip()
    if not value:
        return ""

    earliest = len(value)
    for boundary in VALUE_BOUNDARIES:
        pos = value.find(boundary)
        if pos != -1 and pos < earliest:
            earliest = pos
    if earliest < len(value):
        value = value[:earliest]

    value = value.strip().rstrip(".!?")
    value = value.removeprefix("that ")
    value = value.removeprefix("to ")
    return value


def extract_facts(message: str, source: str = SOURCE_USER) -> list[dict[str, Any]]:
    """Extract structured facts from a single user message.

    Returns fact dicts compatible with :meth:`MemoryManager.store`.
    """
    sentences = _split_into_sentences(message)
    facts: list[dict[str, Any]] = []

    for sentence in sentences:
        lowered = sentence.lower()
        for rule in RULES:
            for trigger in rule["triggers"]:
                if trigger in lowered:
                    value = _extract_value(lowered, trigger)
                    if value and len(value) >= 2:
                        facts.append(
                            {
                                "category": rule["category"],
                                "type": rule["type"],
                                "value": value,
                                "behavior": rule["behavior"],
                                "source": source,
                                "confidence": 1.0,
                            }
                        )
                        break  # one match per rule per sentence
            # allow multiple distinct facts from one sentence

    return facts


__all__ = ["extract_facts"]
