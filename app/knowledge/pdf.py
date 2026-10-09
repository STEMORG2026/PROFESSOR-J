"""PDF text extraction with page-level provenance (Phase 6).

Wraps PyMuPDF (``fitz``) to pull text from PDFs while preserving the page each
block/sentence came from, so downstream citation mapping can produce exact
page-level references.

Externally-dependent: extraction needs a real PDF file. The chunker/citation
layers are deterministic and unit-tested against plain text so the pipeline
contract stays verifiable without shipping a binary fixture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.exceptions import KnowledgeError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PageText:
    """Text extracted from a single PDF page."""

    page_number: int  # 1-based, human-facing
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """Result of extracting a PDF: ordered pages + metadata."""

    source: str
    title: str
    pages: tuple[PageText, ...]

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class PDFExtractor:
    """Extract page-structured text from a PDF via PyMuPDF."""

    def extract(self, path: str | Path) -> ExtractedDocument:
        pdf_path = Path(path)
        if not pdf_path.exists():
            raise KnowledgeError(f"PDF not found: {pdf_path}", code="PDF_NOT_FOUND")
        if pdf_path.suffix.lower() != ".pdf":
            raise KnowledgeError(f"Not a PDF: {pdf_path}", code="PDF_INVALID_EXTENSION")

        import fitz  # PyMuPDF ships its own types; the ignore was unused, and mypy rejects unused ignores

        try:
            doc: Any = fitz.open(str(pdf_path))
            pages = []
            for i, page in enumerate(doc, start=1):
                page_obj: Any = page
                text = page_obj.get_text().strip()
                if text:
                    pages.append(PageText(page_number=i, text=text))
            title: str = doc.metadata.get("title") or pdf_path.stem
            doc.close()
        except Exception as exc:  # noqa: BLE001 - surface corrupt/unreadable PDFs
            raise KnowledgeError(
                f"Failed to parse PDF {pdf_path}: {exc}", code="PDF_PARSE_ERROR"
            ) from exc

        if not pages:
            raise KnowledgeError(
                f"No extractable text in {pdf_path} (possibly scanned/image-only). "
                "OCR (PaddleOCR) is a later phase.",
                code="PDF_NO_TEXT",
            )
        logger.info("extracted %d pages from %s", len(pages), pdf_path)
        return ExtractedDocument(source=str(pdf_path), title=title, pages=tuple(pages))


__all__ = ["PDFExtractor", "ExtractedDocument", "PageText"]
