---
title: "ZHaiCode Task protocol"
description: "Task protocol v0.1."
slug: "task"
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

# Task protocol — v0.1

Task identity, project and objective are persistent. Status follows SPEC.md; generation starts at zero and never resets. Embedded lease is null when unowned. latest_checkpoint is only an operational pointer to verified Git recovery data. `create`, `status`, `claim`, `renew`, `release`, `transition`, `expire` are local CLI/library operations. Read status can show an expired lease until expiry is processed; ownership checks always use current DB time.

## Wire contract

See [JSON Schema](../../schemas/task.schema.json) and [valid example](../../examples/task.json). All objects require `schema_version: "0.1"`; unknown fields and incompatible versions are rejected. Identifiers are 1–128 portable ASCII letters/digits/underscore/hyphen and start with a letter or digit. Semantic cross-object checks and fencing belong to the service, not JSON Schema alone. Protocol changes require explicit versioning and migration; no silent rename.

## References

External references are recorded in [BibTeX](../references.bib).
