"""Memory extraction rules — triggers that classify conversational facts.

Pattern-inherited from JARVIS ``app/memory/rules.py``. Each rule fires when the
conversation contains a trigger phrase; it tags the extracted fact with a
category, memory type, and behavior so :class:`~app.memory.manager.MemoryManager`
stores it correctly.
"""

from __future__ import annotations

from typing import Any

RULES: list[dict[str, Any]] = [
    # ── Identity ─────────────────────────────────────────────────────────
    {
        "triggers": ["i am ", "i'm "],
        "category": "identity",
        "type": "state",
        "behavior": "append",
    },
    {
        "triggers": ["my name is ", "my name's ", "call me ", "i go by "],
        "category": "identity",
        "type": "name",
        "behavior": "append",
    },
    {
        "triggers": ["i identify as ", "i see myself as ", "i consider myself "],
        "category": "identity",
        "type": "self_identification",
        "behavior": "append",
    },
    # ── Preferences ──────────────────────────────────────────────────────
    {
        "triggers": [
            "i like ",
            "i love ",
            "i enjoy ",
            "i prefer ",
            "i'm into ",
            "i am into ",
            "i'm a fan of ",
        ],
        "category": "preference",
        "type": "like",
        "behavior": "append",
    },
    {
        "triggers": ["i dislike ", "i hate ", "i do not like ", "i don't like "],
        "category": "preference",
        "type": "dislike",
        "behavior": "append",
    },
    # ── Skills / ability ─────────────────────────────────────────────────
    {
        "triggers": ["i can ", "i know how to ", "i'm able to ", "i am able to "],
        "category": "skills",
        "type": "ability",
        "behavior": "append",
    },
    {
        "triggers": [
            "i am skilled at ",
            "i'm good at ",
            "i'm great at ",
            "i excel at ",
            "i specialize in ",
        ],
        "category": "skills",
        "type": "proficiency",
        "behavior": "append",
    },
    # ── Learner context (PROFESSOR-J: education fit) ─────────────────────
    {
        "triggers": ["i study ", "i'm studying ", "i am studying ", "i take "],
        "category": "learner",
        "type": "subject",
        "behavior": "append",
    },
    {
        "triggers": ["i struggle with ", "i'm bad at ", "i am bad at ", "i find hard "],
        "category": "learner",
        "type": "struggle",
        "behavior": "append",
    },
]

__all__ = ["RULES"]
