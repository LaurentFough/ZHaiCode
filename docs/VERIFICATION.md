---
title: "ZHaiCode Phase 0/1 verification"
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

# Phase 0/1 verification

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

This does **not** prove two-machine Git recovery yet: checkpoint SHAs in metadata tests are
fixtures. The Git capture/push/verify/restore engine, authenticated transport and running
watchdog remain unimplemented. See [MILESTONE.md](MILESTONE.md) for acceptance steps.

The test database and test files are retained under `.runtime` for inspection. The temporary
PostgreSQL service is stopped after verification. Restart only when needed; retain the
project's consent/ZIP-backup policy before deleting artifacts.

## References

Official protocol and database references are recorded in [BibTeX](references.bib).
