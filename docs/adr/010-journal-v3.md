# 010. Journal schema v3

Status: Accepted
Supersedes: the crash-consistency claims of ADR 006 that v0.2.1 did not meet

## Context

v0.2.1 journals dest sha256 and origin context, but `_publish_temps` still
deletes after a failed dest hash, recovery replays only fact/holder upserts,
journal `complete` can precede a durable registry COMMIT, and pull passes
`expected_revisions=None` (hash-after-lock) — a local edit between classify
and lock is overwritten.

## Decision

Journal payload v3 records, before any dest replace:

```text
origin: profile_id, domain_id, project_id, registry_state
sources: [{path, sha256}]          # never None if bytes influenced the plan
destinations: [{tmp, dest, sha256, mode}]
deletes: [{path, preimage_sha256}]
registry_ops: typed list
postconditions: dest hashes + registry assertions
```

Typed `registry_ops`: `project_upsert`, `project_domain_change`, `fact_upsert`,
`fact_status_change`, `holder_upsert`, `holder_delete`, `tombstone_upsert`,
`conflict_upsert`, `conflict_resolve`, `migration_state_set`.

Publication sequence:

1. Lock (old-domain, new-domain, global, projects — sorted).
2. Recover pending ops for this origin only.
3. Re-read → classify → plan **under lock**. `None` expected hashes are illegal
   for any file that influenced the plan.
4. Prepare temps as `0600`, flush, hash.
5. Persist the complete plan (`pending`).
6. Reverify source hashes.
7. Publish destinations (`os.replace`).
8. Verify every dest hash. Any miss → `pending` or `failed`; **no deletes**.
9. Delete only when preimage still matches.
10. Verify file postconditions.
11. Apply typed registry ops; COMMIT registry.
12. Mark journal `complete` last. A replay `ok: false` keeps pending/failed.

Crash injection (`crash_after` / `CM_CRASH_AFTER`) covers the new step names.
Recovery yields complete-old or complete-new, never mixed.

Temps are mode `0600`. Pull's expected source is the **domain canonical that
produced `want`**, not the legacy global path.

## Alternatives

- **Keep v2 and document the race.** Rejected: silent overwrite is P0.
- **Fact bodies in SQLite.** Rejected: ADR 006.

## Consequences

Positive: pull, forget, enroll, migrate, GC, purge can share one engine.

Negative: classify-under-lock holds the domain lock longer. Tests must use
two processes and a barrier, not sleeps.

## Revisit trigger

Reopen if a new mutation kind cannot be expressed as typed `registry_ops`.
