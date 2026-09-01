"""Tests for the /api/ingest + /api/chat/upload ingestion wiring (Phase 6)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.api import create_app


def _make_pdf(path: Path, text: str = "Forces equal mass times acceleration.\n" * 40) -> Path:
    """Write a real PDF via PyMuPDF so PDFExtractor can read it."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


class TestApiIngest:
    def test_ingest_pdf_indexes_chunks(self, tmp_path: Path) -> None:
        client = TestClient(create_app())
        pdf = _make_pdf(tmp_path / "paper.pdf")
        with open(pdf, "rb") as f:
            resp = client.post(
                "/api/ingest",
                files={"file": ("paper.pdf", f, "application/pdf")},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ingested"
        assert body["source"] == "paper.pdf"
        assert body["chunks"] >= 1
        assert body["file"]["original_name"] == "paper.pdf"

    def test_ingest_rejects_non_pdf(self, tmp_path: Path) -> None:
        client = TestClient(create_app())
        resp = client.post(
            "/api/ingest",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 415

    def test_ingest_source_override(self, tmp_path: Path) -> None:
        client = TestClient(create_app())
        pdf = _make_pdf(tmp_path / "p.pdf")
        with open(pdf, "rb") as f:
            resp = client.post(
                "/api/ingest",
                files={"file": ("p.pdf", f, "application/pdf")},
                data={"source": "my-label.pdf"},
            )
        assert resp.status_code == 200
        assert resp.json()["source"] == "my-label.pdf"

    def test_chat_upload_ingests_and_answers(self, tmp_path: Path) -> None:
        client = TestClient(create_app())
        pdf = _make_pdf(tmp_path / "laws.pdf", "Newton's second law F=ma.\n" * 30)
        with open(pdf, "rb") as f:
            resp = client.post(
                "/api/chat/upload",
                data={
                    "prompt": "What does Newton's second law say?",
                    "session_id": "s-int",
                },
                files={"file": ("laws.pdf", f, "application/pdf")},
            )
        # Tolerate either a direct answer or a grounded response intent;
        # key point: it must not 500, and it must include the model reply.
        assert resp.status_code == 200, resp.text
        assert resp.json().get("response") is not None
