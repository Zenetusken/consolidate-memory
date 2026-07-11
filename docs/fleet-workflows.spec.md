# Fleet workflows — the `--utility` twin over the W-A distill rows (W-B)

**Status:** shipped (this PR). **Scope:** `sync_global.py --workflows [--json]` (+ `cm workflows`,
+ a SKILL Phase-5 distill-gate sub-step) and `memory_status.distill_history` (the `usage_history`
twin). The sixth increment of the audit's enhancement program — W-B of the W-A/W-B/W-C ladder;
consumes the rows W-A (`docs/distill-template-persistence.spec.md`, v0.1.82) persists.

## The blind spot

Before this, no view existed in which *"`smoke && mypy` recurs in 4 of 6 nodes"* was a computable
sentence — per-node a workflow may not even clear the ranking noise floor, yet fleet-wide breadth
is the strongest possible promotion evidence (the workflow analog of the fact cascade's G2.3
"name ≥1 existing other project"). And the distill gate's decline-dedup rule ("previously DECLINED
needs materially NEW evidence") read only the current node's log — the same workflow could be
re-proposed fresh from every project.

## Design — a read-only lens; judgment stays with the model

- **`distill_history(store)`** (memory_status, beside its twin): latest ROW-carrying `distill`
  block per node (**latest-record-only** — the W-A consumer trap: consecutive dreams scan
  overlapping ~30-day windows, so summing across records double-counts; the persisted `window`
  proves coverage) + the FULL verdict/proposed/created lineage (dispositions accumulate, they
  don't overlap). Same `iter_cycle_log` reader, tail cap, guarded-skip posture.
- **Node set = `_log_nodes()`**: every store holding a cycle log — deliberately NOT
  `_network_nodes()` (holding a mirror is orthogonal to having dreamed; the documented-divergence
  discipline).
- **The join**: exact template-string equality across nodes' latest rows. Per template/chain:
  breadth (`nodes`), summed latest-window counts, max day-spread, per-node breakdown; `fleet` =
  ≥2 distinct nodes — structural like `MIN_RECUR`, nothing fitted (no measured base rate exists
  to fit against). Under-joining from cross-node template drift is the safe direction (missed
  candidates, never fabricated ones); the **head-signature families** panel is the mitigation —
  a near-join HINT (same tool, drifting flags) whose counts are never merged (a merged count
  across distinct templates would be a fabricated number).
- **Lineage panel**: every node's dispositions — a decline anywhere blocks a naive re-propose
  everywhere (the materially-new-evidence rule, finally fleet-checkable). **Adoption panel**: the
  W-A `used` tallies summed latest-per-node — the W-C quadrant's numerator (zero is absence of
  evidence, never disuse — the pinned undercount bias). **Inventory panel**: `~/.claude/skills`
  + `~/.claude/commands` names only — a name match is a hint; semantic-coverage judgment stays
  with the MODEL (the degenerate-pass rule: a string match must never become a verdict).
- **Cold-start honesty**: `nodes_reporting` counts nodes whose latest block carries rows
  (v0.1.82+); the live first run correctly reads `0/7 reporting` while the lineage panel already
  renders real historical dispositions. Fleet absence is never inferred from missing
  instrumentation. Cued (Phase-5 dream flow); read-only forever by design — it is a lens, like
  `--network`/`--utility`.

## Acceptance gates

1. Sandbox join pinned: two nodes with W-A rows — fleet flag at ≥2 nodes, the stale record's
   inflated count IGNORED (latest-per-node), single-node rows unflagged, families grouped without
   count-merging, adoption summed, the declined disposition surviving in the lineage.
2. READ-ONLY over every store (hash-verified); JSON-safe payload; absent-log honest-empty shape.
3. Full gates: smoke + sim + mypy + manifests; live read-only run renders the honest cold start.
