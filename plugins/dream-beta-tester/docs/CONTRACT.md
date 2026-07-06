# Orchestrator contract — deterministic self-heal loop

This is the machine-facing interface for a dream-plugin orchestrator that develops
consolidate-memory and **self-heals a release** from the beta-harness's verdict.

## Where to point

```
RESULT:  ~/.dream-beta-test/reports/latest.json              # the deterministic verdict (overwritten every run)
RUN:     plugins/dream-beta-tester/maintainer/ci_check.sh    # runs the gate → writes latest.json → exit 0 (ok) / 1 (block)
```

`RUN` is repo-relative (run from the consolidate-memory checkout you're developing — `ci_check.sh`
resolves its own engine scripts and the skill under test relative to that repo, so this IS the
correct path for a dev orchestrator, not a placeholder). The installed pre-push hook instead execs
whichever cached plugin copy is newest: `~/.claude/plugins/cache/*/dream-beta-tester/*/maintainer/ci_check.sh`
(sorted, last) — use that glob if driving an already-installed plugin rather than a dev checkout.
`RESULT`'s directory defaults to `~/.dream-beta-test` (override via `$DREAM_BETA_STATE` /
`$DREAM_BETA_REPORTS` — see `ci_check.sh`'s own header).

Do **not** parse the human `.md` reports or the gate log — `latest.json` is the contract.
`ci_check.sh` tests the **working-tree** consolidate-memory dev checkout (the code you're about
to ship), against a FROZEN fixture, and proves the oracle still detects a frozen known-bad before
trusting the verdict. Run it on demand (it's idempotent + read-only w.r.t. the skill); the
pre-push git hook runs the same script automatically.

## `latest.json` schema (`schema: "dream-beta-test/result/v1"`)

| field | meaning |
|---|---|
| `verdict` | `clean` · `regression` · `selftest_broken` · `harness_error` (the only branch you switch on) |
| `ship_ok` | `true` iff `verdict == "clean"` |
| `version_under_test` | the working-tree plugin.json version |
| `self_test` | `{canary, min_fail_expected, actual_fail, expected_ids, detected_ids, ok, meaning}` — detection is now an IDENTITY check (`expected_ids ⊆ detected_ids`, the real D3/D4 defect ids), not a count; `min_fail_expected`/`actual_fail` are reported detail only. `meaning` is a human-readable sentence conditioned on `ok`/whether a comparison ran at all — never trust it over `ok` itself, but it's the fastest way to see WHY. `ok=false` ⇒ the HARNESS is broken, not the release |
| `summary` | `{fail, warn, pass, skip, total}` |
| `actionable` | the FAILs to fix, each: `{id, defect_ref, severity, title, expected, actual, evidence, site, basis}` |
| `findings` | every check (PASS/WARN/FAIL) — full detail |
| `fix_reference` | patch by `defect_ref` (see the catalog + STATUS.md) |
| `generated_at` | ISO timestamp — check freshness before acting |

## The self-heal loop (deterministic)

```
loop:
  run  plugins/dream-beta-tester/maintainer/ci_check.sh   # writes latest.json (see "Where to point")
  read ~/.dream-beta-test/reports/latest.json
  switch verdict:
    "clean"           → ship the release. done.
    "regression"      → for each f in actionable:
                          • locate the cause from f.expected vs f.actual + f.evidence (a quoted
                            substring of the skill's REAL rendered output when f.basis=="rendered")
                          • patch consolidate-memory by f.defect_ref (the catalog entry names the
                            root cause + fix direction; e.g. D3 = suppress backfill under an active
                            no-net-grow gate; D4 = route wikilink-reachable orphans to R_referenced)
                        → goto loop   (re-test the patch)
    "selftest_broken" → STOP. the oracle can no longer detect the frozen known-bad — the HARNESS is
                        broken, not the release. Do NOT patch the skill. Escalate / fix beta_checks.py.
    "harness_error"   → STOP. no verdict produced (oracle crash / schema mismatch). Escalate.
```

### Guardrails the loop must honor
- **Never patch the skill on `selftest_broken` / `harness_error`.** Those mean the *tester* failed,
  so a "clean" or "regression" reading would be untrustworthy. The `self_test.ok` flag exists so a
  blind reader can't mistake a broken harness for a clean release.
- **Bound the loop.** If the same `defect_ref` stays in `actionable` after a patch+re-run, the patch
  didn't take — stop and surface it rather than spin.
- **`verdict` is the ONLY control signal.** `exit_code` mirrors it (1 only on `regression`), but read
  the JSON; the exit code can't carry the actionables.

## Coverage boundary (important)

`latest.json` is the **deterministic** gate: it catches *regressions of known defect classes* (the
oracle families), which is exactly what an automated self-heal loop should act on. It does **not**
catch *novel* defect classes — those need the judgment-lens pass. On a version bump, also run
`/dream-beta-test` (agent-driven) and read its markdown report for anything new; crystallize a
confirmed novel class into a `beta_checks.py` family so the deterministic loop covers it next time.

## Producers
`ci_check.sh` (gate) → runs `beta_checks.py` (oracle) → pipes to `emit_result.py` → `reports/latest.json`.
Verified: clean→`clean`/ship_ok, v0.1.19→`regression` with `actionable:[D3,D4]`, broken-canary→`selftest_broken`.
