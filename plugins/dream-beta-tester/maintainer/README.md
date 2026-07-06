# Maintainer continuous-QA gate

**For the consolidate-memory maintainer only.** If you just installed this plugin to QA your own
consolidate-memory, you don't need anything here — use the **`/dream-beta-test`** skill.

This sets up a pre-push gate that runs the deterministic beta-oracle against the consolidate-memory
version you're pushing, on a frozen fixture, and **blocks a push that regresses a known defect**.

## Install
```sh
"$CLAUDE_PLUGIN_ROOT/maintainer/install-gate.sh" [path/to/consolidate-memory-repo]
```
It (1) generates the frozen fixture store, (2) populates the frozen known-bad **canary** from your
plugin cache (any consolidate-memory ≤ 0.1.19 — predating the D3/D4 fixes), and (3) installs a
`pre-push` hook that resolves the latest installed dream-beta-tester at fire time (survives updates).

## Behaviour
- **Self-test first** (watch-the-watcher): the oracle must still detect the frozen canary BY DEFECT
  IDENTITY — `{CHK-GATE-BACKFILL, CHK-EVICT-STAGE} ⊆` the canary's FAIL ids (v0.1.7: hardened from a
  `≥2 FAIL` count check, which the 2026-06-22 incident proved could pass on spurious FAILs that
  contained none of the real defects) — before any "allow" is trusted. If it can't, the gate alerts
  loudly and **fails open** — it never blocks your work on its own malfunction.
- **Blocks** a version whose oracle verdict is `regression`; WARN-level findings print but don't block.
- Writes the deterministic contract to `~/.dream-beta-test/reports/latest.json` (see `../docs/CONTRACT.md`)
  for an orchestrator to read + self-heal. Override a block with `git push --no-verify`.
- Catches **known-defect regressions** only — for **novel** classes, run `/dream-beta-test` (the lens
  pass) and crystallize a confirmed class into `scripts/beta_checks.py`.

State (fixture, canary, reports) lives under `~/.dream-beta-test/`; override with `$DREAM_BETA_STATE`.
