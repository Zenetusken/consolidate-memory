# 004. Stable project identity

Status: Accepted

## Context

Canonical `projects:` provenance records a sanitized project basename. Fleet
reconciliation infers the native store from a lossy slug and suffix match.
That cannot distinguish `/work/client-a/api` from `/work/client-b/api`, a
rename, the same repository under two profiles, two clones in different
trust domains, worktree paths, or punctuation-normalization collisions.

The source already documents overmatching and ghost provenance. Identity is
a P0 release blocker for a heterogeneous fleet.

Constraints: human-facing reports still need readable labels. Markdown fact
bodies stay user-inspectable. The registry is operational state and belongs
under `${CLAUDE_PLUGIN_DATA}` (ADR 006) because plugin data is deleted on
final uninstall unless `--keep-data`. Stdlib `hashlib` / `uuid`. 1.0 HOLD.

## Decision

We will use an internal immutable project ID:

```
project_id = SHA-256(
    schema_version
    + profile_id
    + domain_id
    + normalized_git_common_dir
    + optional_remote_fingerprint
)
```

Non-Git projects get a UUID5 bound to
`schema_version + profile_id + domain_id + normalized_root` (stable, not
random). A rename updates registry metadata (`display_name`, `current_root`,
`native_memory_dir`), not the ID. Same basename, two profiles, two domains,
and two clones are distinct.

The registry (not a rewritten `projects:` list on each canonical) is
authoritative for holder edges. Human-facing frontmatter may keep a display
label. `cm doctor` shows `project_id`.

## Alternatives

- **Keep basename + suffix match, warn on collision.** Rejected: collisions
  are silent cross-talk, not a warning-shaped problem.
- **Git remote URL as the ID.** Rejected: two clones of the same remote in
  different domains *must* be distinct; remote is a fingerprint, not the key.
- **Store the ID in every canonical's `projects:` list.** Rejected: that is
  the rewritten-holder-list problem; edges live in the registry.

## Consequences

Positive: rename, profile split, and same-basename repos stop sharing
identity. Holder queries become exact.

Negative: a moved repo whose git common dir path changed looks like a new
project until the registry records the move (path is input to the hash).
Operators reconnect via `cm doctor` + registry update rather than silent
suffix match. Remote fingerprint is optional so path-only repos still work.

Neutral: `slug_for` remains the *Claude projects-directory* encoding, not
our identity. 1.0 remains HOLD.

## Revisit trigger

Reopen if a hosting layout changes git common-dir paths on every fetch (e.g.
content-addressed checkouts), if UUID5-bound non-Git roots collide across
bind mounts, or if Claude exposes a stable native project ID we should adopt.
