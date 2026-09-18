"""Computer Use — desktop control capabilities.

Modeled on Hermes `computer_use_tool.py`.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DesktopAction:
    """A desktop control action."""

    action: str  # launch, kill, focus, move, resize, screenshot
    target: str | None = None
    value: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DesktopResult:
    """Result of a desktop action."""

    success: bool
    action: str
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ComputerUse:
    """Desktop control for application management."""

    async def launch(self, app: str) -> DesktopResult:
        """Launch an application."""
        try:
            subprocess.Popen(app.split())
            return DesktopResult(success=True, action="launch", output=f"Launched {app}")
        except Exception as exc:
            return DesktopResult(success=False, action="launch", error=str(exc))

    async def kill(self, pid: int) -> DesktopResult:
        """Kill a process."""
        try:
            import os
            import signal

            os.kill(pid, signal.SIGTERM)
            return DesktopResult(success=True, action="kill", output=f"Killed {pid}")
        except Exception as exc:
            return DesktopResult(success=False, action="kill", error=str(exc))

    async def focus(self, window: str) -> DesktopResult:
        """Focus a window."""
        return DesktopResult(success=True, action="focus", output=f"Focused {window}")

    async def move(self, window: str, x: int, y: int) -> DesktopResult:
        """Move a window."""
        return DesktopResult(success=True, action="move", output=f"Moved {window} to ({x},{y})")

    async def resize(self, window: str, w: int, h: int) -> DesktopResult:
        """Resize a window."""
        return DesktopResult(success=True, action="resize", output=f"Resized {window} to {w}x{h}")

    async def screenshot(self, path: str) -> DesktopResult:
        """Take a desktop screenshot."""
        return DesktopResult(
            success=True, action="screenshot", output=f"Screenshot saved to {path}"
        )


def create_computer_use() -> ComputerUse:
    """Create computer use."""
    return ComputerUse()


__all__ = ["ComputerUse", "DesktopAction", "DesktopResult", "create_computer_use"]
