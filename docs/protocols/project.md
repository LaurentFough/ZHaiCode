---
title: "ZHaiCode Project protocol"
description: "Project protocol v0.1."
slug: "project"
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

# Project protocol — v0.1

A project registers ID, display name, repository location, default branch and instruction paths. ZHaiCode is the exact project name for this repository. Git holds the actual specifications and artifacts; database registration is operational discovery metadata. Instruction paths are untrusted until resolved inside an authorized checkout. No arbitrary repository URL is executed in Phase 0/1.

## Wire contract

See [JSON Schema](../../schemas/project.schema.json) and [valid example](../../examples/project.json). All objects require `schema_version: "0.1"`; unknown fields and incompatible versions are rejected. Identifiers are 1–128 portable ASCII letters/digits/underscore/hyphen and start with a letter or digit. Semantic cross-object checks and fencing belong to the service, not JSON Schema alone. Protocol changes require explicit versioning and migration; no silent rename.

## References

External references are recorded in [BibTeX](../references.bib).
