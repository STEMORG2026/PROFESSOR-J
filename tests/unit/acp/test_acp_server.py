"""Tests for the ACP server."""

from __future__ import annotations

import json

import pytest

from app.acp import ACPRequest, ACPServer, create_acp_server


class TestACPServer:
    """Test suite for the ACP server."""

    @pytest.fixture
    def server(self) -> ACPServer:
        return create_acp_server()

    @pytest.mark.asyncio
    async def test_status_method(self, server: ACPServer) -> None:
        request = ACPRequest(id="1", method="status")
        response = await server.handle_request(request)
        assert response.result == {"status": "ready", "protocol": "acp/1.0"}
        assert response.error is None

    @pytest.mark.asyncio
    async def test_capabilities_method(self, server: ACPServer) -> None:
        request = ACPRequest(id="2", method="capabilities")
        response = await server.handle_request(request)
        assert "methods" in response.result
        assert "status" in response.result["methods"]

    @pytest.mark.asyncio
    async def test_unknown_method(self, server: ACPServer) -> None:
        request = ACPRequest(id="3", method="nonexistent")
        response = await server.handle_request(request)
        assert response.error is not None
        assert response.error["code"] == -32601

    @pytest.mark.asyncio
    async def test_message_roundtrip(self, server: ACPServer) -> None:
        msg = '{"jsonrpc": "2.0", "id": "4", "method": "status"}'
        result = await server.handle_message(msg)
        data = json.loads(result)
        assert data["id"] == "4"
        assert data["result"]["status"] == "ready"
