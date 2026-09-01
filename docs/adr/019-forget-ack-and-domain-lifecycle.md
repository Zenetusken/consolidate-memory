# 019. Forget acknowledgment and domain lifecycle

Status: Accepted
Extends: ADR 003, ADR 006

## Context

v0.3.3 `forget` tombstoned the canonical and deleted only the calling
project's holder and mirror. Other projects kept loading the body. Pull
skipped tombstoned canonicals but did not walk existing mirrors. GC treated
on-disk tombstone Markdown as a live stem, so those mirrors were not
orphans.

`--resurrect` wrote an active canonical without `tombstone_delete`, so pull
kept suppressing the stem.

Domain purge revoked one project at a time, then deleted canonicals. A
concurrent pull could recreate a mirror. Missing `current_root` built a
StoreContext from the native-memory path as if it were a project root,
minting a different project id.

## Decision

**Forget is lazy tombstone-acknowledgment.** Forget writes the tombstone,
revokes the calling project's copy, and leaves other holder rows. The next
`--pull` or `--gc --apply` in another project classifies that project's
mirror: delete if clean, quarantine if edited, drop the pointer,
`holder_delete` (the ack). Offline clones keep bytes until they run.

GC live-stem enumeration skips `status: tombstoned`. Catalog generation
parses opening frontmatter only.

`--resurrect` includes `tombstone_delete` in the same migrate apply
transaction as `fact_upsert`.

Domains have a lifecycle row: `active | deleting | deleted` (missing =
active). Domain purge and all-plugin-data purge set `deleting` first; pull,
canonical upsert, and forget refuse while `deleting` or `deleted`. Revoke
uses the recorded `project_id` even when `resolve_store` would hash a
different identity. Mark `deleted` only after the purge transact succeeds.

Capability detection failure **holds** applicability-gated facts (does not
treat `applies_match` as true).

## Alternatives

- Eager lock-all-holders at forget time. Deferred: missing project roots and
  concurrent pull are the same coordination problem as purge; optional
  `--propagate` later.
- Remove `--resurrect`. Rejected: a missing `tombstone_delete` is a one-op
  fix, not a CLI removal.

## Consequences

Positive: a live project that next pulls or GCs will not keep a forgotten
fact. Purge no longer races with pull on the same domain.

Negative: forgotten bytes remain on an offline clone until its next
pull/GC. That is the documented ack lag, not fleet-atomic erasure.

## Revisit trigger

Reopen for eager `cm forget --propagate`, or if a second independent user
needs verified fleet-wide erasure as a 1.0 claim.
