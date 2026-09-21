"""Regenerate protocol v0.1 schemas and valid examples; run from the repository root."""

import json
from pathlib import Path

VERSION = {"const": "0.1"}
ID = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"}
TEXT = {"type": "string", "minLength": 1}
TIME = {"type": "string", "format": "date-time"}
GENERATION = {"type": "integer", "minimum": 1, "maximum": 9223372036854775807}
STRINGS = {"type": "array", "items": TEXT}
SHA = {"type": "string", "pattern": "^([0-9a-f]{40}|[0-9a-f]{64})$"}


def obj(properties):
    """Closed objects catch spelling errors and accidental credential fields."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


lease = obj(
    dict(
        schema_version=VERSION,
        task_id=ID,
        machine_id=ID,
        agent_id=ID,
        generation=GENERATION,
        acquired_at=TIME,
        heartbeat_at=TIME,
        expires_at=TIME,
    )
)
schemas = {
    "lease": lease,
    "task": obj(
        dict(
            schema_version=VERSION,
            task_id=ID,
            project_id=ID,
            objective=TEXT,
            status={
                "enum": [
                    "QUEUED",
                    "CLAIMED",
                    "ACTIVE",
                    "BLOCKED",
                    "PAUSED",
                    "READY_FOR_REVIEW",
                    "ORPHANED",
                    "RECOVERABLE",
                    "RECOVERY_REQUIRED",
                ]
            },
            generation={**GENERATION, "minimum": 0},
            lease={"anyOf": [lease, {"type": "null"}]},
            latest_checkpoint={"anyOf": [ID, {"type": "null"}]},
        )
    ),
    "project": obj(
        dict(
            schema_version=VERSION,
            project_id=ID,
            name=TEXT,
            repository_url=TEXT,
            default_branch=TEXT,
            instructions={"type": "array", "items": TEXT, "minItems": 1},
        )
    ),
    "machine": obj(
        dict(schema_version=VERSION, machine_id=ID, os=TEXT, arch=TEXT, capabilities=STRINGS)
    ),
    "agent": obj(dict(schema_version=VERSION, agent_id=ID, machine_id=ID, role=TEXT, runtime=TEXT)),
    "checkpoint": obj(
        dict(
            schema_version=VERSION,
            checkpoint_id=ID,
            task_id=ID,
            generation=GENERATION,
            commit=SHA,
            base_commit=SHA,
            ref={
                "type": "string",
                "pattern": "^refs/agents/[A-Za-z0-9_-]+/checkpoints/[1-9][0-9]*/[A-Za-z0-9_-]+$",
            },
            handoff_id=ID,
            created_at=TIME,
            durability={"const": "REMOTE_VERIFIED"},
        )
    ),
    "handoff": obj(
        dict(
            schema_version=VERSION,
            handoff_id=ID,
            task_id=ID,
            project_id=ID,
            generation=GENERATION,
            from_machine=ID,
            from_agent=ID,
            objective=TEXT,
            completed=STRINGS,
            working_on=STRINGS,
            remaining=STRINGS,
            decisions=STRINGS,
            issues=STRINGS,
            files=STRINGS,
            context=STRINGS,
            next_action=TEXT,
            commands=STRINGS,
            validation=obj(dict(status={"enum": ["passed", "failed", "not_run"]}, summary=TEXT)),
        )
    ),
}

examples = {
    "project": dict(
        project_id="ZHaiCode",
        name="ZHaiCode",
        repository_url="https://github.com/LaurentFough/ZHaiCode.git",
        default_branch="main",
        instructions=["AGENTS.md", "SPEC.md"],
    ),
    "machine": dict(machine_id="machine-A", os="linux", arch="amd64", capabilities=["python"]),
    "agent": dict(
        agent_id="implementer-A", machine_id="machine-A", role="implementer", runtime="manual"
    ),
    "lease": dict(
        task_id="TASK-001",
        machine_id="machine-A",
        agent_id="implementer-A",
        generation=1,
        acquired_at="2026-09-21T00:00:00Z",
        heartbeat_at="2026-09-21T00:00:00Z",
        expires_at="2026-09-21T00:30:00Z",
    ),
    "task": dict(
        task_id="TASK-001",
        project_id="ZHaiCode",
        objective="Implement recovery",
        status="QUEUED",
        generation=0,
        lease=None,
        latest_checkpoint=None,
    ),
    "checkpoint": dict(
        checkpoint_id="CP-001",
        task_id="TASK-001",
        generation=1,
        commit="a" * 40,
        base_commit="b" * 40,
        ref="refs/agents/TASK-001/checkpoints/1/CP-001",
        handoff_id="HO-001",
        created_at="2026-09-21T00:10:00Z",
        durability="REMOTE_VERIFIED",
    ),
    "handoff": dict(
        handoff_id="HO-001",
        task_id="TASK-001",
        project_id="ZHaiCode",
        generation=1,
        from_machine="machine-A",
        from_agent="implementer-A",
        objective="Implement recovery",
        completed=["Lease model"],
        working_on=["Recovery test"],
        remaining=["Transport"],
        decisions=[],
        issues=[],
        files=["SPEC.md"],
        context=["AGENTS.md", "SPEC.md"],
        next_action="Run the recovery integration test",
        commands=["make check"],
        validation=dict(status="not_run", summary="Initial example only"),
    ),
}

if __name__ == "__main__":
    for kind, schema in schemas.items():
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://github.com/LaurentFough/ZHaiCode/schemas/{kind}.schema.json",
            "title": f"ZHaiCode {kind} v0.1",
            **schema,
        }
        Path(f"schemas/{kind}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
        Path(f"examples/{kind}.json").write_text(
            json.dumps({"schema_version": "0.1", **examples[kind]}, indent=2) + "\n"
        )
