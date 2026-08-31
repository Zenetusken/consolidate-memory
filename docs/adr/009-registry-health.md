# 009. Registry health is an explicit StoreContext field

Status: Accepted
Extends: ADR 002

## Context

`resolve_store()` started `domain = "unknown"` and swallowed registry errors
with `except Exception: pass`. A corrupt, locked, or unreadable
`control.sqlite` silently turned an enrolled project into an unknown project.
With shared-unknown (ADR 003/0.2.1) that was an isolation failure. v0.2.2
Stage 0 added `classify_registry` / `assert_mutation_allowed` for writes;
reads could still fail open.

## Decision

`StoreContext` carries:

```text
registry_state: absent | healthy | locked | corrupt
                | permission-denied | incompatible
cross_project_allowed: bool
```

Mapping:

| registry_state | Effect |
|---|---|
| absent | project-local only (`cross_project_allowed` false) |
| healthy | enrolled-domain behavior if enrolled |
| anything else | refuse all cross-project reads and writes |

No broad `except Exception` on a trust decision. The SessionStart beacon
stays silent (empty stdout, exit 0) on registry failure. `cm doctor` and
mutating commands print the exact state and error. Schema upgrades run only
on the writable `connect()` path.

## Alternatives

- **Fail open to unknown.** Rejected: that was P0-2.
- **Crash the beacon.** Rejected: hook budget / silent-exit-0 contract.

## Consequences

Positive: a damaged control plane cannot impersonate "unenrolled sharing".

Negative: an enrolled project whose DB is locked cannot pull until the lock
clears — fail closed.

## Revisit trigger

Reopen if a reconstructible read-only snapshot of enrollment must serve
during a lock.
