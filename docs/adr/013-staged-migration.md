# 013. Staged migration

Status: Accepted
Supersedes: ADR 007's plan/apply + `legacy-unassigned` enforcement

## Context

v0.2.1 `migrate --apply` copied into the current canonical dir (often
`domains/unknown/facts`), stamped `domain: legacy-unassigned`, and set mode
`enforced`. `legacy-unassigned` equals no real domain, so copied facts became
ineligible. Rollback unlinked absolute paths from mutable JSON without
containment or hash checks. 0.2.1 also left a populated `unknown` pool.

## Decision

Staged commands; `apply` refuses while any fact is unresolved:

```text
inventory → review → assign FACT --domain DOMAIN | exclude FACT
         → resolve-collision → validate → apply → status
         → rollback | finalize
```

Inputs: legacy `~/.claude/memory`, `domains/unknown/facts`, enrolled domain
dirs, unstamped native mirrors, old control/journal schemas.

No silent `personal`/`default` assignment. Assignment writes the plan, not
live files, until `apply`. `apply` journals through v3 and stamps real
destination domains. Dual-read remains until `finalize` sets `enforced`.
Rollback records allowed roots + old/new hashes. Edited-after-migration
files are conflicts, never deleted.

Post-apply tests must pull, forget, GC, restart, and recover — file existence
is not success.

## Alternatives

- **Big-bang personal.** Rejected: ADR 003.
- **Patch legacy-unassigned to mean personal.** Rejected: silent assignment.

## Consequences

Positive: a 0.2.1 unknown-sharing fleet can be reviewed into named domains.

Negative: operators must finish the review before enforcement; dual-read
lasts one migrate window.

## Revisit trigger

Reopen if dual-read on a real fleet exceeds one migrate window.
