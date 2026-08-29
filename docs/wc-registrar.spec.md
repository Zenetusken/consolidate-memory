# W-C registrar — SPEC v0.3 (adversarially reviewed, curated, polish-amended)

**The distill vertical's final stage: the registrar/adoption loop that proposes and places
fleet-wide workflow artifacts from W-A/W-B evidence.** v0.2 = the curated revision after a
3-lens adversarial review; v0.3 = the polish-swarm amendments (declined-leg
pins as data-presence, cue wording — see the commit history) (mechanics/contracts, safety/blast-radius, scope/economy); every
accepted finding was re-verified against the live tree. Companion of record:
`distill-feature-plan` (the vertical's plan + stage-3 inputs) and the SKILL's Phase-5 step 6.

## 1. Goals & non-goals

**Goal — close the distill vertical.** Foundation → local distill → W-A (persisted
template/chain tally per dream) → W-B (`sync_global --workflows`: fleet recurrence,
decline lineage, adoption/inventory panels) are SHIPPED. W-C is the consumer of that
evidence: when a workflow crosses the confidence gates, the dream PROPOSES the smallest
durable artifact (command → skill), a human confirms, the artifact is placed, and the
adoption loop tracks whether the fleet actually uses it.

**Non-goals (explicit):**
- NO auto-authoring — report-then-apply is HARD (an executable/always-on artifact is the
  highest-blast-radius write in this plugin; the conductor + Stop-hook were rejected on
  this exact ground).
- NO granular sharing tier — the user's load-bearing design note stands: sharing is
  BINARY, project-local OR fleet-wide. NO stack-general for artifacts.
- **The proposal ladder is CAPPED at on-demand skill.** The subagent and always-on rungs
  have no defined placement destination and are the highest-blast-radius class — OUT of
  scope for W-C, stated here next to the ladder (the v0.1 draft listed them and thereby
  licensed what this section bans — review catch).
- NO ingest adapter for other harnesses — measured-out (stale + firewall-exposed; the
  real lever is organic CC node growth). Revisit only on the recorded conditions.
- NO changes to dream-beta-tester in this arc (the QA harness may gain W-C families in a
  later arc, never here).
- NO new runtime dependency; the registrar engine lives in the existing stdlib scripts.

## 2. Evidence basis (measured; the v0.1 table was review-corrected)

| Measurement | Result |
|---|---|
| Fleet workflow evidence (live `--workflows`, 2026-08-29) | **2/8 nodes reporting** — `beacon` (rows since 2026-07-17, heavy git-command templates) + `consolidate-memory` (rows since the 08-29 dream) · **0 exact cross-node template/chain recurrences** · 24 distinct single-node templates · 3 same-tool drift families across the 2 nodes (git checkout/commit/status) — the near-join case the gate exists to catch |
| Tonight's distill (this repo, 3 sessions/2 days) | 31 recurring templates, 19 chains; top candidate = the smoke→sim→mypy→manifests gate-chain → **already-covered gate fires** — "create nothing" is the correct, frequent verdict |
| Dormant real stores | Doc-Flo (Jun 22) · job-applicator (Jul 4) — not evidence of coldness, absence of recent dreams |
| Cross-harness adapter | Measured-out: DON'T build (stale, 82% firewall-exposed) — recorded in distill-feature-plan |
| W-A rows accrue since v0.1.82 per dream | key-presence gated (a record's `top` list; an instrumented window with `top: []` COUNTS as reporting — instrumented-empty ≠ legacy) |

**Corrected build-gate story:** the live input stream EXISTS (2 real nodes stream rows);
what is missing is cross-node EXACT recurrence. W-C1 (engine + fixture + pins) is
buildable and certifiable now; W-C2's fleet-wide proposal path stays inert until the
measured trigger — ≥1 exact cross-node recurrence — arrives. (The v0.1 draft's "0/N"
was false at any point since Jul 17; the review caught it from the live lens. The
precedent for shipping an evidence reader on a cold join is W-B's own 0/7 cold-start,
not arc A — review catch.)

## 3. Design decisions

**D-1 — The registrar is a SKILL-phase extension + a sync_global engine, not a new tool.**
The Phase-5 distill step already consults `--workflows`; W-C extends that consultation
into a proposal-placement loop. The ENGINE lives in `sync_global.py` beside the W-B lens
(same data, same single source); the PROPOSAL/PLACEMENT is the dream's (model judgment —
script = evidence, model = workflow recognition + proposal).

**D-2 — TWO gate tiers (the v0.1 draft conflated them — review catch):**
- **Tier 1 (unchanged, governs ALL proposals):** the shipped step-6 gate — ≥2× recurrence
  with stable inputs, repeatable procedure, clear stopping condition, not-already-covered
  (inventory first), not-previously-declined (lineage). A 5-episode SINGLE-NODE workflow
  is legitimately proposable TODAY under this tier, for project-local placement — W-C
  does NOT regress that path.
- **Tier 2 (NEW, governs FLEET-WIDE placement only):** the additional gates —
  1. **Fleet recurrence:** the same normalized template/chain appears in W-A rows of
     **≥2 real nodes**, where "real" means organic discovery scope (§D-2a — there is NO
     provenance check; the mechanism is home-scoping).
  2. **Day-spread:** fleet `d ≥ 2` (the W-B join's per-node-max `d`; a same-day
     double-run has d=1 and fails). Episode arithmetic is PINNED: per-node `n`, fleet
     `d` = max over nodes — a 1-episode-each 2-node pair passes gate 1 and gate 2 with
     d≥2; that is intended (two independent nodes, two distinct days).
  3. **Stable inputs + repeatable procedure + clear stopping condition** — model-judged
     (the engine NEVER fabricates a model-leg verdict — §4 splits mechanical vs
     model-judged legs; no-failure-masking law).
  4. **Not already covered:** the engine's inventory panel is USER-LEVEL
     (`~/.claude/skills` + commands); "the repo, the plugin" is the MODEL's checklist
     leg (the shipped step-6 wording), not an engine claim.
  5. **Not previously declined with an EVIDENCE ANCHOR:** decline-time evidence is
     computable — W-C1 extends `distill_history` to surface the decline record's own row
     snapshot (the rows ARE in the log; the shipped aggregation drops them — a small,
     natural extension). "More nodes/episodes than when declined" compares against that
     anchor; the shipped lineage `{session, verdict, proposed, created}` alone cannot
     compute it (review catch — pin 1's declined leg depends on this).

**D-2a — Provenance is discovery scope, honestly stated.** Every fleet reader is
`Path.home()`-anchored (`_log_nodes`/`_network_nodes`/`_all_stores`); the engine CANNOT
distinguish a fixture store from an organic one under a real-home scan — there is no
provenance check and none is built. The firewall is home-scoping: fixture stores live
under temp HOMEs and are unreachable from live runs by construction. Pin 3 asserts THAT
layout property (a fixture outside the live node set), plus a fixture-builder guard: the
builder REFUSES to run when `Path.home()` resolves to a non-temp dir (the
`simulate_accumulation` hermetic-refusal precedent). A marker-based provenance check was
considered and REJECTED: it would break pins 1–2 (the fixture must cross the gates in
the pin) and the existing W-B smoke fixture already counts as `nodes_reporting == 2`
under discovery scope.

**D-3 — The proposal ladder (smallest form first, CAPPED):** command → on-demand skill.
Each rung costs more per session (destination-layer = the bloat lever). Fleet-wide
placement lands in `~/.claude/commands/` / `~/.claude/skills/`. Genericize before
authoring: no absolute paths, hostnames, or personal values (the secrets firewall
catches credential-shaped text; it does NOT catch machine-specific values — the model's
genericize judgment is the guard). **Placement-bar note (review catch):** Tier 2 raises
the fleet-wide bar (≥2 nodes) above today's single-node fleet placement; existing
user-level artifacts placed under the old gate are GRANDFATHERED (the adoption loop does
not re-litigate them).

**D-4 — The synthetic workflow fixture (the W-B smoke precedent, generalized).** A frozen
2-node fixture built hermetically in the test layer — the EXACT pattern the existing W-B
smoke test already uses (two temp stores under a redirected HOME, hand-built W-A-shaped
logl lines, in-process `fleet_workflows`, `nodes_reporting == 2`). The fixture covers
templates AND chains (a declined-CHAIN case included — the v0.1 draft exercised
templates only): one shared template across both nodes, one single-node template, one
declined-template lineage, one declined-chain, one already-covered template. The
fixture's row shape is pinned to the live W-A schema (drift-proofing). The fixture is
NEVER a real store and NEVER counts as a live node (D-2a).

**D-5 — The adoption loop, with a per-form numerator.** `used[]` tallies SKILL tool_use
invocations ONLY — a placed command never appears in it (review catch: the v0.1 WARN
would have fired on every placed command by construction). Numerator per form:
- **skill** → `used[]` across real nodes;
- **command** → its normalized template's fleet recurrence in W-A rows (that instrument
  exists);
- neither → the form is excluded from the WARN until an instrument exists.
The loop's only automatic action is a WARN-class advisory when adoption reads 0 across N
probative windows — **N is per-node** (the fleet `used` view sums per-node LATEST windows
that are never aligned; per-node probative honesty is the log's own discipline), and the
WARN carries the zero-is-absence caveat INLINE (0 is absence of evidence, never disuse —
the doctrine the v0.1 draft violated). The advisory re-enters the proposal gate as a
decline candidate that ALSO re-walks placement scope (a 0-adoption fleet-wide artifact
may be a single-project workflow misplaced fleet-wide — review catch). The human decides
(report-then-apply). No auto-archive. N is a coarse tunable default, never calibrated
from thin data (the bands discipline).

**D-6 — The authoring sub-skill is CLOSED as a non-goal.** The dream's model already
authors skills/commands in-session under the genericize rules; a dedicated authoring
skill adds indirection without adding judgment. (The retirement of the
distill-feature-plan open question is a dream Phase-4 write, not this spec's — recorded
so the companion doc can be updated on the next pass.)

**D-7 — The proposal record, script-truth evidence.** The `workflow_proposals` block
carries the evidence INJECTED BY THE ENGINE — `--registrar … --into <seed>` (the
distill_scan `--from/--into` pattern; the model NEVER hand-mirrors counts — review
catch). The model writes only the disposition + the GENERICIZED artifact name (never the
raw template — a path-laden template persisted into the record or the debrief is the
genericize blind spot; review catch). Disposition enum completes the loop:
`awaiting-confirmation | confirmed | declined` (the shipped Distill block already
carries `proposed`/`created`; the record must close the placement loop for the adoption
numerator). The artifact itself lands OUTSIDE the audit trail — the debrief names it
explicitly (the existing honest-gap rule).

**D-8 — Key-presence gating, three cases.** The reader gates on the record's `top` key
(no version constant exists). Three cases must stay distinguishable in the report:
(a) pre-v0.1.82 legacy (no `top` key) → "legacy, not instrumented";
(b) instrumented-empty (`top: []`) → counts as REPORTING;
(c) rows-carrying → the evidence.
A maintenance-pivot distill skip is a legitimate skip, never mislabeled legacy.

## 4. The engine surface (W-C1)

`sync_global.py --workflows --registrar [--json]`: the W-B join + the Tier-2 gate
cascade per candidate, emitting
`{candidate, form, evidence: {nodes, d, n}, gates: {mechanical: {fleet_recurrence,
day_spread}, model_judged: [stable_inputs, coverage, decline_lineage]}, disposition}`.
The mechanical legs are engine-computed; the model-judged legs are explicitly NOT
evaluated by the engine (never fabricate a gate verdict). Read-only — the engine NEVER
writes an artifact. Exit 0 clean · 2 usage error (the W-B convention). Registered in
`_CUED_MODES` (conscious choice — the dream-arc cue fires on the consult), the usage
string, and the `cm` CLI. `--registrar --into <seed>` injects the structured evidence
into the cycle record's `workflow_proposals` block (D-7).

## 5. Failure semantics

- A gate failure is a REPORTED disposition, never an error — "create nothing" remains a
  frequent, honorable verdict (tonight's already-covered case is the exemplar).
- Legacy/instrumented-empty rows are REPORTED per the three D-8 cases — per-node
  SKIP-with-reason is a W-C1 BUILD item (the shipped reader's skip is silent:
  denominator + header; review catch — don't claim what isn't built yet).
- The fixture is test-only by discovery scope (D-2a).

## 6. Safety invariants

1. Report-then-apply for EVERY artifact (a single confirmation authorizes ONE specific
   named artifact — the existing distill rule).
2. No executable writes by the engine or the pins; the fixture writes only to temp dirs,
   and its builder refuses a non-temp HOME (D-2a).
3. Genericize-before-authoring is a model-side hard rule; the record carries the
   genericized name, the debrief names the artifact (audit-trail gap disclosed).
4. Zero-dep; read-only engine; no new processes.

## 7. Regression pins (smoke additions)

1. **Gate-cascade pins on the fixture** (templates AND chains): shared→passes fleet
   recurrence · single-node→blocked AT THE FLEET TIER (Tier-1 local proposals are
   unaffected — the two-tier pin) · already-covered→blocked (model leg — pinned as
   not-engine-evaluated, i.e. the engine's disposition leaves it for the model).
   The DECLINE legs are data-presence pins, not dispositions (decline_lineage is
   model-judged — an engine "declined→passes" disposition is impossible by design,
   v0.3 review catch): the fixture carries a declined-still-recurring candidate (its
   anchor surfaces WITH the current-window rows the model compares against) AND a
   declined CHAIN case — the anchor/current pairing is what the model leg consumes.
2. **Shape pin:** the fixture's W-A row shape == the live `distill` block shape the W-B
   reader parses (drift-proof).
3. **Discovery-scope pin:** the fixture, built under a temp HOME, is outside the live
   node set (the layout property — D-2a) + the fixture-builder's non-temp-HOME refusal.
4. **Key-presence pin:** legacy (no `top`) / instrumented-empty (`top: []`) /
   rows-carrying all render distinctly, and instrumented-empty counts as reporting.
5. **Exit-code + injection pin:** `--registrar --json` shape + exit 0/2; `--into <seed>`
   writes the workflow_proposals block with engine-computed counts (and the smoke
   C5-schema pin forces the TypedDict + SKILL-block update to ride W-C2 — the 3-leg
   contract, review catch).

## 8. Build plan (each phase gated)

- **W-C1 — engine + fixture + pins + the evidence anchor** (buildable NOW, deterministic):
  the Tier-2 mechanical gates, the D-2.5 decline-evidence anchor (distill_history
  extension), the three-case D-8 reporting, `_CUED_MODES`/usage/`cm` registrations, the
  synthetic fixture (templates + chains), pins 1–5. **Sequencing rationale (review
  catch):** the flag ships before its dream consumer as deliberate test-first — the
  engine is certified against the fixture BEFORE the dream is taught to consume it; W-C2
  is one gated step behind. Gate: smoke/sim/manifests/mypy + the 3-leg QA gate.
- **W-C2 — the live proposal path:** the SKILL Phase-5 wording (two-tier consumption:
  Tier-1 local as today; Tier-2 fleet placement via `--registrar`), the
  `workflow_proposals` TypedDict + the SKILL schema block (the C5 pin forces all three
  legs together), the `--into` injection, docs sync. Gate: full suite + a lens pass
  (`/dream-beta-test`) — a SKILL.md change is a version change.
- **W-C3 — release:** patch (additive flag + additive record block + SKILL wording; the
  freeze declaration allows additive keys; legacy records render untouched).
- **The live trigger:** W-C2's FLEET-WIDE path fires only on ≥1 exact cross-node
  recurrence (Tier-2 gate 1); until then it renders the honest "2/N nodes reporting ·
  0 fleet templates" state. Tier-1 local proposals are live immediately.

## 9. Open questions (genuinely)

1. **N for the adoption advisory** — a placeholder coarse constant, doctrine-decided as
   never-calibrated-from-thin-data (not a design question; a tunable default).
2. **Decline-panel presentation** — show WHY a candidate is declined
   (machine-declined vs model-judged not-covered) or a single merged disposition?
3. **Per-candidate history across dreams** — is the W-A row + verdict lineage +
   decline-anchor sufficient, or does the record need a candidate-level history?

## 10. Evidence-pending honesty clause

Design-complete, not build-justified: W-C1 ships because a gate cascade is deterministic
logic, certifiable against the fixture regardless of fleet temperature (W-B's own 0/7
cold-start is the precedent). W-C2's fleet-wide path stays inert until the measured
trigger — ≥1 exact cross-node recurrence — arrives. The corrected census (2/8 nodes
reporting, 0 fleet templates) is the standing reference; nothing here invents data.
