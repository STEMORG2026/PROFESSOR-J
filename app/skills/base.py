"""Skill Base Classes — Foundation for all PROFESSOR-J skills."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SkillError(Exception):
    """Base exception for skill errors."""

    def __init__(
        self, message: str, skill_name: str | None = None, code: str | None = None
    ):
        super().__init__(message)
        self.skill_name = skill_name
        self.code = code or "SKILL_ERROR"


class SkillStatus(str, Enum):
    """Skill execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SkillMetadata:
    """Metadata describing a skill."""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "PROFESSOR-J"
    tags: list[str] = field(default_factory=list)
    requires_approval: bool = False
    timeout_seconds: int = 30
    category: str = "general"
    mcp_servers: list[str] = field(default_factory=list)
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    returns_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "requires_approval": self.requires_approval,
            "timeout_seconds": self.timeout_seconds,
            "category": self.category,
            "mcp_servers": self.mcp_servers,
            "parameters_schema": self.parameters_schema,
            "returns_schema": self.returns_schema,
        }


@dataclass
class SkillResult(Generic[T]):
    """Result of skill execution."""

    status: SkillStatus
    data: T | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls, data: T, execution_time_ms: float = 0.0, **metadata
    ) -> SkillResult[T]:
        return cls(
            status=SkillStatus.SUCCESS,
            data=data,
            execution_time_ms=execution_time_ms,
            metadata=metadata,
        )

    @classmethod
    def failure(
        cls, error: str, execution_time_ms: float = 0.0, **metadata
    ) -> SkillResult[T]:
        return cls(
            status=SkillStatus.FAILED,
            error=error,
            execution_time_ms=execution_time_ms,
            metadata=metadata,
        )


class Skill(ABC, Generic[T]):
    """Base class for all skills."""

    def __init__(self, metadata: SkillMetadata | None = None) -> None:
        self.metadata = metadata or self._default_metadata()
        self._execution_id: str | None = None
        self._start_time: float | None = None

    @abstractmethod
    def _default_metadata(self) -> SkillMetadata:
        """Return default metadata for this skill."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> SkillResult[T]:
        """Execute the skill with given parameters."""
        ...

    def validate_params(self, **kwargs: Any) -> bool:
        """Validate input parameters against schema. Override for custom validation."""
        return True

    def get_schema(self) -> dict[str, Any]:
        """Get the skill's parameter/return schema for LLM function calling."""
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "parameters": self.metadata.parameters_schema,
            "returns": self.metadata.returns_schema,
        }

    async def __call__(self, **kwargs: Any) -> SkillResult[T]:
        """Execute with timing and error handling."""
        import time

        self._execution_id = str(uuid.uuid4())[:8]
        self._start_time = time.perf_counter()

        logger.info(
            "Executing skill: %s (id=%s)", self.metadata.name, self._execution_id
        )

        try:
            if not self.validate_params(**kwargs):
                return SkillResult.failure(
                    f"Invalid parameters for skill {self.metadata.name}",
                    execution_time_ms=0.0,
                )

            result = await self.execute(**kwargs)

            elapsed = (time.perf_counter() - self._start_time) * 1000
            result.execution_time_ms = elapsed

            logger.info(
                "Skill %s completed: %s in %.2fms",
                self.metadata.name,
                result.status.value,
                elapsed,
            )
            return result

        except Exception as e:
            elapsed = (
                (time.perf_counter() - self._start_time) * 1000
                if self._start_time
                else 0.0
            )
            logger.exception("Skill %s failed: %s", self.metadata.name, e)
            return SkillResult.failure(str(e), execution_time_ms=elapsed)


class MCPMixin:
    """Mixin for skills that use MCP servers."""

    def __init__(
        self, *args: Any, mcp_servers: list[str] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._mcp_servers = mcp_servers or []
        self._mcp_client: Any = None

    @property
    def mcp_servers(self) -> list[str]:
        return self._mcp_servers

    async def get_mcp_client(self) -> Any:
        """Get or create MCP client (lazy initialization)."""
        if self._mcp_client is None:
            from mcp_agent.app import MCPApp
            from mcp_agent.config import get_settings

            settings = get_settings()
            self._mcp_client = MCPApp(name="professor-j-skills", settings=settings)
            await self._mcp_client.initialize()
        return self._mcp_client

    async def call_mcp_tool(self, server: str, tool: str, args: dict[str, Any]) -> Any:
        """Call an MCP tool on a specific server."""
        client = await self.get_mcp_client()
        server_obj = client.server_registry.get(server)
        if not server_obj:
            raise SkillError(
                f"MCP server '{server}' not found", code="MCP_SERVER_NOT_FOUND"
            )
        return await server_obj.call_tool(tool, args)
