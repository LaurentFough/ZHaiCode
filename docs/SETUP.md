---
title: "ZHaiCode setup"
description: "Portable local runtimes, testing and packaging."
slug: "setup"
author: "LaurentFough"
type: "documentation"
date-created: "2026-09-20"
date-modified: "2026-09-20"
date-published: null
source: "ChatGPT: Multi Agent Setup Suggestions (6ab07655-babc-83e8-9a97-6ee4d9a21b03); current Phase 0/1 handoff"
domain: "software"
url: "https://github.com/LaurentFough/ZHaiCode"
draft: true
tags: ["ZHaiCode", "distributed-agents"]
keywords: ["leases", "recovery", "fencing"]
---

# Setup and development

## Python runtime

Use Python 3.11+ and Git. `make install` is the standard macOS/Linux/Unix path. Equivalent:

```sh
mkdir -p .runtime/tmp
python3 -m venv .venv
PIP_CACHE_DIR="$PWD/.runtime/pip-cache" TMPDIR="$PWD/.runtime/tmp" \
  .venv/bin/python -m pip install -e '.[dev]'
```

Optional uv uses the same local virtual environment:

```sh
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv venv --python python3 .venv
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv pip install --python .venv/bin/python -e '.[dev]'
```

On Windows, prefer WSL for Make parity. PowerShell can use `py -3 -m venv .venv`, then
`.venv\Scripts\python.exe -m pip install -e '.[dev]'` and
`.venv\Scripts\python.exe -m pytest -m 'not postgres'`. Set PIP_CACHE_DIR and TEMP/TMP to
project-local `.runtime` folders before installing. Syslog is optional and platform-dependent.
Never create project runtimes in global directories.

## PostgreSQL

Use an existing dedicated PostgreSQL 15+ instance/database or install a supported PostgreSQL
runtime explicitly. To keep data and sockets in this folder with available PostgreSQL tools:

```sh
mkdir -p .runtime/pgsocket
initdb -D "$PWD/.runtime/pgdata" --auth-local=trust --auth-host=scram-sha-256 --no-clean
pg_ctl -D "$PWD/.runtime/pgdata" -l "$PWD/.runtime/postgres.log" \
  -o "-k $PWD/.runtime/pgsocket -h ''" start
```

This development configuration uses local Unix-socket trust and no TCP listener. Only use
it in a private project directory. Long project paths may exceed the Unix socket path limit;
use a shorter **project-local** socket directory or a protected loopback TCP configuration.
For production choose authenticated access, backups and separate migration/runtime roles.
Do not expose PostgreSQL directly to worker/model credentials or the public Internet.

Set `ZHAICODE_DSN` via your shell or libpq service settings. `agentctl migrate` applies the
idempotent v1 schema. Set `ZHAICODE_TEST_DSN` to a separate test database for `make integration`.
Each integration test creates unique IDs and retains records; tests do not drop databases
or schemas. Stop a local server with `pg_ctl -D "$PWD/.runtime/pgdata" stop` without deleting data.

## Logs and build

`agentctl --log-file .runtime/agentctl.log status TASK-001` writes safe metadata locally;
`--syslog-address /var/run/syslog` is an optional macOS destination, `/dev/log` is common on
Linux. No default syslog dependency. Daemon logging can use stdout; CLI keeps stdout JSON.

`make build` creates wheel/sdist in `dist/`. The wheel includes the SQL migration and JSON
schemas, so installed operation does not depend on a source checkout. `requirements-dev.lock`
records the tested dependency versions; combine it with `pip install -c requirements-dev.lock
-e '.[dev]'` when recreating that environment (platform wheels still vary).

`make release` requires unit/schema checks, a real database integration run and packaging.
It does not publish, tag, merge or delete. Review artifacts and choose explicit version-control
and distribution actions. Git metadata operations may need host sandbox permission.

## References

External references are recorded in [BibTeX](references.bib).
