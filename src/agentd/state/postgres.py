"""PostgreSQL repository; each mutation locks one task and uses database time."""

import logging
from dataclasses import replace
from importlib.resources import files

import psycopg
from psycopg.types.json import Jsonb

from agentd.leases import model
from agentd.protocol import task_from_payload, task_payload, validate

log = logging.getLogger(__name__)


class PostgresState:
    """Trusted control-plane library. Do not distribute its database credentials to workers."""

    def __init__(self, dsn: str):
        if not dsn:
            raise model.ProtocolError("DATABASE_REQUIRED")
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(
            self.dsn, connect_timeout=5, options="-c statement_timeout=10000 -c lock_timeout=5000"
        )

    def migrate(self):
        with self.connect() as conn:
            #= Serialize bootstrap so concurrent startup cannot race CREATE TABLE.
            conn.execute("SELECT pg_advisory_xact_lock(9021001)")
            conn.execute(files("agentd.migrations").joinpath("001_initial.sql").read_text())
        log.info("migration applied version=1")

    def register(self, kind: str, payload: dict):
        validate(kind, payload)
        with self.connect() as conn:
            if kind == "project":
                conn.execute(
                    "INSERT INTO projects VALUES (%s, %s)", (payload["project_id"], Jsonb(payload))
                )
            elif kind == "machine":
                conn.execute(
                    "INSERT INTO machines VALUES (%s, %s)", (payload["machine_id"], Jsonb(payload))
                )
            elif kind == "agent":
                conn.execute(
                    "INSERT INTO agents VALUES (%s, %s, %s)",
                    (payload["agent_id"], payload["machine_id"], Jsonb(payload)),
                )
            else:
                raise model.ProtocolError("INVALID_REGISTRATION")
        log.info("registered kind=%s", kind)

    def create(self, task: model.Task):
        if (
            task.generation != 0
            or task.lease
            or task.status != model.TaskStatus.QUEUED
            or task.latest_checkpoint
        ):
            raise model.ProtocolError("INVALID_NEW_TASK")
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (%s, %s, %s, %s)",
                (task.task_id, task.project_id, task.generation, Jsonb(task_payload(task))),
            )
            self._event(conn, task, "CREATED")
        return task

    def get(self, task_id: str):
        model.identifier(task_id)
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM tasks WHERE task_id=%s", (task_id,)).fetchone()
            if not row:
                raise model.ProtocolError("TASK_NOT_FOUND")
            return task_from_payload(row[0])

    @staticmethod
    def _event(conn, task, kind):
        conn.execute(
            "INSERT INTO events(task_id, generation, kind) VALUES (%s, %s, %s)",
            (task.task_id, task.generation, kind),
        )

    def mutate(self, task_id: str, operation: str, **kwargs):
        """No caller-supplied clock; fencing and writes share a transaction."""
        operations = {
            "claim": model.claim,
            "renew": model.renew,
            "release": model.release,
            "transition": model.transition,
            "expire": model.expire,
        }
        if operation not in operations:
            raise model.ProtocolError("UNKNOWN_OPERATION")
        model.identifier(task_id)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM tasks WHERE task_id=%s FOR UPDATE", (task_id,)
            ).fetchone()
            if not row:
                raise model.ProtocolError("TASK_NOT_FOUND")
            task = task_from_payload(row[0])
            #= Read time AFTER waiting for the lock; transaction start time could be stale.
            now = conn.execute("SELECT clock_timestamp()").fetchone()[0]
            if operation == "claim":
                owner = conn.execute(
                    "SELECT machine_id FROM agents WHERE agent_id=%s", (kwargs.get("agent_id"),)
                ).fetchone()
                if not owner or owner[0] != kwargs.get("machine_id"):
                    raise model.ProtocolError("OWNER_NOT_REGISTERED")
            if operation in {"expire", "claim"} and task.lease and task.lease.expires_at <= now:
                self._event(conn, task, "ORPHANED")
                self._event(conn, task, model.expire(task, now).status.value)
            updated = operations[operation](task, now=now, **kwargs)
            if operation == "transition" and updated.status == model.TaskStatus.READY_FOR_REVIEW:
                evidence = conn.execute(
                    "SELECT generation, handoff FROM checkpoints WHERE checkpoint_id=%s",
                    (task.latest_checkpoint,),
                ).fetchone()
                if (
                    not evidence
                    or evidence[0] != task.generation
                    or evidence[1]["validation"]["status"] != "passed"
                ):
                    raise model.ProtocolError("VALIDATED_CHECKPOINT_REQUIRED")
            conn.execute(
                "UPDATE tasks SET generation=%s, payload=%s WHERE task_id=%s",
                (updated.generation, Jsonb(task_payload(updated)), task_id),
            )
            if updated != task:
                self._event(conn, updated, operation.upper())
        log.info(
            "task mutation task=%s operation=%s generation=%s",
            task_id,
            operation,
            updated.generation,
        )
        return updated

    def authorize_checkpoint(self, handoff: dict) -> dict:
        """Fence before Git side effects and return the registered project destination."""
        validate("handoff", handoff)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM tasks WHERE task_id=%s FOR UPDATE", (handoff["task_id"],)
            ).fetchone()
            if not row:
                raise model.ProtocolError("TASK_NOT_FOUND")
            task = task_from_payload(row[0])
            now = conn.execute("SELECT clock_timestamp()").fetchone()[0]
            model.fence(task, handoff["from_machine"], handoff["from_agent"],
                        handoff["generation"], now)
            if handoff["project_id"] != task.project_id or handoff["objective"] != task.objective:
                raise model.ProtocolError("HANDOFF_MISMATCH")
            return conn.execute("SELECT payload FROM projects WHERE project_id=%s",
                                (task.project_id,)).fetchone()[0]

    def checkpoint(self, checkpoint: dict, handoff: dict, machine_id: str, agent_id: str):
        """Register a remotely verified commit. Caller is the trusted checkpoint publisher."""
        validate("checkpoint", checkpoint)
        validate("handoff", handoff)
        if (
            checkpoint["task_id"] != handoff["task_id"]
            or checkpoint["handoff_id"] != handoff["handoff_id"]
            or checkpoint["generation"] != handoff["generation"]
            or handoff["from_machine"] != machine_id
            or handoff["from_agent"] != agent_id
        ):
            raise model.ProtocolError("HANDOFF_MISMATCH")
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM tasks WHERE task_id=%s FOR UPDATE", (checkpoint["task_id"],)
            ).fetchone()
            if not row:
                raise model.ProtocolError("TASK_NOT_FOUND")
            task = task_from_payload(row[0])
            now = conn.execute("SELECT clock_timestamp()").fetchone()[0]
            model.fence(task, machine_id, agent_id, checkpoint["generation"], now)
            if handoff["project_id"] != task.project_id or handoff["objective"] != task.objective:
                raise model.ProtocolError("HANDOFF_MISMATCH")
            expected_ref = (
                f"refs/agents/{task.task_id}/checkpoints/"
                f"{task.generation}/{checkpoint['checkpoint_id']}"
            )
            if checkpoint["ref"] != expected_ref:
                raise model.ProtocolError("CHECKPOINT_REF_MISMATCH")
            existing = conn.execute(
                "SELECT payload, handoff FROM checkpoints WHERE checkpoint_id=%s",
                (checkpoint["checkpoint_id"],),
            ).fetchone()
            if existing:
                if existing != (checkpoint, handoff):
                    raise model.ProtocolError("CHECKPOINT_CONFLICT")
                #= A retry must not rewind the latest pointer over a newer checkpoint.
                return task
            conn.execute(
                "INSERT INTO checkpoints VALUES (%s, %s, %s, %s, %s)",
                (
                    checkpoint["checkpoint_id"],
                    task.task_id,
                    task.generation,
                    Jsonb(checkpoint),
                    Jsonb(handoff),
                ),
            )
            updated = replace(task, latest_checkpoint=checkpoint["checkpoint_id"])
            conn.execute(
                "UPDATE tasks SET payload=%s WHERE task_id=%s",
                (Jsonb(task_payload(updated)), task.task_id),
            )
            self._event(conn, updated, "CHECKPOINT")
        return updated

    def recovery(self, task_id: str):
        """Read a consistent task + durable handoff bundle, independent of session history."""
        model.identifier(task_id)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT t.payload, c.payload, c.handoff FROM tasks t LEFT JOIN checkpoints c "
                "ON c.checkpoint_id=t.payload->>'latest_checkpoint' WHERE t.task_id=%s",
                (task_id,),
            ).fetchone()
            if not row:
                raise model.ProtocolError("TASK_NOT_FOUND")
            if row[1] is None:
                raise model.ProtocolError("CHECKPOINT_REQUIRED")
            return {"task": row[0], "checkpoint": row[1], "handoff": row[2]}
