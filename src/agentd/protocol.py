"""Versioned wire representations and JSON Schema validation."""

import json
from dataclasses import asdict
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from agentd.leases.model import Lease, ProtocolError, Task, TaskStatus

KINDS = {"task", "lease", "checkpoint", "handoff", "machine", "agent", "project"}


def validate(kind: str, payload: dict) -> dict:
    if kind not in KINDS:
        raise ProtocolError("UNKNOWN_PROTOCOL")
    root = files("agentd").joinpath("schemas")
    if not root.is_dir():
        root = Path(__file__).resolve().parents[2] / "schemas"
    schema = json.loads(root.joinpath(f"{kind}.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    if next(validator.iter_errors(payload), None) is not None:
        raise ProtocolError("INVALID_PAYLOAD")
    return payload


def task_payload(task: Task) -> dict:
    payload = asdict(task)
    payload["schema_version"] = "0.1"
    payload["status"] = task.status.value
    if task.lease:
        payload["lease"]["schema_version"] = "0.1"
        for key in ("acquired_at", "heartbeat_at", "expires_at"):
            payload["lease"][key] = getattr(task.lease, key).isoformat()
    return validate("task", payload)


def task_from_payload(payload: dict) -> Task:
    validate("task", payload)
    data = {key: value for key, value in payload.items() if key != "schema_version"}
    data["status"] = TaskStatus(data["status"])
    if data["lease"]:
        lease = {key: value for key, value in data["lease"].items() if key != "schema_version"}
        for key in ("acquired_at", "heartbeat_at", "expires_at"):
            lease[key] = datetime.fromisoformat(lease[key])
        data["lease"] = Lease(**lease)
    return Task(**data)
