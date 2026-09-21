"""Validate portable protocol fixtures and reject incompatible payloads."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agentd.leases.model import ProtocolError
from agentd.protocol import KINDS, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_schemas_and_examples(kind):
    schema = json.loads((ROOT / "schemas" / f"{kind}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    payload = json.loads((ROOT / "examples" / f"{kind}.json").read_text())
    validate(kind, payload)
    for change in ({"schema_version": "99"}, {"unexpected_secret": "never accepted"}):
        with pytest.raises(ProtocolError, match="INVALID_PAYLOAD"):
            validate(kind, {**payload, **change})
    for field in schema["required"]:
        incomplete = deepcopy(payload)
        incomplete.pop(field)
        with pytest.raises(ProtocolError, match="INVALID_PAYLOAD"):
            validate(kind, incomplete)


def test_bad_time_and_generation():
    lease = json.loads((ROOT / "examples/lease.json").read_text())
    for change in (
        {"generation": 0},
        {"generation": True},
        {"expires_at": "yesterday"},
        {"expires_at": "2026-09-21T00:00:00"},
    ):
        with pytest.raises(ProtocolError, match="INVALID_PAYLOAD"):
            validate("lease", {**lease, **change})
