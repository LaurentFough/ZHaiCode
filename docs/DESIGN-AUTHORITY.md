---
title: "ZHaiCode design authority"
description: "Provenance of preserved decisions."
slug: "design-authority"
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

# Design authority

On 2026-09-20 the bootstrap read the original ChatGPT task **Multi Agent Setup Suggestions**
(ID `6ab07655-babc-83e8-9a97-6ee4d9a21b03`) through the app's task reader.
The design turns dated 2026-09-20 establish the operational-state service, structured
handoffs, PostgreSQL row-locked leases, monotonic fencing, separate watchdog and Git refs.
The final handoff is reproduced in scope by the user's current request.

Earlier suggestions called the state-plane repository `agentd` and used legacy `ZAICODE`
workspace examples. The user's later explicit naming instruction supersedes that working
repository name: this repository is **ZHaiCode**; `agentd`, `agent-watchd` and `agentctl`
remain component names. Existing component names and accepted boundaries are preserved.

Implementation clarifications for v0.1: identifiers are portable strings, generation is
signed 64-bit, deadlines are exclusive, grace is a warning inside TTL, and ORPHANED is
recorded as an event within the expiry transaction. These concrete protocol choices fill
in details not fixed by the conversation. Material changes require approval before coding.

The complete conversation is not copied into this repository because unrelated personal
history is unnecessary for recovery. SPEC.md, ADRs and protocols carry the project decisions.

## References

External references are recorded in [BibTeX](references.bib).
