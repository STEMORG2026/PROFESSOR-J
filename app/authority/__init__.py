"""PROFESSOR-J Authority Package — root-of-trust, identity, and enforcement."""

from __future__ import annotations

from app.authority.gateway import (
    AuthorityGateway,
    AuthorizationDecision,
    GatewayResult,
    get_gateway,
    require_gateway,
    set_gateway,
)
from app.authority.principal import (
    Principal,
    get_current_principal,
    require_principal,
    reset_current_principal,
    set_current_principal,
)

__all__ = [
    "AuthorityGateway",
    "AuthorizationDecision",
    "GatewayResult",
    "get_gateway",
    "set_gateway",
    "require_gateway",
    "Principal",
    "get_current_principal",
    "require_principal",
    "set_current_principal",
    "reset_current_principal",
]
