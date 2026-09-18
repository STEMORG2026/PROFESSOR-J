"""Scheduler — cron-like task scheduling.

Modeled on Hermes `cron/`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """A scheduled job."""

    job_id: str
    name: str
    schedule: str  # cron expression or interval
    task: str  # task description to execute
    agent: str  # agent to route to
    status: str = "pending"  # pending, running, completed, failed
    last_run: str | None = None
    next_run: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Scheduler:
    """Schedule and manage recurring tasks."""

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._running: dict[str, asyncio.Task[object]] = {}

    def add_job(
        self,
        name: str,
        schedule: str,
        task: str,
        agent: str,
        **metadata: Any,
    ) -> ScheduledJob:
        """Add a scheduled job."""
        job_id = str(uuid.uuid4())
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            schedule=schedule,
            task=task,
            agent=agent,
            next_run=datetime.now(UTC).isoformat(),
            metadata=metadata,
        )
        self._jobs[job_id] = job
        logger.info("Added scheduled job: %s", name)
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def list_jobs(self) -> list[ScheduledJob]:
        """List all scheduled jobs."""
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> ScheduledJob | None:
        """Get a specific job."""
        return self._jobs.get(job_id)

    async def execute_job(self, job_id: str) -> bool:
        """Execute a job immediately."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = "running"
        job.last_run = datetime.now(UTC).isoformat()
        # In production, this would route to the appropriate agent
        logger.info("Executing job: %s → agent: %s", job.name, job.agent)
        job.status = "completed"
        return True


def create_scheduler() -> Scheduler:
    """Create a scheduler."""
    return Scheduler()


__all__ = ["Scheduler", "ScheduledJob", "create_scheduler"]
