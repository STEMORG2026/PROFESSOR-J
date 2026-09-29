"""API authentication and egress allow-listing.

This module is the single ingress boundary for the HTTP surface. It exists because
the audit (``_audit/02_FINDINGS.md`` S0-1, S0-2) established that all 34 routes were
reachable without credentials and that a caller-supplied ``base_url`` was paired with
the server's own provider key.

Two controls live here, and both **fail closed**:

``require_api_key``
    Rejects any request that does not carry the configured bearer token. If the
    configured token is absent or is a known placeholder, *every* request is rejected
    and the reason is logged. A placeholder token is not a weaker password — it is a
    publicly known one — so accepting it would be worse than no check at all, because
    it would appear in the route table as an enforced dependency.
    ``dependencies=[Depends(require_api_key)]``.

``resolve_base_url``
    Decides which upstream origins the server may be pointed at, and whether a
    credential the *server* owns may be sent there. The rule is narrow and deliberate:
    a server-side provider credential may only travel to an origin on the allow-list.
    A caller that nominates its own origin must supply its own credential.

Allow-listed origins, in order of precedence:

1. Origins named in ``PROFESSOR_ALLOWED_BASE_URLS`` (comma-separated).
2. The configured provider endpoints the server itself owns
   (``singularity_base_url``, ``bluesmind_base_url``).
3. Loopback origins on any port — the local-inference path (Ollama, llama.cpp),
   which cannot exfiltrate a credential off the machine.
"""

from __future__ import annotations

import hmac
import logging
import os
from urllib.parse import urlsplit

from fastapi import Header, HTTPException, status

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

#: Values that must never be accepted as a bearer token. These are the defaults and
#: near-defaults a reader would guess; ``changeme`` is the declared default of
#: ``Settings.api_key``.
_PLACEHOLDER_KEYS: frozenset[str] = frozenset(
    {"", "changeme", "change-me", "changeme!", "dev", "development", "test", "secret", "api-key"}
)

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def _configured_api_key() -> str:
    """Return the configured bearer token, or ``""`` when it is unusable."""
    return (get_settings().api_key or "").strip()


def auth_is_configured() -> bool:
    """Whether a usable (non-placeholder) bearer token is configured."""
    return _configured_api_key() not in _PLACEHOLDER_KEYS


async def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    """FastAPI dependency enforcing the bearer token on every protected route.

    Accepts either ``Authorization: Bearer <token>`` or ``X-API-Key: <token>``.
    Raises 401 for a missing or wrong token, and 503 when no usable token is
    configured — because in that state the correct answer is "this server is not
    safe to serve traffic", not "let the request through".
    """
    expected = _configured_api_key()

    if expected in _PLACEHOLDER_KEYS:
        logger.error(
            "API authentication is not configured (PROFESSOR_API_KEY is unset or a "
            "placeholder); refusing request to protect the unauthenticated surface"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "API authentication is not configured. Set PROFESSOR_API_KEY to a "
                "secure random value before serving requests."
            ),
        )

    presented = ""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            presented = token.strip()
    if not presented and x_api_key:
        presented = x_api_key.strip()

    # Constant-time comparison: a length-independent early return would leak the
    # token's length and prefix through timing.
    if not presented or not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _allowed_origins() -> set[str]:
    """Origins the server may be pointed at, as ``scheme://host:port`` strings."""
    settings = get_settings()
    origins: set[str] = set()

    raw = os.environ.get("PROFESSOR_ALLOWED_BASE_URLS", "")
    for item in raw.split(","):
        item = item.strip().rstrip("/")
        if item:
            origins.add(item)

    # `getattr` rather than direct attribute access: the audit found the bluesmind
    # branch reading `settings.bluesmind_base_url`, which does not exist (S2-17). A
    # resolver that crashes on a misdeclared setting would turn a safe request into a
    # 500, so an absent setting is treated as "no allow-listed origin from settings".
    for name in ("singularity_base_url", "bluesmind_base_url", "openai_base_url"):
        candidate = getattr(settings, name, None)
        if isinstance(candidate, str) and candidate:
            origins.add(candidate.rstrip("/"))

    return origins


def resolve_base_url(candidate: str | None, default: str | None) -> str | None:
    """Return a safe origin to contact, or raise 400.

    ``candidate`` is the caller-supplied value and is therefore untrusted. When it is
    absent the server's own ``default`` is used and needs no checking. When it is
    present it must be loopback or explicitly allow-listed.
    """
    if not candidate:
        return default

    candidate = candidate.strip().rstrip("/")
    if not candidate:
        return default

    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="base_url must be an absolute http(s) URL",
        )

    if parts.hostname in _LOOPBACK_HOSTS:
        return candidate

    if candidate in _allowed_origins():
        return candidate

    logger.warning(
        "Rejected caller-supplied base_url (host=%s): not allow-listed, and the "
        "server's own provider credential will not be sent there",
        parts.hostname,
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "base_url host is not allow-listed. A server-side provider credential is "
            "never sent to a caller-nominated origin; add the origin to "
            "PROFESSOR_ALLOWED_BASE_URLS if it is trusted, or supply your own api_key."
        ),
    )
