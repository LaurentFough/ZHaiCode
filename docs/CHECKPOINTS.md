---
title: "ZHaiCode checkpoint operation"
description: "Capture policy, durable publication and safe retries."
slug: "checkpoints"
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

# Git checkpoint operation — package v0.2.0

The trusted control-plane administrator can now capture work, publish a unique Git recovery
ref and register its verified SHA in PostgreSQL. The wire protocol remains v0.1. This is
one step toward remote continuation; it does not launch or supervise model workers.

## Before capture

Run from the project folder. The repository, its Git common directory and any local-file
remote must remain inside that folder. Linked worktrees within it are supported. A configured
SSH/HTTPS remote can be external; the engine matches it against the registered project's
repository_url (SSH/HTTPS spellings of the same host/path are equivalent).

Stop all writers that do not participate in `GitCheckpoint.worktree_lock()`. The POSIX lock
coordinates cooperating processes only. `--quiesced` confirms you have stopped other writers;
it does not stop, signal or freeze an arbitrary worker. Before and after capture the engine
compares content, modes, HEAD and the original index, failing if they differ. This detects
ordinary races but is not an OS-enforced snapshot against uncooperative/malicious writers.
Use macOS/Linux/Unix or WSL for this engine; native Windows locking is not implemented.

Create a valid handoff using examples/handoff.json as a template. Set the real task/project,
current generation and owner IDs, objective, test results and next action. Keep this input
under `.runtime` if it is administrative metadata, rather than adding it to the capture list.
The service checks it against the live PostgreSQL task before Git side effects and again
before publication; final registration fences against database time after upload.

```sh
.venv/bin/agentctl checkpoint CP-002 \
  --repository "$PWD" \
  --handoff .runtime/handoff.json \
  --include-untracked src/new_module.py \
  --quiesced
```

Use a globally unique checkpoint ID. Repeat `--include-untracked` for each intended new file.
The command returns one checkpoint JSON document only after remote verification and successful
operational registration. Diagnostics go to stderr; existing file/syslog options still apply.
Use `make checkpoint-help` and `make checkpoint-check` for command help and focused tests.

## Captured state

All regular paths from HEAD or the current index are considered tracked, including staged
additions. Capture uses current filesystem bytes, not the staged/unstaged partition. Already
absent tracked files are absent from the snapshot; the engine does not delete working files.
Executable modes and binary bytes are retained. Other untracked files are omitted by default.
The original index remains byte-for-byte unchanged, and no checkout/merge/stash is performed.

A separate retained index is built from validated raw bytes under
`.runtime/checkpoints/<attempt>/index`. Filters and local Git hooks are bypassed; therefore
Git LFS/filter transformations are not supported by capture. Symlinks, submodules, unmerged
indexes, sparse checkouts and shallow repositories fail closed in this version. Untracked
paths must be exact relative paths, not globs, and cannot be ignored. Dotenv files, common key
files, credential folders, runtime/cache directories and escaping paths are denied even if
explicitly selected. At most 10,000 paths, 10 MiB/file and 50 MiB total are allowed; the handoff
manifest is limited to 1 MiB. Known-key/token pattern scanning is a baseline, not comprehensive
secret detection. Reviewed parent history is required: historical secrets are not scrubbed.

The recovery commit's message starts with `ZHaiCode checkpoint v0.1`, followed by a JSON
manifest containing `checkpoint`, `handoff`, and `included_untracked`. The embedded checkpoint
omits its own commit SHA and durability flag. This avoids recursive hashes and keeps handoff
metadata out of source-tree paths. `GitCheckpoint.read_manifest(commit)` loads the manifest.
A resumed agent must read it in addition to AGENTS.md/SPEC.md and the operational task.

## Publication and failure handling

1. Fence ownership and confirm the project destination.
2. Capture a consistent snapshot or reuse the original immutable local operation ID.
3. Create `refs/agents/<task>/checkpoints/<generation>/<checkpoint>` locally.
4. Fence ownership again, then push only if the destination ref is absent. An explicit empty
   expected old SHA makes remote creation atomic against a concurrent creator.
5. Query the same push destination and verify the exact SHA, then register under a DB fence.

A matching existing remote ref is a safe retry. A different SHA is a hard conflict; the engine
never overwrites it. No task branch or main is pushed by this operation. Protected remote
permissions are still required against tools/credentials outside this trusted publisher.

On a failed push, retain the local checkpoint/ref and retry the same command and input after
repairing access. If the database fails or the lease expires after upload, the remote ref
remains an orphan; no current checkpoint pointer is advanced. Do not delete it. If ownership
is still valid, an identical retry re-verifies publication and registration. If ownership is
lost, fail closed and inspect state as an operator; cross-generation orphan adoption is not
automated. A DB response lost after commit is safe to retry while the lease remains valid.

A reused ID always means the original frozen commit, even if files have since changed. Use
a new ID for a new snapshot. Changed handoff/include selection under the same ID is refused.
An identical registration retry never rewinds the latest pointer over a newer checkpoint.

## Verification and remaining work

Tests use retained local Git remotes plus real PostgreSQL. They cover publication, exact
working bytes/modes, branch/index preservation, fresh-worktree hydration, create races,
push failure/retry, secret/path/size policy, quiescence, lease expiry after upload and
idempotent registration. These simulate independent machine identities on one host; they do
not prove real network authentication or watchdog-driven recovery on separate hosts.

Next: authenticated transport and operator-facing resume, then watchdog lifecycle integration.
No semantic/vector memory or automatic merging has been added. The Python/Git plumbing path
keeps this implementation within the agreed stack; a separate Git wrapper library is not
needed for the initial portable engine.

## References

See the official Git manuals for [index input](https://git-scm.com/docs/git-update-index),
[object creation](https://git-scm.com/docs/git-hash-object), and
[push compare-and-swap options](https://git-scm.com/docs/git-push).
Bibliographic records are in [references.bib](references.bib).
