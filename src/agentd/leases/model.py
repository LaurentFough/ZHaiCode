"""Pure lease transitions. Production callers supply PostgreSQL time under a row lock."""

import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

log = logging.getLogger(__name__)
MAX_GENERATION = 2**63 - 1


class ProtocolError(ValueError):
    """Stable machine-readable failure; no database or credential details."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class TaskStatus(StrEnum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    ORPHANED = "ORPHANED"
    RECOVERABLE = "RECOVERABLE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


def identifier(value: str) -> str:
    """Restrict protocol identifiers to portable, ref-safe components."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ProtocolError("INVALID_IDENTIFIER")
    return value


def seconds(value: int) -> int:
    """Bound durations and reject booleans, floats and negative values."""
    if type(value) is not int or not 1 <= value <= 86400:
        raise ProtocolError("INVALID_DURATION")
    return value


def instant(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProtocolError("TIMEZONE_REQUIRED")


@dataclass(frozen=True)
class Lease:
    task_id: str
    machine_id: str
    agent_id: str
    generation: int
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime

    def __post_init__(self):
        for value in (self.task_id, self.machine_id, self.agent_id):
            identifier(value)
        if type(self.generation) is not int or not 1 <= self.generation <= MAX_GENERATION:
            raise ProtocolError("INVALID_GENERATION")
        for value in (self.acquired_at, self.heartbeat_at, self.expires_at):
            instant(value)
        if not self.acquired_at <= self.heartbeat_at < self.expires_at:
            raise ProtocolError("INVALID_LEASE_TIMES")


@dataclass(frozen=True)
class Task:
    task_id: str
    project_id: str
    objective: str
    status: TaskStatus = TaskStatus.QUEUED
    generation: int = 0
    lease: Lease | None = None
    latest_checkpoint: str | None = None

    def __post_init__(self):
        identifier(self.task_id)
        identifier(self.project_id)
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ProtocolError("OBJECTIVE_REQUIRED")
        if type(self.generation) is not int or not 0 <= self.generation <= MAX_GENERATION:
            raise ProtocolError("INVALID_GENERATION")
        if not isinstance(self.status, TaskStatus):
            raise ProtocolError("INVALID_STATUS")
        if self.latest_checkpoint is not None:
            identifier(self.latest_checkpoint)
        if self.lease and (
            self.lease.task_id != self.task_id or self.lease.generation != self.generation
        ):
            raise ProtocolError("LEASE_MISMATCH")


def expire(task: Task, now: datetime) -> Task:
    """Equality is expired; callers persist ORPHANED as an audit event."""
    instant(now)
    if task.lease and task.lease.expires_at <= now:
        status = TaskStatus.RECOVERABLE if task.latest_checkpoint else TaskStatus.RECOVERY_REQUIRED
        return replace(task, lease=None, status=status)
    return task


def claim(task: Task, machine_id: str, agent_id: str, now: datetime, ttl: int = 1800) -> Task:
    """A claim always advances the task's durable fencing generation."""
    seconds(ttl)
    task = expire(task, now)
    if task.lease:
        raise ProtocolError("LEASE_HELD")
    if task.status not in {TaskStatus.QUEUED, TaskStatus.PAUSED, TaskStatus.RECOVERABLE}:
        raise ProtocolError("TASK_NOT_CLAIMABLE")
    if task.generation == MAX_GENERATION:
        raise ProtocolError("GENERATION_EXHAUSTED")
    lease = Lease(
        task.task_id,
        machine_id,
        agent_id,
        task.generation + 1,
        now,
        now,
        now + timedelta(seconds=ttl),
    )
    log.info("claim task=%s generation=%s", task.task_id, lease.generation)
    return replace(task, lease=lease, generation=lease.generation, status=TaskStatus.CLAIMED)


def fence(task: Task, machine_id: str, agent_id: str, generation: int, now: datetime) -> Lease:
    """Validate owner, generation and deadline on every owner-authorized mutation."""
    instant(now)
    lease = task.lease
    if (
        type(generation) is not int
        or lease is None
        or lease.expires_at <= now
        or (lease.machine_id, lease.agent_id, lease.generation)
        != (machine_id, agent_id, generation)
    ):
        raise ProtocolError("STALE_LEASE")
    return lease


def renew(
    task: Task, machine_id: str, agent_id: str, generation: int, now: datetime, ttl: int = 1800
) -> Task:
    seconds(ttl)
    lease = fence(task, machine_id, agent_id, generation, now)
    #= A backwards authority clock must fail closed, not shorten or rewind ownership.
    if now < lease.heartbeat_at:
        raise ProtocolError("CLOCK_REGRESSION")
    return replace(
        task,
        lease=replace(
            lease, heartbeat_at=now, expires_at=max(lease.expires_at, now + timedelta(seconds=ttl))
        ),
    )


def release(task: Task, machine_id: str, agent_id: str, generation: int, now: datetime) -> Task:
    fence(task, machine_id, agent_id, generation, now)
    if not task.latest_checkpoint:
        raise ProtocolError("CHECKPOINT_REQUIRED")
    return replace(task, lease=None, status=TaskStatus.PAUSED)


def transition(
    task: Task, machine_id: str, agent_id: str, generation: int, now: datetime, status: TaskStatus
) -> Task:
    fence(task, machine_id, agent_id, generation, now)
    allowed = {
        TaskStatus.CLAIMED: {TaskStatus.ACTIVE, TaskStatus.BLOCKED},
        TaskStatus.ACTIVE: {TaskStatus.BLOCKED, TaskStatus.READY_FOR_REVIEW},
        TaskStatus.BLOCKED: {TaskStatus.ACTIVE},
    }
    if status not in allowed.get(task.status, set()):
        raise ProtocolError("INVALID_TRANSITION")
    if status == TaskStatus.READY_FOR_REVIEW:
        if not task.latest_checkpoint:
            raise ProtocolError("CHECKPOINT_REQUIRED")
        return replace(task, status=status, lease=None)
    return replace(task, status=status)


def lease_health(lease: Lease, now: datetime, grace: int = 600) -> str:
    """SUSPECT is the warning window before expiry; grace never extends ownership."""
    seconds(grace)
    instant(now)
    if now >= lease.expires_at:
        return "EXPIRED"
    return "SUSPECT" if now >= lease.expires_at - timedelta(seconds=grace) else "VALID"
