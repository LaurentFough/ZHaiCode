---
title: "ZHaiCode verification"
description: "Verified behavior, environment and remaining milestone work."
slug: "verification"
author: "LaurentFough"
type: "verification-report"
date-created: "2026-09-20"
date-modified: "2026-09-20"
date-published: null
source: "Local bootstrap validation on macOS arm64"
domain: "software"
url: "https://github.com/LaurentFough/ZHaiCode"
draft: true
tags: ["ZHaiCode", "testing"]
keywords: ["PostgreSQL", "fencing", "recovery"]
---

# ZHaiCode verification

## Phase 0/1 baseline

`make release` passed on macOS arm64 with Python 3.14.7 and a project-local PostgreSQL 16.2
instance. No externally managed database was used. Test dependencies are recorded in
requirements-dev.lock. CI is configured for Python 3.11 and 3.14 against PostgreSQL 16;
local verification does not establish results for the hosted CI runs or other platforms.

| Check | Result |
|---|---|
| Ruff source/test/script lint | Passed |
| Unit, schema and CLI tests | 29 passed |
| Real PostgreSQL integration tests | 9 passed |
| Wheel and source distribution | Built successfully |
| Wheel schemas/migration inventory | Seven schemas and SQL migration present |
| Isolated wheel import and schema validation | Passed |
| Git whitespace check | Passed |

Integration coverage includes simultaneous claims; expiry and fresh-service recovery of
metadata; stale renewal, release, transition and checkpoint rejection; missing checkpoints;
renewal persistence; repeat migration preserving generations; review validation and rollback;
and prevention of reusing old-generation validation after reclaim.

The first schema-test run found that date-time format checks require an optional validator;
rfc3339-validator is now an explicit runtime dependency and invalid timestamps are rejected.
PostgreSQL initialization and socket connections required host sandbox permission.

At this baseline, checkpoint SHAs in metadata tests were fixtures; the Git engine,
authenticated transport and running watchdog were unimplemented. The v0.2.0 results below
supersede the Git checkpoint portion of that baseline. See [MILESTONE.md](MILESTONE.md) for acceptance steps.

The test database and test files are retained under `.runtime` for inspection. The temporary
PostgreSQL service is stopped after verification. Restart only when needed; retain the
project's consent/ZIP-backup policy before deleting artifacts.

## Checkpoint engine v0.2.0 verification

After the Phase 0/1 baseline, the Git engine passed **63 tests**: 51 unit/Git/schema/CLI
checks and 12 PostgreSQL integration checks. Ruff and Git whitespace checks passed. Wheel
and source distribution builds succeeded; an isolated wheel import confirms version 0.2.0,
checkpoint service/CLI modules, all seven schemas and the SQL migration are packaged.

Real Git tests use retained bare remotes and independent clone/worktree directories. They
verify raw tracked/selected-untracked content, executable modes, binary bytes, original
index/branch preservation, handoff recovery, create-only remote races, conflicting IDs,
failed-push retries, secret/path/size policy, stopped-writer requirements and snapshot races.
Real Git + PostgreSQL tests verify checkpoint command output, idempotent registration without
pointer rewind, generation-2 hydration, stale-owner rejection and expiry after upload leaving
an orphan ref without advancing the operational pointer. The temporary test database process
was stopped after testing; its data and Git fixtures remain under `.runtime`.

These new checks establish the checkpoint/publish/registration stage and manual fresh-worktree
hydration. An operator-facing resume command, authenticated network transport and an active
watchdog still remain. No actual two-host supervision or network outage recovery is claimed.

## References

Official protocol and database references are recorded in [BibTeX](references.bib).
