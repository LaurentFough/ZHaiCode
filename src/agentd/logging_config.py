"""Opt-in stdout/file/syslog logging. Never log DSNs or handoff bodies."""

import logging
import sys
from logging.handlers import SysLogHandler
from pathlib import Path


def configure(
    log_file: str | None = None, syslog_address: str | None = None, debug: bool = False, stream=None
):
    handlers = [logging.StreamHandler(stream or sys.stdout)]
    if log_file:
        path = Path(log_file).resolve()
        if not path.is_relative_to(Path.cwd().resolve()):
            raise ValueError("log file must be inside the current project folder")
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    if syslog_address:
        handlers.append(SysLogHandler(address=syslog_address))
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )
