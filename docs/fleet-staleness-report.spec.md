# Fleet staleness report — absorption lag, measured per node (beacon Stage A)

**Status:** shipped (this PR). **Scope:** `sync_global.py --staleness [--json]` + `cm staleness`.
The third increment of the audit's enhancement program (harness-native lens, Proposal 1 **Stage
A** — the observe-only artifact that must prove, or refute, the SessionStart beacon's premise
before any hook ships).

## The blind spot

The propagation model is pull-based and eventually-consistent by design ("each project syncs
itself the next time you consolidate it"), with an honest corollary the audit's intent map
flagged: **absorption latency is unbounded, and nothing anywhere measures or reports it.** A
project that never dreams never receives the fleet's knowledge — and never contributes evidence
(the harvest, v0.1.79, fixed the *contribution* half; this measures the *absorption* half). Live
fleet: 3 mirror-holding nodes, most stores never dreamed, and the only lag signal
(`dream_timing_advisory`) renders solely inside the very flows a lagging node by definition
doesn't run.

## Design — read-only, all stores, never guessed

`--staleness` sweeps **every** project store under `~/.claude/projects/` (not just
mirror-holders — a store with zero mirrors is exactly the most starved), plus the trigger —
**unconditionally** (PR-#93 review, two reviewers convergent): an absent or empty trigger store
is the maximally-starved row (never dreamed, absorbed nothing), never an omission; every
relevant canonical then counts MISSING. Per node:

- **last dream** — the `.consolidation-state.json` marker timestamp → age in days;
  `(never dreamed)` when absent. The marker is model-written (SKILL Phase 5 step 5); this only
  reads it.
- **missing globals** — relevant canonicals with no file in the store (never absorbed).
  **Scope basis is honest per node**: full relevance (live `detect_stacks`) is computable only
  for the TRIGGER — a slug is not invertible to a project path, so other nodes are assessed on
  `user-global` canonicals only, and each row is labeled with its basis. Never guessed. (The
  beacon's Stage B adds a SKILL-written `stacks`/`project_path` cache to the state file, which
  will upgrade non-trigger rows to full scope — deferred with it.)
- **content-stale mirrors** — a mirror whose body-lineage hash (`_body_hash`, v0.1.78) differs
  from its canonical's. Deliberately content-level for Stage A: hook/description drift is
  `--pull`'s refresh job; what lag *harms* is stale knowledge.
- **evidence coverage** — own-log usage windows (`usage_history`) and whether the harvest
  ledger covers the node.

Aggregates: nodes behind (**missing > 0 OR content-stale > 0** — stale knowledge is the sweep's
other half), never-dreamed count (keyed on the SAME unparseable-age predicate the render and
sort use — a present-but-malformed marker reads as never-dreamed everywhere, consistently).
Review-hardened edges: a PRESENT-but-unreadable fact file (chmod/read race) is neither missing
nor stale (skip — under-report, the pinned bias); a FUTURE marker clamps age to 0.0 (raw
timestamp kept in `last_dream` for audit). `--json` for machines (the Stage-B beacon and any
future absorption-latency metric consume this shape). Not in `_CUED_MODES` — like `--network`,
a maintainer/observability lens outside dream flow.

## Alternatives rejected

Auto-pull into lagging stores (violates report-then-apply and the dream-governance model);
inferring non-trigger stacks from slug names (the lossy-slug lesson — never guess); putting the
sweep in `memory_status` (fleet aggregation over `~/.claude/projects` is `sync_global`'s
exclusive competence — the `--utility`/`--workflows` module-boundary precedent).

## Acceptance gates

1. Fixture: a fresh node (recent marker, fully mirrored) and a starved node (no marker, missing
   user-global, one content-stale mirror) — the report shows exactly that, with per-row scope
   basis labels and the trigger assessed at full scope.
2. READ-ONLY over every store (hash-verified); `--json` parses, `age_days` null-safe for
   never-dreamed nodes.
3. Full gates: smoke + sim + mypy + manifests.
