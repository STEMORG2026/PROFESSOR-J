"""MCP Transport abstractions for stdio and Streamable HTTP."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPMessage:
    """Represents an MCP JSON-RPC message."""

    jsonrpc: str = "2.0"
    id: Any = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any = None
    error: dict[str, Any] | None = None

    def to_json(self) -> str:
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method is not None:
            data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = self.error
        return json.dumps(data)

    @classmethod
    def from_json(cls, text: str) -> MCPMessage:
        data = json.loads(text)
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )

    def is_request(self) -> bool:
        return self.method is not None and self.id is not None

    def is_notification(self) -> bool:
        return self.method is not None and self.id is None

    def is_response(self) -> bool:
        return self.id is not None and self.method is None


class MCPTransport(ABC):
    """Abstract transport for MCP communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish the transport connection."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the transport connection."""

    @abstractmethod
    async def send(self, message: MCPMessage) -> None:
        """Send a message."""

    @abstractmethod
    async def receive(self) -> MCPMessage | None:
        """Receive a message. Returns None on EOF/close."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""


class StdioTransport(MCPTransport):
    """Stdio transport for MCP servers launched as subprocesses."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        self._reader = self._process.stdout
        self._writer = self._process.stdin
        self._connected = True
        logger.info("MCP stdio transport connected: %s", self._command)

    async def disconnect(self) -> None:
        if not self._connected:
            return
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        if self._process:
            self._process.terminate()
            await self._process.wait()
        self._connected = False
        logger.info("MCP stdio transport disconnected")

    async def send(self, message: MCPMessage) -> None:
        if not self._connected or not self._writer:
            raise RuntimeError("Transport not connected")
        data = message.to_json() + "\n"
        self._writer.write(data.encode())
        await self._writer.drain()

    async def receive(self) -> MCPMessage | None:
        if not self._connected or not self._reader:
            return None
        try:
            line = await self._reader.readline()
            if not line:
                return None
            return MCPMessage.from_json(line.decode().strip())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to decode MCP message: %s", e)
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._process is not None and self._process.returncode is None


class StreamableHTTPTransport(MCPTransport):
    """Streamable HTTP transport for MCP servers over HTTP/SSE."""

    def __init__(self, base_url: str, headers: dict[str, str] | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._client: Any = None
        self._connected = False
        self._message_queue: asyncio.Queue[MCPMessage] = asyncio.Queue()
        self._sse_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        if self._connected:
            return
        import httpx

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=httpx.Timeout(30.0),
        )
        # Start SSE listener for server-sent events
        self._sse_task = asyncio.create_task(self._listen_sse())
        self._connected = True
        logger.info("MCP HTTP transport connected: %s", self._base_url)

    async def disconnect(self) -> None:
        if not self._connected:
            return
        if self._sse_task:
            self._sse_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sse_task
        if self._client:
            await self._client.aclose()
        self._connected = False
        logger.info("MCP HTTP transport disconnected")

    async def _listen_sse(self) -> None:
        try:
            async with self._client.stream(
                "GET", "/events", headers={"Accept": "text/event-stream"}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            msg = MCPMessage.from_json(data)
                            await self._message_queue.put(msg)
                        except json.JSONDecodeError:
                            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("SSE listener error: %s", e)

    async def send(self, message: MCPMessage) -> None:
        if not self._connected or not self._client:
            raise RuntimeError("Transport not connected")
        # For requests, use POST to /messages endpoint
        response = await self._client.post(
            "/messages",
            json=json.loads(message.to_json()),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    async def receive(self) -> MCPMessage | None:
        if not self._connected:
            return None
        try:
            # Wait for message from SSE queue with timeout
            return await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
        except TimeoutError:
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None
