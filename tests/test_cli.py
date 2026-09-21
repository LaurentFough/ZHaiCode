"""Entrypoint contracts and safe logging destinations."""

import json

from agent_watchd.__main__ import main as watch_main
from agentctl.__main__ import main
from agentd.logging_config import configure


def test_no_database_is_an_explicit_error(monkeypatch, capsys):
    monkeypatch.delenv("ZHAICODE_DSN", raising=False)
    assert main(["status", "TASK-1"]) == 1
    result = capsys.readouterr()
    assert not result.out
    assert '"error": "DATABASE_REQUIRED"' in result.err


def test_watchdog_exposes_design_defaults(capsys):
    assert watch_main(["--show-policy"]) == 0
    policy = json.loads(capsys.readouterr().out)
    assert policy["heartbeat_seconds"] < policy["lease_ttl_seconds"]
    assert policy["checkpoint_seconds"] == 600


def test_log_file(workspace):
    import logging

    configure(str(workspace / "test.log"))
    logging.getLogger("test").info("safe metadata")
    assert "safe metadata" in (workspace / "test.log").read_text()
    #= Restore a live stream after pytest's per-test capture stream goes away.
    configure()
