---
title: "ADR 0002 — Durable Git checkpoints"
description: "Durable Git checkpoints"
slug: "adr-0002-git-checkpoints"
author: "LaurentFough"
type: "architecture-decision"
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

# ADR 0002 — Durable Git checkpoints

Status: accepted by the project design conversation.

## Context

Dirty work must be recoverable from another machine without polluting main.

## Decision

Use durable commits under unique refs/agents/<task>/checkpoints/<generation>/<checkpoint> refs, pushed and verified before fenced registration. Store the handoff inside the commit. Do not use git stash. Task completion does not merge.

## Consequences

Capture needs quiescing, secret policy and a separate index. Git/DB atomicity is impossible: retain unregistered refs and reconcile; never announce remote recovery before publication succeeds. Immutable/create-only ref enforcement is required at the publisher/remote boundary.

## References

External references are recorded in [BibTeX](../references.bib).
