---
title: "ADR 0003 — Lease fencing"
description: "Lease fencing"
slug: "adr-0003-lease-fencing"
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

# ADR 0003 — Lease fencing

Status: accepted by the project design conversation.

## Context

A sleeping or partitioned machine may wake after another owner starts work.

## Decision

Serialize task mutations with a PostgreSQL row lock; read database time after locking. Increment a durable per-task generation on each claim. Validate agent, machine, generation and expiry on every owner-authorized write. Release and expiry retain the generation.

## Consequences

Stale workers fail closed even before a replacement exists. Warning grace does not extend the deadline. Fencing applies to service writes; shared Git refs need their own protected publisher. No automatic reclaim without a checkpoint. Tests must cover real concurrent connections.

## References

External references are recorded in [BibTeX](../references.bib).
