#!/usr/bin/env python3
"""Verify the STEMMA knowledge-export contract from PROFESSOR-J consumer side.

Computes the SHA-256 of the STEMMA export and compares against the pinned
expected digest. This is the mechanical half of the "consumers must verify"
contract: PROFESSOR-J reads STEMMA exports, and unplanned
regeneration (drift) must be caught.

Usage:
    verify_export_contract.py            # verify pinned digest (CI-safe, read-only)
    verify_export_contract.py --record   # recompute + write digest
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
STEMMA_EXPORT = REPO_ROOT.parent / "STEMMA" / "exports" / "knowledge.json"
MANIFEST = REPO_ROOT / "authority" / "exports-manifest.yaml"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true", help="Recompute and write pinned digest")
    args = ap.parse_args()

    if not STEMMA_EXPORT.is_file():
        print(f"export-contract: missing STEMMA export at {STEMMA_EXPORT}", file=sys.stderr)
        return 2

    actual = sha256_of(STEMMA_EXPORT)

    if args.record:
        # Update manifest if it exists
        if MANIFEST.is_file():
            data = yaml.safe_load(MANIFEST.read_text()) or {}
            exports = data.get("exports", {})
            if "knowledge-json" in exports:
                expected = exports["knowledge-json"].get("expected", {})
                if isinstance(expected, dict):
                    expected["sha256"] = actual
                else:
                    exports["knowledge-json"]["expected"] = {"sha256": actual}
            else:
                exports["knowledge-json"] = {
                    "path": "../STEMMA/exports/knowledge.json",
                    "expected": {"sha256": actual}
                }
            data["exports"] = exports
            yaml.safe_dump(data, MANIFEST.open("w"), sort_keys=False, default_flow_style=False)
            print(f"export-contract: recorded new digest for knowledge-json")
        else:
            # Create minimal manifest
            data = {
                "exports": {
                    "knowledge-json": {
                        "path": "../STEMMA/exports/knowledge.json",
                        "expected": {"sha256": actual}
                    }
                }
            }
            yaml.safe_dump(data, MANIFEST.open("w"), sort_keys=False, default_flow_style=False)
            print(f"export-contract: created manifest with digest for knowledge-json")

    else:
        # Verify mode - check against manifest
        if not MANIFEST.is_file():
            print(f"export-contract: manifest not found at {MANIFEST.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1

        data = yaml.safe_load(MANIFEST.read_text()) or {}
        exports = data.get("exports", {})
        meta = exports.get("knowledge-json")
        if not meta:
            print("export-contract: knowledge-json not pinned in manifest", file=sys.stderr)
            return 1

        expected = meta.get("expected", {}) if isinstance(meta.get("expected"), dict) else {}
        pinned = expected.get("sha256")
        if not pinned:
            print("export-contract: knowledge-json not yet pinned (run --record)", file=sys.stderr)
            return 1

        if pinned != actual:
            print(f"export-contract: knowledge-json DRIFT — digest mismatch (content regenerated without record)", file=sys.stderr)
            return 1

    print("export-contract OK: STEMMA knowledge.json matches pinned digest")
    return 0


if __name__ == "__main__":
    sys.exit(main())