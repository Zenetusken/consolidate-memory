---
name: dream-beta-test
description: >-
  Beta-test the consolidate-memory "dream" / memory-consolidation skill ITSELF: run the
  dream beta-harness against a repo and produce a structured, version-stamped defect report
  (the dream dashboard + a severity-ranked findings catalog that combines a deterministic
  invariant oracle with adversarial judgment lenses). Use this whenever the user wants to
  beta-test, QA, stress-test, audit, or find bugs/inconsistencies in the dream /
  consolidate-memory skill, run "dream-beta-test" or "the dream beta-harness", or validate a
  new consolidate-memory version against a repo. IMPORTANT: this is the TESTER, not the
  dream — do NOT trigger it on a normal request to "dream" / "consolidate my memory" /
  "checkpoint" / "save what you learned" (that is the skill UNDER test; use consolidate-memory
  for those). Honest by construction: confirmed defects and suspected ones are kept separate.
---

# Dream beta-test

Beta-test the **consolidate-memory "dream" skill** in a target repo and emit one structured,
version-stamped report. You are the dream skill's **consumer / beta-tester** — you run it
faithfully, instrument it, and report defects. **You never patch the dream skill** (nothing
under its plugin dir); this tooling ships as the `dream-beta-tester` plugin — its scripts live
under `$CLAUDE_PLUGIN_ROOT/scripts/` and you run them from there.

The harness has two detectors and your job is to run **both**:

1. a **deterministic invariant oracle** (already built: `beta_checks.py`, driven by
   `run_beta.py`) that re-tests known defect **families** every run — the trustworthy floor;
2. the **judgment lenses** (this skill's contribution) that you apply by hand to *this* run's
   actual artifacts to catch **novel** defects the families don't encode — the dynamic half.

Two properties make this worth doing, and everything below serves them:
- **Dynamic, not overfit** — adapt to whatever *this* run surfaces; never just re-run a frozen
  checklist. The oracle re-tests known classes; the lenses find new ones.
- **Honest** — a confident-wrong defect is worse than a missed one. The harness has already
  retracted two of its own hand-diagnoses, so **every finding is re-verified against source
  before it is called confirmed**, and suspected ones are quarantined, never counted.

## Flow

### 1 · Run the deterministic engine
```
python3 "$CLAUDE_PLUGIN_ROOT/scripts/run_beta.py" --repo <TARGET_REPO> --test --json
```
`--test` (default) restores the store afterward — a pure beta-test that leaves no mutation;
default repo is cwd. The runner snapshots the store, runs the oracle (which drives the dream
skill's **own read-only scripts** from a clean subprocess pinned to the target repo),
renders a report to `reports/<slug>__<version>__<ts>.md`, diffs the store, and restores.

Note the **consolidate-memory version under test** (stamped in the report header) and the
report path. Read the rendered report.

### 2 · Confirm the oracle's findings — promote or downgrade
Oracle WARN/FAIL findings land in the report's **§2a-FLAGGED** (oracle-flagged, unconfirmed).
For each, open the **live** skill output it refers to and either:
- **promote → §2a-VERIFIED**, quoting the exact contradicting line from the real
  `memory_status.py` / `render_dashboard.py` output; or
- **downgrade**, if you cannot reproduce it. The oracle is a hypothesis too — re-firing a
  defect the skill has already FIXED is itself a harness bug, and saying so is the job.

### 3 · Apply the judgment lenses — the dynamic half
Read `references/lenses.md` and apply each lens to *this* run's artifacts (the rendered dream
dashboard + the oracle JSON + the live store). The lenses are constant; the findings are
per-run. They exist to catch what the deterministic families don't: a novel inconsistency, a
dishonest claim, an incoherent recommendation, an unsafe suggestion.

### 4 · Reduce every judgment finding before cataloging it
A lens finding is a **suspicion, not a defect.** Quarantine it in **§2b (judgment-flagged,
UNVERIFIED)** until it reduces to one of:
- (a) a **reproducible deterministic check** — you can show the exact command + its output; or
- (b) a **quoted source-contradiction** — you quote the skill's own output contradicting
  itself or reality.

Only then promote it to **§2a-VERIFIED**. Whatever you cannot reduce stays in §2b, shipped
explicitly as an unverified hypothesis for human triage — **never counted as a defect.** This
single discipline is the skill's whole value; it is what keeps the catalog trustworthy.

### 5 · Write the findings in + present
Augment the rendered report: fill §2a-VERIFIED (confirmed, with quotes) and §2b (unverified
hypotheses). A **clean run is a clean report** — empty findings is a valid, good outcome; do
not invent defects to fill space. Present the report path + a tight summary: *version under
test · N confirmed · N unverified · the run-delta vs the prior report for this repo*.

### 6 · (Optional) Crystallize a confirmed novel class into a family
If you confirmed a **novel, general** defect class (not an existing family, not a one-off),
you may add it to `$CLAUDE_PLUGIN_ROOT/scripts/beta_checks.py` as a new `(Ctx) -> [Result]` family so every future run
re-tests it deterministically — the harness gets smarter each run. Tie its PASS to the FIXED
behavior so a real regression flips it. This is the only code you write, and only for the
harness — never the dream skill.

## Hard rules
- **Never patch the consolidate-memory skill.** You are its consumer/tester; surface defects
  in the report and let its author patch them. Writing into its plugin dir is out of scope.
- **Any-repo.** Derive the slug; run the skill's scripts from `cwd = target repo` via a clean
  subprocess (the contamination root cause the harness exists to catch). `run_beta.py` already
  does this — if you run a skill script by hand, pass the target repo **positionally**.
- **Reports** live under `~/.dream-beta-test/reports/` (a stable user dir, so they survive plugin
  updates and the orchestrator has a fixed `latest.json` path). Never write into the skill's dir.
- This skill is the **tester**. A plain "dream / consolidate / checkpoint my memory" request
  is the skill **under test** — use `consolidate-memory`, not this.

## Depth
The authoritative design is `$CLAUDE_PLUGIN_ROOT/docs/SPEC.md` (§4 detection · §5 flow ·
§6 report · §7 snapshot · §8 versioning). Read it when you need the *why* behind a step.
