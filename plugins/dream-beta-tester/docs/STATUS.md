# Dream Beta-Harness — STATUS (dream-beta-tester v0.1.8 · built 2026-06-21 · refreshed 2026-08-28)

A reusable, any-repo harness that beta-tests the **consolidate-memory "dream" skill**: runs it
as a faithful consumer, adversarially verifies it, and emits a version-stamped defect report.
This document IS dream-beta-tester's changelog (the plugin has no separate `CHANGELOG.md` —
its `plugin.json` version is the source of truth, currently **0.1.8**); this refresh validates
the **consolidate-memory SKILL** at v0.1.85 — a different plugin's version, tracked
separately in *its* `CHANGELOG.md`, which does not mention these dream-beta-tester fixes.
Consumer/beta-tester tooling — it NEVER patches the skill it tests. Design: [`SPEC.md`](SPEC.md);
harness-teeth design of record: [`SPEC-A.md`](SPEC-A.md).

## Automation — continuous QA (installed 2026-06-21)
A **pre-push gate** runs the deterministic oracle on every consolidate-memory push and **blocks
a version that regresses a known defect** (oracle FAIL); WARN-level findings print but don't block.
- Thin trigger: `consolidate-memory/.git/hooks/pre-push` (local, untracked) → `exec ci_check.sh`.
- Logic: `ci_check.sh` (here, outside the skill dir) → `beta_checks.py` against the working-tree
  version, on a **FROZEN synthetic fixture** store (`fixtures/make_fixture.py` → `gate-repo`) built to
  reliably fire D3 (over-budget gate) + D4 (wikilink-reachable orphan), decoupled from any live store.
  **Fail-open** on harness error; logs to `reports/.gate-log.tsv`. Override a block with `git push --no-verify`.
- Proven both ends: allows v0.1.23 (0 FAIL, 0 WARN — the fixture is noise-free); blocks cached v0.1.19 (D3+D4 FAIL).
- **Self-test (watch-the-watcher):** before trusting an "allow", the gate proves the oracle still detects a
  FROZEN known-bad (source scripts VENDORED in `fixtures/canary-v0.1.19/`, tag-faithful; the
  grafted runtime copy lives under `~/.dream-beta-test/canary-v0.1.19/` — generated, never
  committed) BY DEFECT IDENTITY — `{CHK-GATE-BACKFILL, CHK-EVICT-STAGE} ⊆`
  the canary's FAIL ids (v0.1.7/B6 — **CLOSED**, see below; was a `≥2 FAIL` count check). The canary is
  v0.1.19 (real D3/D4 defect) with the
  **M3 slug GRAFTED at install-gate time** — REQUIRED since cm v0.1.40: v0.1.19 is old-slug (`[/_]`), the
  harness is M3 (`[^A-Za-z0-9]`), so on a `.`-bearing state path (default `~/.dream-beta-test`) an un-grafted
  canary resolves a DIFFERENT, EMPTY store → reports 0 → *spurious* FAILs that coincidentally satisfy "≥2" =
  a FALSE-GREEN that does not actually prove detection (the 2026-06-22 fix; the slug isn't the defect, so the
  graft preserves D3/D4). If the canary stops dying, detection is broken → loud alert + fail-open (verdicts
  UNTRUSTWORTHY, logged `SELFTEST_BROKEN`). Closes the silent-fail-open hole.
  **CLOSED (was a KNOWN GAP):** the self-test used to check the FAIL *count* (≥2), not the SPECIFIC ids — a
  future canary break could hit a spurious ≥2 (the false-green class the 2026-06-22 incident actually hit).
  v0.1.7/B6 hardened it to an IDENTITY check: `{CHK-GATE-BACKFILL, CHK-EVICT-STAGE} ⊆ detected_ids`
  (`emit_result.py`'s `self_test` block now carries `expected_ids`/`detected_ids`; `min_fail_expected`/
  `actual_fail` are reported detail only, no longer the gate).
- **Novel-class reminder:** on a version bump the gate reminds you to run `/dream-beta-test` (the lens pass) —
  the gate itself only catches KNOWN-defect regressions, not new classes.
- DECLINED: a skip-on-unchanged speed optimization — a mis-keyed skip would silently pass a regressed version,
  trading the gate's whole purpose for marginal speed. The gate is ~deterministic-oracle-fast; safety wins.
- The judgment lenses are NOT auto-run (they need an agent) — run `/dream-beta-test` for the full pass.

## Orchestrator interface (deterministic self-heal) — see `CONTRACT.md`
- **Point at:** `reports/latest.json` (`schema: dream-beta-test/result/v1`, overwritten every run) —
  `verdict` (`clean`·`regression`·`selftest_broken`·`harness_error`) + `ship_ok` + `actionable[]`
  (each FAIL with `defect_ref`, `expected`/`actual`, quoted `evidence`) + `self_test.ok`.
- **Produce it:** run `ci_check.sh` (exit 0=ok / 1=block; writes `latest.json`). Loop:
  run → read `latest.json` → `clean`→ship · `regression`→patch by `defect_ref`+`evidence`, re-run ·
  `selftest_broken`/`harness_error`→STOP (the harness failed, not the release; never patch the skill).
- Producers: `ci_check.sh` → `beta_checks.py` → `emit_result.py` → `reports/latest.json`.

## How to run (human)
- **One command (any repo):** `/dream-beta-test` (the skill) — runs the engine + the judgment
  lenses + writes the report. Triggers on "beta-test the dream", "QA/audit consolidate-memory",
  "validate a new version"; does NOT hijack a normal "dream/consolidate" request.
- **Engine directly:** `python3 run_beta.py --repo <DIR> --test`  (scripts-only, restores after).
- **Oracle only (JSON):** `python3 beta_checks.py --repo <DIR> --json`  (exit 1 iff any FAIL).
- **Pin a version under test:** `--skill <cached-version-scripts-dir>`.

## Capture families (QA-currency — v0.1.7/B5 refresh)
The "latest persisted dream captured its X" advisory families (LOW severity, PASS-or-WARN, never
FAIL — a missing capture on a too-old record is expected, not a defect). All four share the
`_latest_capture_check` scaffold: version-gated (skill below `min_version` → not applicable),
SKIP-by-empty on a log-less store (no persisted dream yet — invisible in `families_ran`/
`families_skipped`, not even a SKIP row), then PASS/WARN on the latest record's completeness. Three
of the four (`distill_capture`/`usage_capture`/`demotion_capture` — every family EXCEPT
`dream_arc_capture`) additionally share `_maintenance_pivoted(ctx)`: a maintenance/bootstrap pass
scoped to pull+health legitimately skips their step too, so it's SKIP-by-empty there as well, never
a WARN — see each row's "carve-out" note below.

| Family | `check_id` | `min_version` | Completeness signal |
|---|---|---|---|
| `dream_arc_capture` | `CHK-DREAM-ARC` | 0.1.54 | `dream.sleep`+`dream.wake` non-empty AND `dream.beats` == 6 (the == 6 count since v0.4.1; 1–5 beats compliant on pre-0.4.1 records) |
| `distill_capture` | `CHK-DISTILL-VERDICT` | 0.1.55 | `distill.verdict` non-empty (carve-out: SKIP on a maintenance/bootstrap pivot) |
| `usage_capture` | `CHK-USAGE-CAPTURE` | 0.1.63 | `usage.window` non-empty (the injection step ran, regardless of what it found; carve-out: SKIP on a maintenance/bootstrap pivot) |
| `demotion_capture` | `CHK-DEMOTION-VERDICT` | 0.1.67 | `demotion.verdict` non-empty (dormant is a valid, honest verdict; carve-out: SKIP on a maintenance/bootstrap pivot) |

## v0.1.8 — SPEC-A "harness teeth" (2026-08-28)
Three-lens adversarial spec review, curated v0.2; evidence phase measured hermetically.

- **Cycle-probe self-test leg** (`beta_checks.py --cycle-probe`): a FROZEN contaminated cycle
  record (a second project's real seed, `after_tokens=9999`, stamped) is fed into
  `cycle_identity` on the MAIN gate invocation only — teeth-intact iff BOTH `CHK-CYCLE-PROJECT`
  + `CHK-CYCLE-BUDGET` FAIL by identity; probe results are partitioned out of the push verdict
  (never `results[]`/`_summary`/the exit code). Missing/corrupt/unstamped record →
  `cycle_probe.ok:false` → `selftest_broken`-class (loud, fail-open), NEVER `clean`.
  `emit_result.py` gained `--probe-ok` (default false — an un-updated emit path cannot emit
  clean) + the `cycle_probe` latest.json block; `install-gate.sh` generates the record once
  (`fixtures/make_cycle_probe.py`, hermetic — never touches the real projects dir).
- **Fixture re-baselined**: ONE `global_ref:` mirror (+ index pointer) makes the fixture store a
  network trigger node — `CHK-CYCLE-BUDGET` was previously SILENTLY ABSENT from the fixture run
  (no node → check suppressed). Re-baselined: 21 results, 0 FAIL / 0 WARN. The mirror's canonical
  is deliberately FICTIONAL — no synthetic canonical is ever written into a real global store.
  Known cost, accepted: the fixture now appears as a KNOWN SYNTHETIC node in the maintainer's own
  fleet scans (`--tokens`/`--network`/`--staleness`) — inert by construction (the fictional
  canonical never replicates), and `--gc` reclaiming it is self-healed by the gate (A6).
- **Scripted mutating pass** (`run_beta.py --mutate`): the dream's real write order (snapshot →
  marker stamp → seed → audit `--into` → seed-marker stamp → driver-authored scoped fact →
  persist → promote) on a HERMETIC TEMP-HOME copy, verified against a claimed-writes plan
  (`snapshot.diff(claimed=…)` — unclaimed writes and phantom claims both FAIL) plus an
  out-of-band global-store channel (canonical created, provenance names the repo, origin
  converted to mirror). Per-subprocess env pinning (leak-home smoke-pinned); restore-by-
  construction (the temp world is discarded; `--keep` retains the pid-suffixed copy — the frozen
  fixture is never written); frozen stamp constants + fixed repo path → deterministic modulo the
  promote-minted `global_ref_since:` stamp.
- **Canary VENDORED (A5)** — the frozen known-bad no longer depends on the plugin cache (a
  cache-only canary is lost forever on a fresh machine — v0.1.19 is not installable today):
  `fixtures/canary-v0.1.19/` holds the five v0.1.19 scripts byte-faithful to the tag
  (`e28c6bd`), manifest-pinned (`SHA256SUMS`, smoke-verified), grafted at install time;
  `install-gate.sh` prefers the cache, falls back to the vendored copy, and ABORTS on a failed
  manifest (a tampered known-bad would false-green the watch-the-watcher). The full canary leg
  is now smoke-pinned hermetically — grafted → self-test fires by identity + verdict `clean`;
  ungrafted on a dot-path → `selftest_broken` (the 2026-06-22 false-green class stays closed).

**Before v0.1.7, the gate fixture had no `.consolidation-log.jsonl`** — `dream_arc_capture`/
`distill_capture` returned `[]` on the empty-log guard (absent from BOTH `families_ran` and
`families_skipped`, invisible rather than a visible SKIP), and nothing covered the index-lifecycle
ladder at all. `fixtures/make_fixture.py` now writes one current-shape record (honest dormant/zero
values); regenerate an existing on-disk fixture with `install-gate.sh` to pick it up.

## Validation matrix — every axis proven on BOTH ends
| Property | Evidence |
|---|---|
| **Detects defects (goes RED on bad input)** | vs cached **v0.1.19**: `CHK-GATE-BACKFILL` (D3) + `CHK-EVICT-STAGE` (D4) → **FAIL, exit 1** |
| **Honesty / claim-vs-reality goes RED** | injected rogue fact + index edit → `unexpected_store: 2`, marker delta tracked, **diff exit 1**; derived side-files correctly `allowed` |
| Clean on fixed code (no false positives) | vs live **v0.1.22**: 0 FAIL (12 PASS, 1 advisory WARN); later re-verified **v0.1.23**: 0 FAIL, 0 WARN (fixtures/README) |
| Deterministic / byte-stable | two runs byte-identical (after the orphan-sort fix) |
| Type-clean | `pyright` 0 errors / 0 warnings |
| Portable (any-repo) | clean run on `job-applicator-python` (different slug/store, version-aware, SKIP-not-crash on inapplicable families) |
| Honest by construction | retracted its own D1/D2 hand-diagnosis; quarantines judgment-flagged vs confirmed |
| **v0.1.7/B5-B7 both-ends (measured 2026-07-06)** | canary (grafted v0.1.19): `fail=4`, ids ⊇ `{CHK-GATE-BACKFILL, CHK-EVICT-STAGE}` ✓ · current tree (v0.1.68 scripts): `fail=0`, `families_ran` includes ALL FOUR captures (`dream_arc_capture`/`distill_capture`/`usage_capture`/`demotion_capture`) — none SKIP-by-empty · `ci_check.sh` end-to-end: `clean`/`ship_ok:true` |
| **B6 sabotage (measured)** | ungrafted v0.1.19 cache (the ACTUAL 2026-06-22 mechanism — wrong slug → empty-store resolution): `fail=4` (would satisfy the OLD `≥2` count check) but ids = `{CHK-QTY-*-TRUTH ×2, CHK-REM-REQUIRED, CHK-REM-RESOLVED}` — **none of the real D3/D4 ids** → correctly `selftest_broken`, not a false green |
| **B7(a) sabotage (measured, both failure modes)** | over the over-budget fixture: (a) helpers renamed CONSISTENTLY (module still runs) → `CHK-EVICT-STAGE` SKIP, "helpers unavailable … despite the store being over budget"; (b) helpers renamed but a stale internal caller crashes `memory_status --json` itself (Gate-2a found this zeroes `ctx.status`, the naive signal's exact blind spot) → SKIP, "memory_status --json itself failed to run cleanly (…NameError…)" — both produce an explicit, cause-labeled SKIP, never silent omission |
| Self-improving | dynamic lens caught + fixed a flaw in its own oracle (`CHK-BUDGET-CALIBRATION`) |
| Triggering | direct selector probes: beta-test → `dream-beta-test`; consolidate → `consolidate-memory` |
| **A1 probe teeth (measured)** | contaminated record → `{CHK-CYCLE-PROJECT, CHK-CYCLE-BUDGET}` FAIL exactly; clean record → both PASS (no false red); missing record → teeth-loss, verdict `selftest_broken`, never `clean` |
| **A1 inert seam (measured)** | flag-absent oracle output carries no `cycle_probe` key; main summary/results byte-stable while the probe FAILs; exit code untouched |
| **A3 mutating pass (measured)** | clean: 0 unexpected, 0 phantom, oob green, marker advanced; two runs byte-identical modulo `global_ref_since:`; leak-home unwritten (env pinning); frozen fixture untouched |
| **A3 claimed-writes seam** | unclaimed write → unexpected; claimed-without-delta → phantom; allowlisted no-delta → not a phantom; `claimed=None` = pre-A2 behavior |
| **A6 GC-reclaim self-heal (measured)** | the maintainer's own `--gc --apply` reclaims the fixture's orphan mirror (its canonical is fictional); the gate regenerates the idempotent fixture on the next run and still reaches `clean` with teeth intact — pinned end-to-end |

## The closed loop (both ends observed)
My v0.1.19-era defect catalog (`~/consolidate-memory-v0.1.19-defects.md`) → the author's patches
→ the harness scores them: **v0.1.19 RED, v0.1.22 GREEN.**

| Catalog | Fixed in | Harness verdict |
|---|---|---|
| D1/D2 (cycle/project contamination) | v0.1.20 (`acaa6ba`, per-slug temp path) | retracted by oracle; CHK-CYCLE-* PASS |
| D3 (backfill under no-net-grow gate) | v0.1.21 (`c3e3ec7`) | v0.1.19 FAIL → v0.1.22 PASS |
| D4 (evict wikilink-reachable orphan) | v0.1.21 (`c3e3ec7`) | v0.1.19 FAIL → v0.1.22 PASS |
| D5 (prune can't reach budget) | superseded by standing-justify | PASS (SKIP on pre-field v0.1.19) |
| D7 (no standing-justify) | v0.1.21 | PASS |
| D6/D8–D11 (calibration framing, dangling links) | open / advisory | WARN (design feedback) |

## Known limitations (honest)
- The skill-creator `run_loop` trigger-optimizer scored uniform 0% recall here — a **harness
  artifact** (its temp-command mechanism didn't expose a user-global skill from the plugin-cache
  cwd; even the literal invocation name scored 0%). Real triggering confirmed by direct probe.
  To re-run that optimizer, launch it from a project root, not the nested skill-creator cwd.
- The full **mutating-dream** path is now wired SCRIPTED (v0.1.8/A3: `run_beta.py --mutate` runs the
  real write scripts end-to-end on a hermetic copy, claim-verified); the **agent-driven** full dream
  (the model performing Phase-4 surfacing) remains `/dream-beta-test` lens-pass territory — not
  gate-wired, by design (the gate stays deterministic-oracle-fast).
- **`cycle_identity`'s two checks (`CHK-CYCLE-PROJECT`/`CHK-CYCLE-BUDGET`) are identity-by-construction**
  in the MAIN run (the seed is built from the target, honestly labeled `basis="identity-by-construction"`)
  — but v0.1.8/A1 gives them TEETH: the cycle-probe leg feeds a frozen contaminated record and the gate
  reports `selftest_broken`-class teeth-loss unless BOTH checks FAIL on it by identity, every run
  (measured both ends: contaminated → FAIL pair; clean → both PASS).
- Layout (v0.1.7 refresh — the plugin layout, not the pre-plugin draft): engine scripts
  (`beta_checks.py`/`snapshot.py`/`render_beta_report.py`/`run_beta.py`/`emit_result.py`) at
  `plugins/dream-beta-tester/scripts/`; the skill at
  `plugins/dream-beta-tester/skills/dream-beta-test/SKILL.md`; maintainer runtime state
  (fixture/canary/`reports/`) at `~/.dream-beta-test/` (overridable via `$DREAM_BETA_STATE`).
