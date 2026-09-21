"""Service bootstrap; network transport is intentionally not implemented in Phase 0/1."""

import argparse
import logging
import os

import psycopg

from agentd import __version__
from agentd.leases.model import ProtocolError
from agentd.logging_config import configure
from agentd.state.postgres import PostgresState


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agentd", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--migrate", action="store_true", required=True)
    parser.add_argument("--log-file")
    parser.add_argument("--syslog-address")
    args = parser.parse_args(argv)
    try:
        configure(args.log_file, args.syslog_address)
        PostgresState(os.environ.get("ZHAICODE_DSN", "")).migrate()
        return 0
    except (ProtocolError, psycopg.Error, ValueError, OSError) as exc:
        logging.getLogger(__name__).error("bootstrap failed type=%s", type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
