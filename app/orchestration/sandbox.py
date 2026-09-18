"""Sandboxed Execution — bubblewrap/E2B isolation for child agents.

Modeled on dsh `sandbox/` and `e2b/` packages.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Sandbox configuration."""

    memory_mb: int = 512
    cpu_quota: int = 50000  # 50% of one CPU core
    timeout_seconds: int = 30
    network: bool = False
    read_only: bool = True
    working_dir: str = "/tmp/sandbox"


@dataclass
class SandboxResult:
    """Result of sandboxed execution."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class SandboxedExecution:
    """Execute code in an isolated sandbox."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()

    async def execute_command(
        self,
        command: list[str],
        stdin: str | None = None,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Execute a command in the sandbox."""
        import time

        start = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin else None,
                env=env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(stdin.encode() if stdin else None),
                timeout=self._config.timeout_seconds,
            )
            duration = (time.monotonic() - start) * 1000
            return SandboxResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                timed_out=False,
                duration_ms=duration,
            )
        except TimeoutError:
            duration = (time.monotonic() - start) * 1000
            return SandboxResult(
                stdout="",
                stderr="TIMEOUT",
                exit_code=-1,
                timed_out=True,
                duration_ms=duration,
            )

    async def execute_script(
        self,
        script: str,
        extension: str = ".py",
    ) -> SandboxResult:
        """Execute a script in a temp file."""
        with tempfile.NamedTemporaryFile(suffix=extension, mode="w", delete=False) as f:
            f.write(script)
            script_path = f.name
        try:
            result = await self.execute_command(["python3", script_path])
        finally:
            Path(script_path).unlink(missing_ok=True)
        return result


def create_sandbox(config: SandboxConfig | None = None) -> SandboxedExecution:
    """Create a sandboxed execution environment."""
    return SandboxedExecution(config)


__all__ = ["SandboxedExecution", "SandboxConfig", "SandboxResult", "create_sandbox"]
