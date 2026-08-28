"""Document ingestion + page-exact citation mapping (Phase 6).

Chunk an extracted document, index the chunks into a retrieval backend (reusing
the Phase 4 :class:`~app.memory.backends.MemoryBackend` seam), and map retrieved
chunks back to a canonical (source, page, snippet) citation. The backend is a
seam: a ChromaVectorStore+dense retriever can be dropped in later without
touching this layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.knowledge.pdf import ExtractedDocument
from app.memory.backends import MemoryBackend

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TextChunker:
    """Split text into size-bounded, overlapping lexical chunks.

    ``chunk_size`` is a target character budget; chunks break on sentence/word
    boundaries where possible and overlap by ``overlap_chars`` so retrieval does
    not lose context across chunk seams.
    """

    chunk_size: int = 1200
    overlap_chars: int = 150

    def chunk(self, text: str) -> list[str]:
        if not text.strip():
            return []
        text = " ".join(text.split())  # normalize whitespace
        if len(text) <= self.chunk_size:
            return [text]
        chunks: list[str] = []
        step = max(1, self.chunk_size - self.overlap_chars)
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            cut = text[start:end]
            # Try to break at a natural sentence end near the boundary.
            boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            if boundary >= self.chunk_size // 2:
                end = start + boundary + 1
            chunks.append(text[start:end].strip())
            start += step if end < len(text) else len(text)
            if end >= len(text):
                break
        return [c for c in chunks if c]


@dataclass(frozen=True, slots=True)
class Citation:
    """A page-exact reference to a retrieved chunk."""

    source: str
    page: int
    title: str
    snippet: str


def _doc_id(source: str, page: int, idx: int) -> str:
    import hashlib

    raw = f"{source}#p{page}#c{idx}"
    # blake2b (not sha1) for a deterministic, non-crypto chunk id — B324-safe.
    return hashlib.blake2b(raw.encode(), digest_size=8).hexdigest()


class DocumentIngester:
    """Extract -> chunk -> index a document into a retrieval backend."""

    def __init__(self, backend: MemoryBackend, chunker: TextChunker | None = None) -> None:
        self.backend = backend
        self.chunker = chunker or TextChunker()

    def ingest(self, document: ExtractedDocument, source: str | None = None) -> int:
        """Chunk and index every page; returns the number of chunks stored."""
        src = source or document.source
        count = 0
        for page in document.pages:
            chunks = self.chunker.chunk(page.text)
            for idx, chunk in enumerate(chunks):
                self.backend.add(
                    _doc_id(src, page.page_number, idx),
                    chunk,
                    {
                        "source": src,
                        "page": page.page_number,
                        "title": document.title,
                    },
                )
                count += 1
        logger.info("indexed %d chunks from %s", count, src)
        return count


class CitationMapper:
    """Retrieve chunks for a query and return page-exact citations."""

    def __init__(self, backend: MemoryBackend) -> None:
        self.backend = backend

    def retrieve(
        self,
        query: str,
        k: int = 5,
        *,
        source: str | None = None,
    ) -> list[Citation]:
        """Return the top-k citations for ``query`` across the index."""
        items = self.backend.search(query, k=k)
        citations: list[Citation] = []
        for item in items:
            meta: dict[str, Any] = item.metadata
            if source and meta.get("source") != source:
                continue
            citations.append(
                Citation(
                    source=str(meta.get("source", "?")),
                    page=int(meta.get("page", 0)),
                    title=str(meta.get("title", "")),
                    snippet=item.text[:220],
                )
            )
        return citations


__all__ = [
    "TextChunker",
    "Citation",
    "DocumentIngester",
    "CitationMapper",
]
