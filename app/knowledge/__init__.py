"""Knowledge subsystem — LearningHubSTEM adapter + Phase 6 research pipeline.

Exposes the canonical-knowledge adapter (LHS), plus the research/PDF ingestion
and citation pipeline (extract -> chunk -> index -> cited retrieval).
"""

from app.knowledge.ingest import (
    Citation,
    CitationMapper,
    DocumentIngester,
    TextChunker,
)
from app.knowledge.lhs_adapter import (
    GeneralKnowledgeAdapter,
    LHSKnowledgeAdapter,
    create_knowledge_adapters,
)
from app.knowledge.pdf import ExtractedDocument, PageText, PDFExtractor
from app.knowledge.research import ResearchAgent

__all__ = [
    "LHSKnowledgeAdapter",
    "GeneralKnowledgeAdapter",
    "create_knowledge_adapters",
    "PDFExtractor",
    "ExtractedDocument",
    "PageText",
    "TextChunker",
    "DocumentIngester",
    "CitationMapper",
    "Citation",
    "ResearchAgent",
]
