# 006. Transactional control plane

Status: Accepted

## Context

Single-file writes are already atomic (`os.replace`, exclusive `os.link`).
A promotion still touches many files (canonical, provenance, origin mirror,
origin index, rename cleanup, cycle state) and is explicitly not
crash-atomic. Concurrent provenance updates can drop an entry. The global
store has no lock. The fleet usage ledger accepts torn appends. These are
P0 for a fleet that dreams from more than one session.

`${CLAUDE_PLUGIN_DATA}` is persistent plugin data that survives plugin
updates and is deleted on final-scope uninstall unless `--keep-data`.
Canonical user facts must not live there. Markdown remains the source of
fact *content*. Zero third-party dependencies; `sqlite3` is stdlib. WAL
locks can misbehave on network/FUSE filesystems (Phase 6, not a pip reason).

## Decision

Markdown stays the fact-content plane (domain-scoped directories under
`<config-root>/consolidate-memory/domains/<domain-id>/facts/`).

SQLite under `${CLAUDE_PLUGIN_DATA}` (`<config-root>/plugins/data/consolidate-memory/`)
is the control plane: project registry, stable fact IDs, domain membership,
holder edges, base/canonical revisions, tombstones, operation journal,
usage/workflow aggregates, migration state.

Every cross-store mutation:

1. acquire the domain/global lock;
2. acquire project locks in sorted stable-ID order;
3. record expected revisions;
4. write a journal operation;
5. prepare same-directory temporary files;
6. verify sources have not changed;
7. publish atomically;
8. commit the registry transaction;
9. mark the journal complete;
10. recover or roll forward incomplete operations on the next command.

`cm canonical upsert` is the sole canonical writer (schema, secret and
confidentiality policy, domain auth, applies, link validation, exact index
projection, transactional canonical + origin mirror + index + registry).
The global `MEMORY.md` is a generated catalog. Intentional forget writes a
tombstone (`status`, `deleted_at`, `reason`, `replacement_id`, `grace_until`);
absence alone is not deletion.

A control-plane-only restore must not invent fact bodies.

## Alternatives

- **Markdown-only with better `os.replace` sequencing.** Rejected: that is
  today's primitive; it does not give crash recovery or a lock.
- **Put fact bodies in SQLite.** Rejected: loses inspectable Markdown; plugin
  data deletion would destroy user knowledge.
- **A pip dependency (SQLAlchemy, filelock).** Rejected: zero-runtime-deps is
  a product invariant; `sqlite3` + `fcntl` are enough on POSIX.

## Consequences

Positive: interrupted promotions become recoverable; concurrent dreams
serialize on the domain lock; holder edges stop living in rewritten
frontmatter.

Negative: SQLite on FUSE/network FS is a known soak item. Uninstall without
`--keep-data` drops the registry (facts on disk remain; edges rebuild from
mirrors + dual-read). Dual-write to the legacy `~/.claude/memory` path
continues until migrate completes.

Neutral: `promote()` remains as a compatibility entry that journals through
the same writer. 1.0 remains HOLD.

## Revisit trigger

Reopen if a non-POSIX lock is required for a supported Windows-native path,
if uninstall data-loss surprises operators despite `--keep-data` docs, or if
journal replay is not idempotent under a new mutation kind.
