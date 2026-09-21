---
title: "ZHaiCode Handoff protocol"
description: "Handoff protocol v0.1."
slug: "handoff"
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

# Handoff protocol — v0.1

The durable handoff contains objective, completed, working_on, remaining, decisions, issues, files, context, commands, validation and next_action. Empty lists are explicit, never missing. Bind it to task, project, source owner and generation. Include this JSON in the Git checkpoint; keep an indexed operational copy. It does not contain the enclosing commit SHA, avoiding recursive hashes. Never execute stored commands automatically. No conversation is required to understand the next action.

## Wire contract

See [JSON Schema](../../schemas/handoff.schema.json) and [valid example](../../examples/handoff.json). All objects require `schema_version: "0.1"`; unknown fields and incompatible versions are rejected. Identifiers are 1–128 portable ASCII letters/digits/underscore/hyphen and start with a letter or digit. Semantic cross-object checks and fencing belong to the service, not JSON Schema alone. Protocol changes require explicit versioning and migration; no silent rename.

## References

External references are recorded in [BibTeX](../references.bib).
