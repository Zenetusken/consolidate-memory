# 003. Domain isolation (trust ≠ applicability)

Status: Accepted — superseded in part by ADR 008 (unknown is local-only; no cross-domain authorization)

## Context

`scope: user-global | stack-general | project-local` answers "which projects
could *benefit* from this fact?" It does not answer "which projects are
*allowed* to receive it?" A single Claude install can hold personal work,
employer code, client engagements, and confidential financial or security
projects. A fact can be sensitive without matching a credential regex.

Cross-domain replication of customer names, internal architecture, incident
detail, or unreleased plans is a confidentiality failure, not a relevance
miss. Treating `user-global` as installation-global is a P0 release blocker.

Constraints: existing lifecycle probes write unscoped `user-global` facts
into the legacy `~/.claude/memory` store and pull them; those probes must
stay green during the dual-read window. Existing canonicals must not be
silently assigned to a universal or personal domain. Stdlib only. 1.0 HOLD.

## Decision

We will separate:

| Field | Meaning |
|---|---|
| Native `type` | user / feedback / project / reference |
| `domain` | who may receive it (trust boundary) |
| `applies` | which capabilities or contexts benefit |
| `sensitivity` | public / internal / confidential / secret |
| `tier` | always-loaded cue / on-demand body / archive |
| `status` | active / superseded / tombstoned / expired |

Rules:

1. **`user-global` becomes domain-global, not installation-global.**
2. Unknown-domain projects receive no *domain-tagged* cross-project facts.
3. Cross-domain replication is denied unless explicitly authorized.
4. `secret` is never retained as a fact body — a safe pointer only.
5. `confidential` stays inside its domain.
6. Every promotion, import, upsert, and migrate path runs the same policy
   function (`admit_cross_project`).
7. Legacy facts with no `domain` field plus projects with `domain_id=unknown`
   remain readable under dual-read (ADR 007) so existing installs and
   hermetic probes do not silently change trust assignment. Dual-read is not
   an assignment to a universal domain. `cm migrate --apply` is the review
   plan that tags domains.

## Alternatives

- **Keep scope-as-trust and add a disclaimer.** Rejected: the blast radius is
  other people's codebases on the same laptop.
- **One `personal` default domain for everything untagged.** Rejected: that
  *is* silently assigning existing canonicals to a universal-personal domain.
- **OS-user as the domain.** Rejected: one OS user routinely holds employer
  and personal profiles (`CLAUDE_CONFIG_DIR`).

## Consequences

Positive: personal and employer fleets can share an install without sharing
facts. Sensitivity is a write gate, not a regex afterthought.

Negative: until migrate, dual-read still replicates untagged legacy
`user-global` facts to unknown-domain projects (old behavior). Operators
must run the review plan to close that window. Unknown-domain *new* writes
that carry a domain tag are denied.

Neutral: applicability (`stacks` / `applies`) remains a separate matcher.
1.0 remains HOLD.

## Revisit trigger

Reopen if a profile split is not captured by `profile_id`+`domain_id`, if
operators cannot complete migrate without a silent default, or if a
sensitivity class finer than confidential/secret is forced by a real fleet.
