#!/usr/bin/env python3
"""Verify PROFESSOR-J repository.

Usage:
  python3 scripts/verify.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    # Run pytest and mypy
    code = 0
    for cmd in [
        [".venv/bin/python", "-m", "pytest", "tests/", "-q"],
        [".venv/bin/mypy", "app/"],
        [".venv/bin/pre-commit", "run", "--all-files"],
    ]:
        print(f"→ Verifying PROFESSOR-J: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"✗ PROFESSOR-J verification FAIL (exit {result.returncode})", file=sys.stderr)
            code = result.returncode
            break
    else:
        print("✓ PROFESSOR-J verification PASS")
    return code


if __name__ == "__main__":
    sys.exit(main())
