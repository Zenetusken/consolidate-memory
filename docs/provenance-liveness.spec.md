# Provenance liveness — the denominator finally tracks live topology (P4)

**Status:** shipped (this PR). **Scope:** `sync_global.py` (the shared slug resolver, the edge
classifier, `fleet_utility`'s live-basis columns, `--gc --edges [--apply]`). The seventh
increment of the audit's enhancement program (signal-sufficiency lens, P4).

## The measured problem (live fleet, 2026-07-11, read-only)

`projects:` provenance is append-mostly and accrues ghosts. Measured: **76 edges, 16 (21%)
UNRESOLVED** — exactly the two known dead test fixtures (`cmtest_x` ×12, `cm-prop-test` ×4),
zero store matches each — while **≈713 of ≈3420 fleet-tax tokens (20%) were ghost-attributed**.
Every consumer of the denominator was drifting on corpses: `fleet_tax` vs the warn-only advisory,
`--utility`'s evidence table, `--network`'s minds/edges, and the deferred CLAUDE.md graduation
lane is explicitly gated on this cleanup. The existing dead-edge report is single-project-scoped
(only the triggering node's absent mirrors), so fleet-wide ghosts were never enumerated in one
place, and no prune lever existed at all.

## Design — classify honestly, prune only the provable, self-healing

- **One resolver** (`_slug_matches`, factored from the train-review-fixed `_mind_unresolved`,
  which now delegates — no second copy): normalize the holder token in SLUG space (every
  non-alnum → `-`, the `slug_for` rule) and match store-holding dirs under `~/.claude/projects`
  by equality or `-`-suffix.
- **The edge classifier** (`_classify_edge(holder, stem)`):
  `live` — ≥1 matching store holds `<stem>.md` as a managed mirror (it pays the pointer tax);
  `stale` — exactly one match, mirror absent (the old dead-edge case: real project, dropped
  mirror — gc'd frozen, evicted by hand, or pre-dating the fact);
  `unresolved` — ZERO store matches (deleted or renamed project — the ghost class);
  `ambiguous` — multiple matches, none holding (can't tell which store was meant — treated
  conservatively, never prunable).
- **`fleet_utility`**: per-canonical `holders_live/stale/unresolved/ambiguous` (additive keys,
  emitted when non-zero) and a payload/report-level **`fleet_tax_live`** = Σ pointer × LIVE
  holders — printed BESIDE the provenance upper bound, never replacing it (the advisory's
  documented denominator stays the upper bound until the advisory itself is re-derived — a
  separate, reviewed change).
- **`--gc . --edges`**: the fleet-wide UNRESOLVED report — every ghost edge with its resolution
  attempt shown. **`--gc . --edges --apply`** removes ONLY unresolved holder tokens from
  canonicals' `projects:` lists (atomic via `_atomic_write_text`; the `_record_provenance` D-2
  concurrency stance inherited). `stale`/`ambiguous` are NEVER prunable — a renamed store also
  matches nothing it shouldn't, and a wrongly pruned edge **self-heals**: that project's next
  `--pull`/`--promote` re-adds it via `_record_provenance`, bounding the failure cost to a
  temporary undercount (the documented-safe direction). This *upgrades*, not violates, the
  "dead-edge provenance is reported, not auto-pruned" rule: still never automatic — the report
  is finally fleet-complete and the confirmed-apply lever exists. Refuses when
  `~/.claude/projects` is absent (nothing claimable ≠ everything ghost — the gc mass-delete
  guard's sibling).

## Acceptance gates

1. The design doc's own stated acceptance, on the LIVE fleet (read-only classify): the two known
   ghosts classify `unresolved`; the three live nodes classify `live` (incl. `Doc_Flo`, the
   underscore case); nothing classifies `ambiguous` on the real fleet today.
2. Sandbox E2E: all four classes constructed; `--edges` reports exactly the ghosts;
   `--edges --apply` removes ONLY their tokens (other holders byte-verbatim, canonical BODY
   untouched, write atomic), and a subsequent pull from a live project re-adds its own edge
   (the self-heal pinned).
3. `fleet_tax_live` ≤ `fleet_tax` always; the advisory comparison unchanged.
4. Full gates: smoke + sim + mypy + manifests.
