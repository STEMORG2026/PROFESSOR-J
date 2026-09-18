"""Subagent Manager — spawn, control, steer, stop child agent processes."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SubagentProcess:
    """Represents a running subagent process."""

    agent_id: str
    command: list[str]
    process: asyncio.subprocess.Process | None = None
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


class SubagentManager:
    """Manages subagent processes (spawn, control, steer, stop)."""

    def __init__(self) -> None:
        self._agents: dict[str, SubagentProcess] = {}

    async def spawn(self, agent_id: str, command: list[str], **kwargs: Any) -> SubagentProcess:
        """Spawn a new subagent process."""
        proc = SubagentProcess(agent_id=agent_id, command=command)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            proc.process = process
            proc.status = "running"
            self._agents[agent_id] = proc
            logger.info("Spawned subagent %s (pid=%s)", agent_id, process.pid)
        except Exception as exc:
            proc.status = "failed"
            logger.error("Failed to spawn subagent %s: %s", agent_id, exc)
            raise
        return proc

    async def stop(self, agent_id: str) -> bool:
        """Stop a running subagent."""
        proc = self._agents.get(agent_id)
        if proc and proc.process:
            proc.process.terminate()
            await proc.process.wait()
            proc.status = "stopped"
            logger.info("Stopped subagent %s", agent_id)
            return True
        return False

    async def steer(self, agent_id: str, message: str) -> bool:
        """Send a steering message to a subagent."""
        proc = self._agents.get(agent_id)
        if proc and proc.process and proc.process.stdin:
            proc.process.stdin.write(message.encode() + b"\n")
            await proc.process.stdin.drain()
            return True
        return False

    def list_agents(self) -> list[SubagentProcess]:
        """List all managed subagents."""
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> SubagentProcess | None:
        """Get a specific subagent."""
        return self._agents.get(agent_id)


def create_subagent_manager() -> SubagentManager:
    """Create a subagent manager."""
    return SubagentManager()


__all__ = ["SubagentManager", "SubagentProcess", "create_subagent_manager"]
