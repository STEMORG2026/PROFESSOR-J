"""Tests for the Phase 6 knowledge/research pipeline (chunk -> index -> cite)."""

from __future__ import annotations

from app.knowledge import (
    CitationMapper,
    DocumentIngester,
    ExtractedDocument,
    PageText,
    ResearchAgent,
    TextChunker,
)
from app.memory import InMemoryBackend


def _doc() -> ExtractedDocument:
    return ExtractedDocument(
        source="/tmp/paper.pdf",
        title="Forces in Motion",
        pages=(
            PageText(
                page_number=1,
                text=(
                    "Newton's second law states that the net force on a body "
                    "equals the product of its mass and acceleration. "
                    "This relationship is written as F equals m times a. "
                    "The law underpins most classical mechanics problems."
                ),
            ),
            PageText(
                page_number=2,
                text=(
                    "A heavier object does not necessarily fall faster in a "
                    "vacuum; gravitational acceleration is the same for all "
                    "masses. This is a common misconception that the professor "
                    "must explicitly address during tutoring."
                ),
            ),
        ),
    )


class TestTextChunker:
    def test_small_text_is_single_chunk(self) -> None:
        c = TextChunker(chunk_size=2000)
        assert c.chunk("short text here") == ["short text here"]

    def test_empty_text(self) -> None:
        assert TextChunker().chunk("   ") == []

    def test_long_text_splits_into_multiple_chunks(self) -> None:
        c = TextChunker(chunk_size=50, overlap_chars=10)
        chunks = c.chunk("word " * 30)
        assert len(chunks) > 1
        assert all(chunk.strip() for chunk in chunks)


class TestIngestAndCitations:
    def test_ingest_indexes_chunks_with_page_metadata(self) -> None:
        backend = InMemoryBackend()
        n = DocumentIngester(backend).ingest(_doc())
        assert n >= 2  # at least one chunk per page
        assert backend.count() == n

    def test_citation_mapper_returns_page_exact(self) -> None:
        backend = InMemoryBackend()
        DocumentIngester(backend).ingest(_doc())
        cites = CitationMapper(backend).retrieve("acceleration mass force", k=5)
        assert cites
        first = cites[0]
        assert first.source == "/tmp/paper.pdf"
        assert first.page in (1, 2)
        assert first.title == "Forces in Motion"
        assert first.snippet

    def test_source_filter(self) -> None:
        backend = InMemoryBackend()
        ing = DocumentIngester(backend)
        ing.ingest(_doc(), source="alpha.pdf")
        cites = CitationMapper(backend).retrieve("acceleration", source="other.pdf")
        assert cites == []


class TestResearchAgent:
    def test_answer_cited_synthesis(self) -> None:
        agent = ResearchAgent(InMemoryBackend())
        agent.ingest_document(_doc())
        out = agent.answer("acceleration mass force")
        assert out["success"] is True
        assert out["citations"]
        assert "p.1" in out["answer"] or "p.2" in out["answer"]

    def test_answer_ungrounded_when_no_match(self) -> None:
        agent = ResearchAgent(InMemoryBackend())
        agent.ingest_document(_doc())
        out = agent.answer("quantum chromodynamics nowhere mentioned")
        assert out["success"] is False
        assert "UNGROUNDED" in out["answer"]

    def test_pdf_ingest_requires_real_file(self) -> None:
        agent = ResearchAgent(InMemoryBackend())
        import pytest

        from app.exceptions import KnowledgeError

        with pytest.raises(KnowledgeError):
            agent.ingest_pdf("/does/not/exist.pdf")
