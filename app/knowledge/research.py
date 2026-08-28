"""ResearchAgent — ingest, retrieve, and synthesize with page-exact citations.

A thin orchestrator over the Phase 6 pipeline: extract a PDF, chunk/index it,
retrieve relevant chunks for a query, and build a cited answer. The retrieval
backend is the Phase 4 :class:`~app.memory.backends.MemoryBackend` seam.
Synthesis here is deterministic (concatenates top citations); an LLM-reworded
synthesis goes through the model router in a later increment.
"""

from __future__ import annotations

import logging
from typing import Any

from app.knowledge.ingest import CitationMapper, DocumentIngester
from app.knowledge.pdf import ExtractedDocument, PDFExtractor
from app.memory.backends import MemoryBackend

logger = logging.getLogger(__name__)


class ResearchAgent:
    """End-to-end research over ingested documents."""

    def __init__(
        self,
        backend: MemoryBackend,
        extractor: PDFExtractor | None = None,
    ) -> None:
        self.backend = backend
        self.extractor = extractor or PDFExtractor()
        self.ingester = DocumentIngester(backend)
        self.citations = CitationMapper(backend)

    def ingest_pdf(self, path: str, source: str | None = None) -> int:
        """Extract + index a PDF, returning the chunk count."""
        document = self.extractor.extract(path)
        return self.ingester.ingest(document, source=source)

    def ingest_document(self, document: ExtractedDocument, source: str | None = None) -> int:
        """Index an already-extracted document."""
        return self.ingester.ingest(document, source=source)

    def answer(self, query: str, k: int = 5) -> dict[str, Any]:
        """Retrieve top-k citations and assemble a cited answer block."""
        found = self.citations.retrieve(query, k=k)
        if not found:
            return {
                "success": False,
                "answer": "[UNGROUNDED] No ingested source matched the query.",
                "citations": [],
            }
        answer = "\n\n".join(
            f"[{i + 1}] {c.snippet} — ({c.title}, p.{c.page})" for i, c in enumerate(found)
        )
        return {
            "success": True,
            "answer": answer,
            "citations": [
                {"source": c.source, "page": c.page, "snippet": c.snippet} for c in found
            ],
        }


__all__ = ["ResearchAgent"]
