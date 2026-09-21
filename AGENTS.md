---
title: "ZHaiCode agent instructions"
description: "Mandatory project and architecture rules for future agents."
slug: "agents"
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

# ZHaiCode agent instructions

## Design authority

The ChatGPT conversation "Multi Agent Setup Suggestions" and the current Phase 0/1 handoff
are project-design authority. Read SPEC.md, ARCHITECTURE.md and the ADRs before changes.
Use `ZHaiCode` exactly as the repository/project name. Do not redesign or rename established
components without discussing the proposed change first. Preserve Git artifact authority,
PostgreSQL operational authority, ephemeral sessions, durable Git recovery refs instead of
stash, a separate `agent-watchd`, and completion without automatic merge. No semantic/vector
memory in this phase. Do not spawn agents unless explicitly requested by the user.

## User's project constraints

- Never write outside the current project folder.
- Never delete project files without consent. Every deletion must be versioned and backed
  up; present a ZIP backup before deletion. Do not introduce destructive cleanup targets.
- Never rename variables, objects, functions or established components.
- Preserve existing inline comments; they are intentional.
- Keep `PROJECT.actions.logs` with implementation details and cross-device setup/recovery
  information. Update it for each development session.
- Generate detailed documentation and project-local virtual runtime setup options.
- Maintain a Makefile with build, check, release, venv and necessary commands.
- Prefer modular, reusable solutions with input verification, error checking and debugging.
  Provide logging to file, stdout and opt-in syslog; keep secrets out of all destinations.
- Suggest simpler, maintainable alternatives when relevant; do not silently replace the design.
- Prefer macOS, Linux and Unix portability; document Windows via PowerShell/WSL where possible.
  Preferred languages include fish, Python, Rust, Ruby, Zig, zsh, bash and POSIX sh.
- Write actual comments as `#= ...` in Python/shell, `--= ...` in SQL, or the corresponding
  language comment character followed by `= `. Commented-out program code uses normal syntax.
- Version all code. Include useful inline documentation notes and tests from the beginning.
- Created Markdown must be PKIM/Obsidian-ready with frontmatter fields in this order:
  title, description, slug, author, type, date-created, date-modified, date-published,
  source, domain, url, draft, tags, keywords.
- Include external references in BibTeX format. Prefer academic, official documentation,
  online learning and verified forum sources.

## Development workflow

Run from the repository root. `make install` creates `.venv`; use `.runtime` for caches,
logs and retained test outputs. Run `make check`, `make integration` with a dedicated
ZHAICODE_TEST_DSN, then `make build`. Integration skips are not evidence of PostgreSQL safety.
Never reset generations, substitute a local file/SQLite store as authority, silently steal
leases or treat local-only Git objects as remote checkpoints. Keep service credentials away
from workers. Capture material assumptions and limitations in documentation and actions log.

Read docs/MILESTONE.md before extending recovery. The current executables are explicit
skeletons; do not describe them as a complete background supervisor or authenticated API.

## References

External references are recorded in [BibTeX](docs/references.bib).
