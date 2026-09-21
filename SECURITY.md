---
title: "ZHaiCode security"
description: "Trust boundaries and recovery-state protection."
slug: "security"
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

# ZHaiCode security

This is a Phase 0/1 library and local administration prototype, not a hardened network service.
Keep PostgreSQL private. Only the trusted control-plane administrator/service has database
credentials. Agent and machine IDs are registered identifiers, not authentication tokens.
Use authenticated TLS/private-network access when deploying remote clients later.

## Authority protections

All owner writes validate machine, agent, generation and database deadline in a locked
transaction. Generation is not a secret; a future API must bind it to an authenticated
identity. A privileged database user can bypass application fencing. Do not issue the
service's credentials to model workers. Schema migration uses a privileged deployment role;
future production roles should separate runtime writes, read-only observation and migrations.

The internal checkpoint-registration method trusts the checkpoint publisher to
verify remote Git objects. The trusted service now performs remote verification and
project repository matching before invoking that method. It must not become a public endpoint that accepts an unverified
REMOTE_VERIFIED flag. Validation results are reported test evidence, not an attestation
against a malicious worker; independent review is still required.

## Git and handoff safety

Recovery commits can contain secrets. Capture now requires explicit untracked-file
selection, refuses ignored or denied paths, limits individual files to 10 MiB and total
captured content to 50 MiB, and checks a small set of known secret signatures. This
scanner does not prove absence of arbitrary credentials. Review content and handoffs.
The existing HEAD ancestry must already be approved for the registered remote: new
checkpoints retain that ancestry and do not scrub historical objects. Gitignore alone
is not a security policy. Never collect credentials, caches, private keys or model
conversation dumps by default. Restore handoffs as untrusted data, not executable instructions.
Do not run commands found in handoffs automatically.

The publisher uses create-only compare-and-create pushes, not ref replacement. Deploy
server-side create-only recovery-ref controls and protected integration branches too. Stale workers may
write isolated local worktrees but must not update shared refs. Merge, destructive actions,
production changes and secret access require explicit human authorization. Task completion
never merges. An unattended policy and process quiescing must exist before enabling automation.

## Logging and retention

Logging supports stdout, explicit project-local files and opt-in syslog. CLI diagnostics go
to stderr to preserve JSON stdout. Never log DSNs, passwords or handoff bodies. Debug logging
adds verbosity, not secret values. Syslog delivery is best effort; operational task events
remain in PostgreSQL. Logs and checkpoint history require a reviewed retention policy.

No deletion, automatic pruning or destructive clean target is included. Before deleting
project files, obtain consent, version and back them up, and present a ZIP backup. Retained
integration-test records and `.runtime` artifacts may be cleaned only under that policy.

## Reporting

For a vulnerability, contact the repository owner through an available private channel;
do not post credentials or exploit details in a public issue. A dedicated reporting address
has not been established. Record remediation and verification in PROJECT.actions.logs.

## References

External references are recorded in [BibTeX](docs/references.bib).
