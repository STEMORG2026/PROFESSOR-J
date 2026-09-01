"""PROFESSOR-J authority package — root-of-trust, identity, and enforcement.

Provides identity/principal management, authorization gateway enforcement,
capability registration policy, and the immutable authority audit ledger.
"""

from __future__ import annotations

from app.authority.gateway import (
    AuthorityGateway,
    AuthorizationDecision,
    GatewayResult,
    get_gateway,
    require_gateway,
    set_gateway,
)
from app.authority.ledger import AuthorityLedger
from app.authority.policy import (
    _BLESSED_REGISTRAR_TIERS,
    RegisterPolicy,
    default_register_policy,
)
from app.authority.principal import (
    Principal,
    get_current_principal,
    require_principal,
    reset_current_principal,
    set_current_principal,
)

__all__ = [
    # Gateway
    "AuthorityGateway",
    "AuthorizationDecision",
    "GatewayResult",
    "get_gateway",
    "set_gateway",
    "require_gateway",
    # Principal
    "Principal",
    "get_current_principal",
    "require_principal",
    "set_current_principal",
    "reset_current_principal",
    # Registration policy / audit
    "AuthorityLedger",
    "RegisterPolicy",
    "default_register_policy",
    "_BLESSED_REGISTRAR_TIERS",
]