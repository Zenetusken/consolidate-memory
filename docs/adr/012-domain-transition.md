# 012. Transactional domain transition and rebind

Status: Accepted
Extends: ADR 003, ADR 004

## Context

`enroll_project` / `unenroll_project` only UPDATE the registry row. Native
`MEMORY.md` and mirrors are untouched. Switching `work → personal` keeps work
facts always-loaded. Reusing `enroll` to switch domains is silent. A moved
repo whose git common dir changed looks like a new project (ADR 004).

## Decision

Distinct commands, dry-run by default, confirmation phrase required for
`--apply`:

| Command | Intent | Refuse when |
|---|---|---|
| `cm project enroll --domain NAME` | first grant | already enrolled |
| `cm project move-domain --to NAME` | A→B | not enrolled, or `--to` equals current |
| `cm project unenroll` | A→unknown (local-only) | not enrolled |
| `cm project rebind` | git-common-dir / root moved | would collide with another `project_id` |

Transaction (journal v3, ADR 010): lock old-domain, new-domain, global,
project; inventory managed mirrors by canonical fact id/domain; quarantine
locally edited mirrors; remove clean mirrors not admitted in the destination
(unenroll removes all managed mirrors); remove exact index pointers;
`holder_delete` old edges; `project_domain_change`; commit; pull the new
domain only afterward.

`unknown` is a sentinel: still take project + global locks; take the old
named-domain lock when leaving one.

## Alternatives

- **Reuse enroll to switch.** Rejected: silent domain change.
- **Leave mirrors in place.** Rejected: always-loaded unauthorized facts.

## Consequences

Positive: domain membership matches what sessions load.

Negative: a local edit during move is quarantined (operator must resolve).

## Revisit trigger

Reopen if Claude exposes a stable native project ID we should adopt for rebind.
