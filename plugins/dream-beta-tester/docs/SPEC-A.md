# Dream Beta-Harness — SPEC-A v0.2 (harness teeth)

**Cycle-identity probe + scripted mutating-pass driver — IMPLEMENTED (P-1…P-4, dream-beta-tester
v0.1.8).** v0.2 = the curated revision after a 3-lens adversarial review
(mechanics/contracts, threat/safety, scope/economy); every review finding below was
re-verified against the live tree before curation. Grounded in the measured evidence phase of
2026-08-28 (hermetic runs, HOME=<tmp>). Extends `SPEC.md` §3 (the deterministic engine) and §7
(snapshot/restore); the shipped-layout note in SPEC.md:32-33 applies. Companion of record:
`STATUS.md`, `CONTRACT.md`.

## 1. Goals & non-goals

**Goal — give the gate two teeth it lacks today, both measured:**

1. **Cycle-identity teeth.** `CHK-CYCLE-PROJECT` / `CHK-CYCLE-BUDGET` carry
   `basis="identity-by-construction"` and CANNOT fail as shipped (`beta_checks.py:764-768`):
   `gather()` rebuilds the seed from the target's own store (`beta_checks.py:349-358`), so no
   foreign record can reach them. Add a test-only seam that feeds a FROZEN contaminated
   record into `cycle_identity`, plus a self-test leg proving the family FAILs on it —
   mirroring the canary self-test's defect-identity discipline.
2. **A scripted mutating pass.** The claim-vs-reality apparatus (`snapshot.py`) is proven
   only against hand-injected mutations; `run_beta.py:270-272` discloses the coverage limit.
   Add a deterministic driver performing the dream's REAL write order with the real scripts
   and validating the store delta against a claimed-writes plan — the honesty leg with a real
   claimed set.

**Non-goals (unchanged, explicitly):**
- NO agent-driven dream automation — the pre-push gate stays deterministic and fast
  ("~deterministic-oracle-fast; safety wins", `STATUS.md:39`); the agent-driven full dream
  remains the `/dream-beta-test` lens pass.
- NO patch to the consolidate-memory skill — `CONTRACT.md` law (harness failures → STOP,
  never patch the skill). This arc changes only dream-beta-tester + its fixtures + tests.
- NO folding-in of the D6/D8–D11 advisory items (WARN-class design feedback — separate track).
- NO probe leg on the canary (the canary is old-skill; the probe flag appears ONLY on the
  main invocation — §8).

## 2. Evidence basis (measured, then review-corrected)

| Measurement | Result |
|---|---|
| Contaminated fixture store (foreign fact + index pointer + persisted record naming `OTHER-PROJ`, `after_tokens=9999`) through the current oracle | **rc=0, fail=0** — invisible. Gap confirmed. |
| No foreign-record input seam exists | `gather()` rebuilds the seed from the target (`beta_checks.py:355`) |
| Scripted write-pass (seed → stamp → audit → persist, promote guard-refused) two runs | byte-identical stores, 0.3 s wall |
| **Review correction** — determinism WITH a completing promote | **unverified, refuted by code**: the origin mirror is minted `since=_now_iso()` (`sync_global.py:1623, 467-468`) — cross-run byte-identity requires normalizing `since:` (D-7) |
| **Review correction** — the fixture is NOT a network node | `make_fixture.py` writes zero `global_ref:` mirrors; node status requires a mirror (`sync_global.py:1746-1758`), so `_trigger_node` (`beta_checks.py:530-537`) returns None and `CHK-CYCLE-BUDGET` is **silently absent** from the fixture run (`beta_checks.py:793`) — the probe's budget FAIL needs a mirror in the fixture (D-3) |
| Oracle baseline on the fixture | 0.4 s; 20 results, 0 FAIL, 0 WARN (re-measured by the mechanics reviewer) |
| `--persist` refuses an unstamped seed (`marker.timestamp` empty) | measured — the stamp is a MODEL step; `--audit --into` does NOT inject it (`memory_status.py:2917-2927`) |
| `--promote` guard ladder | scopeless refused → `stacks:` missing refused → non-`_DETECTABLE_STACKS` refused (`sync_global.py:1535-1556`) — all correct |
| `--pull` on the fixture | no-op by design (M1 hold — fixture index 3879 est-tokens vs `INDEX_CEILING_TOKENS` 3840) |
| Cross-run state-file diff from differing repo paths | `_write_stacks_cache` merges `project_path` (`sync_global.py:718-745`) — the driver MUST use a fixed repo path |
| `run_beta.py` subprocess env | **no `env=` pin anywhere** (`run_beta.py:155, 162, 215`) — ambient HOME inheritance (D-9) |
| Contaminant magnitude | `after_tokens=9999` vs fixture trigger ~3879: Δ≫ tolerance `max(50, 0.10×ntok)` (`beta_checks.py:795`) — sound at any plausible fixture size |

## 3. Design decisions

**D-1 — The seam is a beta_checks CLI flag, inert by default.**
`beta_checks.py --cycle-probe FILE.json`: when absent, behavior is bit-identical to today.
When present, `cycle_identity` is evaluated a second time against the foreign record in place
of the live seed; probe results are partitioned (D-2) and never enter top-level `results[]`.
Rejected: env var (invisible surface, accidental activation), wrapper script (the oracle
carries its own teeth-proving capability), store-level splicing (measured: invisible to the
seed — the record seam is the only faithful vector).

**D-2 — The probe is a self-test leg with the FAIL-identity formula.**
Teeth-intact = `expected_ids ⊆ detected_ids` where detected = the probe leg's FAIL ids —
the canary CIDS discipline verbatim (`ci_check.sh:50, 60-78`). Probe results carry
`basis="probe"` (free-form `basis`, `beta_checks.py:521-528`; precedent: B7 minted
`identity-by-construction`) and a probe-identifying `site`. **Teeth check asserts BOTH FAILs
explicitly** — an ABSENT check reads as teeth-loss, never as intact (absence ≠ PASS: today a
missing trigger node silently omits `CHK-CYCLE-BUDGET`, `beta_checks.py:793`; under the probe
the same absence must degrade to loud teeth-loss, D-3).

**D-3 — Fixture re-baselined with one mirror; probe record FROZEN, self-stamped.**
The probe budget check needs a trigger node → the fixture store needs ONE `global_ref:`
mirror fact + its index pointer (added in P-1). This amends the freeze rule: **the fixture is
frozen per arc version, and P-1 re-baselines it** — the 0-FAIL/0-WARN baseline is RE-VERIFIED
after the mirror lands (the ground-truth family recomputes store quantities, so "unchanged"
is an assumption, not a promise; §11 row 2 reads "re-baselined"). New
`fixtures/make_cycle_probe.py`: builds a second dummy repo + store (distinct slug), runs the
SKILL's own `memory_status.py --json` on it (current-skill-shaped record), stamps it
`probe: true` + a sentinel, freezes it to `$DREAM_BETA_STATE/cycle-probe.json`. **The probe
leg verifies the stamp; an unstamped/tampered/foreign file → teeth-loss, never green**
(a path-confused invocation must not test like-with-like). Regeneration is an explicit
maintainer command, documented in the fixture README; `install-gate.sh` generates the probe
record once, exactly like the canary graft. Rationale for a separate generator (vs a
make_fixture mode): make_fixture never subprocesses the skill; the generator's whole job is
subprocessing it, and its lifecycle (state artifact) differs from the fixture's.

**D-4 — The mutating pass is a `run_beta.py` mode, reusing its snapshot/diff/restore spine.**
`run_beta.py --mutate [--keep]` executes the measured write order (§5) between snapshot and
diff, then emits the diff disposition with the claimed-writes set. Default: restore (a
beta-test leaves no mutation, `snapshot.py:528-529`). **`--keep` writes to a COPY of the
fixture, never the frozen store; and any restore failure mid-pass exits with a distinct code
+ writes a fixture-dirty marker that `ci_check.sh` refuses on** (a half-restored FROZEN
fixture would shift trigger-node tokens → false reds/greens on every subsequent run; the
remedy is `install-gate.sh` regeneration, said explicitly in the marker message).

**D-5 — The claimed-writes seam is a new keyword param on `snapshot.diff`.**
`diff(before, after, *, against_live=False, claimed: frozenset[str] | None = None)` —
backward-compatible. With `claimed` set: a store `*.md` / index delta NOT in
`claimed ∪ allowlist` is `unexpected` (dashboard-dishonesty class); a claimed write with no
delta is a phantom claim — **scoped to NON-allowlisted claims only** (an allowlisted file
carrying the frozen stamp yields no delta and is not a phantom; and the pass REFUSES to start
if the before-manifest already contains the plan's writes — no stale-fixture phantom
misfires). Keys are `(origin, name)` pairs per the delta naming in `snapshot.py:431-499`.

**D-6 — The write plan is split into diff-universe claims + out-of-band verification.**
The diff's universe is the project store + repo docs only (`_live_manifest`,
`run_beta.py:274`); the promote step's canonical + provenance + fleet-ledger writes land in
`$FIXTURE_HOME/.claude/memory` — OUTSIDE that universe. So: plan entries carry class
`derived|fact|index` (diff-verified claims) or `canonical` (out-of-band): the driver hashes
the fixture global store before/after and asserts the canonical body, the `projects:`
provenance append, and the `.fleet-usage.jsonl` row DIRECTLY. **`clean` requires BOTH
channels verified** — a silently-refused promote (guard ladder) must fail the out-of-band
assert, never report a green honesty leg.

**D-7 — Determinism is normalized, not naive.**
Fixed repo path + frozen stamp constants (§2 evidence). Cross-run byte-compare normalizes
the mirror's `global_ref_since:` line (minted `_now_iso()`, `sync_global.py:1623`) before
hashing. Primary pin = within-run delta accounting + normalized cross-run compare; a
pin-break caused by a benign future skill change is "investigate", never an auto-defect
(CONTRACT.md law — never patch the skill).

**D-8 — Promote runs on a driver-authored scoped fact, stacks from `_DETECTABLE_STACKS`.**
The driver writes its own fact with `scope: stack-general` AND a non-empty `stacks:` drawn
from `_DETECTABLE_STACKS` (a non-detectable stack is refused, `sync_global.py:1549-1554`),
INSIDE the frontmatter block (a body append is invisible to the parser — measured), claims
it in the plan (`fact` class), and promotes it. The local mirror rewrite + index pointer are
diff-visible claims; the canonical side is out-of-band (D-6).

**D-9 — HOME hygiene is implemented, not asserted.**
Every driver subprocess runs with an explicit env dict: `HOME=$FIXTURE_HOME`,
`DREAM_BETA_STATE`/`DREAM_BETA_REPORTS` scrubbed or redirected into the fixture tree — the
current spine inherits the ambient env (`run_beta.py:155, 162, 215`), and one leaked
`--promote` writes a canonical + an append-only ledger row into the REAL `~/.claude/memory`
(unrecoverable by restore — the global store is outside the manifest). `make_cycle_probe.py`
applies the same env discipline (its ambient-HOME regeneration would drop a synthetic store
into the real projects dir). A smoke pin additionally asserts the real `~/.claude/memory`
(and the real projects slug) are byte-unchanged after a full pass — the existing
`_assert_hermetic` pattern (`tests/simulate_accumulation.py:182-191`) proves path containment
only; the byte-unchanged assert is NEW.

## 4. The cycle probe (end state)

1. Gate run: `beta_checks.py --repo $STATE/gate-repo --skill <tree scripts> --json
   --cycle-probe $STATE/cycle-probe.json` — on the MAIN invocation only (never the canary
   leg; §8), and only when `ci_check.sh` finds the probe file.
2. Main families evaluate the live ctx exactly as today.
3. `cycle_identity` re-evaluates against the probe record: `CHK-CYCLE-PROJECT` FAILs on the
   foreign `project`; `CHK-CYCLE-BUDGET` FAILs on the foreign `after_tokens` vs the LIVE
   trigger node (the mirror added in D-3 makes the fixture a node; `_trigger_node` reads
   `ctx.network`, `beta_checks.py:530-537`).
4. Partitioned results in the JSON: `cycle_probe: {expected_ids, detected_ids, ok, results[],
   stamp_verified}`. Teeth-intact iff stamp verified AND
   `{CHK-CYCLE-PROJECT, CHK-CYCLE-BUDGET} ⊆ detected_ids` (BOTH, explicitly — absence is
   teeth-loss).
5. Missing/corrupt probe file, unstamped record, or any shape-guard SKIP in the probe leg
   (the §8 SKIP-with-reason is NEW behavior — today the missing-path omission is silent,
   `beta_checks.py:793`) → `cycle_probe.ok: false` → `ci_check.sh` maps it to the
   `selftest_broken` class — the canary-BROKEN path (`ci_check.sh:72-78`), NOT the
   canary-missing path. Fail-open, loud, and the verdict is never `clean`.

## 5. The mutating pass (write order)

Measured order (each step a separate subprocess of the real script, env per D-9):

1. `memory_status.py <repo> --snapshot` — BEFORE manifest + content-hash (Phase 0).
2. Marker stamp: merge frozen `{commit, timestamp}` constants into
   `.consolidation-state.json` (the dream's Phase 5 step 5, scripted).
3. `memory_status.py <repo> --json` → seed record.
4. `memory_status.py --audit <snapshot> --into <seed>` — mutation-trail injection.
5. Seed-marker stamp: set the seed record's `marker.commit`/`marker.timestamp` to the frozen
   constants (the MODEL's Phase-5 job, scripted — `--persist` refuses unstamped seeds and
   `--audit` does not stamp).
6. `render_dashboard.py <seed> --persist <store>` — the terminal write (measured: log
   appends 1 line).
7. Driver writes the scoped+stacked fact (D-8), claims it, then
   `sync_global.py --promote <repo> <fact>` — the two-store write (canonical side verified
   out-of-band per D-6).
8. `snapshot.diff(before, live, claimed=plan)` → disposition; every delta accounted for;
   marker advanced; then the out-of-band global-store assert; then restore (default) or
   `--keep` (copy).

## 6. Failure semantics & exit codes

- `beta_checks.py` exit codes unchanged: 0 = no FAIL in the MAIN run; 1 = any main-run FAIL;
  2 = scripts-not-found. Probe-leg results never change the exit code (they ride the JSON,
  partitioned).
- `ci_check.sh`: blocks (exit 1) only on verdict `regression`; probe-teeth loss OR missing
  probe artifacts map to `selftest_broken`-class (fail-open, loud) — verdict ladder
  `selftest_broken > harness_error > regression > clean` (`emit_result.py:103-110`).
- `run_beta.py --mutate`: exit 0 = pass complete, both channels clean, restored; exit 1 =
  any unexpected/phantom diff-write or out-of-band assert failure (the honesty FAIL),
  OR'd with the renderer verdict (`run_beta.py:452` — combination rule: 0 iff renderer
  verdict clean AND diff clean); distinct exit (2) = restore failure → fixture-dirty marker.
- `emit_result.py` gains `--probe-ok` (and the mutating-pass block); B2(c) discipline
  (`emit_result.py:98-101` — exact literal "true", fail toward distrust): passed EXPLICITLY
  on every ci_check emit path (both `:75` and `:98`); absent → verdict cannot be `clean`.

## 7. Safety invariants

1. **Hermeticity, enforced.** Per-subprocess env dict (D-9); smoke pin asserts the real
   `~/.claude/memory` and real project slug are byte-unchanged after a full pass.
2. **Inert seam.** Absent `--cycle-probe`, the oracle is bit-identical to today; probe
   results never reach `results[]`/`_summary`/the exit code/the renderer's re-grep (verified:
   all five sinks consume top-level results only — `beta_checks.py:1414-1421, 1472`;
   `ci_check.sh:50-51, 102-105`; `emit_result.py:96-110`; `render_beta_report.py:186-187`).
3. **Restore-or-hard-stop.** Default restore; `--keep` = copy; restore failure = distinct
   exit + dirty marker + `ci_check.sh` refusal (D-4).
4. **Frozen inputs, per arc version.** Fixture + probe record frozen; P-1 re-baselines the
   fixture once (D-3); the only variable input is the skill under test (the point).
5. **No network, no third-party deps, no new processes beyond the existing scripts.**

## 8. Canary & version gating

- The probe leg and the mutating pass run ONLY against the current working-tree skill. The
  flag must be pinned to the MAIN invocation (`ci_check.sh:97`); the canary leg's payload
  must carry no `cycle_probe` block (asserted by a pin), and the canary self-test identity
  set stays exactly `{CHK-GATE-BACKFILL, CHK-EVICT-STAGE}` — a mis-wired shared `run_oracle`
  would otherwise degrade every canary leg to permanent `selftest_broken`.
- Shape-guard SKIPs inside the probe leg are teeth-loss (D-2/§4.5), never silent.
- Acceptance also pins the CANARY leg's summary unchanged (fail=4, `STATUS.md:93` — no new
  ids, no new WARNs).

## 9. Contract impact (`reports/latest.json`)

NOT free: `emit_result.py:139-164` rebuilds the contract dict from named args and drops
unknown keys — the new blocks require an emit_result change (P-1/P-3), not just producer
output. Additive keys: `cycle_probe` (as in §4) and, on `--mutate` runs,
`mutating_pass: {planned, performed, unexpected, phantom, out_of_band_ok, ok}`. **A MISSING
`cycle_probe` block in latest.json is teeth-loss** — the orchestrator (`CONTRACT.md:41-68`)
must treat an absent block exactly like an `ok: false` one (an old/wrong ci_check must never
emit `clean` with no teeth info). Verdict semantics unchanged; `actionable[]` FAIL-only.

## 10. Regression pins (added to `tests/smoke.py`)

1. **Probe teeth pin:** hermetic build of the frozen record; beta_checks with `--cycle-probe`
   → stamp verified, detected ids == the expected pair (BOTH); a clean record (target's own
   seed) → both checks PASS (no false red); **and** main summary + `families_ran` unchanged
   with the flag present and the probe FAILing (exit 0, `cycle_identity` appearing once —
   the partition discipline pin).
2. **Mutating-pass pin:** within-run delta accounting clean; normalized cross-run compare
   (`since:`-line-normalized, D-7) identical; hermeticity assert (real stores byte-unchanged).
3. **Claimed-writes pins:** an intentionally unclaimed write → FAIL; a claimed-but-unperformed
   write (phantom, non-allowlisted) → FAIL; an allowlisted no-delta stamp → NOT a phantom.
4. **Inert-seam pin:** scoped to `families_ran` + fail-count + results-count unchanged from
   the arc-start baseline (captured at P-1, paths normalized — no committed golden exists
   and the JSON embeds absolute paths, `beta_checks.py:1450-1460`), NOT full byte-identity.
5. **Canary pins:** canary leg summary unchanged (fail=4); canary payload carries no
   `cycle_probe` block; B6 ungrafted sabotage still yields `selftest_broken`.
6. **Tolerance-margin pin:** assert `|9999 − fixture_trigger_tokens| > max(50, 0.10×trigger)`
   so a future fixture edit can't silently turn the probe into a tolerance test.
7. **Genericity/secret-safety:** new fixture content is synthetic; runs through the existing
   genericity scan and secret firewall untouched.

## 11. Acceptance criteria (measurable)

- [ ] Probe on the contaminated record: `CHK-CYCLE-PROJECT` AND `CHK-CYCLE-BUDGET` both FAIL
  (BUDGET present at all — fixture re-baselined with the mirror); clean record: both PASS.
- [ ] Main-run summary on the RE-BASELINED fixture: 0 FAIL, 0 WARN (re-verified after the
  mirror lands, not assumed unchanged).
- [ ] Canary leg: self-test fires by `{CHK-GATE-BACKFILL, CHK-EVICT-STAGE} ⊆` detected ids;
  canary summary unchanged (fail=4); no `cycle_probe` block in the canary payload.
- [ ] `--mutate`: within-run delta accounting clean; normalized cross-run compare identical;
  out-of-band global-store assert green; restore verified (store matches the pre-run
  manifest); restore-failure path produces the dirty marker + distinct exit.
- [ ] Missing probe file / unstamped record / shape-guard SKIP → `cycle_probe.ok: false` →
  verdict `selftest_broken`-class, NEVER `clean`.
- [ ] Gate wall time on the fixture ≤ 3 s total (main 0.4 s + canary ~0.4 s + pass 0.3 s +
  probe < 0.1 s, 2× margin).
- [ ] `python3 tests/smoke.py` green (incl. all 7 pins); `tests/simulate_accumulation.py`
  green; `tests/validate_manifests.py` green; mypy green.
- [ ] `ci_check.sh` end-to-end on the tree: verdict `clean`, `ship_ok: true`; latest.json
  carries `cycle_probe` + `self_test` blocks; `emit_result` emits `--probe-ok true`
  explicitly.
- [ ] B6 sabotage re-check: ungrafted canary still yields `selftest_broken`.
- [ ] This spec reviewed + curated (v0.2 — the present review).

## 12. Build plan (phased, each gated)

- **P-1 (fixture re-baseline + seam + probe):** SHIPPED — mirror added to make_fixture
  (re-baselined 21 results, 0 FAIL / 0 WARN), `--cycle-probe` flag + partition + stamp
  verification, `make_cycle_probe.py`, `ci_check.sh` wiring (main invocation only,
  probe-missing → teeth-loss), `emit_result.py --probe-ok` + latest.json `cycle_probe`
  block, pins 1 + 4 + 5 + 6. Gate: rows 1-3, 5, 8, 9-10 — all measured green.
- **P-2 (claimed-writes seam):** SHIPPED — `snapshot.diff(claimed=…)` with the
  allowlist-scoped phantom rule, pin 3. Gate: row 9 + honesty matrix unchanged.
- **P-3 (driver):** SHIPPED — `run_beta.py --mutate` (env discipline D-9, write plan D-6,
  out-of-band global-store channel, restore-by-construction, `--keep` copy), pins 2 + 3
  end-to-end. Implementation note vs spec: the temp-home-copy design makes the
  restore-failure class STRUCTURALLY IMPOSSIBLE (the real fixture is never written), which
  is stronger than the spec's restore-failure hard-stop countermeasure.
- **P-4 (release):** SHIPPED — dream-beta-tester `0.1.7 → 0.1.8` (additive patch — policy
  rule 3, no breaking change to existing installs; main plugin untouched), STATUS.md
  changelog rows + SPEC.md pointer, full gate suite.
- Known cross-plugin coupling, stated for the record: the main plugin's smoke gate now
  subprocesses the skill's WRITE scripts via the mutating-pass pins — a future legitimate
  main-plugin behavior change can therefore block a main release through a beta-tester pin;
  that is intentional (the gate tests the tree).

## 13. Open questions

Closed by the review: Q1 (frozen + shape-guard + regeneration command is sufficient — the
canary precedent settles it), Q2 (seed-only is the faithful D1/D2 signature —
`STATUS.md:105`), Q4 (`basis="probe"` is right — free-form basis, honesty-labeling doctrine,
`beta_checks.py:507, 788`). One genuine remainder:

1. **Fixture mirror placement.** The D-3 mirror makes the fixture a node and shifts
   ground-truth quantities. If the re-baseline surfaces a WARN (e.g., index-weight change
   near a budget edge), does the arc accept a re-baselined non-zero baseline with a
   documented justification row, or must the mirror content be tuned until 0/0 holds?
   Decision gate: P-1's re-baseline measurement, before any P-2 work.

## 14. Release plan

- Dream-beta-tester `0.1.8` patch (additive). No consolidate-memory version change — the
  skill is never patched by this arc (`CONTRACT.md` law).
- `STATUS.md` gains the arc's rows (probe + mutating-pass evidence); SPEC.md §3/§7 get a
  one-line pointer to this doc.
- The auto-update cycle delivers the new oracle to installed gates at the next plugin-cache
  refresh; `install-gate.sh` regenerates the fixture (with the mirror) and generates the
  probe record once, like the canary graft.
