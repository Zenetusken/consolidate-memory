# Evidence-clock stamps — zero-read windows that survive mirror refreshes

**Status:** shipped (this PR). **Scope:** `sync_global.py` (`_as_mirror`, `run()`, `promote()`,
`fleet_utility`) — the first increment of the audit's enhancement program (signal-sufficiency
lens, P2). **Supersedes** the mtime-clock rule stated in
`docs/index-usage-and-budget-ladder.spec.md` §C4 for MIRRORS (authored facts keep mtime — an
author edit legitimately resets their clock; `demotion_candidates` excludes mirrors, so local
demotion is untouched).

## The measured problem (audit F9, verified PARTIAL)

`fleet_utility`'s per-canonical probative windows are mtime-gated (`window start ≥ mirror
st_mtime`) and a STALE refresh rewrites the file. The refutation half first: **adoption does NOT
reset clocks** (`_as_mirror` strips `projects:`, so a new holder never re-writes other mirrors —
verified). But any *text* delta does, including a pure `description:` hook tweak — measured red on
the pre-fix tree: one probative window accrued, one description-only edit + `--pull`, **windows
1 → 0 fleet-side**. With `_DEMOTION_MIN_WINDOWS = 3` and dreams at arc boundaries, a canonical
edited faster than three windows accrue can **never** converge zero-read evidence — the
"undercounts, the safe direction" note was correct per-event and starvation-blind in aggregate.
The clock granularity is wrong, not the instinct: "the fact's CONTENT changed" (old zero-reads
don't indict new content — reset is right) is not "the mirror file was mechanically rewritten"
(evidence must persist).

## Design: a content-lineage clock stamped into the mirror

`_as_mirror(text, name, since="", body_hash="")` gains two script-owned stamps under the same
`metadata:` anchor as `global_ref:` (the frontmatter-scoped strip widens to the `global_ref`
prefix so re-stamping stays idempotent; `_is_mirror` keys on `global_ref:` only — the smoke-pinned
producer↔recognizer round-trip is untouched):

```yaml
metadata:
  global_ref: <name>
  global_ref_since: <ISO — when this mirror's current content-lineage began>
  global_ref_body: <sha1-12 of _body(canonical) — the lineage key, BODY-only by design>
```

`run()` computes the carry at classify time, so `cur == want` keeps its exact in-sync shape:

- current mirror's `global_ref_body` == new hash and its `since` parses → **carry** `since`
  (description/stacks/provenance tweaks refresh the text without resetting the clock);
- legacy/garbled stamps but the *body* matches → `since` = the mirror file's **mtime** (the
  migration wave: the fleet's existing evidence age is preserved, not restarted from zero;
  reported as `restamped N` in the RESULT line);
- body genuinely changed (or brand-new pull) → `since` = **now** (new lineage — reset is correct).

`promote()` mints the origin mirror with a fresh stamp; the Probe-K byte-identical follow-up-pull
invariant holds (the pull carries the promote-time `since` — same body hash).

**Consumer:** `fleet_utility` counts windows against `parse(global_ref_since)` when present and
parseable, else `st_mtime` (legacy fallback — pre-upgrade behavior, undercount-safe; a garbled
stamp fails toward less evidence). Per-canonical `fallback_nodes` (additive `--json` key) keeps
evidence provenance visible. The stamps' only *reach limit*: a mirror minted through the
no-`metadata:`-block fallback (`# global_ref:` comment form) carries no stamps and stays on the
mtime clock — real facts all carry `metadata:` per the documented schema.

## What this deliberately does NOT do

No decay constants or fitted half-lives (nothing measured to calibrate against); no cycle-record
schema change; no change to any demotion veto, `_KEEP_RE`, miss-scar, or report-then-apply
posture — this only makes NEGATIVE evidence accrue truthfully, and every downstream safety valve
consuming it is unchanged. Failure cost of a wrong stamp is a candidate *surfaced* for judgment,
never an action.

## Acceptance gates

1. RED pre-fix (measured): description-only edit wipes windows 1 → 0. GREEN post-fix:
   description-only edit **preserves** (1); a BODY edit **resets** (0) — both pinned in smoke.
2. The `_is_mirror(_as_mirror(...))` round-trip + idempotence pins, Probe K's byte-identical
   follow-up pull, and the whole existing suite stay green (stamps are carry-stable).
3. Legacy migration pinned: an unstamped mirror's first refresh seeds `since` from its mtime
   (windows preserved across the upgrade), and reports `restamped`.
4. Full gates: smoke + sim + mypy + manifests.
