"""JSON CLI. Database access stays on the trusted control-plane host in Phase 0/1."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import psycopg

from agentd import __version__
from agentd.checkpoints.service import create_checkpoint
from agentd.leases.model import ProtocolError, Task, TaskStatus
from agentd.logging_config import configure
from agentd.protocol import task_payload
from agentd.state.postgres import PostgresState


def parser():
    result = argparse.ArgumentParser(prog="agentctl")
    result.add_argument("--version", action="version", version=__version__)
    result.add_argument("--log-file")
    result.add_argument("--syslog-address")
    result.add_argument("--debug", action="store_true")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    register = commands.add_parser("register")
    register.add_argument("kind", choices=["project", "machine", "agent"])
    register.add_argument("file", type=Path)
    create = commands.add_parser("create")
    create.add_argument("task_id")
    create.add_argument("project_id")
    create.add_argument("objective")
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("checkpoint_id")
    checkpoint.add_argument("--repository", type=Path, default=Path.cwd())
    checkpoint.add_argument("--handoff", type=Path, required=True)
    checkpoint.add_argument("--remote", default="origin")
    checkpoint.add_argument("--include-untracked", action="append", default=[])
    checkpoint.add_argument("--quiesced", action="store_true", required=True,
                            help="Confirm all non-cooperating worktree writers are stopped")
    for name in ("status", "recovery", "expire", "claim", "renew", "release", "transition"):
        command = commands.add_parser(name)
        command.add_argument("task_id")
        if name in {"claim", "renew", "release", "transition"}:
            command.add_argument("--machine-id", required=True)
            command.add_argument("--agent-id", required=True)
        if name in {"renew", "release", "transition"}:
            command.add_argument("--generation", type=int, required=True)
        if name in {"claim", "renew"}:
            command.add_argument("--ttl", type=int, default=1800)
        if name == "transition":
            command.add_argument("--status", choices=[s.value for s in TaskStatus], required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        #= Keep stdout as one JSON document for scripts; daemon logging defaults to stdout.
        configure(args.log_file, args.syslog_address, args.debug, stream=sys.stderr)
        state = PostgresState(os.environ.get("ZHAICODE_DSN", ""))
        if args.command == "migrate":
            state.migrate()
            output = {"schema_version": 1}
        elif args.command == "register":
            state.register(args.kind, json.loads(args.file.read_text()))
            output = {"registered": args.kind}
        elif args.command == "create":
            output = task_payload(state.create(Task(args.task_id, args.project_id, args.objective)))
        elif args.command == "status":
            output = task_payload(state.get(args.task_id))
        elif args.command == "recovery":
            output = state.recovery(args.task_id)
        elif args.command == "checkpoint":
            output = create_checkpoint(
                state, args.repository, args.checkpoint_id,
                json.loads(args.handoff.read_text()), remote=args.remote,
                included_untracked=args.include_untracked, quiesced=args.quiesced,
            )
        else:
            kwargs = {
                key: getattr(args, key)
                for key in ("machine_id", "agent_id", "generation", "ttl")
                if hasattr(args, key)
            }
            if args.command == "transition":
                kwargs["status"] = TaskStatus(args.status)
            output = task_payload(state.mutate(args.task_id, args.command, **kwargs))
        print(json.dumps(output))
        return 0
    except (ProtocolError, psycopg.Error, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, ProtocolError) else "OPERATION_FAILED"
        logging.getLogger(__name__).error(
            "command failed code=%s type=%s", code, type(exc).__name__
        )
        print(json.dumps({"error": code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
