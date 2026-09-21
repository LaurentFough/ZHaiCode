---
title: "ZHaiCode recovery milestone"
description: "Acceptance runbook and next implementation sequence."
slug: "milestone"
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

# First end-to-end milestone

**Start on machine A → lose the originating agent/session → resume on B with no conversation.**

## What Phase 0/1 proves

Real PostgreSQL tests exercise competing claims, deadline expiry, durable generation
increments, rejection of stale owners, metadata recovery by a fresh service instance,
and readiness gating. Protocol tests establish portable payload shapes. These are foundation
checks. The checkpoint engine adds real Git/local-remote integration tests: tracked dirty
and explicitly selected untracked files are committed and published, PostgreSQL records
verified metadata, and a fresh generation-2 worker can read the commit in a new worktree.
The older metadata-only tests still deliberately use fixture hashes.

## Next implementation sequence

1. **Implemented:** trusted alternate-index Git capture/publisher with explicit untracked
   selection, path/size/known-secret checks, JSON handoff in the commit, and unchanged
   branch/index. Operators must stop non-cooperating writers.
2. **Implemented:** create-only remote publication, SHA verification, fencing and local-ID
   retries without pointer rewind. Cross-machine orphan adoption and retention remain open.
3. Implement authenticated agentd transport; expose worker operations through it, not DB
   credentials. Add resume orchestration that acquires a lease before hydrating a worktree.
4. Implement separate agent-watchd supervision, heartbeat scheduling, periodic/event
   checkpoints and fail-closed lease loss. Suspend hooks are best effort on each OS.
5. Execute the acceptance scenario below on independent clones/identities and then real hosts.

## Acceptance scenario

- Start a private Git remote and PostgreSQL state service; register project, machines A/B
  and separate agent identities. Create TASK-001 and claim generation 1 on A.
- Modify a tracked file and add an allowed untracked file. Record current objective,
  completed/remaining work, test evidence, decisions and next action in a structured handoff.
- Publish/verify a durable checkpoint. Verify main and the original index are unchanged.
- Terminate the worker/session. In a separate case, stop all of machine A. Never consult
  its model conversation. Wait for authority expiry; verify ORPHANED and RECOVERABLE events.
- B claims generation 2, fetches exactly the checkpoint SHA into a fresh worktree, reads
  task/handoff/AGENTS/SPEC, reruns the recorded tests and continues a meaningful next step.
- Wake A and try renewal, checkpoint registration, completion and shared-ref mutation with
  generation 1. All authority writes must be rejected; B's pointer remains unchanged.
- Complete and validate on B; mark READY_FOR_REVIEW. Verify main was not merged or moved.

Repeat with a failed push, DB failure after successful push, duplicate delivery, concurrent
claim on B/C, missing remote objects, no checkpoint, mismatched task/handoff, secrets in
untracked files, worker writes during capture, and suspend with no network. Retain artifacts
and run logs under the project. Deletion requires consent and a presented ZIP backup.

## References

External references are recorded in [BibTeX](references.bib).
