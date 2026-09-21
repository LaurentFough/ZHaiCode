---
title: "ZHaiCode Checkpoint protocol"
description: "Checkpoint protocol v0.1."
slug: "checkpoint"
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

# Checkpoint protocol — v0.1

Checkpoints are immutable recovery commits/refs. Full 40- or 64-character Git OIDs, generation, handoff ID and unique ref are required. REMOTE_VERIFIED is asserted only by the trusted publisher after remote verification. Push first, then fenced DB registration. The current metadata method assumes that verification; the Git publisher is future work. Never use example OIDs for actual recovery. A lost DB response may leave a committed checkpoint; inspect state before retrying.

## Wire contract

See [JSON Schema](../../schemas/checkpoint.schema.json) and [valid example](../../examples/checkpoint.json). All objects require `schema_version: "0.1"`; unknown fields and incompatible versions are rejected. Identifiers are 1–128 portable ASCII letters/digits/underscore/hyphen and start with a letter or digit. Semantic cross-object checks and fencing belong to the service, not JSON Schema alone. Protocol changes require explicit versioning and migration; no silent rename.

## References

External references are recorded in [BibTeX](../references.bib).
