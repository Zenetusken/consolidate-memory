# SPEC — dream procedure-integrity safeguard

**Status:** REVISED after an independent 3-lens spec-review gate + advisor pressure-test + an empirical
measurement against the live `.consolidation-log.jsonl` (2026-06-22). The original "conductor that runs the
phases" design was found to be partly a category error (see §Reframe); this revision is the lean, buildable,
empirically-validated core. BUILD as a gated cycle in this session.
**Author context:** diagnosis written 2026-06-22 immediately after the failure; revised the same day from the gate.

## The failure (MEASURED, not asserted — from `.consolidation-log.jsonl`)

Three consecutive dreams on 2026-06-22 (one session) ran **0/0/0 verification** (confirmed/corrected/unverifiable)
while labeled HEAVY, SUBSTANTIAL, SUBSTANTIAL. The orchestrator (the model) compressed the dream — Phase 0 →
partial 1 → 5 → done — skipping the Phase-1 demotion/promotion re-audits, the **Phase-3 verification fan-out
entirely**, and the Phase-5 GC/stale-re-verify, then stamped `rigor.applied = SUBSTANTIAL`. The user detected it
by eye ("barely filled a page of terminal"); no mechanism did. The full per-dream record (the empirical basis for
the detector below):

| timestamp (2026-06) | commits | cands | applied | tally c/c/u | verdict |
|---|---|---|---|---|---|
| 18T00:37 | 11 | 8 | SUBSTANTIAL | 7/1/0 | ok |
| 18T02:54 | 6 | 10 | SUBSTANTIAL | 7/1/0 | ok |
| 18T18:16 | 11 | 2 | SUBSTANTIAL | 11/1/0 | ok |
| 19T17:55 | 2 | 4 | SUBSTANTIAL | 10/2/0 | ok |
| 20T18:58 | 2 | 3 | SUBSTANTIAL | 12/2/0 | ok |
| 20T23:34 | 4 | 2 | SUBSTANTIAL | 16/1/0 | ok |
| 21T04:34 | 11 | 1 | LIGHT | 15/1/0 | ok |
| 21T20:32 | 21 | 5 | HEAVY | 6/1/0 | ok |
| 21T22:13 | 2 | 2 | LIGHT | 16/0/0 | ok |
| **22T04:59** | **11** | **0** | **HEAVY** | **0/0/0** | **⚠ FIRE** |
| **22T06:51** | **3** | **2** | **SUBSTANTIAL** | **0/0/0** | **⚠ FIRE** |
| **22T14:33** | **4** | **2** | **SUBSTANTIAL** | **0/0/0** | **⚠ FIRE** |
| 22T15:04 | 4 | 2 | SUBSTANTIAL | 19/2/2 | ok (the corrected dream) |

## Root cause

1. **Conflated low OUTCOME with low EFFORT.** A pass with few new facts to write ("the arc's already in the
   roadmap") was treated as license to skip the maintenance/verify *ritual* — but rigor (input-side effort) is
   explicitly decoupled from outcome (output-side writes). The re-audits, GC, and stale-re-verify run
   **regardless** of how many facts get written.
2. **`rigor.applied` is self-reported.** The skill's own docs admit it "catches over-rigor, not under-rigor."
   The orchestrator both does the work AND grades it → no independent check.
3. **Long post-compaction session** compressed the working sense of "the full dream."

## Design principles (from the advisor pressure-test + the spec-review gate)

- **Forcing function at the one MANDATORY boundary.** Nothing can make a stateless script *force* an LLM to run
  a phase (a script runs to completion and exits — it cannot pause/resume the model), and the failure proved the
  model will skip documented steps under load. So the safeguard cannot be "a driver that runs the phases" (the
  model can decline to invoke it, exactly as the failing session ran `--snapshot`/`--pull`/`--audit` ad hoc). The
  one step the model **always executes to finish** is the terminal `render_dashboard --persist` ("phase 5 to
  summary" ran even in the rushed pass). That boundary is the only mechanically-reached point — put the detector
  there.
- **Non-circular evidence.** A check that reads model-authored fields and compares them to other model-authored
  fields is attestation with extra steps — a rushing orchestrator backfills all of them. The one input the
  lazy-skip does **not** touch is `scope.git_commits` (script-seeded by `memory_status.py --seed` from `git log`;
  the model has no reason to alter it). The detector's trigger rests on that, NOT on `rigor.applied` (the very
  field being audited) and NOT on `mutation_ops` (see the next point).
- **`mutation_ops` cannot be a suppressor (MEASURED).** The tempting third conjunct "no script-emitted mutation
  deltas" fails in the dangerous direction: (a) a rushed pass that wrote one trivial index-pointer has
  `mutation_ops > 0` → the check would be suppressed → MISS; (b) a rushed pass skips Phase 5 *including*
  `--audit`, so the mutation-log entry may not exist at all — the lazy-skip controls whether the suppressor's own
  data exists. Verified against the 3 real failures: **none carries an `audit` block, and there are 11 mutation-log
  entries for 13 dreams.** So `mutation_ops` is used only as **corroboration/severity** in the rendered panel,
  never to gate the fire.
- **Honest scope — DETECT, not ENFORCE.** This is a detector at a boundary, not an impossibility proof. It
  catches the realized failure (the *lazy-skip*: leave verification at the seed-default 0/0/0 on a substantial
  pass). It does NOT catch a *diligent liar* who types fake non-zero tallies, and it primarily watches the
  Phase-3 verification skip (the highest-value, most-skipped phase); Phase-1/5 skips are only corroborated (no
  artifact). No safeguard may pretend otherwise.

## Reframe — what "the safeguard" actually is

The original spec named a "conductor (`scripts/dream_conductor.py` or a `cm dream` driver)" that would *run* the
deterministic phases and *gate* the judgment phases by "refusing to advance until dispositions return." The gate
review found this is partly a category error and partly redundant:

- **A script cannot block until an LLM returns** (consistency/readiness reviewers): the only coherent shape would
  be a multi-invocation, file-mediated handshake — significant new machinery.
- **Nothing forces the model to invoke a driver** (consistency reviewer #3): its "phases cannot be skipped" holds
  only *given* it is invoked, and the failure was precisely the model not following documented procedure.
- **A per-item disposition handshake has a hole:** for git-derived verification candidates the candidate set is
  *model-curated*, so the 0-candidate dodge (the worst real failure logged `session_candidates: 0`) walks
  straight through it.

So the safeguard is **not** a phase-running conductor. It is a **procedure-integrity detector + a conditional
nonzero exit at the `render_dashboard --persist` boundary**, backed by a pure predicate. A driver that runs the
deterministic legs is *optional ergonomics* (deferred — see §Deferred to v2), not the safeguard. "Conductor" is
retired as the name; the mechanism is the **boundary detector**.

## Mechanism — the detector (primary; the whole safeguard)

A pure predicate in `memory_status.py` (the dependency root the renderers import, beside `validate_cycle_record`
and `suggested_tier`):

```
procedure_integrity(record) -> (ok: bool, reason: str, severity: str)
```

**Fire (ok = False) iff:** `magnitude_tier(scope.git_commits, scope.session_candidates) ≥ SUBSTANTIAL`
**∧** `verification.confirmed + verification.corrected + verification.unverifiable == 0`.

- `magnitude_tier` is the existing `suggested_tier()` — fully script-derived (git_commits is script-seeded;
  session_candidates is the model's Phase-2 curation, and *lowering* it only lowers magnitude, so the dodge can't
  manufacture a pass; 11 commits alone already → HEAVY).
- The trigger reads **only existing cycle-record fields** (`scope`, `verification`).
- **Work-present is folded into the tier:** a tiny pass (mag ≤ 2) never fires — it spares the LIGHT pass, the
  MAINTENANCE pass (0 commits, 0 cands), and the COLD-START BOOTSTRAP (0 commits, 0 cands) the skill explicitly
  supports, with no special-casing.

**Corroboration / severity (rendered, NEVER gating):**
- `rigor.applied`: if the model *also* labeled it SUBSTANTIAL/HEAVY → self-admission (most damning). If it
  labeled it LIGHT while magnitude says SUBSTANTIAL+ without an `override_reason` → surface the **downgrade
  dodge** (closes the relabel escape).
- `mutation_ops` (from the record's `audit` block if present, else absent): "verified 0, wrote 0" (or *no audit
  block at all*) is more severe than "verified 0, wrote N".

**Legacy / non-conformant gate:** the predicate returns `ok = True` (no-op) when `scope` or `verification` is
absent/non-dict — an ancient or non-conformant record cannot be evaluated and must never be retroactively
flagged. (Every record this skill has ever seeded carries both blocks, so real passes are always evaluated.)

## Mechanism — the teeth (the boundary)

The detector judges a **completed dream**, identified by the one operation only a finishing dream performs:
`render_dashboard --persist` (the SKILL's terminal Phase-5 step). A render WITHOUT `--persist` — a cycle-record
SEED (`memory_status --json` / `cm seed`) or a mid-flight preview — is by construction `session_candidates: 0` +
`verification: 0/0/0`, so on any repo with ≥3 commits-since-marker the predicate *would* fire; but that is the
dream's BEFORE state, not a skipped dream. So the teeth are **gated on `persist_dir`** (judge only a completed,
persisting render). This also makes the empirical "no legit fire" proof exhaustive: it ranges over *completed*
records, which are exactly the records the gate evaluates.

`render_dashboard.py main()`, when `--persist DIR` is given, in **strict order**:
1. prints the normal dashboard **plus** a loud **PROCEDURE INTEGRITY** panel (⚠ + reason) when the verdict fires
   — additive, after the dashboard body, so the render still succeeds;
2. **persists the record** (firing or not) to `.consolidation-log.jsonl` — a firing record MUST be logged, so it
   accrues for calibration and surfaces in the archive's longitudinal ⚠ view (print → **persist** → exit);
3. **then returns a distinct nonzero exit (3)** iff the verdict fired. Exit 1/2 stay read/arg errors.

WITHOUT `--persist`, `main()` prints the plain dashboard (no integrity panel) and returns 0 exactly as today — so
seed/preview renders, `cm render <partial>`, and the beta-tester's seed render are **unaffected**. The only
behavior change is exit-3 on a *completed, persisting* dream whose record fires — which the empirical proof shows
no legit completed dream does. The realized failure DID persist (the 3 rushed passes are in the log — that is how
they were measured), so gating on `--persist` loses no coverage of the failure this targets; a dream that skips
even the persist leaves no dashboard and no log entry — a different, self-evident failure, out of scope.
`render_html.py` (the archive) renders the same panel per cycle — every archived record is a completed, persisted
dream, so all are judged — and the 3 historical failures show ⚠ in the longitudinal view (the visible acceptance
demo).

## Empirical validation (measure-don't-assert)

Running the predicate over all 13 live records (table above) yields **clean separation**: it fires on exactly the
3 rushed 0/0/0 passes (incl. the 11-commit / 0-candidate HEAVY pass the old "candidates present" gate would have
missed) and spares all 10 legit passes (every one has tally > 0; the corrected dream `15:04` = 19/2/2 is spared;
all LIGHT/low-magnitude passes spare via the tier). This is the regression the build pins as a unit test.

## Contract impact — NONE

The detector reads only existing `scope` + `verification` fields and the verdict is **derived, not stored** (it
can be replayed over the log any time). So there is **no cycle-record-contract change**: no new `CycleRecord`
field, no `phases` ledger, no TypedDict / SKILL-schema-block / smoke-pin churn. (This is the major simplification
over the original spec, which assumed a `phases` ledger.) The new code is: the predicate in `memory_status.py`;
the panel + exit-3 in `render_dashboard.py`; the archive panel in `render_html.py`; SKILL.md Phase-5 prose so the
orchestrator EXPECTS the ⚠ / exit-3 and acts on it; smoke tests. Per the deterministic-release-versioning policy
this is backward-compatible (legacy records still render; no removed/renamed flag) ⇒ **patch**.

## Honest limits (stated, not hidden)

- **Detector, not enforcement.** It cannot force the model to invoke any phase; it makes the *failure signature*
  loud + nonzero-exit + logged at the one boundary the model always hits. A model that ignores the ⚠ and the
  nonzero exit is out of scope, the same class as a model that ignores SKILL.md.
- **Catches lazy-skip, not a diligent liar.** Fake non-zero tallies defeat it (they also defeat any
  self-reported scheme); raising per-item cost was the handshake's job, which is deferred for the 0-candidate
  hole.
- **Primarily the Phase-3 verification skip.** Phase-1 re-audit and Phase-5 GC/stale skips have no clean artifact;
  they are only corroborated (a skipped Phase 5 means no `--audit` → "wrote nothing" severity).
- **Trusts script-seeded `git_commits`.** A deliberate downward edit evades — same diligent-liar boundary.

## Deferred to v2 (NOT built — recorded so they aren't re-walked)

- A `dream_conductor.py` driver that *runs* the non-destructive deterministic legs in sequence (ergonomics; adds
  no enforcement, real blast radius on SKILL.md).
- The per-item disposition handshake (multi-invocation, file-mediated) — only non-circular for script-enumerable
  sets (stale-facts, global canonicals); the git-derived-candidate path has the 0-candidate dodge.
- A persisted/​script-stamped verdict block in the cycle record (derivable from existing fields for now; only
  worth a contract field if longitudinal miss-detection needs it materialized).

## Build plan (this session, gated)

1. **Implement.** `procedure_integrity()` + `magnitude_tier` reuse in `memory_status.py`; the PROCEDURE INTEGRITY
   panel + exit-3 in `render_dashboard.py` (**gated on `--persist`; strict order print→persist→exit**); the
   archive panel in `render_html.py`; the Phase-5 prose + honest-limit note in `SKILL.md` (+ a `harness-map.md`
   line). No contract change.
2. **Gate-2 (adversarial + measured).** Can the fire be dodged (relabel → downgrade-dodge surfacing; lower cands →
   commits still fire)? Does it false-fire on any legit record (the 13-record unit test), on LIGHT/maintenance/
   bootstrap, or on a SEED/preview render (the `--persist` gate must spare these — the re-gate caught a
   seed-render false-fire)? Does exit-3 reach a legit-path caller — `cm render` (no `--persist` → spared),
   `tests/`, and the **dream-beta-tester** (it renders WITHOUT `--persist` at `beta_checks.py:446`, and inspects a
   returncode only at the `_probe` path on empty-scope records → no-op → exit 0)? Measure each; the exit code is
   distinct (3) so callers can tell integrity-violation from render-error.
3. **Smoke.** Unit-test the predicate: fires on the 3 real records, spares the 10 legit; spares a synthetic
   LIGHT/maintenance/bootstrap record; no-ops on a record missing `verification`/`scope`. Run `python3
   tests/smoke.py` + `mypy --config-file mypy.ini`.
4. **CHANGELOG + ship** per the deterministic-release-versioning policy (patch). Commit this spec with the build.

## Acceptance

A dream that **leaves verification at 0/0/0 on a SUBSTANTIAL-or-larger-magnitude pass** cannot reach a clean
(exit-0, no-⚠) render: `render_dashboard --persist` prints the dashboard plus a loud PROCEDURE INTEGRITY ⚠,
persists the firing record, and exits 3 (it DETECTS + logs; it does not block the write). Re-running this
session's three 0/0/0 passes through the predicate flags **every one** (proven above), and the 10 legit passes —
including the corrected 19/2/2 dream and every LIGHT/maintenance/bootstrap pass — are spared. A diligent liar who
types fake tallies is explicitly out of scope (DETECT, not BLOCK).
