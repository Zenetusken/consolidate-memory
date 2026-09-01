# 017. Journal complete-old via trash

Status: Accepted
Supersedes: the complete-old *implementation* claims of ADR 010 (the typed-op
schema is unchanged)

## Context

v0.3.3 `transact` published destinations then unlinked deletes sequentially.
If deletion A succeeded and B failed, dest preimages were restored but A's
body was gone. Destination restore overwrote concurrent edits. Create-mode
used `O_EXCL` then write, and treated a zero-byte dest as the plugin's own
incomplete inode. `recover_pending` published files then opened a new
registry transaction. Journal payloads stored dest bodies as `bytes_b64`.

ADR 010 already promised complete-old or complete-new, never mixed.

## Decision

Deletes are `os.rename` into a same-directory `.cm-trash-<op-id>-<n>` file
(mode `0600`). Permanent unlink happens only after registry COMMIT and
journal `complete`. Partial rename rolls already-trashed entries back.
`EXDEV`/`EPERM` fail closed.

Dest snapshots live under `plugin-data/recovery/<op-id>/` as `0600` blobs.
New journal rows record hashes and blob paths, never fact bodies. Legacy
`bytes_b64` rows still restore.

Restore a dest only when its current hash equals the transaction's published
hash (or the dest is absent). A concurrent edit is quarantined, then the
original snapshot is written onto the now-free path.

Create-mode publishes with same-directory `os.link`. No empty visible inode.
A no-hardlink filesystem falls back to `O_EXCL` + full write in-process
without the empty-unlink recover heuristic.

`recover_pending` applies registry ops in an open savepoint, then trashes
and publishes, then COMMITs. Source drift becomes `conflicted` (not silent
`pending`). Registry failure after files are moved compensates and marks
`conflicted`.

## Alternatives

- Preflight-then-unlink. Rejected: first unlink is still unrecoverable.
- Trash only under plugin-data/recovery. Rejected: `EXDEV` when native is
  another filesystem; copy is not complete-old.

## Consequences

Positive: multi-delete, dest-edit, and recover match ADR 010's promise for
new operations.

Negative: short-lived `.cm-trash-*` siblings. Historical completed rows are
redacted by `cm journal compact` (also run from `cm data compact`).

## Revisit trigger

Reopen when a native-Windows exclusive-create primitive is required.
