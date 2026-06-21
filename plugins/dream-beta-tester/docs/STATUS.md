# Dream Beta-Harness — STATUS (built + validated 2026-06-21)

A reusable, any-repo harness that beta-tests the **consolidate-memory "dream" skill**: runs it
as a faithful consumer, adversarially verifies it, and emits a version-stamped defect report.
Consumer/beta-tester tooling — it NEVER patches the skill it tests. Design: [`SPEC.md`](SPEC.md).

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
  FROZEN known-bad (`fixtures/canary-v0.1.19` → ≥2 FAIL). If the canary stops dying, detection is broken →
  loud alert + fail-open (verdicts UNTRUSTWORTHY, logged `SELFTEST_BROKEN`). Closes the silent-fail-open hole.
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

## Validation matrix — every axis proven on BOTH ends
| Property | Evidence |
|---|---|
| **Detects defects (goes RED on bad input)** | vs cached **v0.1.19**: `CHK-GATE-BACKFILL` (D3) + `CHK-EVICT-STAGE` (D4) → **FAIL, exit 1** |
| **Honesty / claim-vs-reality goes RED** | injected rogue fact + index edit → `unexpected_store: 2`, marker delta tracked, **diff exit 1**; derived side-files correctly `allowed` |
| Clean on fixed code (no false positives) | vs live **v0.1.22**: 0 FAIL (12 PASS, 1 advisory WARN) |
| Deterministic / byte-stable | two runs byte-identical (after the orphan-sort fix) |
| Type-clean | `pyright` 0 errors / 0 warnings |
| Portable (any-repo) | clean run on `job-applicator-python` (different slug/store, version-aware, SKIP-not-crash on inapplicable families) |
| Honest by construction | retracted its own D1/D2 hand-diagnosis; quarantines judgment-flagged vs confirmed |
| Self-improving | dynamic lens caught + fixed a flaw in its own oracle (`CHK-BUDGET-CALIBRATION`) |
| Triggering | direct selector probes: beta-test → `dream-beta-test`; consolidate → `consolidate-memory` |

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
- The full **mutating-dream** path (running the dream's real write phases end-to-end) is not
  wired; the claim-vs-reality apparatus is proven against a synthetic injected mutation instead.
- Layout: `beta_checks.py` (oracle) · `snapshot.py` (snapshot/diff/restore) ·
  `render_beta_report.py` (report) · `run_beta.py` (runner) · `reports/` · the skill at
  `~/.claude/skills/dream-beta-test/`.
