"""Tests for MCP transports."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp.transports import MCPMessage, StdioTransport, StreamableHTTPTransport


class TestMCPMessage:
    def test_to_json_request(self) -> None:
        msg = MCPMessage(id=1, method="tools/list", params={})
        json_str = msg.to_json()
        data = eval(json_str)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["method"] == "tools/list"
        assert data["params"] == {}

    def test_to_json_response(self) -> None:
        msg = MCPMessage(id=1, result={"tools": []})
        json_str = msg.to_json()
        data = eval(json_str)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["result"] == {"tools": []}

    def test_to_json_error(self) -> None:
        msg = MCPMessage(id=1, error={"code": -32601, "message": "Method not found"})
        json_str = msg.to_json()
        data = eval(json_str)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["error"]["code"] == -32601

    def test_from_json(self) -> None:
        json_str = '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
        msg = MCPMessage.from_json(json_str)
        assert msg.jsonrpc == "2.0"
        assert msg.id == 1
        assert msg.method == "tools/list"
        assert msg.params == {}

    def test_is_request(self) -> None:
        msg = MCPMessage(id=1, method="tools/list")
        assert msg.is_request() is True
        assert msg.is_notification() is False
        assert msg.is_response() is False

    def test_is_notification(self) -> None:
        msg = MCPMessage(method="notifications/initialized")
        assert msg.is_notification() is True
        assert msg.is_request() is False
        assert msg.is_response() is False

    def test_is_response(self) -> None:
        msg = MCPMessage(id=1, result={})
        assert msg.is_response() is True
        assert msg.is_request() is False
        assert msg.is_notification() is False


class TestStdioTransport:
    @pytest.mark.asyncio
    async def test_init(self) -> None:
        transport = StdioTransport(["echo", "test"], env={"TEST": "value"})
        assert transport._command == ["echo", "test"]
        assert transport._env == {"TEST": "value"}
        assert transport.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        transport = StdioTransport(["sleep", "10"])
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdin = AsyncMock()
            mock_process.returncode = None
            mock_exec.return_value = mock_process

            await transport.connect()
            assert transport.is_connected is True
            assert transport._process is not None

            await transport.disconnect()
            assert transport.is_connected is False
            mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_receive(self) -> None:
        transport = StdioTransport(["echo", "test"])
        mock_writer = AsyncMock()
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(
            return_value=b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n'
        )

        transport._writer = mock_writer
        transport._reader = mock_reader
        transport._connected = True

        msg = MCPMessage(id=1, method="test")
        await transport.send(msg)
        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_called_once()

        received = await transport.receive()
        assert received is not None
        assert received.id == 1
        assert received.result == {}


class TestStreamableHTTPTransport:
    @pytest.mark.asyncio
    async def test_init(self) -> None:
        transport = StreamableHTTPTransport("http://localhost:8000", headers={"Auth": "Bearer"})
        assert transport._base_url == "http://localhost:8000"
        assert transport._headers == {"Auth": "Bearer"}
        assert transport.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        transport = StreamableHTTPTransport("http://localhost:8000")
        with patch("httpx.AsyncClient", new_callable=MagicMock) as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            await transport.connect()
            assert transport.is_connected is True
            assert transport._client is not None
            assert transport._sse_task is not None

            await transport.disconnect()
            assert transport.is_connected is False
            mock_client.aclose.assert_called_once()
            assert transport._sse_task.cancelled()

    @pytest.mark.asyncio
    async def test_send(self) -> None:
        transport = StreamableHTTPTransport("http://localhost:8000")
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_client.post.return_value = mock_response
        transport._client = mock_client
        transport._connected = True

        msg = MCPMessage(id=1, method="tools/call", params={"name": "test", "arguments": {}})
        await transport.send(msg)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/messages"

    @pytest.mark.asyncio
    async def test_receive_timeout(self) -> None:
        transport = StreamableHTTPTransport("http://localhost:8000")
        transport._connected = True
        transport._message_queue = asyncio.Queue()

        result = await transport.receive()
        assert result is None
