"""Phase 0 smoke test: package imports and version contract."""

from __future__ import annotations

import app


def test_package_imports() -> None:
    assert app.__version__ == "0.0.1"
