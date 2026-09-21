---
title: "ZHaiCode Lease protocol"
description: "Lease protocol v0.1."
slug: "lease"
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

# Lease protocol — v0.1

A lease binds task, agent, machine and generation with acquired_at, heartbeat_at and expires_at. Timestamps require timezone offsets. Defaults: TTL 1800s, heartbeat 300s, warning window 600s within TTL. Equality at deadline expires. Claim increments generation; renew preserves it. All owner mutations fence owner identity, generation and validity under the task row lock. No client-provided time in production.

## Wire contract

See [JSON Schema](../../schemas/lease.schema.json) and [valid example](../../examples/lease.json). All objects require `schema_version: "0.1"`; unknown fields and incompatible versions are rejected. Identifiers are 1–128 portable ASCII letters/digits/underscore/hyphen and start with a letter or digit. Semantic cross-object checks and fencing belong to the service, not JSON Schema alone. Protocol changes require explicit versioning and migration; no silent rename.

## References

External references are recorded in [BibTeX](../references.bib).
