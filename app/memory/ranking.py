"""Memory ranking — relevance x importance x frequency x recency x confidence.

Pattern-inherited from JARVIS ``app/memory/ranking.py``: separation of
retrieval (candidate discovery) from ranking (scoring) lets the two evolve
independently and weights be tuned per deployment.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from app.memory.schema import Memory, MemoryResult
from app.utils.text import STOP_WORDS, extract_keywords


@dataclass
class RankingWeights:
    """Weights for the ranking factors (sum ~1.0 for interpretable scores)."""

    relevance: float = 0.35  # keyword/vector overlap with the query
    importance: float = 0.25  # explicitly set importance
    frequency: float = 0.15  # access count (log scale)
    recency: float = 0.15  # time since last used (half-life decay)
    confidence: float = 0.10  # reliability of the fact


DEFAULT_WEIGHTS = RankingWeights()


class MemoryRanker:
    """Ranks candidate memories by their relevance to a query."""

    def __init__(
        self,
        weights: RankingWeights | None = None,
        recency_half_life_days: float = 7.0,
        frequency_scale: int = 10,
    ) -> None:
        self.weights: RankingWeights = weights or DEFAULT_WEIGHTS
        # Seconds for recency to decay by 50%.
        self._recency_half_life: float = recency_half_life_days * 24 * 60 * 60
        # Access count at which frequency_score saturates at 1.0.
        self._frequency_scale: int = frequency_scale

    def rank(
        self,
        candidates: list[Memory],
        query: str,
        limit: int = 20,
        min_score: float = 0.0,
    ) -> list[MemoryResult]:
        """Rank candidates and return the top ``limit`` above ``min_score``."""
        if not candidates:
            return []
        query_keywords = self._extract_keywords(query)
        current_time = time.time()

        scored: list[MemoryResult] = []
        for memory in candidates:
            scores = self._calculate_all_scores(memory, query_keywords, current_time)
            total = self._combine_scores(scores)
            if total >= min_score:
                scored.append(MemoryResult(memory=memory, score=total))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    def _calculate_all_scores(
        self, memory: Memory, query_keywords: set[str], current_time: float
    ) -> dict[str, float]:
        return {
            "relevance": self._score_relevance(memory, query_keywords),
            "importance": self._score_importance(memory),
            "frequency": self._score_frequency(memory),
            "recency": self._score_recency(memory, current_time),
            "confidence": self._score_confidence(memory),
        }

    def _combine_scores(self, scores: dict[str, float]) -> float:
        return (
            self.weights.relevance * scores["relevance"]
            + self.weights.importance * scores["importance"]
            + self.weights.frequency * scores["frequency"]
            + self.weights.recency * scores["recency"]
            + self.weights.confidence * scores["confidence"]
        )

    def _score_relevance(self, memory: Memory, query_keywords: set[str]) -> float:
        """Jaccard keyword overlap between query and memory, with category/type boosts."""
        if not query_keywords:
            return 0.0
        memory_keywords = self._extract_keywords(
            f"{memory.value} {memory.category} {memory.memory_type}"
        )
        if not memory_keywords:
            return 0.0
        overlap = query_keywords & memory_keywords
        union = query_keywords | memory_keywords
        jaccard = len(overlap) / len(union) if union else 0.0
        category_boost = 0.2 if memory.category in query_keywords else 0.0
        type_boost = 0.15 if memory.memory_type in query_keywords else 0.0
        return min(1.0, jaccard + category_boost + type_boost)

    @staticmethod
    def _score_importance(memory: Memory) -> float:
        return memory.importance

    def _score_frequency(self, memory: Memory) -> float:
        if memory.access_count <= 0:
            return 0.0
        return min(1.0, math.log(1 + memory.access_count) / math.log(1 + self._frequency_scale))

    def _score_recency(self, memory: Memory, current_time: float) -> float:
        age_seconds = current_time - memory.last_used
        if age_seconds <= 0:
            return 1.0
        ratio: float = age_seconds / self._recency_half_life
        return float(0.5**ratio)

    @staticmethod
    def _score_confidence(memory: Memory) -> float:
        return memory.confidence

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        return extract_keywords(text, STOP_WORDS)


__all__ = ["MemoryRanker", "RankingWeights", "DEFAULT_WEIGHTS"]
