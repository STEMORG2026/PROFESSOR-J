"""Token counting — accurate where available, word-based fallback.

Pattern-inherited from JARVIS ``app/utils/tokenizer.py``. Priority:
1. tiktoken (OpenAI-compatible), 2. transformers (HuggingFace/Llama),
3. word-based estimation (approximate, dependency-free). Results are cached.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache


@lru_cache(maxsize=128)
def get_token_counter(model_name: str = "default") -> Callable[[str], int]:
    """Return a cached token-counting function for ``model_name``."""
    counter = _try_tiktoken(model_name)
    if counter:
        return counter
    counter = _try_transformers(model_name)
    if counter:
        return counter
    return _word_counter


def _try_tiktoken(model_name: str) -> Callable[[str], int] | None:
    try:
        from tiktoken import get_encoding as _get_encoding  # type: ignore[import-not-found]
    except ImportError:
        return None
    encoding = _get_encoding("cl100k_base")

    def _count(text: str) -> int:
        return len(encoding.encode(text))

    return _count


def _try_transformers(model_name: str) -> Callable[[str], int] | None:
    try:
        from transformers import AutoTokenizer  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name or "bert-base-uncased")
    except Exception:
        return None
    return lambda text: len(tokenizer.encode(text))


def _word_counter(text: str) -> int:
    """Dependency-free token estimate: ~1.3 tokens per word."""
    words = text.split()
    return sum(_estimate_units(w) for w in words) or 0


_ESTIMATED_CHARS_PER_TOKEN = 4.0


def _estimate_units(word: str) -> int:
    # Rough per-token estimate based on word length.
    return max(1, int(math.ceil(len(word) / _ESTIMATED_CHARS_PER_TOKEN)))


def get_tokenizer_info() -> dict[str, str]:
    """Report which tokenizer backend is active."""
    if _try_tiktoken("default"):
        return {"backend": "tiktoken"}
    if _try_transformers("default"):
        return {"backend": "transformers"}
    return {"backend": "word-fallback"}


__all__ = ["get_token_counter", "get_tokenizer_info"]
