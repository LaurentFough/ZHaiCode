"""Lease boundary and stale-worker safety tests, using a deterministic authority clock."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from agentd.leases.model import (
    MAX_GENERATION,
    ProtocolError,
    Task,
    TaskStatus,
    claim,
    expire,
    fence,
    lease_health,
    release,
    renew,
    transition,
)
from agentd.protocol import task_from_payload, task_payload

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def owned():
    return claim(Task("TASK-1", "ZHaiCode", "Implement recovery"), "A", "worker-A", NOW)


def test_wire_roundtrip():
    assert task_from_payload(task_payload(owned())) == owned()


def test_no_steal_and_no_renew_after_expiry():
    task = owned()
    with pytest.raises(ProtocolError, match="LEASE_HELD"):
        claim(task, "B", "worker-B", NOW)
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        renew(task, "A", "worker-A", 1, task.lease.expires_at)


def test_recover_generation_fences_old_machine():
    task = replace(owned(), latest_checkpoint="CP-1")
    recovered = claim(task, "B", "worker-B", task.lease.expires_at)
    assert recovered.generation == 2
    for operation in (renew, release):
        with pytest.raises(ProtocolError, match="STALE_LEASE"):
            operation(recovered, "A", "worker-A", 1, recovered.lease.acquired_at)
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        transition(recovered, "A", "worker-A", 1, recovered.lease.acquired_at, TaskStatus.ACTIVE)


def test_expiry_without_checkpoint_needs_intervention():
    task = owned()
    expired = expire(task, task.lease.expires_at)
    assert expired.status == TaskStatus.RECOVERY_REQUIRED
    with pytest.raises(ProtocolError, match="TASK_NOT_CLAIMABLE"):
        claim(expired, "B", "worker-B", task.lease.expires_at)


def test_release_reacquire_never_resets_generation():
    task = replace(owned(), latest_checkpoint="CP-1")
    task = release(task, "A", "worker-A", 1, NOW)
    assert task.generation == 1
    assert claim(task, "A", "worker-A", NOW).generation == 2


@pytest.mark.parametrize(
    "machine,agent,generation",
    [("B", "worker-A", 1), ("A", "worker-B", 1), ("A", "worker-A", 0), ("A", "worker-A", True)],
)
def test_fence_checks_complete_identity(machine, agent, generation):
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        fence(owned(), machine, agent, generation, NOW)


def test_warning_does_not_extend_ownership():
    task = owned()
    assert lease_health(task.lease, NOW) == "VALID"
    assert lease_health(task.lease, NOW + timedelta(seconds=1200)) == "SUSPECT"
    assert lease_health(task.lease, NOW + timedelta(seconds=1800)) == "EXPIRED"
    assert renew(task, "A", "worker-A", 1, NOW + timedelta(seconds=1300)).generation == 1


@pytest.mark.parametrize("ttl", [0, -1, True, 1.5, 86401])
def test_invalid_duration(ttl):
    with pytest.raises(ProtocolError, match="INVALID_DURATION"):
        claim(Task("T", "P", "Objective"), "A", "worker", NOW, ttl)


def test_clock_and_overflow_fail_closed():
    with pytest.raises(ProtocolError, match="TIMEZONE_REQUIRED"):
        expire(owned(), NOW.replace(tzinfo=None))
    with pytest.raises(ProtocolError, match="CLOCK_REGRESSION"):
        renew(owned(), "A", "worker-A", 1, NOW - timedelta(seconds=1))
    with pytest.raises(ProtocolError, match="GENERATION_EXHAUSTED"):
        claim(Task("T", "P", "Objective", generation=MAX_GENERATION), "A", "worker", NOW)


def test_review_releases_lease_but_does_not_merge():
    task = transition(owned(), "A", "worker-A", 1, NOW, TaskStatus.ACTIVE)
    with pytest.raises(ProtocolError, match="CHECKPOINT_REQUIRED"):
        transition(task, "A", "worker-A", 1, NOW, TaskStatus.READY_FOR_REVIEW)
    ready = transition(
        replace(task, latest_checkpoint="CP-1"),
        "A",
        "worker-A",
        1,
        NOW,
        TaskStatus.READY_FOR_REVIEW,
    )
    assert ready.lease is None
    assert ready.status == TaskStatus.READY_FOR_REVIEW
    with pytest.raises(ProtocolError, match="TASK_NOT_CLAIMABLE"):
        claim(ready, "B", "worker-B", NOW)


def test_unsafe_identifier_and_invalid_transition():
    with pytest.raises(ProtocolError, match="INVALID_IDENTIFIER"):
        Task("../bad", "P", "Objective")
    with pytest.raises(ProtocolError, match="INVALID_TRANSITION"):
        transition(owned(), "A", "worker-A", 1, NOW, TaskStatus.QUEUED)
