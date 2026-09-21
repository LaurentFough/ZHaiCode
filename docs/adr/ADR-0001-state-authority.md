---
title: "ADR 0001 — State authority"
description: "State authority"
slug: "adr-0001-state-authority"
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

# ADR 0001 — State authority

Status: accepted by the project design conversation.

## Context

Operational ownership must survive loss of any model session.

## Decision

Git is authoritative for project artifacts, instructions and recovery commits. PostgreSQL is authoritative for task/lease state, identities, checkpoint pointers and events. Agent sessions are ephemeral. No vector memory in Phase 0/1.

## Consequences

Remote continuation reads Git plus PostgreSQL and structured handoffs. No session synchronization, SQLite fallback, or vector index may replace these authorities. Backups must preserve generation high-water marks.

## References

External references are recorded in [BibTeX](../references.bib).
