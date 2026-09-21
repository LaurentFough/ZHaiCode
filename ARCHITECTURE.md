---
title: "ZHaiCode architecture"
description: "State ownership, process boundaries and recovery design."
slug: "architecture"
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

# ZHaiCode architecture

```text
Hermes (coordination) / OpenCode (execution) / ZHaiCode (workspace UX)
                         |
                  agentd state service
                         |
             PostgreSQL operational authority
                         |
          verified pointers to Git recovery commits

machine A: worker + separate agent-watchd
machine B: fresh worker + separate agent-watchd
```

Hermes, OpenCode, Herdr and model providers are future adapters. Their runtime observations
never override task ownership in PostgreSQL. Existing ZAICODE picker concepts remain
future workspace integration inputs; the project/repository name here is exactly ZHaiCode.

## Implemented boundaries

| Component | Current responsibility |
|---|---|
| `agentd.leases.model` | Immutable values, pure transitions and fencing checks |
| `agentd.state.postgres` | Transactions, registration, task state, events and recovery metadata |
| `agentd.protocol` | Portable wire conversion and closed JSON Schema validation |
| `agentd.git.checkpoint` | Isolated-index capture, immutable refs and remote verification |
| `agentd.checkpoints.service` | Authorize → publish → fence operational registration |
| `agentctl` | Trusted local administrative and checkpoint commands with JSON output |
| `agentd` executable | Explicit schema bootstrap only |
| `agent-watchd` executable | Separate policy skeleton; no background heartbeat yet |

Task records retain the fencing counter even with no lease. JSONB carries protocol v0.1
payloads while relational keys, generation checks and foreign keys protect core references.
Only the trusted service database role may mutate them. A future migration runner must
be additive and checksum-aware; v1 bootstrap is idempotent and serialized, not a general
schema-upgrade engine. Production operational backup/restore must preserve generations.

## Recovery flow and current coverage

1. Create a task-specific isolated worktree and acquire a lease.
2. Worker writes code and structured handoff content; watchdog observes it independently.
3. Quiesce writers, commit dirty state using an alternate index, publish a unique recovery ref.
4. Verify the remote ref, then atomically register the pointer under the current fence.
5. Lose worker A. Watchdog requests safe checkpoint/release if possible; otherwise leases expire.
6. B claims a new generation, fetches and verifies the recorded commit, creates a new worktree,
   and reads AGENTS.md, SPEC.md, task data and handoff before resuming.
7. A waking later loses permission for all authoritative writes with its stale generation.

Steps 3–4 are implemented for stopped/cooperating writers; tests manually exercise
fetching the published commit into a fresh worktree after a new claim. Automated
resume and worker/watchdog lifecycle integration remain next.

A fencing token cannot stop arbitrary filesystem writes or independent Git pushes by
credentials outside agentd's control. Workers must use isolated worktrees and cannot
possess credentials that overwrite shared authoritative refs. The publisher uses an empty expected-old-OID compare-and-create push and verifies the
resulting ref. Production remotes still need server-side create-only authorization;
a privileged independent Git credential can bypass the publisher.

## Failure semantics

Database outage means no fresh ownership or authoritative mutation. No SQLite/file fallback.
Unpublished local files cannot survive total machine loss. Recovery's loss window is time
since the latest successfully published and registered checkpoint, potentially longer
than the intended ten-minute schedule during outages. Never promise zero data loss.

Published-but-unregistered refs are retained for reconciliation. Missing remote objects
must stop restore and require repair. Backup restoration to an earlier database snapshot
must fence all prior workers and restore the generation high-water marks before writes
resume; simply restarting old counters would break safety.

## Implementation alternatives

Python plus psycopg and JSON Schema is sufficient for the agreed first phase. A later Go
or Rust watchdog could simplify single-binary deployment, but replacing Python or changing
component responsibilities requires discussion first. PostgreSQL row locks keep the initial
ownership protocol simpler than adding an independent distributed lock service.

## References

External references are recorded in [BibTeX](docs/references.bib).
