"""Immutable audit ledger (Phase 2 — P9).

Append-only JSONL ledger recording consequential (T2+) authority actions: capability
registrations (and denials), MCP tool calls, and destructive operations. Each entry is
hash-chained (SHA-256 of the previous entry's hash), so tampering with any prior record
breaks the chain and is detectable by :func:`verify_chain`. This is tamper-EVIDENT, not
tamper-proof: it detects alteration, which is the recorded promise.

Location: data/ledger/authority.jsonl (beneath the repo, gitignored runtime data).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_LEDGER = Path("data/ledger/authority.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class AuthorityLedger:
    """Append-only, hash-chained audit ledger for consequential authority actions."""

    def __init__(self, path: Path | str = _DEFAULT_LEDGER) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        """Tail hash of the ledger if it has entries, else the genesis string."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return hashlib.sha256(b"genesis").hexdigest()
        last_line = b""
        # Efficient tail read: scan from the end for the last newline.
        with self.path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            read = min(size, 8192)
            fh.seek(size - read)
            tail = fh.read()
        # take content after the last newline
        idx = tail.rfind(b"\n")
        if idx != -1:
            last_line = tail[idx + 1 :]
        try:
            parsed = json.loads(last_line.decode().strip())
            h = parsed.get("hash") if isinstance(parsed, dict) else None
            if isinstance(h, str):
                return h
            return self._scan_last_hash()
        except Exception:  # noqa: BLE001 - corrupt/missing tail; recompute from scan
            return self._scan_last_hash()

    def _scan_last_hash(self) -> str:
        last_hash = hashlib.sha256(b"genesis").hexdigest()
        if not self.path.exists():
            return last_hash
        for line in self.path.read_text().splitlines():
            try:
                parsed = json.loads(line)
                h = parsed.get("hash") if isinstance(parsed, dict) else None
                if isinstance(h, str):
                    last_hash = h
            except Exception:  # noqa: BLE001
                continue
        return last_hash

    def append(
        self,
        action: str,
        principal: str,
        resource: str,
        *,
        detail: dict[str, Any] | None = None,
        approved: bool | None = None,
    ) -> str:
        """Append one chained entry. Returns its hash."""
        prev = self._last_hash()
        entry: dict[str, Any] = {
            "ts": _utcnow_iso(),
            "principal": principal,
            "action": action,
            "resource": resource,
            "approved": approved,
            "detail": detail or {},
            "prev_hash": prev,
            "hash": "",
        }
        # chain the entry over its content (excluding its own hash)
        body = json.dumps(
            {k: v for k, v in entry.items() if k != "hash"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        entry_hash = hashlib.sha256(body).hexdigest()
        entry["hash"] = entry_hash
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
        logger.info("ledger: %s %s %s (%s)", action, principal, resource, entry_hash[:8])
        return entry_hash

    def verify_chain(self) -> bool:
        """Re-run the hash chain; returns True if no entry was tampered."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return True
        prev = hashlib.sha256(b"genesis").hexdigest()
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except Exception:  # noqa: BLE001
                return False
            body = json.dumps(
                {k: v for k, v in entry.items() if k != "hash"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            if hashlib.sha256(body).hexdigest() != entry.get("hash"):
                return False
            if entry.get("prev_hash") != prev:
                return False
            prev = entry["hash"]
        return True

    def read_entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]


__all__ = ["AuthorityLedger"]
