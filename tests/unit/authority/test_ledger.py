"""Tests for the immutable audit ledger (Phase 2 — P9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.authority.ledger import AuthorityLedger


class TestAuthorityLedger:
    def test_append_and_read(self, tmp_path: Path) -> None:
        ledger = AuthorityLedger(tmp_path / "auth.jsonl")
        h = ledger.append("register", "professor:tool-executor", "run_code", approved=True)
        entries = ledger.read_entries()
        assert len(entries) == 1
        assert entries[0]["action"] == "register"
        assert entries[0]["approved"] is True
        assert entries[0]["hash"] == h

    def test_hash_chain_verifies_when_intact(self, tmp_path: Path) -> None:
        ledger = AuthorityLedger(tmp_path / "auth.jsonl")
        ledger.append("a", "p", "r")
        ledger.append("b", "p", "r2")
        ledger.append("c", "p", "r3")
        assert ledger.verify_chain() is True

    def test_empty_ledger_verifies(self, tmp_path: Path) -> None:
        ledger = AuthorityLedger(tmp_path / "auth.jsonl")  # no writes
        assert ledger.verify_chain() is True

    def test_tampered_hash_breaks_chain(self, tmp_path: Path) -> None:
        ledger = AuthorityLedger(tmp_path / "auth.jsonl")
        ledger.append("a", "p", "r", approved=True)
        ledger.append("b", "p", "r2", approved=True)
        assert ledger.verify_chain() is True
        # Tamper with a prior entry (change an approved flag from true to false).
        path = tmp_path / "auth.jsonl"
        text = path.read_text()
        # JSONL is written with compact separators (",", ":") => no space after the colon.
        corrupted = text.replace('"approved":true', '"approved":false', 1)
        assert corrupted != text, "tamper target not found (ledger text differs than expected)"
        path.write_text(corrupted)
        assert ledger.verify_chain() is False

    def test_executor_records_registration_to_ledger(self, tmp_path: Path) -> None:
        from app.authority.ledger import AuthorityLedger
        from app.domain.tool import SafetyTier
        from app.tools.executor import ToolExecutor

        ledger = AuthorityLedger(tmp_path / "auth-exec.jsonl")
        executor = ToolExecutor(ledger=ledger)
        executor.register_fn("solve", lambda: 1, tier=SafetyTier.SAFE, description="x")
        entries = ledger.read_entries()
        # one register event (plus none denied) for the single registration
        assert any(e["action"] == "register" and e["resource"] == "solve" for e in entries)

    def test_executor_records_denied_registration(self, tmp_path: Path) -> None:
        from app.authority.ledger import AuthorityLedger
        from app.authority.policy import default_register_policy
        from app.domain.tool import SafetyTier
        from app.exceptions import CapabilityRegistrationError
        from app.tools.executor import ToolExecutor

        ledger = AuthorityLedger(tmp_path / "auth-exec2.jsonl")
        executor = ToolExecutor(
            register_policy=default_register_policy,
            blessed_registrar=False,
            ledger=ledger,
        )
        with pytest.raises(CapabilityRegistrationError):
            executor.register_fn(
                "run_code", lambda: None, tier=SafetyTier.DESTRUCTIVE, description="x"
            )
        entries = ledger.read_entries()
        assert any(
            e["action"] == "register-denied" and e["resource"] == "run_code" for e in entries
        )
