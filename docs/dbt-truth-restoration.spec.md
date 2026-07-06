# dream-beta-tester truth restoration (Track B) — spec DRAFT
<!-- Materializes as docs/dbt-truth-restoration.spec.md on branch fix/dbt-truth-restoration.
     SEQUENCING: branch AFTER PR-1 (fix/cm-audit-hygiene) merges — B9 widens the smoke genericity
     pin that PR-1 introduces (same tests/smoke.py region; no stacking per the PR-flow rule). -->

**Provenance:** the 2026-07-05 four-lens audit, beta-tester lens (all findings confirmed at
file:line) + the orchestrator's own gate-log forensics. Theme: the harness's MECHANICS are sound
(honest-by-construction verified; gate live through v0.1.68) but its shipped TRUTH SURFACE decayed —
docs point at dead homes, the oracle's blocking floor froze at ~v0.1.37, and the self-test proves
detection by count, not identity. Version: dream-beta-tester 0.1.6 → **0.1.7** (rides PR-2).

## Scope

| ID | Finding | File(s) | Class |
|---|---|---|---|
| B1 | orchestrator contract points at the dead pre-plugin home | `docs/CONTRACT.md:9,10,37,38` | P1 machine-doc |
| B2 | emit_result: personal/stale fix_reference · first-brace parse · lax self_test_ok | `scripts/emit_result.py:46,51,83-84` | P1/P3 |
| B3 | STATUS.md frozen at 2026-06-21 / v0.1.22-23 / dead layout | `docs/STATUS.md:1,50-62,83-85` | P1 doc |
| B4 | SPEC.md placement contradicts shipped reality + carries `/home/<user>` | `docs/SPEC.md:27,31-52` | P1 doc + genericity |
| B5 | oracle blocking floor ≈v0.1.37: capture families SKIP-by-empty on the gate fixture; no index-lifecycle families | `scripts/beta_checks.py`, `fixtures/make_fixture.py`, gate fixture | P1 QA-currency |
| B6 | self-test proves detection by COUNT (≥2), not the specific canary defect IDs | `maintainer/ci_check.sh:47-57`, `scripts/emit_result.py` | P2 false-green class |
| B7 | D4's only FAIL leg silently degrades to green if triage helpers vanish; cycle_identity can't-fail as shipped | `scripts/beta_checks.py:872-916,754-792` | P2 oracle honesty |
| B8 | portability: GNU-only `sed -i`; fixed `/tmp/.dbt_*` names; make_fixture takes any argv as write-target, no `encoding=` | `maintainer/install-gate.sh:34`, `maintainer/ci_check.sh:49,72,73`, `fixtures/make_fixture.py` | P2/P3 |
| B9 | genericity: scrub dbt tree; widen PR-1's smoke pin to all of `plugins/` | `docs/SPEC.md:27` (+ grep sweep), `tests/smoke.py` | P2 |
| B10 | the dead `~/.claude/dream-beta-tester/` home persists in FOUR shipped-script docstrings + a skill-reference doc, untouched by B1-B4 | `scripts/beta_checks.py:12-13`, `scripts/snapshot.py:39-40`, `scripts/run_beta.py:54`, `scripts/render_beta_report.py:11`, `skills/dream-beta-test/references/lenses.md:64` | P1 machine/maintainer-doc |

## B1 — point the machine contract at the live paths

**Current.** CONTRACT.md tells an orchestrator to RUN `~/.claude/dream-beta-tester/ci_check.sh` and
read `~/.claude/dream-beta-tester/reports/latest.json` (:9-10; repeated in the loop pseudocode
:37-38). That home is the pre-plugin standalone — absent on a fresh install, and on the maintainer
box a stale separate repo whose `latest.json` still says `regression / ship_ok:false` (v0.1.40,
2026-06-22). The live gate (ci_check.sh:16-17) writes `${DREAM_BETA_REPORTS:-$HOME/.dream-beta-test/reports}/latest.json`.
`maintainer/README.md:22` already names the right path — the shipped docs disagree internally.

**Change.** In CONTRACT.md: RUN → the plugin checkout's `plugins/dream-beta-tester/maintainer/ci_check.sh`
(the orchestrator develops consolidate-memory, so the repo-relative path is the stable one; note the
installed-cache glob the pre-push hook uses as the alternative), RESULT →
`~/.dream-beta-test/reports/latest.json`, with the `DREAM_BETA_STATE` / `DREAM_BETA_REPORTS` env
overrides documented once. All four lines.

**Acceptance.** `grep -rn 'claude/dream-beta-tester' plugins/dream-beta-tester/` → **exactly 3
deliberate hits, never more**: `maintainer/install-gate.sh` (the v0.1.41 stale-hook HISTORY note) and
`docs/SPEC.md` ×2 (the explicitly-labeled "superseded" draft-placement block, B4). *(Gate-2b
correction: this acceptance originally said "0 hits" — falsified by B4's own kept-history block and
B10's own kept-history note, both deliberate per THIS spec. A future re-verification must not read
those 3 as a regression; the actual anti-regression gate for CONTRACT.md/emit_result.py/STATUS.md/
scripts/skill-reference specifically is B10's narrower grep below.)* The documented RUN path exists
in-tree; the documented RESULT path matches ci_check.sh's default
exactly ($STATE/reports/latest.json with $STATE default `~/.dream-beta-test`).

## B2 — emit_result truthfulness

**Current.** (a) `:83-84` `fix_reference` names `~/consolidate-memory-v0.1.19-defects.md` (a personal
HOME file) and `~/.claude/dream-beta-tester/STATUS.md` (the dead home). (b) `:46` parses stdin with
`raw[raw.find("{"):]` — the FIRST-brace heuristic beta_checks itself rejected (`_last_json_object`,
its docstring cites why). Latent-only today (oracle stdout is pure JSON) but it's the exact
divergence class the repo documents. (c) `:51` `st_ok = a.self_test_ok != "false"` — any
typo/garbage silently TRUSTS the self-test (fail-open toward "harness OK", the wrong direction).

**Change.** (a) fix_reference → the in-plugin docs: "patch by `defect_ref` — see the dream-beta-tester
plugin's `docs/STATUS.md` fixed-vs-open table". (b) Replace with a last-JSON-object parse (small
inline copy of the beta_checks approach, comment naming the shared rationale — the two scripts share
no import path by design). (c) `st_ok = a.self_test_ok == "true"` — garbage now fails toward
`selftest_broken` (distrust), matching the guardrail's intent.

**Acceptance.** New smoke checks: (b) a stdin payload with a stray `{` in a WARN title before the
real JSON object still parses to the right verdict (pre-fix FAILS); (c) `--self-test-ok TRUE|""|junk`
→ `selftest_broken` (pre-fix: `clean`/trusted — FAILS); (a) grep: no `~/` personal path in
emit_result output fields.

## B3 — STATUS.md refresh (currency, not rewrite)

**Change.** Update the header (built 2026-06-21 · **refreshed 2026-07-05, validated against
v0.1.68/0.1.69**), the layout paragraph (:83-85 → the plugin layout: engine in
`plugins/dream-beta-tester/scripts/`, skill at `skills/dream-beta-test/`, state at
`~/.dream-beta-test/`), the validation matrix (append the current both-ends proof produced by B5/B6
acceptance runs), and the known-gap list (count-based self-test → CLOSED by B6; add the two
still-open items honestly: cycle_identity is identity-by-construction, the mutating-dream path stays
unwired). History stays — it's the provenance log.

**Acceptance.** STATUS names no dead path — a BROADER grep than B1's (`claude/dream-beta-tester`
alone misses :85's `~/.claude/skills/dream-beta-test/`, a different dead string): use
`grep -inE 'claude/(dream-beta-tester|skills/dream-beta-test)'` → 0 hits; its families table lists
`usage_capture`/`demotion_capture` with min-versions; its self-test section describes ID-matching.

## B4 — SPEC.md surgical truth fix

**Change.** (:27) the non-goal becomes "Ships as its own plugin (`plugins/dream-beta-tester/` in the
consolidate-memory repo) — consumer-only: it never patches the skill it tests" (drops the false
path claim AND the `/home/<user>` literal). (§2 :31-52) prepend one banner line — "*(v0.1 design
draft — placement superseded by the shipped plugin layout; see STATUS.md)*" — and update the tree
block to the shipped paths (engine/scripts, fixtures, maintainer, docs, skill; state at
`~/.dream-beta-test/`). The design prose (any-repo rules, D1/D2 lesson) is still true — keep it.

**Acceptance.** No `/home/<user>` literal anywhere under `plugins/dream-beta-tester/` (B9's widened
pin enforces permanently); SPEC's placement section names only shipped paths.

## B5 — grow the oracle floor to the shipped contract (the QA-currency P1)

**Current.** The blocking gate's real floor is ~v0.1.37: the gate fixture has no
`.consolidation-log.jsonl`, so `dream_arc_capture` (min 0.1.54) and `distill_capture` (min 0.1.55)
**never emit a row on the empty-log guard** (`_latest_capture_check` returns `[]` at the
`if not ctx.log_records: return out` short-circuit, beta_checks.py:1204) — they are therefore
absent from BOTH `families_ran` and `families_skipped` (:1331-1332 computes `families_skipped` as
families that emitted a row minus `families_ran`; a family with zero rows is in neither set). NOT
"SKIP-by-empty" in the sense of a visible SKIP result — they're invisible, which is arguably worse.
Nothing covers the index-lifecycle ladder (v0.1.63 usage · v0.1.66 hard ceiling · v0.1.67
demotion/miss/utility). A Phase A/B/C regression ships green through the gate; only the 695-check
smoke suite covers it, and only in-repo.

**Change.** Two legs, both reusing the existing v0.1.55 capture scaffold (`beta_checks.py:1190`):
1. **Fixture carries a persisted dream.** `make_fixture.py` additionally writes a
   `.consolidation-log.jsonl` with ONE current-shape cycle record (dream + distill + usage +
   demotion blocks present, honest dormant/zero values) into the gate store. Dot-file state is
   invisible to the fact scans (D3/D4 token math unchanged — verify in acceptance).
2. **Two new capture families** via the scaffold: `usage_capture` (block_key `usage`, min_version
   (0,1,63)) and `demotion_capture` (block_key `demotion`, min_version (0,1,67)) — same
   presence+shape assertions the dream/distill captures make, version-gated SKIP below min.

**Acceptance.** (pre-fix evidence, corrected at Gate-1B) gate run on the OLD fixture:
`dream_arc_capture` and `distill_capture` are absent from BOTH `families_ran` AND `families_skipped`
(they return `[]` on the empty-log guard, emitting no row at all — not a visible SKIP) →
(post-fix) gate run on the regenerated fixture: `families_ran` includes dream_arc_capture,
distill_capture, usage_capture, demotion_capture — none absent, none SKIP-by-empty — AND the canary
still FAILs D3+D4 (fixture change didn't defuse the known-bad proof — the dot-file log is invisible
to the `store.glob("*.md")` fact scan that D3/D4 measure); summary totals grow accordingly;
`beta_checks.py --json` on the cm working tree stays 0 FAIL. *(Operational note: an existing
on-disk `~/.dream-beta-test/gate-repo` fixture from a prior `install-gate.sh` run stays log-less —
and captures keep being invisible — until `install-gate.sh` is re-run to regenerate it with the new
log; state this in the PR's rollout steps so a stale local fixture doesn't look like a regression.)*

## B6 — ID-matched self-test (close the false-green class STATUS already names)

**Current.** ci_check.sh:50-51 trusts `CFAIL >= 2` — ANY two spurious FAILs (the 2026-06-22
incident's exact shape) prove "detection" without detecting the actual defects. STATUS.md:24-26
documents this as the recommended hardening; observed today: canary_fail=4, so the count check is
even less diagnostic.

**Change.** The canary leg parses the canary run's FAIL **ids** (`run_oracle` already writes
`FAIL {id} …` to its stderr detail file, ci_check.sh:40 — the id-parse extends that, no new plumbing)
and requires `{CHK-GATE-BACKFILL, CHK-EVICT-STAGE} ⊆ ids` (the real D3/D4 identities, cross-checked
against beta_checks.py:813-839/:881-887 and STATUS.md:53/CONTRACT.md:72). Count drops to a reported
detail. On a miss → the existing SELFTEST_BROKEN path (fail-open + loud, verdicts untrustworthy).
emit_result's `self_test` gains additive fields `expected_ids` + `detected_ids` (schema stays
`result/v1` — additive, consumers unaffected; update CONTRACT.md:26's `self_test` field list to
match — doc-currency is this track's whole theme, so the contract table can't itself go stale on
day one). *(Note the B6/B7a synergy: a renamed triage helper turns CHK-EVICT-STAGE into a SKIP
instead of a FAIL on the canary run → the subset check fails → SELFTEST_BROKEN — B7a's honesty
label and B6's id-match reinforce each other.)*

**Acceptance.** (both ends) Real canary → self_test.ok true with both ids in detected_ids;
sabotage evidence run — point the canary at an EMPTY scripts dir (the 2026-06-22 spurious-FAIL
shape): old logic would pass on count, new logic → SELFTEST_BROKEN. Recorded on the PR.

## B7 — oracle honesty labels

**Change.** (a) `safe_suggestion`/D4: when the store is over budget but `_skill_triage` resolves
None (helpers renamed/absent), emit an explicit SKIP result — "D4 leg not provable: triage helpers
unavailable" — instead of silently omitting the FAIL-capable leg (families_skipped then shows it;
B6's ID-matched self-test is the systemic backstop — a defused D4 kills the canary's
CHK-EVICT-STAGE and trips SELFTEST_BROKEN). (b) `cycle_identity`: label the two checks
identity-by-construction in their result `basis` + docstring + STATUS (they cannot fail in
scripts-only mode); the contaminated-record probe that would make them fail-capable is a declared
NON-GOAL this cycle (needs a synthetic contaminated seed harness — roadmap).

**Acceptance.** Gate run with a stub skill dir missing the triage helpers over an over-budget
store → an explicit SKIP row (pre-fix: silent green); cycle_identity rows carry the basis label.

## B8 — portability + fixture-builder hygiene

**Change.** (a) install-gate.sh:34 `sed -i` → POSIX tmp+mv loop (BSD/macOS `sed -i` needs a suffix
arg; a failed graft = un-grafted canary = the exact false-green B6 closes — belt and suspenders).
(b) ci_check.sh `/tmp/.dbt_canary`, `/tmp/.dbt_detail` → `mktemp` (TMPDIR-portable, no fixed name in
a world-writable dir). (c) make_fixture.py: argparse with a positional target that REFUSES a
leading-'-' path (the audit's live repro: `make_fixture.py --help` created a `./--help/` fixture),
`--help` now documents usage; every `write_text` gains `encoding="utf-8"` (the one plugin script
breaking the discipline).

**Acceptance.** `make_fixture.py --help` exits 0 printing usage, creates NOTHING (pre-fix: creates
`./--help/`); `sh -n` passes both maintainer scripts; grep: no bare `write_text(` without encoding
in dbt scripts; no literal `/tmp/.dbt` in ci_check.sh.

## B9 — genericity closure (depends on PR-1)

**Change.** Scrub the dbt tree of personal-path literals (SPEC.md:27 via B4; sweep
`grep -rn '<user>' plugins/dream-beta-tester` for any residue), then widen PR-1's smoke genericity
pin roots from `plugins/consolidate-memory` to `plugins` (both plugins covered; allowed-set
unchanged). THIS is the item that forces the branch-after-PR-1-merge sequencing.

**Acceptance.** Widened pin green; sabotage evidence: re-adding a `/home/<realname>` line to any dbt
file flips the pin red.

## B10 — scrub the dead home from shipped scripts + skill reference (Gate-1B finding)

**Current.** B1/B3/B4 fix the dead `~/.claude/dream-beta-tester/` home in CONTRACT.md, emit_result.py,
STATUS.md, and SPEC.md — but the SAME false claim survives, untouched, in five more places:
- `scripts/beta_checks.py:12-13` — "It lives OUTSIDE the skill (`~/.claude/dream-beta-tester/`) and
  NEVER patches it."
- `scripts/snapshot.py:39-40` — the same claim.
- `scripts/run_beta.py:54` — the same.
- `scripts/render_beta_report.py:11` — the same.
- `skills/dream-beta-test/references/lenses.md:64` — "add a family to
  `~/.claude/dream-beta-tester/beta_checks.py`" (an instruction that, followed literally, edits a
  file that doesn't exist in a fresh install rather than the real `plugins/dream-beta-tester/scripts/beta_checks.py`).

These four are SHIPPED script docstrings — read by every contributor who opens the file, not just an
orchestrator following CONTRACT.md — so leaving them is the exact "shipped truth surface decayed"
defect this whole track exists to close. B9's widened genericity pin **cannot** catch this: it
matches `/home/<name>` and `-home-<name>-`, not the literal string `~/.claude/dream-beta-tester/`
(a real path, not a username) — so nothing enforces the fix without this item.
(`maintainer/install-gate.sh:53` also names the dead home, but as HISTORY documenting the v0.1.41
stale-hook bug — like STATUS.md's provenance log, that one stays.)

**Change.** Reword all five: the four docstrings → "lives as its own plugin
(`plugins/dream-beta-tester/`) and never patches the skill it tests"; lenses.md:64 → "add a family
to `plugins/dream-beta-tester/scripts/beta_checks.py`" (or, better, the plugin-relative phrasing
CONTRACT.md now uses post-B1, so the two docs stay consistent).

**Acceptance.** `grep -rn 'claude/dream-beta-tester' plugins/dream-beta-tester/scripts
plugins/dream-beta-tester/skills` → 0 hits (install-gate.sh is out of this grep's path — its
historical mention is intentional and unaffected); the five sites read the corrected phrasing.

## Non-goals (deliberate)

- **cycle_identity contaminated-record probe** — roadmap (needs a synthetic contamination harness;
  B7 labels the limitation honestly instead).
- **The mutating-dream E2E path** — unchanged known limitation, restated in STATUS.
- **Auto-running the lens pass** — the gate stays deterministic-only by design; lens-debt
  VISIBILITY (a `cm status` advisory) is Track-D/roadmap material, not a dbt change.
- **CONTRACT schema bump** — all emit_result additions are additive inside `self_test`; `result/v1`
  holds.

## Rollout

- Branch `fix/dbt-truth-restoration` off main AFTER PR-1 merges; one PR (PR-2), full body with the
  both-ends acceptance evidence; merge reserved.
- `plugins/dream-beta-tester/.claude-plugin/plugin.json` version 0.1.6 → **0.1.7** in the PR (dbt has
  no CHANGELOG; STATUS.md carries the change log entry — cm's CHANGELOG.md is NOT touched).
- Gates: smoke/mypy/manifests/`claude plugin validate --strict` + the B5/B6 both-ends oracle proof +
  Gate 2a full `/code-review` on the diff; Gate 2b on the PR.
- PR body includes a re-run of `install-gate.sh` against the regenerated fixture (B5's operational
  note) so the both-ends oracle proof reflects the NEW fixture, not a stale on-disk one.
