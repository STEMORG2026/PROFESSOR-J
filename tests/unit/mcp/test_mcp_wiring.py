"""Tests for MCP composition-root wiring (bootstrap) + package/leaf import isolation.

Verifies that:
- the package `app.mcp` exports the legacy client layer, and
- the current `app.mcp.manager` layer is what bootstrap wires (dormant by default),
- both layers import independently without a circular-import failure.
"""

from __future__ import annotations


def test_package_exports_legacy_client_layer() -> None:
    from app.mcp import (
        MCPResource,
        MCPServerConfig,
        MCPTool,
    )

    # Legacy client model uses server_id / transport.
    tool = MCPTool("read", "desc", {"type": "object"}, server_id="fs")
    assert tool.server_id == "fs"
    cfg = MCPServerConfig(server_id="fs", name="Filesystem", transport="stdio", command=["npx"])
    assert cfg.transport == "stdio"
    assert isinstance(MCPResource("mem://a", "A", None, None, "fs"), MCPResource)


def test_manager_layer_keeps_distinct_leaf_model() -> None:
    from app.mcp.manager import MCPServerConfig as ManagerConfig, MCPTool as ManagerTool

    # Current manager model uses server_name / transport_type / headers.
    tool = ManagerTool("read", "desc", {}, server_name="fs")
    assert tool.server_name == "fs"
    cfg = ManagerConfig(
        name="svc", transport_type="http", url="http://localhost", headers={"X": "y"}
    )
    assert cfg.transport_type == "http"
    assert cfg.headers == {"X": "y"}


def test_the_two_mcp_tools_are_distinct_models() -> None:
    from app.mcp import MCPTool as ClientTool
    from app.mcp.manager import MCPTool as ManagerTool

    # Same name but different semantics: field names differ, so they are NOT one shared model.
    client_fields = set(ClientTool.__dataclass_fields__)
    manager_fields = set(ManagerTool.__dataclass_fields__)
    assert client_fields == {"name", "description", "input_schema", "server_id"}
    assert {"server_id"} <= client_fields
    assert "server_id" not in manager_fields  # current manager uses server_name (+ tier)
    assert "server_name" in manager_fields
    assert client_fields != manager_fields


def test_bootstrap_wires_current_manager_layer() -> None:
    import app.bootstrap

    root = app.bootstrap.build_root()
    assert root.mcp is not None
    # It is the current management layer, NOT the legacy client manager.
    assert type(root.mcp).__name__ == "MCPServerManager"
    assert type(root.mcp).__module__ == "app.mcp.manager"
    # Dormant by default: no servers registered.
    assert root.mcp.list_tools() == []


def test_mcp_package_imports_without_app_initialization() -> None:
    # Importing the MCP package must not pull in unrelated app bootstrap/gateway.
    import app.mcp as mcp_pkg

    assert mcp_pkg.MCPClientManager is not None
    # Creating a client manager is lightweight and needs no policy/app root.
    _ = mcp_pkg.MCPClientManager()
