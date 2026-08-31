# 001. Empty-set judgment and targeted fact-body reads

Status: Accepted

## Context

A dream felt slow because of too many judgment beats on empty scans and because
Phase 1 sequentially Read every auto-memory fact body "to orient." The operator
constraint was explicit: no thoroughness or precision loss for a bit of speed.
Script wall-clock was not the bottleneck (stdlib over local files; `detect_stacks`
already cached after `--pull`). Phase-4 report-then-apply was out of scope.

Rigor already scaled *verification* (LIGHT inline vs SUBSTANTIAL+ fan-out). It did
not scale Phase-5 judgment: distill, registrar, demotion, archive, and defrag still
asked the model to walk empty or blocked-only result sets. Phase 1 still preloaded
the store even after Phase 0 had named lists (`archive?`, `defrag?`, re-verify,
`promote?`) and the index was already the always-loaded inventory.

A conductor that runs the phases was already considered and deferred
(`docs/dream-procedure-integrity.spec.md` §Deferred to v2): a script cannot force
the model to invoke it, and the measured 2026-06-22 failure was skipping Phase-3
verification, not missing a driver.

## Decision

We will keep every detector on the path and gate only *judgment*:

1. **Empty-set rule.** When a scripted candidate set is empty (`archive? 0`,
   `defrag? 0`, `promote?` seed empty, no `user-global` canonicals,
   `demotion.eligible == 0` with nothing surfaced, distill `n_recurring == 0` and
   `n_chains == 0`, registrar `fleet-candidates: 0`), emit the required one-liner
   verdict from those counts, `--into` it where the phase says to, and proceed.
   Do not open a judgment pass, re-read the empty list, invent a nearest-miss, or
   walk `blocked: generic-cli` rows as a docket. A non-empty set gets the full
   content judgment (report-then-apply, never auto). **Never skip the scan.**
2. **Targeted body reads.** Do not sequentially Read every local fact body to
   orient. The indexes are the inventory. Body reads remain mandatory wherever
   content is the input: every `user-global` canonical (demotion), every
   `promote?` seed body, every Phase-0 named file when N>0. Phase-2 dedup is
   indexes, then grep of each candidate's distinctive nouns, then Read of hits.
3. **Dream-arc beats still fire.** Presence does not scale; an empty set gets one
   short line, not a skipped beat.

The procedure is in SKILL.md (*Empty-set rule*, Phase 1 *Fact bodies — targeted*).
Smoke pins the rule text and the absence of the old "Read fully" / store-wide
preload instruction.

## Alternatives

- **Collapse phases 2+3 or 0–5 into a shorter ritual.** Rejected: mixes
  claim-generation with confirmation; the lazy-skip detector keys on that split.
- **Skip harvest / `--recalls` / distill scan on LIGHT.** Rejected: those are
  capture-before-rotation, not ceremony. First harvest of a node can be slow;
  re-runs watermark to no-op.
- **Cap the demotion re-audit** (like `_PROMO_CAP`). Rejected: delayed
  demotion of an over-promoted `user-global` taxes every project's always-loaded
  index until the next full walk.
- **Auto-apply recall-tier local writes.** Rejected under "no quality hit";
  always-loaded and global writes stay gated.
- **A second `dream-fleet` skill.** Rejected as the default: harvest would then
  depend on the operator remembering to run it.
- **LangGraph / `dream_conductor.py` / another orchestration stack.** Rejected:
  the bottleneck is what the model is asked to consider; a driver adds no
  enforcement. Conductor remains deferred v2 ergonomics.

## Consequences

Positive: empty fleet/distill/demotion/archive/defrag sets stop costing a content
walk; Phase-1 context stays available for Phase-3 verification instead of 40 fact
bodies; grep-based dedup is stricter than hoping the model remembers every body.

Negative: a body-level duplicate whose description *and* body share no grepable
nouns with the new candidate can slip until a later pass. Mitigated by reading
grep hits and by Phase-0 re-verify / archive / defrag lists. A model that treats
"empty-set" as license to skip the scan is a procedure skip, not this rule —
harvest/`--recalls`/distill `--json` remain mandatory.

Neutral: SKILL body only (two-way; `/reload-plugins`). No cycle-record schema
change. Lands as a patch under the pre-1.0 policy.

## Revisit trigger

Reopen if a later dream misses a body-level duplicate that grep would not have
caught, if empty-set language correlates with skipped *scans* (check
`.consolidation-log.jsonl` for absent `distill` / `usage` / `workflow_proposals`
on finishing dreams), or if 1.0 freezes procedure into a committed API and this
rule needs to be named there.
