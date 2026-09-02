# 021. Journal terminal cleanup and split schemas

Status: Accepted
Extends: ADR 006, ADR 010, ADR 017

## Context

ADR 017 unlinks `.cm-trash-*` and recovery blobs *after* marking the journal
`complete`. A crash or `OSError` in that window left forgotten bodies on disk
while recovery treated the op as done. `connect_journal()` ran the full
registry `SCHEMA_SQL`, so `journal.sqlite` was a second control-plane database.
Schema migrations ran before mutation locks. Temp files used `os.getpid()`,
which collides across PID reuse. `compact_journal` redacted payloads but never
bounded row count. `set_canonical_status` hashed the live path after
transforming earlier bytes.

## Decision

1. **Terminal phase.** After registry COMMIT the journal becomes
   `committed-cleanup-pending`. Trash, recovery blobs, and temps are deleted
   and verified gone (the delete/replace parent dirs are fsynced — best-effort,
   process-crash durability, not power-loss). Only then `complete`. Cleanup
   helpers return `{deleted, missing, errors}` and never swallow `OSError`.
   Recovery retries `committed-cleanup-pending` without republishing.
2. **Split connections.** `connect_base` (no DDL). `connect_registry` takes
   `locks/schema.lock`, inspects `PRAGMA user_version`, runs one transactional
   migration. `connect_journal` creates only `journal` + `journal_metadata`.
   Leftover registry tables in an old `journal.sqlite` are ignored, never used.
3. **Temps** are `{name}.tmp-{op_id}` / `{name}.restore-{op_id}`, never PID.
4. **Compact** collapses complete/abandoned rows older than 90 days to a
   receipt (`op_id`, kind, terminal status, timestamps, hash digests). Pending,
   failed, conflicted, and cleanup-pending rows are not compacted.
5. **Abandon** refuses while trash or recovery remains unless `--accept-fs`.
   Rollback of a post-commit op is refused; a failed restore does not mark
   abandoned.
6. **Snapshot-then-transform** for canonical status (and migrate keep-existing
   rewrite): `expected_revisions` is the hash of the bytes that were
   transformed.

`cm journal cleanup [--scan-all-stores] [--apply --confirm journal-cleanup]`
retries leftover cleanup and scavenges orphan/terminal trash/recovery. It
never unlinks pending, failed, or conflicted complete-old preimages.

## Alternatives

- Keep unlink-after-complete (ADR 017). Rejected: the privacy window is P0.
- Drop leftover registry tables in journal.sqlite. Rejected: a swapped file
  would lose data; ignore is safer.
- Power-loss durability on every FS. Rejected: we fsync file + parent dir at the
  load-bearing sites (commit-trash, secure-unlink, restore, publish, delete-rename)
  and document POSIX process-crash durability as the narrow guarantee (the WSL/
  Windows mutation contract is ADR 016; the durability claim itself lives here).

## Consequences

Positive: a successful forget leaves no original body in trash or recovery; a
cleanup failure is never `complete`; two first-run processes cannot race DDL.

Negative: an operator may see `WriteRefused: committed cleanup pending` after
the logical mutation has committed; `journal retry` / next transact recovers it.

## Revisit trigger

Reopen if journal inventory at 1M rows still cannot be paginated (Phase 5).
