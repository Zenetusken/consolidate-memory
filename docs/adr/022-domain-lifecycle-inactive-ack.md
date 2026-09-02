# 022. Domain lifecycle and inactive mirror ack

Status: Accepted
Extends: ADR 019

## Context

ADR 019 set domain rows to `deleting` then `deleted` and made forget a lazy
tombstone-ack. Domain purge still left projects `enrolled` in the deleted
domain, so `cross_project_allowed` stayed true and `domain-transition` was
refused (`assert_domain_writable`). `ack_tombstoned_mirrors` ignored
superseded/expired. `reactivate` rewrote the forget stub to `status: active`.
All-plugin-data purge journaled a revoke then `rmtree`'d plugin-data (including
the journal) with no external resume fence.

## Decision

1. **Purge unenrolls in the same transact** that marks `deleted`. Postcondition:
   `domain.status == deleted` ⇒ zero `projects` rows with that `domain_id` and
   `status='enrolled'`. Former members are local-only and may enroll elsewhere.
   Enroll/move into `deleting`/`deleted` is refused.
2. **`StoreContext.domain_lifecycle`** (`active|deleting|deleted|unknown`).
   `cross_project_allowed` requires `domain_lifecycle == active`.
   `domain-transition`, `purge-resume`, and `purge-cancel` join
   `DOMAIN_LIFECYCLE_KINDS` so unenroll/move from a dead domain can run.
3. **`cm data purge-status|purge-resume|purge-cancel --domain NAME`.**
   Cancel is allowed only while `deleting`. If canonicals are already gone,
   `--accept-partial` unsticks `deleting` and does not restore facts.
4. **`reconcile_inactive_mirrors`** covers tombstoned, superseded, expired, and
   a missing canonical with authoritative inactive registry state. Supersession
   installs/verifies the replacement mirror first, then drops the old pointer.
5. **Reactivate** only from valid inactive v3 (`expired|superseded`) with a real
   body. Tombstone stubs use `cm canonical resurrect STEM --file NEW_BODY`
   through the full upsert pipeline; `tombstone_delete` is in the same transact.
6. **All-plugin-data fence** at
   `<config-root>/consolidate-memory-purge/<purge-id>.json`, outside both
   deletion roots:
   `planned → mirrors-revoked → plugin-data-deleting → canonical-data-deleting
   → verified → complete`. The next invocation resumes. Success only when every
   intended path is absent.

## Alternatives

- Unenroll after rmtree. Rejected: a crash leaves enrolled members of a
  deleted domain.
- Keep tombstone-only ack. Rejected: superseded/expired stayed in recall.
- In-tree resume file under plugin-data. Rejected: rmtree deletes it.

## Consequences

Positive: a purged domain has no enrolled members; pull will not recreate its
canonicals; a forget stub cannot become an active fact.

Negative: cancel does not undelete already-removed canonicals (documented).

## Revisit trigger

Reopen for eager `cm forget --propagate`, or if a second independent user
needs verified fleet-wide erasure as a 1.0 claim.
