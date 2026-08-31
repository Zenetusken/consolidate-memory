# 005. Mirror conflict protocol

Status: Accepted

## Context

Claude Code permits users and Claude to edit auto-memory Markdown, and
writes a native `modified` timestamp on frontmatter-bearing files. A managed
mirror is still a native, writable file. Today's pull computes the desired
representation from the canonical and rewrites a "stale" mirror. It
distinguishes "different from canonical" more reliably than "outdated cache"
vs "legitimate local edit." Silent overwrite of a local edit is a P0.

Constraints: existing STALE-refresh probes change the canonical while the
mirror body still matches the last pull — those must keep refreshing (Probe
C). Semantic equality must ignore volatile metadata (`modified`,
`mirrored_at`, holder provenance, usage timestamps). Unknown frontmatter
survives a rewrite. A `FileChanged` hook is optional early warning, not the
guarantee. SessionStart stays advisory-only. 1.0 HOLD.

## Decision

Each managed mirror carries `base_revision` (semantic hash originally
mirrored), `canonical_revision` (last observed canonical semantic hash), and
a semantic hash of the current local body.

Classifier (never overwrite a divergent local body):

| Local body | Canonical body | Action |
|---|---|---|
| Unchanged | Changed | Refresh |
| Changed | Unchanged | Stop; offer fork or promote-back |
| Changed | Same result | Restamp |
| Changed | Differently changed | Conflict; never overwrite |
| Corrupt/missing base | Any | Quarantine and repair |

Legacy mirrors that only have `global_ref_body` (body hash) use that as a
body-level base: an unchanged body still refreshes (description/pointer
drift — Probe C); a changed local body with an unchanged canonical body
stops; both changed differently conflict.

Shipped commands: `cm conflicts`; `cm resolve <fact> --keep-canonical`;
`cm resolve <fact> --fork-local <new-name>`; `cm resolve <fact> --promote-local`;
`cm repair-mirror <fact>`.

Pull itself is the guarantee. Extra hooks do not substitute.

## Alternatives

- **Treat every mirror as canonical-owned; document "don't edit".** Rejected:
  Claude and users *will* edit; the contract says they may.
- **Three-way only when `base_revision` is present; legacy always refresh.**
  Rejected: that leaves today's silent overwrite for the entire pre-v2
  fleet. Body-hash fallback is the dual-read compromise.
- **FileChanged hook as the lock.** Rejected: the hook can miss; pull must
  refuse overwrite even with no extra hooks.

## Consequences

Positive: a local edit survives the next dream. Conflicts are a queue, not a
lost body.

Negative: a description-only local edit on a *legacy* mirror (body-hash base)
still refreshes — same as today — until the mirror is rewritten with a
semantic `base_revision`. Operators resolve via `cm conflicts`.

Neutral: `present(local)` (project-authored same-name shadow) is unchanged.
GC still only touches recognized managed mirrors. 1.0 remains HOLD.

## Revisit trigger

Reopen if native `modified` updates cause false conflicts after semantic
exclusion, if unknown-frontmatter preservation drops a field Claude later
requires, or if conflict volume on a real fleet needs a batch resolver.
