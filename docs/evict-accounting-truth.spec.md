# Evict accounting truth — plan once, measure freed, refuse gainless

**Status:** shipped (this PR). **Scope:** `sync_global.py` `run()` + the `--evict` valve.
**Provenance:** a 2026-07-10 end-to-end audit of the cross-project layer (multi-agent finders +
adversarial verifiers, every finding reproduced in a HOME-sandboxed fixture) found four defects
sharing one root. All five repro probes ran RED against the pre-fix tree before this design was
implemented (`5/5 defects PRESENT`), and flip green with it — the measure-first gate.

## The measured defects (pre-fix tree, ceiling C = INDEX_CEILING_TOKENS = 3840)

- **F1 — mirror evict self-defeats.** `--pull --evict=<mirror>` was accepted (and the
  EVICT-TO-RECEIVE table *listed* mirrors as candidates). Evicting a mirror of a live relevant
  canonical makes it MISSING in the same pass; the alphabetical pull loop re-pulled it into the
  freed room and the held global stayed held. Measured: `evicted-mirror-re-pulled=True,
  held-global-landed=False, "held 1"`. Opposite sort order: the evictee itself becomes held →
  the two oscillate on every future pull.
- **F2a — phantom freed breaches the hard ceiling.** `freed` was `est_tokens(_pointer_line(...))`
  — DERIVED from frontmatter, never measured from the store's real `MEMORY.md`. Evicting a fact
  with NO index line credited ~33 phantom tokens (`_remove_index_pointer`'s `False` return was
  ignored), `running_idx` under-counted, and the pull landed the real index at **3857 > 3840** —
  the M1 ceiling, the layer's one hard budget guarantee, breached by its own release valve. The
  authored fact was deleted for it.
- **F2b — the best candidate wrongly refused.** A hand-written fat real line (~74t) judged by its
  lean derived pointer (~7t): `"frees only ~7 tok"` refusal for an evict that would actually free
  10× the needed room.
- **F3 — authored fact destroyed for zero gain.** The `held_pre` pre-scan and `_evict_frees_enough`
  fit-check evaluated against the STATIC seeded index while the pull loop ACCUMULATES
  alphabetically (the old `:651` comment claimed "SAME predicate" — same function, *different
  argument*). Measured fixture (fill=11t, held=25t, freed=19t, seed=3829): fit passed statically
  ((3829−19)+25 = 3835 ≤ 3840), the loop pulled the filler first, the target global was re-held,
  and the evicted authored fact — which, unlike a mirror, has **no canonical to re-pull it** —
  was gone. A/B: the identical global set landed with and without the evict. Guard-3
  ("never a destructive op that gains nothing") violated.
- **F4 — stale-refresh deltas untracked.** A STALE refresh whose canonical description grew
  rewrote the index line (+22t measured) but `running_idx` never learned; a later MISSING fact
  was pulled on the stale figure and the real index landed at **3862 > 3840**. Bounded per
  refresh by the 88-char hook cap (≈±22t), cumulative across same-pass refreshes.

## Design: classify → plan → execute (one decision source)

The root of F1/F3/F4 is that run() made pull/hold decisions in three places with three different
index models. The fix is structural, not point patches:

1. **Classify (no writes).** One pass computes every fact's status exactly as before
   (irrelevant / MISSING / present(local) / in-sync / STALE-mirror).
2. **Plan (`_plan_pull`, pure, smoke-pinned).** Replays the loop's accounting IN ITERATION
   ORDER over `(name, status, cost_new, cost_old)` items: a MISSING pull grows the index by
   `cost_new − cost_old` (cost_old = the REAL existing line for that stem, usually 0) unless
   that nets past the budget (→ HELD); a STALE refresh ALWAYS runs and contributes its real
   pointer delta (closes F4). Returns `{"pull", "held", "end_idx"}`.
3. **Execute.** The write loop consults plan membership — it never re-decides. `held_facts`
   IS `plan["held"]`.

The `--evict` gate then becomes an **A/B replay of the actual plan**, not a static predicate:

- `freed = _index_line_cost(index_text, evict)` — MEASURED from the store's real `MEMORY.md`
  line via the `](stem.md)` anchor (the `_ensure_index_pointer`/`_remove_index_pointer` rule).
  `0` → refuse (*"evicting frees NOTHING"*; closes F2a). A fat hand-written line is credited at
  its real cost (closes F2b).
- A managed MIRROR is refused as evictee (*the lever for a mirror is the GLOBAL store:
  demote/delete the canonical, then `--gc`*; closes F1). The candidates table offers
  **authored facts only**, with measured real-line costs.
- Gain gate (Guard-3, now enforced by construction): `plan_with = _plan_pull(items,
  seed − freed, …)`; refuse unless `plan_with["pull"]` strictly exceeds `plan["pull"]` —
  i.e. the destruction demonstrably lands ≥1 additional held global (closes F3). The refusal
  prints both plans (measured A/B, no vibes).
- On an accepted evict, the executed plan IS `plan_with` — the gain check and the writes can
  never diverge (statuses are frozen at classify time; a same-stem global freed by evicting a
  local *shadow* re-enters on the NEXT pull, deliberately — the plan the gate approved is the
  plan that runs).

`_evict_frees_enough` is superseded by the gain gate and removed (its smoke pins are replaced by
`_plan_pull`/`_index_line_cost` pins). `_would_net_grow` is unchanged — `_plan_pull` consumes it,
keeping the v0.1.38/v0.1.66 pins intact.

## Contract / compatibility

- CLI surface unchanged (`--pull --evict=FACT [--allow-net-grow]`); no schema keys, no new flags.
- Behavior deltas, all in the REFUSE direction or accounting-correctness: mirror evictees refused;
  unindexed evictees refused; gainless evicts refused; fat-real-line evicts now correctly
  accepted; stale-refresh deltas now counted (a pull near the ceiling may hold where it previously
  breached). Backward-compatible ⇒ **patch** under the versioning policy.
- The known est-granularity mix (whole-file seed + per-line deltas, the `_node_tokens` ceil note)
  is unchanged and now confined to `_plan_pull`'s docstring.

## Acceptance gates (all must hold)

1. The five audit repro probes (smoke `v0.1.73` block + sim Probe V) — RED pre-fix, GREEN post-fix.
2. Existing suites untouched-green: `python3 tests/smoke.py`, `python3 tests/simulate_accumulation.py`
   (Probes R/R2 evict refusal messages unchanged), `mypy --config-file mypy.ini`,
   `python3 tests/validate_manifests.py`.
3. The evict happy path — previously **zero in-repo coverage** (smoke:1453 conceded it ran
   "out-of-band") — is now pinned end-to-end in the sim (authored evictee freed → held global
   lands → index ≤ ceiling).
