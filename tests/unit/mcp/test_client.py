"""Tests for app.mcp — the concrete MCP clients and manager.

Covers :class:`StdioMCPClient`, :class:`SSEClient`, :class:`MCPClientManager`,
:class:`MCPToolSkill`, and :func:`create_mcp_manager_from_config`. No real
subprocesses (npx, etc.) are ever launched: IO is faked via stub writers and a
monkeypatched ``asyncio.create_subprocess_exec``.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import pytest

from app.mcp import (
    MCPClientManager,
    MCPResource,
    MCPServerConfig,
    MCPTool,
    MCPToolSkill,
    SSEClient,
    StdioMCPClient,
    create_mcp_manager_from_config,
)


def _stdio_config(**overrides: Any) -> MCPServerConfig:
    defaults: dict[str, Any] = {
        "server_id": "fs",
        "name": "Filesystem",
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem"],
    }
    defaults.update(overrides)
    return MCPServerConfig(**defaults)


class _ResolvingWriter:
    """Fake StreamWriter whose drain resolves the latest pending request."""

    def __init__(self, client: StdioMCPClient, result: dict[str, Any]) -> None:
        self._client = client
        self._result = result
        self.written = b""

    def write(self, data: bytes) -> None:
        self.written += data

    async def drain(self) -> None:
        if self._client._pending:
            rid = max(self._client._pending)
            self._client._handle_message({"id": rid, "result": self._result})


class _SilentWriter:
    """Fake StreamWriter that never resolves pending requests (timeouts)."""

    def __init__(self) -> None:
        self.written = b""

    def write(self, data: bytes) -> None:
        self.written += data

    async def drain(self) -> None:
        return None


class _FakeProcess:
    """Minimal stand-in for asyncio.subprocess.Process."""

    def __init__(
        self,
        stdin: Any,
        stdout: Any = None,
        stderr: Any = None,
        *,
        wait_raises: bool = False,
    ) -> None:
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.wait_raises = wait_raises
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.wait_calls += 1
        if self.wait_raises and self.wait_calls == 1:
            raise TimeoutError("timeout")
        return 0


class _StubClient:
    """Controllable MCPClientBase stand-in for manager-level tests."""

    def __init__(
        self, tools: list[MCPTool], resources: list[MCPResource], *, fail_connect: bool = False
    ) -> None:
        self.tools = tools
        self.resources = resources
        self.fail_connect = fail_connect
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.call_log: list[tuple[str, dict[str, Any]]] = []
        self.read_log: list[str] = []

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.fail_connect:
            raise RuntimeError("boom")

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def initialize(self) -> dict[str, Any]:
        return {}

    async def list_tools(self) -> list[MCPTool]:
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.call_log.append((name, arguments))
        return {"ok": True}

    async def list_resources(self) -> list[MCPResource]:
        return list(self.resources)

    async def read_resource(self, uri: str) -> dict[str, Any]:
        self.read_log.append(uri)
        return {"contents": []}

    async def subscribe_resource(self, uri: str) -> None:
        return None

    async def unsubscribe_resource(self, uri: str) -> None:
        return None


class TestStdioMCPClientValidation:
    def test_requires_command(self) -> None:
        with pytest.raises(ValueError):
            StdioMCPClient(_stdio_config(command=None))

    def test_accepts_command(self) -> None:
        client = StdioMCPClient(_stdio_config())
        assert client._writer is None
        assert client._initialized is False

    def test_command_without_transport_arg_is_fine(self) -> None:
        # Args are independent of command; empty args list is allowed.
        client = StdioMCPClient(_stdio_config(args=[]))
        assert client.config.args == []


class TestStdioMCPClientMessaging:
    async def test_send_request_raises_when_not_connected(self) -> None:
        client = StdioMCPClient(_stdio_config())
        with pytest.raises(RuntimeError):
            await client._send_request("initialize")

    async def test_send_notification_raises_when_not_connected(self) -> None:
        client = StdioMCPClient(_stdio_config())
        with pytest.raises(RuntimeError):
            await client._send_notification("notifications/initialized")

    async def test_send_request_success(self) -> None:
        client = StdioMCPClient(_stdio_config())
        writer = _ResolvingWriter(client, {"serverInfo": {"name": "test"}})
        client._writer = cast(Any, writer)
        result = await client._send_request("initialize")
        assert result == {"serverInfo": {"name": "test"}}
        assert client._request_id == 1
        assert b'"initialize"' in writer.written

    async def test_send_request_timeout(self) -> None:
        client = StdioMCPClient(_stdio_config(timeout_seconds=0.01))
        client._writer = cast(Any, _SilentWriter())
        with pytest.raises(TimeoutError):
            await client._send_request("initialize")
        # Pending entry is cleaned up on timeout.
        assert client._pending == {}

    async def test_initialize_sets_server_info(self) -> None:
        client = StdioMCPClient(_stdio_config())
        client._writer = cast(
            Any, _ResolvingWriter(client, {"serverInfo": {"name": "s"}, "capabilities": {}})
        )
        info = await client.initialize()
        assert info == {"name": "s"}
        assert client._initialized is True
        assert client._capabilities == {}

    async def test_initialize_short_circuits_when_already_initialized(self) -> None:
        client = StdioMCPClient(_stdio_config())
        client._initialized = True
        client._server_info = {"name": "cached"}
        result = await client.initialize()
        assert result == {"name": "cached"}


class TestStdioMCPClientJsonParsing:
    def test_try_parse_json_complete_object(self) -> None:
        client = StdioMCPClient(_stdio_config())
        msg, consumed = client._try_parse_json('{"a": 1}\n{"b": 2}')
        assert msg == {"a": 1}
        assert consumed == 8

    def test_try_parse_json_empty_and_incomplete(self) -> None:
        client = StdioMCPClient(_stdio_config())
        assert client._try_parse_json("") == (None, 0)
        assert client._try_parse_json('{"a":') == (None, 0)

    def test_try_parse_json_nested_strings_and_escapes(self) -> None:
        client = StdioMCPClient(_stdio_config())
        msg, consumed = client._try_parse_json(r'{"s": "he\"llo}", "k": 2}')
        assert msg is not None
        assert msg["s"] == 'he"llo}'
        assert msg["k"] == 2
        assert consumed == len(r'{"s": "he\"llo}", "k": 2}')

    def test_try_parse_json_index_points_to_first_json(self) -> None:
        client = StdioMCPClient(_stdio_config())
        raw = '{"id": 1, "result": {"x": [1, 2, {"y": "}"}]}}extra'
        msg, consumed = client._try_parse_json(raw)
        assert msg is not None
        assert msg == {"id": 1, "result": {"x": [1, 2, {"y": "}"}]}}
        assert raw[consumed:] == "extra"

    def test_try_parse_json_invalid_balanced_object_returns_none(self) -> None:
        client = StdioMCPClient(_stdio_config())
        # Braces balance (depth reaches 0) but the payload is not valid JSON.
        assert client._try_parse_json('{"a": }') == (None, 0)


class TestStdioMCPClientHandleMessage:
    async def test_handle_message_resolves_pending(self) -> None:
        client = StdioMCPClient(_stdio_config())
        client._request_id = 1
        fut: Any = asyncio.get_event_loop().create_future()
        client._pending = {1: fut}
        client._handle_message({"id": 1, "result": {"ok": True}})
        assert fut.result() == {"ok": True}
        assert 1 not in client._pending

    async def test_handle_message_error_sets_exception(self) -> None:
        client = StdioMCPClient(_stdio_config())
        fut: Any = asyncio.get_event_loop().create_future()
        client._pending = {1: fut}
        client._handle_message({"id": 1, "error": {"message": "kaput"}})
        assert "kaput" in str(fut.exception())

    def test_handle_notification_ignored(self) -> None:
        client = StdioMCPClient(_stdio_config())
        client._handle_message({"method": "notifications/thing"})
        # No exception; pending untouched.
        assert client._pending == {}


class TestStdioMCPClientOperations:
    async def test_list_tools_builds_mcp_tools(self) -> None:
        client = StdioMCPClient(_stdio_config())

        async def _fake_send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {
                "tools": [
                    {"name": "read", "description": "Read", "inputSchema": {"type": "object"}},
                    {"name": "write"},  # missing description/inputSchema fall back to defaults
                ]
            }

        client._send_request = _fake_send  # type: ignore[method-assign]
        tools = await client.list_tools()
        assert tools == [
            MCPTool("read", "Read", {"type": "object"}, "fs"),
            MCPTool("write", "", {}, "fs"),
        ]

    async def test_call_tool(self) -> None:
        client = StdioMCPClient(_stdio_config())

        async def _fake_send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {"content": [{"type": "text", "text": "hi"}]}

        client._send_request = _fake_send  # type: ignore[method-assign]
        out = await client.call_tool("read", {"path": "/tmp"})
        assert out == {"content": [{"type": "text", "text": "hi"}]}

    async def test_list_resources_builds_mcp_resources(self) -> None:
        client = StdioMCPClient(_stdio_config())

        async def _fake_send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {
                "resources": [
                    {"uri": "mem://a", "name": "A", "description": "d", "mimeType": "text/plain"}
                ]
            }

        client._send_request = _fake_send  # type: ignore[method-assign]
        resources = await client.list_resources()
        assert resources == [MCPResource("mem://a", "A", "d", "text/plain", "fs")]

    async def test_read_resource(self) -> None:
        client = StdioMCPClient(_stdio_config())

        async def _fake_send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            assert params is not None
            return {"contents": [{"uri": params["uri"], "text": "x"}]}

        client._send_request = _fake_send  # type: ignore[method-assign]
        out = await client.read_resource("mem://a")
        assert out["contents"][0]["uri"] == "mem://a"

    async def test_subscribe_unsubscribe(self) -> None:
        client = StdioMCPClient(_stdio_config())

        async def _fake_send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {}

        client._send_request = _fake_send  # type: ignore[method-assign]
        await client.subscribe_resource("mem://a")
        await client.unsubscribe_resource("mem://a")


class TestStdioMCPClientConnection:
    async def test_connect_launches_subprocess_and_initializes(self, monkeypatch: Any) -> None:
        client = StdioMCPClient(_stdio_config(timeout_seconds=5, env={"DEBUG": "1"}))
        main_script = {"serverInfo": {"name": "filesystem"}, "capabilities": {"tools": {}}}
        exec_kwargs: dict[str, Any] = {}

        async def _fake_exec(*args: Any, **kwargs: Any) -> _FakeProcess:
            exec_kwargs.update(kwargs)
            return _FakeProcess(stdin=_ResolvingWriter(client, main_script), stdout=None)

        monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)
        await client.connect()
        assert client._process is not None
        assert client._initialized is True
        assert client._server_info == {"name": "filesystem"}
        assert exec_kwargs["env"]["DEBUG"] == "1"

    async def test_connect_without_env_uses_process_env(self, monkeypatch: Any) -> None:
        client = StdioMCPClient(_stdio_config(timeout_seconds=5))
        exec_kwargs: dict[str, Any] = {}

        async def _fake_exec(*args: Any, **kwargs: Any) -> _FakeProcess:
            exec_kwargs.update(kwargs)
            return _FakeProcess(stdin=_ResolvingWriter(client, {}), stdout=None)

        monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)
        await client.connect()
        assert exec_kwargs["env"]["PATH"]  # falls back to os.environ copy

    async def test_read_messages_no_reader_returns(self, monkeypatch: Any) -> None:
        client = StdioMCPClient(_stdio_config())

        async def _fake_exec(*args: Any, **kwargs: Any) -> _FakeProcess:
            return _FakeProcess(stdin=_ResolvingWriter(client, {}), stdout=None)

        monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)
        await client._read_messages()  # no reader -> returns immediately, no exception

    async def test_read_messages_parses_and_handles_lines(self) -> None:
        client = StdioMCPClient(_stdio_config())

        class Reader:
            def __init__(self) -> None:
                self.lines = ['{"id": 1, "result": {"ok": true}}\n', ""]
                self.at_eof_flag = False

            async def readline(self) -> bytes:
                if not self.lines:
                    self.at_eof_flag = True
                    return b""
                return self.lines.pop(0).encode()

            def at_eof(self) -> bool:
                return self.at_eof_flag

        fut: Any = asyncio.get_event_loop().create_future()
        client._pending = {1: fut}
        client._reader = cast(Any, Reader())
        client._process = cast(Any, _FakeProcess(stdin=None))
        await client._read_messages()
        assert fut.result() == {"ok": True}

    async def test_read_messages_logs_and_stops_on_error(self) -> None:
        client = StdioMCPClient(_stdio_config())

        class BadReader:
            async def readline(self) -> bytes:
                raise OSError("io error")

            def at_eof(self) -> bool:
                return False

        client._reader = cast(Any, BadReader())
        client._process = cast(Any, _FakeProcess(stdin=None))
        # Should not raise; logs and breaks the loop.
        await client._read_messages()

    async def test_disconnect_terminates_process(self) -> None:
        client = StdioMCPClient(_stdio_config())
        proc = _FakeProcess(stdin=None)
        client._process = cast(Any, proc)
        await client.disconnect()
        assert proc.terminated is True
        assert client._process is None

    async def test_disconnect_kills_on_timeout(self) -> None:
        client = StdioMCPClient(_stdio_config())
        proc = _FakeProcess(stdin=None, wait_raises=True)
        client._process = cast(Any, proc)
        await client.disconnect()
        assert proc.terminated is True
        assert proc.killed is True
        assert client._process is None

    async def test_disconnect_noop_when_no_process(self) -> None:
        client = StdioMCPClient(_stdio_config())
        await client.disconnect()  # no process -> no exception


class TestSSEClient:
    def test_requires_url(self) -> None:
        cfg = MCPServerConfig(server_id="sse", name="SSE", transport="sse", url=None)
        with pytest.raises(ValueError):
            SSEClient(cfg)

    def test_stub_raises_not_implemented(self) -> None:
        cfg = MCPServerConfig(
            server_id="sse", name="SSE", transport="sse", url="http://localhost:8000"
        )
        with pytest.raises(NotImplementedError):
            SSEClient(cfg)


class TestMCPClientManager:
    async def test_add_stdio_server(self) -> None:
        manager = MCPClientManager()
        manager.add_server(_stdio_config())
        assert "fs" in manager._clients
        assert isinstance(manager._clients["fs"], StdioMCPClient)

    def test_add_stdio_without_command_raises(self) -> None:
        manager = MCPClientManager()
        with pytest.raises(ValueError):
            manager.add_server(_stdio_config(command=None))

    def test_add_sse_is_stub(self) -> None:
        manager = MCPClientManager()
        cfg = MCPServerConfig(server_id="sse", name="SSE", transport="sse", url="http://localhost")
        with pytest.raises(NotImplementedError):
            manager.add_server(cfg)

    def test_add_unsupported_transport_raises(self) -> None:
        manager = MCPClientManager()
        cfg = MCPServerConfig(server_id="x", name="X", transport="websocket", url="wss://h")
        with pytest.raises(ValueError):
            manager.add_server(cfg)

    async def test_connect_all_success(self) -> None:
        manager = MCPClientManager()
        tool = MCPTool("read", "desc", {"type": "object"}, "s")
        res = MCPResource("mem://a", "A", None, None, "s")
        stub = _StubClient([tool], [res])
        manager._clients["s"] = cast(Any, stub)
        results = await manager.connect_all()
        assert results == {"s": True}
        assert manager.get_tool("s:read") == tool
        assert manager.get_resource("s:mem://a") == res

    async def test_connect_all_failure_returns_false(self) -> None:
        manager = MCPClientManager()
        # Inject directly so no real client is constructed for this branch test.
        stub = _StubClient([], [], fail_connect=True)
        manager._clients["bad"] = cast(Any, stub)
        results = await manager.connect_all()
        assert results == {"bad": False}
        assert manager.list_tools() == []
        assert manager.list_resources() == []

    async def test_refresh_server_unknown_is_noop(self) -> None:
        manager = MCPClientManager()
        await manager._refresh_server("missing")
        assert manager.list_tools() == []

    async def test_refresh_server_logs_client_errors(self) -> None:
        manager = MCPClientManager()

        class ErrorClient(_StubClient):
            async def list_tools(self) -> list[MCPTool]:
                raise RuntimeError("refresh failed")

        manager._clients["bad"] = cast(Any, ErrorClient([], []))
        await manager._refresh_server("bad")
        assert manager.list_tools() == []
        assert manager.list_resources() == []

    async def test_disconnect_all_continues_on_client_error(self) -> None:
        manager = MCPClientManager()

        class ErrorClient(_StubClient):
            async def disconnect(self) -> None:
                raise RuntimeError("disconnect failed")

        good = _StubClient([], [])
        manager._clients["bad"] = cast(Any, ErrorClient([], []))
        manager._clients["good"] = cast(Any, good)
        await manager.disconnect_all()
        assert good.disconnect_calls == 1
        assert manager._clients == {}

    async def test_disconnect_all_clears_state(self) -> None:
        manager = MCPClientManager()
        stub = _StubClient([MCPTool("t", "d", {}, "s")], [])
        stub_2 = _StubClient([], [])
        manager._clients["a"] = cast(Any, stub)
        manager._clients["b"] = cast(Any, stub_2)
        await manager.disconnect_all()
        assert stub.disconnect_calls == 1
        assert stub_2.disconnect_calls == 1
        assert manager._clients == {}
        assert manager.list_tools() == []

    async def test_call_tool_unknown_server_raises(self) -> None:
        manager = MCPClientManager()
        with pytest.raises(ValueError):
            await manager.call_tool("nope", "t", {})

    async def test_call_tool_forwards(self) -> None:
        manager = MCPClientManager()
        stub = _StubClient([], [])
        manager._clients["s"] = cast(Any, stub)
        out = await manager.call_tool("s", "read", {"path": "/"})
        assert out == {"ok": True}
        assert stub.call_log == [("read", {"path": "/"})]

    async def test_read_resource_unknown_server_raises(self) -> None:
        manager = MCPClientManager()
        with pytest.raises(ValueError):
            await manager.read_resource("nope", "uri")

    async def test_read_resource_forwards(self) -> None:
        manager = MCPClientManager()
        stub = _StubClient([], [])
        manager._clients["s"] = cast(Any, stub)
        out = await manager.read_resource("s", "mem://a")
        assert out == {"contents": []}


class TestMCPToolSkill:
    def _skill(self) -> tuple[MCPToolSkill, _StubClient]:
        manager = MCPClientManager()
        stub = _StubClient(
            [MCPTool("read", "Read files", {"type": "object"}, "fs")],
            [MCPResource("mem://a", "A", "d", "text/plain", "fs")],
        )
        manager._clients["fs"] = cast(Any, stub)
        tool = stub.tools[0]
        res = stub.resources[0]
        manager._all_tools[f"{tool.server_id}:{tool.name}"] = tool
        manager._all_resources[f"{res.server_id}:{res.uri}"] = res
        return MCPToolSkill(manager), stub

    async def test_execute_tool(self) -> None:
        skill, stub = self._skill()
        out = await skill.execute_tool("fs", "read", {"path": "/"})
        assert out == {"ok": True}
        assert stub.call_log == [("read", {"path": "/"})]

    async def test_read_resource(self) -> None:
        skill, stub = self._skill()
        out = await skill.read_resource("fs", "mem://a")
        assert out == {"contents": []}

    def test_list_available_tools_and_resources(self) -> None:
        skill, _ = self._skill()
        tools = skill.list_available_tools()
        assert tools == [
            {
                "key": "fs:read",
                "name": "read",
                "description": "Read files",
                "server_id": "fs",
                "input_schema": {"type": "object"},
            }
        ]
        resources = skill.list_available_resources()
        assert resources == [
            {
                "key": "fs:mem://a",
                "uri": "mem://a",
                "name": "A",
                "description": "d",
                "mime_type": "text/plain",
                "server_id": "fs",
            }
        ]


class TestCreateMCPManagerFromConfig:
    def test_missing_file_returns_empty_manager(self, tmp_path: Any) -> None:
        manager = create_mcp_manager_from_config(str(tmp_path / "nope.json"))
        assert manager.list_tools() == []

    def test_valid_config_builds_stdio_clients(self, tmp_path: Any) -> None:
        cfg = tmp_path / "mcp_servers.json"
        cfg.write_text(
            json.dumps(
                {
                    "servers": [
                        {
                            "server_id": "fs",
                            "name": "Filesystem",
                            "transport": "stdio",
                            "command": ["npx", "-y", "server-fs"],
                            "args": ["/tmp"],
                            "timeout_seconds": 5,
                            "auto_reconnect": False,
                        },
                        {
                            "server_id": "mem",
                            "name": "Memory",
                            "transport": "stdio",
                            "command": ["node", "mem.js"],
                            "env": {"DEBUG": "1"},
                        },
                    ]
                }
            )
        )
        manager = create_mcp_manager_from_config(str(cfg))
        assert set(manager._clients) == {"fs", "mem"}
        assert isinstance(manager._clients["fs"], StdioMCPClient)
        fs_cfg = manager._configs["fs"]
        assert fs_cfg.command == ["npx", "-y", "server-fs"]
        assert fs_cfg.args == ["/tmp"]
        assert fs_cfg.timeout_seconds == 5
        assert fs_cfg.auto_reconnect is False
        assert manager._configs["mem"].env == {"DEBUG": "1"}

    def test_invalid_json_returns_empty_manager(self, tmp_path: Any) -> None:
        cfg = tmp_path / "mcp_servers.json"
        cfg.write_text("{ not json")
        manager = create_mcp_manager_from_config(str(cfg))
        assert manager.list_tools() == []
