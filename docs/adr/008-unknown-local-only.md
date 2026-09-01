# 008. Trust: unknown is local-only

Status: Accepted
Supersedes: ADR 003 rules 2, 3, and 7 (unknown dual-read; cross-domain authorization)

## Context

v0.2.1 made unenrolled projects share `domains/unknown/facts`. Tests required
unenrolled A→B pull. That is an installation-wide compatibility domain whose
members are every repository the operator has not enrolled. A newly cloned or
malicious repo can absorb preferences, environment facts, and workflows from
unrelated unenrolled work. ADR 003 promised unknown projects receive no
domain-tagged facts, but left untagged/`unknown` sharing as dual-read.

v0.2.2 Stage 0 documented this honestly. This ADR changes the model.

## Decision

We will:

1. Treat `unknown` as a **local-only sentinel**, not a domain. An unenrolled
   project may use native Auto Memory. It must not create, pull, harvest,
   appear in, or GC-across cross-project canonicals.
2. Require explicit enrollment into a named domain (`personal` recommended)
   for sharing. There is no implicit `default` pool.
3. Treat `domains/unknown/facts` and legacy `~/.claude/memory` as **migration
   inputs only** (ADR 013).
4. Restate: `user-global` means domain-global, not installation-global.
5. **Drop cross-domain authorization.** Remove the `authorized_pairs` table
   and API. Cross-domain replication is unsupported in 0.3.0.

`cross_project_allowed` is true iff `registry_state == healthy` AND the project
is enrolled AND `domain_id != "unknown"`.

## Alternatives

- **Keep unknown sharing with a warning.** Rejected: Stage 0 already warns;
  the blast radius is other repos on the laptop.
- **Silent assign to `personal`.** Rejected: that is a universal domain
  (ADR 003).
- **Keep dormant `authorized_pairs`.** Rejected: no producer-only feature.

## Consequences

Positive: unenrolled clones cannot absorb the fleet.

Negative: 0.2.1 unknown-pool facts become invisible until migrate+enroll.
Operators must inventory `domains/unknown/facts` (ADR 013). Lifecycle Probe AG
and smoke P0-3 invert.

Neutral: 1.0 remains HOLD.

## Revisit trigger

Reopen if an operator-facing `default` opt-in domain is required, or if a
real fleet needs authorized cross-domain pairs.
