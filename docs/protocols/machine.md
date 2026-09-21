---
title: "ZHaiCode Machine protocol"
description: "Machine protocol v0.1."
slug: "machine"
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

# Machine protocol — v0.1

Register a unique machine_id, OS, architecture and capability strings. This registry describes capabilities; it does not prove liveness or confer authorization. Machine heartbeat APIs and capability-based routing are deferred. Clone identities must be distinct on separate physical or virtual workers.

## Wire contract

See [JSON Schema](../../schemas/machine.schema.json) and [valid example](../../examples/machine.json). All objects require `schema_version: "0.1"`; unknown fields and incompatible versions are rejected. Identifiers are 1–128 portable ASCII letters/digits/underscore/hyphen and start with a letter or digit. Semantic cross-object checks and fencing belong to the service, not JSON Schema alone. Protocol changes require explicit versioning and migration; no silent rename.

## References

External references are recorded in [BibTeX](../references.bib).
