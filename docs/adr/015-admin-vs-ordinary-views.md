# 015. Ordinary reports are current-domain only

Status: Accepted

## Context

`global_facts()` returned `(stem, fm, text)` and consumers keyed by bare stem.
Two facts named `deploy` in `personal` and `work` collided in beacon, network,
tokens, utility, staleness, GC, and workflows. Ordinary dream output could
enumerate another domain.

## Decision

All ordinary fleet operations take `StoreContext` and enumerate only
admissible `CanonicalRef` objects (ADR 008/009). Ordinary reports
(`--list`, `--tokens`, `--network`, `--utility`, `--staleness`,
`--workflows`, beacon, dashboards) never mention another domain's fact names.

An explicit administrative `--all-domains` view may exist. It is never
invoked from SKILL.md, never implicit in a dream, and redacts bodies by
default.

## Alternatives

- **Stem-global uniqueness.** Rejected: domains are the trust boundary.
- **Always show the whole install.** Rejected: isolation failure.

## Consequences

Positive: a `personal` dream cannot leak `work` topology.

Negative: operators debugging cross-domain issues need `--all-domains`.

## Revisit trigger

Reopen if a dream must surface a same-stem collision as a *conflict to
resolve* without naming the other domain's body.
