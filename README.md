---
title: "ZHaiCode"
description: "Recoverable distributed agent tasks, Phase 0/1."
slug: "readme"
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

# ZHaiCode

ZHaiCode is the project/workspace foundation for recoverable agent work across machines.
The first milestone is: **start a task on machine A, lose its worker/session, and continue
on machine B using durable project artifacts and a handoff, without the old conversation.**

## Phase 0/1 status

Implemented: Python package and three entry points; task/lease transition model;
PostgreSQL operational repository and migration; monotonic fencing generations; seven
JSON Schema protocols and examples; checkpoint/handoff metadata registration; recovery
bundle reads; transactional and protocol tests. Version: `0.1.0`.

`agentd --migrate` bootstraps PostgreSQL. `agentctl` is a trusted local administrative CLI.
`agent-watchd --show-policy` exposes the agreed policy from a separate executable.
The latter two daemon entry points are skeletons, not running network services or supervisors.

**The complete two-machine milestone is not yet implemented.** Git checkpoint capture,
remote verification, worktree restoration, HTTP authentication/transport, and periodic
watchdog hooks remain next. Metadata registration is an internal trusted-service boundary;
it is not proof of an uploaded Git commit. See [the milestone runbook](docs/MILESTONE.md).
No semantic/vector memory or provider integrations are included.

## Architecture contract

- Git owns project artifacts and durable recovery commits/refs.
- PostgreSQL owns tasks, ownership, checkpoints' operational pointers and events.
- Model/agent sessions are ephemeral; structured handoffs carry continuation context.
- Recovery never uses `git stash`.
- `agent-watchd` is a separate process from the worker.
- Completion ends at `READY_FOR_REVIEW`; it never merges automatically.

The original design conversation and explicit handoff are authoritative. See
[SPEC.md](SPEC.md), [ARCHITECTURE.md](ARCHITECTURE.md), [AGENTS.md](AGENTS.md),
[SECURITY.md](SECURITY.md) and [design provenance](docs/DESIGN-AUTHORITY.md).

## Local development

Requires Python 3.11+, Git, and PostgreSQL 15+ for integration tests. On macOS/Linux/Unix:

```sh
make install
make check
make build
.venv/bin/agentctl --help
.venv/bin/agent-watchd --show-policy
```

`make install` creates `.venv`, keeps pip caches and temporary files under `.runtime`, and
installs editable development dependencies. Build prerequisites are included in `dev`.
Run commands from the repository root. No system Python packages are modified.
See [SETUP](docs/SETUP.md) for direct venv, uv, Windows/WSL, PostgreSQL and logging options.

Point `ZHAICODE_DSN` at a dedicated operational database via your shell's secret handling
or libpq service configuration; never commit credentials. Then:

```sh
.venv/bin/agentd --migrate
.venv/bin/agentctl register project examples/project.json
.venv/bin/agentctl register machine examples/machine.json
.venv/bin/agentctl register agent examples/agent.json
.venv/bin/agentctl create TASK-001 ZHaiCode 'Implement recovery'
.venv/bin/agentctl claim TASK-001 --machine-id machine-A --agent-id implementer-A
.venv/bin/agentctl status TASK-001
```

Registration is insert-only and duplicate IDs fail. Do not rerun examples against real
project identifiers. Owner mutations require both IDs and the returned generation.
Renewal uses `renew TASK-001 --machine-id machine-A --agent-id implementer-A --generation 1`.
Do not use example checkpoint SHAs as real evidence.

```sh
#= Set ZHAICODE_TEST_DSN to a separate test database before running integration tests.
make integration
```

Tests retain uniquely named records and project-local files for inspection. No destructive
clean target is provided. `make release` runs checks, requires real PostgreSQL integration
tests, and builds artifacts; publishing/tagging/merging remain explicit actions.

## References

External references are recorded in [BibTeX](docs/references.bib).
