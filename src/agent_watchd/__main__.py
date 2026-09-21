"""Watchdog policy skeleton. OS hooks and worker supervision are not implemented yet."""

import argparse
import json

from agentd import __version__

POLICY = {
    "lease_ttl_seconds": 1800,
    "heartbeat_seconds": 300,
    "grace_seconds": 600,
    "checkpoint_seconds": 600,
    "idle_seconds": 300,
    "checkpoint_on": ["lease_warning", "agent_exit", "shutdown", "context_pressure"],
}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agent-watchd", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--show-policy", required=True, action="store_true")
    parser.parse_args(argv)
    print(json.dumps(POLICY))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
