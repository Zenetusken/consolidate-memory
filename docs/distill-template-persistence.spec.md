# Distill-template persistence — the workflow vertical's Phase A (W-A)

**Status:** shipped (this PR). **Scope:** `distill_scan.py` (`scan` + `inject_into`) +
`memory_status.py` (`Distill` TypedDict, cap mirrors, validator) + the SKILL/harness-map
schema blocks. The fifth increment of the audit's enhancement program (workflow-distillation
lens, W-A of the W-A/W-B/W-C ladder — deliberately shaped like the shipped A/B/C budget
ladder: instrument, then aggregate read-only, then dormant policy behind an evidence gate).

## The problem (the pre-Phase-A usage mistake, byte for byte)

`scan()` computes template-level evidence every dream — recurring command classes and chains
with counts and day-spreads — and `inject_into` persisted only the COUNTS (`n_recurring`,
`n_chains`). The templates themselves died with the scan; transcripts rotate in weeks. So
nothing fleet-level ("`smoke && mypy` recurs in 4 of 6 nodes" — the strongest possible
promotion evidence, the workflow analog of the cascade's G2.3), nothing longitudinal ("this
template has recurred in 6 consecutive windows"), and no cross-node decline-dedup (a workflow
declined in project A is naively re-proposed from project B) could ever be built. W-B
(`--workflows`, the `--utility` twin) and W-C (the registrar + adoption loop) are strictly
blocked on this. The RED baseline is the contract itself: the pre-change scan-contract pin
asserted the exact output key set without `used`, and the record block carried no rows.

## Design

- **Additive `Distill` keys** (all `total=False`; legacy records render unchanged):
  `top` (≤12 `{t,n,d}` template rows), `top_chains` (≤8 `{t:[a,b],n,d}`), `used` (≤12 `{a,n}`).
  Compact single-letter row keys — the block is appended to every dream's log line forever.
- **Script-truth only**, injected by the existing `--from <scan> --into <seed>` path — the
  model never authors a row (the `n_recurring: 47` hand-mirror lesson, row edition). The
  validator length-backstops each list against `_DISTILL_PERSIST_CAP`/`_DISTILL_USED_CAP`
  (memory_status mirrors of the producer constants, cross-module smoke-pinned like
  `_DISTILL_CAPS`).
- **Privacy boundary unchanged**: rows are projected from the scan WITHOUT `sample` — samples
  carry raw command text (machine paths, repo names) and stay display-only; templates are
  already the safe tier (`_seg_template` drops absolute paths/branch-likes/flag values and
  screens every emission through `_looks_secret`). Pinned: no `sample` string can reach the
  durable record.
- **The `used` adoption tally** (new scanning branch): Skill `tool_use` invocations by name,
  window-scoped by the same per-line instant rule Bash commands use. This is the denominator
  W-C's lifecycle quadrant needs (invoked + raw templates declining = a working distillation;
  not-invoked + templates persisting = a failed one) — it must accrue NOW, per-window, or be
  lost to rotation, the identical argument that shipped usage Phase A observe-only ahead of
  Phase C. Undercount bias pinned up front: a skill can fire without a Skill tool_use in every
  harness path — zero invocations is absence of evidence, never sole grounds.
- **Consumer trap, designed against up front** (recorded in harness-map): consecutive dreams
  scan overlapping ~30-day windows — summing a node's rows ACROSS records double-counts. W-B
  must aggregate from the latest record per node; the persisted `window` string proves what
  was aggregated.

## Reach limits (seams-review findings, recorded — not chased)

- The documented weak-password firewall boundary (a short, no-digit, single-case value passes
  `_looks_secret`) now produces a DURABLE template where it was display-only — durability is the
  only delta; the boundary itself is the module-doc's pre-existing accepted gap.
- `used` counts the current dream's OWN Skill invocations (no dream-span exclusion — usage Phase A
  has one, this v1 does not). Observe-only today; **W-C's adoption denominator must dream-span
  exclude** before any lifecycle judgment consumes it.
- Decline-dedup lineage is ARTIFACT-NAME-granular (`proposed`/`created`), not template-granular —
  the structured template↔artifact link is W-C's registry `templates` field, by design.
- Longitudinal recurrence reads PRESENCE across records (never sums — the same overlap rule).

## Staging

Observe-only by construction: nothing reads the new keys yet (renderers ignore unknown keys —
suites confirm). W-B ships next as a read-only `sync_global --workflows` lens over the
accrued rows; W-C's registrar/adoption loop stays behind its own evidence gate.

## Acceptance gates

1. Round-trip pinned: a 15/10/14-row scan persists 12/8/12 projected rows, sample-free, with
   the model's `verdict` preserved and `n_recurring` still counting the FULL scan.
2. The `used` tally counts Skill invocations window-scoped (pre-window excluded), end-to-end
   from a fixture transcript.
3. Cap mirrors smoke-pinned equal; the validator warns on an over-cap row list; the SKILL
   schema block and scan-contract pins updated in the same commit (the schema-pin discipline
   fired on both during implementation, as designed).
4. Full gates: smoke + sim + mypy + manifests.
