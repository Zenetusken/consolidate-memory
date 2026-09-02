# 024. Trajectory evidence ladder — sketch removal, deferred rebuild

**Status:** Accepted (v0.4.0).

## Context

The P1-11 audit ("cross-project workflow learning remains an incomplete feature")
was verified against the pre-0.4.0 tree and against the live tree. Its premise
held for the old code: the hook-sketch layer (`hook_sketches.py` +
`CM_HOOK_SKETCHES=1`) synthesized pseudo-hook events from transcripts in the
caller (`extract_signals._hook_sketch`, pre-deletion), normalized them
(`normalize_hook_event`, tool-family collapse, forbidden-key scrub), appended
them to `hook-sketches.jsonl` without a lock or a dedupe key, carried no domain
identity, had no retention path, and defined a promotion gate
(`workflow_promotion_allowed`) that **never had a caller** — the registrar never
consumed it. Against the required 10-step pipeline it scored 2 PRESENT
(normalize; the dead gate) / 2 PARTIAL (capture lived in the caller;
confirmation was a dead return value) / 6 ABSENT (correlation, domain-stamp,
dedupe, retain/compact, cross-project aggregation, adoption tracking). Its one
clean piece was the raw-data discipline: the forbidden-key scrub
(`_FORBIDDEN_KEYS`) held, and the seven fields it wrote stored no raw prompts,
commands, results, or diffs.

v0.4.0 (commit `7f0483e`) already deleted the module and its extractor
integration; the CHANGELOG records it; a smoke pin asserts the import fails.
The shipping workflow ladder — transcript → `distill_scan` (recurring Bash
templates + compound-command chains) → W-A persisted rows → W-B fleet join
(`sync_global.py:2995-3124`) → W-C registrar Tier-2 gate
(`sync_global.py:3153-3167`: distinctive + ≥2 nodes + fleet-min-d ≥2) → model
proposal → report-then-apply confirmation → adoption tallies (`distill.used`) —
is complete, smoke-tested, and never depended on sketch events at any stage.
The sketch layer was redundant, not a prerequisite.

## Decision

1. **Finish the removal.** The dormant `usage_events`/`workflow_sketches`
   registry tables are dropped: removed from `SCHEMA_SQL` (fresh installs never
   get them) and dropped from existing installs by a `REGISTRY_USER_VERSION`
   3→4 migration in `_migrate_schema`, with the same idempotent DROP in
   `_migrate_journal_schema` (pre-split journal files may physically carry
   them). Doc inventories no longer list the module; the removal pins extend
   from the module to the schema.
2. **The registrar ladder is the workflow-learning system.** Its contract
   remains template-centric; the sketch feature is out of the product contract
   (as it has been since 0.3.5) and nothing in the installed hook manifest
   (SessionStart beacon only) captures trajectory events.
3. **Trajectory-level evidence is future work, built from scratch** — not a
   resurrection of the deleted layer — when measured demand justifies it. The
   registrar is currently dormant by data (0 distinctive fleet-candidates as
   of 2026-08-30), not by code: building a second evidence stream before the
   first has produced one measured promotion would be speculative.

## Alternatives considered

- **Complete the sketch layer in place** (resurrect + finish the 10 steps).
  Rejected: the old gate had zero callers, so the feature was never load-
  bearing; the append path had no lock, dedupe, or retention, so enabling it
  meant unbounded unlocked growth; and the work is a multi-PR ladder whose
  outcome the registrar already covers.
- **Keep the dormant tables.** Rejected: empty `usage_events`/
  `workflow_sketches` tables in every existing `control.sqlite` are exactly the
  residue a removal exists to eliminate; leaving them keeps a second silent
  schema surface alive.
- **Adopt the old `workflow_promotion_allowed` gate into the registrar.**
  Rejected: a second gate would fork the promotion contract. The registrar's
  shipped, smoke-tested Tier-2 gate already implements fleet recurrence and
  day-spread mechanically; a parallel gate would disagree by construction.
- **Contract honesty.** The feature was marked experimental/out of contract in
  0.3.5; removing it makes the code match the contract, and the CHANGELOG +
  this ADR record the full reasoning.

## The 10-step pipeline — future requirements

A future trajectory-evidence layer must implement every step, or not ship. The
standing constraint is unchanged: **never store raw prompts, commands, results,
or diffs**.

1. **Capture** — either real hooks (PostToolUse/PostToolBatch) or retrospective
   transcript synthesis. Both must first meet the budget below.
2. **Normalize** — tool-name → family collapse, outcome normalization,
   action truncation, forbidden-key scrub (the old `normalize_hook_event`
   contract, minus its unsanctioned truncate-not-reject fallback).
3. **Correlate invocation/outcome** — a real pairing key. Join on journal
   `op_id`/session slots or a normalized-command hash, **never** stored
   command text (per the cross-project audit 2026-08-31 rule: "Do not store
   raw prompts or tool results. Emit compact event sketches").
4. **Domain-stamp** — every record carries the enrolling `domain_id`; the old
   records' `project_id`+`session_id` pair is not domain identity.
5. **Deduplicate** — a unique dedupe key and idempotent writes; the old
   unlocked append is not acceptable.
6. **Retain/compact** — bounded retention tied to `retention.py`'s tiers:
   detailed normalized sketches 30-90 days; daily usage/workflow aggregates
   ≤12 months; raw transcript-derived text never; conflicts until resolved.
7. **Aggregate across independent projects/days** — a fleet join over the
   sketch store (the W-B `fleet_workflows` shape generalized), not per-node
   files.
8. **Gate promotion** — composes into the existing Tier-2 `_eval` as one more
   mechanical flag (see below). Never a parallel gate.
9. **Require confirmation** — the existing report-then-apply contract: the
   model proposes, the user confirms, one confirmation authorizes one named
   artifact. Nothing auto-promotes.
10. **Track artifact adoption** — the shipped `distill.used` tallies are the
    denominator; 0-adoption over a bounded window emits the spec'd D-5 WARN or
    a demotion-candidate, never an auto-demote.

## Future integration design (built from scratch)

- **One gate.** Trajectory evidence lands as a new mechanical flag — the W-D
  rung — inside the existing Tier-2 `_eval` (`sync_global.py:3153-3167`), with
  the same first-failing-gate disposition ordering (generic-cli →
  fleet-recurrence → day-spread → W-D). The disposition enum and the
  `fleet-candidate`/`blocked:*` contract in `memory_status.py` extend, they are
  not replaced. `workflow_promotion_allowed` stays dead.
- **Sole-authority storage (ADR 023).** The sketch store is a new
  `control.sqlite` table added through the same schema-locked
  `REGISTRY_USER_VERSION` migration; writers run under `locks/global.lock`
  (the journaled transact machinery); a dedupe index on
  `(domain_id, sketch_hash)`; **no new unlocked JSON file** —
  `store-grants.json` is the precedent ADR 023 exists to prevent.
- **The capture layer must earn its hook budget first.** Acceptance criterion
  before any capture hook ships: zero-cost-on-idle plus a benchmarked
  per-invocation overhead ceiling (the SessionStart beacon's 2s timeout and the
  Phase-5 SLO discipline are the existing precedents). Otherwise the layer
  ships as retrospective transcript synthesis, which needs no hook budget.
- **Anchored ladder.** The W-D rung consumes the same evidence objects the
  registrar already reads (harness-map.md:381-394; docs/fleet-workflows.spec.md;
  docs/wc-registrar.spec.md) — sketches must produce candidate templates, not a
  parallel evidence language.

## Consequences

- Fresh `control.sqlite` files never contain `usage_events`/`workflow_sketches`;
  existing ones lose them on first connect after upgrade (v4 migration, under
  `locks/schema.lock`). The registry `user_version` becomes 4; a v0.3.x plugin
  refuses a v0.4.0-written DB (the designed downgrade protection).
- The ImportError pin stays; new pins assert the schema-level removal (fresh
  DB + simulated v3 migration) and the doc inventories.
- The product contract remains template-centric; P1-11 closes as
  "removed + future design recorded here".

## Revisit trigger

Rebuild the trajectory ladder only on measured demand. Reopen this ADR when any
of: (a) ≥N W-C candidates are blocked at the Tier-2 gate (N to be set from the
first N observed) whose missing witness is outcome-correlation evidence, across
≥2 domains over ≥30 days; (b) the D-5 0-adoption WARN fires for a shipped
workflow artifact; or (c) template+chain evidence proves insufficient for a
promotion the user explicitly requests — a concrete miss, not an anticipated
one.
