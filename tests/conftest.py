"""Root test configuration.

Sets a non-placeholder API key for the whole test session. Before the audit,
``create_app()`` served every route unauthenticated; authentication is now enforced
app-wide (audit S0-1), so the suite must authenticate like any other client.

This does not disable the gate — it supplies a real credential, so a test that succeeds
proves the gate is passable. Tests covering the unauthenticated path live in
``tests/unit/adapters/test_auth.py`` and assert the 401/503 behaviour explicitly.
"""

from __future__ import annotations

import os

#: Matches tests/unit/adapters/_auth_helper.py:TEST_API_KEY
_TEST_API_KEY = "test-key-not-a-real-credential-2f9c1a"

os.environ.setdefault("PROFESSOR_API_KEY", _TEST_API_KEY)
