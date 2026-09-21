---
title: "ZHaiCode specification"
description: "Protocol v0.1 invariants and acceptance criteria."
slug: "spec"
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

# ZHaiCode specification — v0.1

## Authority and scope

The design conversation plus current user handoff govern this repository. Implementation
choices below resolve underspecified details without changing the named components.
Material architecture changes and renames require discussion and approval first.

Phase 0/1 establishes protocols, database transactions, tests and executable skeletons.
It intentionally does not implement semantic memory, inference providers, orchestrator
integration, network APIs, process supervision or automatic merging.

## Task lifecycle

`QUEUED → CLAIMED → ACTIVE`; active work may become `BLOCKED`, then return to `ACTIVE`.
A valid owner may release checkpointed work to `PAUSED`. A validated current-generation
checkpoint permits `ACTIVE → READY_FOR_REVIEW`, ending ownership without merging.
`PAUSED` and `RECOVERABLE` can be claimed again; each claim increments the generation.

On expiry, record `ORPHANED`, then `RECOVERABLE` if a checkpoint pointer exists, otherwise
`RECOVERY_REQUIRED`. These events and the final task state commit atomically. ORPHANED
is an audit transition, not a durable intermediate row state. No automatic reclaim is
allowed from RECOVERY_REQUIRED. An operator recovery workflow is future work; do not
reset task generations to bypass it. No completion/merge or cancellation state is invented.

## Ownership

One live lease per task. `(task_id, machine_id, agent_id, generation)` identifies ownership.
The generation is a persisted signed 64-bit positive integer after first claim (initially
zero), never reset on release/expiry. Exhaustion fails closed. Renew, release, status
transition and checkpoint registration must fence the caller in the same transaction as
the write. Expired ownership fails even when no new owner has claimed.

Production time comes from `clock_timestamp()` after acquiring `SELECT ... FOR UPDATE`.
`now >= expires_at` is expired. No worker wall clock can lengthen ownership.
A claim transaction checks the registered agent/machine binding. Watchdog identity will
be authenticated by the future transport; IDs alone are not authentication.

Default TTL is 30 minutes, heartbeat every 5 minutes, warning/grace window 10 minutes.
Protocol clarification: the grace window is the final 10 minutes **within** the TTL;
SUSPECT is observable health and never grants an additional write interval. Renewal in
that window is allowed before expiry. Heartbeats do not increment generation. The
prototype accepts 1–86400 seconds for deterministic tests and explicit policy tuning.

## Checkpoints and handoffs

A checkpoint has immutable identity, task/generation, full Git object IDs, recovery ref,
handoff identity and timestamp. Use `refs/agents/<task>/checkpoints/<generation>/<checkpoint>`.
The trusted publisher must quiesce writes, capture eligible dirty/untracked state, create
a durable commit, push the unique ref, verify the remote SHA, then register metadata while
still owning the lease. Normal branches and the user's index must not be changed by capture.
Do not stash. Do not mark local-only data recoverable after a remote push failure.

Git and PostgreSQL have no shared atomic transaction. Publish Git first. A failed database
write can leave an unregistered immutable ref; it must never become the recovery pointer
without successful fenced registration. Retry/reconciliation by operation ID and safe
ref retention are future work. A lost response must be resolved by reading state rather
than blindly repeating a claim.

The handoff records objective, completed/current/remaining work, decisions, issues, files,
context references, recent commands, validation and next action. Embed it in the recovery
commit before publishing; operational metadata may retain an indexed copy. The handoff
omits the checkpoint commit SHA to avoid a self-referential commit hash.

The Phase 0/1 `PostgresState.checkpoint` method validates metadata and fences registration.
Its precondition is verified remote durability; it does not itself run Git. Never expose
this method as a worker-supplied assertion that `REMOTE_VERIFIED` is true.

## Acceptance criteria

1. Exactly one of two simultaneous claims succeeds against PostgreSQL.
2. Release and reclaim, or expiry and recovery, strictly increase generations.
3. Old owners cannot renew, release, transition or publish checkpoint pointers.
4. No-checkpoint failures require explicit intervention.
5. Task state and a structured handoff can be read by a fresh service instance.
6. READY_FOR_REVIEW requires passing validation from the current generation; no merge runs.
7. All seven portable schemas reject invalid versions, unknown fields and missing fields.
8. The full milestone additionally requires actual pushed dirty recovery commits and a
   fresh machine worktree. Metadata-only integration tests do not establish that milestone.

## API boundaries

Phase 0/1 uses Python methods and a local admin CLI. Reserved `agentd/api`, `agentd/git`,
`agentd/checkpoints`, and `agentd/handoffs` packages mark future service boundaries.
HTTP/MCP are deferred until the core is verified. No unauthenticated listener is started.
Protocol errors include LEASE_HELD, STALE_LEASE, TASK_NOT_CLAIMABLE, CHECKPOINT_REQUIRED,
VALIDATED_CHECKPOINT_REQUIRED, OWNER_NOT_REGISTERED and INVALID_PAYLOAD. Clients must
not interpret a network error or unknown commit outcome as proof of mutation failure.

## References

External references are recorded in [BibTeX](docs/references.bib).
