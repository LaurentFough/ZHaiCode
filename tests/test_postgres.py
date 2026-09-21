"""Real PostgreSQL transactions. Retain uniquely named test records for inspection."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from agentd.leases.model import ProtocolError, Task, TaskStatus
from agentd.protocol import task_payload
from agentd.state.postgres import PostgresState

pytestmark = pytest.mark.postgres
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def state():
    dsn = os.environ.get("ZHAICODE_TEST_DSN")
    if not dsn:
        pytest.skip("Set ZHAICODE_TEST_DSN; pure tests do not prove database concurrency")
    store = PostgresState(dsn)
    store.migrate()
    return store


@pytest.fixture
def task(state):
    prefix = uuid4().hex[:12]
    state.register(
        "project",
        dict(
            schema_version="0.1",
            project_id=prefix,
            name="ZHaiCode",
            repository_url="example",
            default_branch="main",
            instructions=["AGENTS.md"],
        ),
    )
    for machine in ("A", "B"):
        machine_id = prefix + machine
        state.register(
            "machine",
            dict(
                schema_version="0.1",
                machine_id=machine_id,
                os="linux",
                arch="amd64",
                capabilities=[],
            ),
        )
        state.register(
            "agent",
            dict(
                schema_version="0.1",
                agent_id=machine_id,
                machine_id=machine_id,
                role="implementer",
                runtime="test",
            ),
        )
    return state.create(Task(prefix, prefix, "Implement recovery"))


def owner(task, machine="A", generation=1):
    return dict(
        machine_id=task.task_id + machine, agent_id=task.task_id + machine, generation=generation
    )


def claim_task(state, task, machine="A"):
    identity = owner(task, machine)
    identity.pop("generation")
    return state.mutate(task.task_id, "claim", **identity)


def publish_fixture(state, task, passed=False):
    checkpoint = json.loads((ROOT / "examples/checkpoint.json").read_text())
    handoff = json.loads((ROOT / "examples/handoff.json").read_text())
    checkpoint.update(
        checkpoint_id="CP-" + task.task_id,
        task_id=task.task_id,
        handoff_id="HO-" + task.task_id,
        generation=task.generation,
        ref=f"refs/agents/{task.task_id}/checkpoints/{task.generation}/CP-{task.task_id}",
    )
    handoff.update(
        handoff_id=checkpoint["handoff_id"],
        task_id=task.task_id,
        project_id=task.project_id,
        generation=task.generation,
        from_machine=task.lease.machine_id,
        from_agent=task.lease.agent_id,
    )
    if passed:
        handoff["validation"] = {"status": "passed", "summary": "Tests passed"}
    state.checkpoint(checkpoint, handoff, task.lease.machine_id, task.lease.agent_id)
    return checkpoint, handoff


def force_expiry(state, task):
    #= Test-only deadline adjustment avoids sleeps and never exists in the production API.
    payload = task_payload(state.get(task.task_id))
    with state.connect() as conn:
        now = conn.execute("SELECT clock_timestamp()").fetchone()[0]
        payload["lease"]["acquired_at"] = (now - timedelta(seconds=100)).isoformat()
        payload["lease"]["heartbeat_at"] = (now - timedelta(seconds=90)).isoformat()
        payload["lease"]["expires_at"] = (now - timedelta(seconds=1)).isoformat()
        conn.execute("UPDATE tasks SET payload=%s WHERE task_id=%s", (Jsonb(payload), task.task_id))


def test_simultaneous_claim_has_one_winner(state, task):
    barrier = Barrier(2)

    def compete(machine):
        barrier.wait()
        try:
            return claim_task(PostgresState(state.dsn), task, machine).generation
        except ProtocolError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, ("A", "B")))
    assert sorted(map(str, results)) == ["1", "LEASE_HELD"]


def test_session_loss_recovery_and_stale_mutations(state, task):
    claimed = claim_task(state, task)
    checkpoint, handoff = publish_fixture(state, claimed)
    force_expiry(state, task)
    fresh_service = PostgresState(state.dsn)
    resumed = claim_task(fresh_service, task, "B")
    assert resumed.generation == 2
    bundle = fresh_service.recovery(task.task_id)
    assert bundle["handoff"] == handoff
    assert bundle["checkpoint"] == checkpoint
    for operation in ("renew", "release"):
        with pytest.raises(ProtocolError, match="STALE_LEASE"):
            state.mutate(task.task_id, operation, **owner(task))
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        state.checkpoint(
            checkpoint, handoff, **{k: v for k, v in owner(task).items() if k != "generation"}
        )
    with state.connect() as conn:
        events = [
            row[0]
            for row in conn.execute(
                "SELECT kind FROM events WHERE task_id=%s ORDER BY event_id", (task.task_id,)
            )
        ]
    assert "ORPHANED" in events and "RECOVERABLE" in events


def test_uncheckpointed_task_cannot_silently_resume(state, task):
    claim_task(state, task)
    force_expiry(state, task)
    expired = state.mutate(task.task_id, "expire")
    assert expired.status == TaskStatus.RECOVERY_REQUIRED
    with pytest.raises(ProtocolError, match="TASK_NOT_CLAIMABLE"):
        claim_task(state, task, "B")


def test_release_keeps_counter_and_review_requires_validation(state, task):
    claimed = claim_task(state, task)
    publish_fixture(state, claimed)
    state.mutate(task.task_id, "transition", status=TaskStatus.ACTIVE, **owner(task))
    with pytest.raises(ProtocolError, match="VALIDATED_CHECKPOINT_REQUIRED"):
        state.mutate(task.task_id, "transition", status=TaskStatus.READY_FOR_REVIEW, **owner(task))
    assert state.get(task.task_id).status == TaskStatus.ACTIVE
    state.mutate(task.task_id, "release", **owner(task))
    assert claim_task(state, task, "B").generation == 2


def test_complete_stops_at_review(state, task):
    claimed = claim_task(state, task)
    publish_fixture(state, claimed, passed=True)
    state.mutate(task.task_id, "transition", status=TaskStatus.ACTIVE, **owner(task))
    ready = state.mutate(
        task.task_id, "transition", status=TaskStatus.READY_FOR_REVIEW, **owner(task)
    )
    assert ready.status == TaskStatus.READY_FOR_REVIEW
    assert ready.lease is None


def test_registration_and_checkpoint_mismatch_rollback(state, task):
    with pytest.raises(ProtocolError, match="OWNER_NOT_REGISTERED"):
        state.mutate(task.task_id, "claim", machine_id="missing", agent_id="missing")
    assert state.get(task.task_id).generation == 0
    claimed = claim_task(state, task)
    checkpoint, handoff = publish_fixture(state, claimed)
    handoff["task_id"] = "different"
    with pytest.raises(ProtocolError, match="HANDOFF_MISMATCH"):
        state.checkpoint(checkpoint, handoff, claimed.lease.machine_id, claimed.lease.agent_id)


def test_renew_persists_deadline_and_migration_preserves_generation(state, task):
    claimed = claim_task(state, task)
    renewed = state.mutate(task.task_id, "renew", ttl=3600, **owner(task))
    assert renewed.generation == claimed.generation
    assert renewed.lease.expires_at > claimed.lease.expires_at
    state.migrate()
    assert state.get(task.task_id) == renewed


def test_expired_owner_cannot_write_before_replacement(state, task):
    claimed = claim_task(state, task)
    checkpoint, handoff = publish_fixture(state, claimed)
    force_expiry(state, task)
    for operation in ("renew", "release"):
        with pytest.raises(ProtocolError, match="STALE_LEASE"):
            state.mutate(task.task_id, operation, **owner(task))
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        state.mutate(task.task_id, "transition", status=TaskStatus.ACTIVE, **owner(task))
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        state.checkpoint(checkpoint, handoff, claimed.lease.machine_id, claimed.lease.agent_id)
    assert state.get(task.task_id).generation == 1


def test_previous_generation_validation_cannot_complete_new_work(state, task):
    claimed = claim_task(state, task)
    publish_fixture(state, claimed, passed=True)
    state.mutate(task.task_id, "release", **owner(task))
    claim_task(state, task, "B")
    state.mutate(
        task.task_id, "transition", status=TaskStatus.ACTIVE, **owner(task, "B", generation=2)
    )
    with pytest.raises(ProtocolError, match="VALIDATED_CHECKPOINT_REQUIRED"):
        state.mutate(
            task.task_id,
            "transition",
            status=TaskStatus.READY_FOR_REVIEW,
            **owner(task, "B", generation=2),
        )
