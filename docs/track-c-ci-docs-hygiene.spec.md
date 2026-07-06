# CI + repo-doc hygiene (Track C) — spec DRAFT

<!-- Materializes as docs/track-c-ci-docs-hygiene.spec.md on branch fix/ci-docs-hygiene.
     SEQUENCING (corrected at Gate-1C): Track C is main-INDEPENDENT — Track A's diff never
     touched README.md/CLAUDE.md (confirmed empty diff on those files) and Track B's scope
     is entirely plugins/dream-beta-tester/ + tests/smoke.py's pin (not top-level docs), so
     there is no real rebase dependency and Track C could branch off main today. Landing it
     last is a discretionary PR-queue preference (land the low-risk polish after the two
     behavioral tracks so review attention goes to A/B first), not a technical requirement. -->

**Provenance:** the 2026-07-05 four-lens audit's "go-external gate" items (F-P2-2 no CI,
F-P3 onboarding/doc gaps) — the last tranche before the skillset is comfortable in front
of strangers. No behavioral script changes; this track is CI + docs + repo metadata only.

## Scope

| ID | Finding | File(s) | Class |
|---|---|---|---|
| C1 | no CI — contributor PRs get zero automated gate | `.github/workflows/` (empty) | P2 release-eng |
| C2 | README has no uninstall/data-purge instructions | `README.md` | P3 onboarding |
| C3 | README has no explicit platform-support statement | `README.md` | P3 onboarding |
| C4 | README architecture tree omits `dashboard.template.html` | `README.md:229-250` | P3 cosmetic |
| C5 | README never mentions the second plugin (dream-beta-tester) | `README.md` | P3 discoverability |
| C6 | CLAUDE.md Layout tree omits the ENTIRE dream-beta-tester plugin | `CLAUDE.md:34-59` | P2 maintainer-doc |
| C7 | CLAUDE.md "byte-pinned copies" overstates a behavioral pin | `CLAUDE.md:51` | P3 precision |
| C8 | repo has no topics (discoverability only) | GitHub repo metadata | P3 |

## C1 — CI workflow

**Current.** `.github/workflows/` exists but is empty and untracked (confirmed:
`git ls-files .github/` → 0 hits). `plugins/dream-beta-tester/maintainer/ci_check.sh` is
scaffolded but nothing remote invokes it. The only gate on this public, auto-updating
plugin is the maintainer's local, gitignored `release.sh` + pre-push hook — a contributor
PR from a fork gets no automated check at all.

**Change.** Add `.github/workflows/ci.yml`:
- Triggers: `pull_request` (any branch → main) + `push` (main).
- Job `test`: matrix `python-version: ["3.10", "3.11", "3.12", "3.13"]` (the range this
  repo already claims "validated" — CLAUDE.md/README's "3.8+ stdlib; validated on
  3.10–3.13"). Steps: checkout, `actions/setup-python@v5`, run
  `python3 tests/smoke.py`, `python3 tests/validate_manifests.py`,
  `python3 tests/simulate_accumulation.py` (each a separate step so a failure names
  which suite broke).
- Job `typecheck` (single version, 3.11): `pip install mypy` (the one CI-only, dev-only
  dependency — never a runtime one; matches CLAUDE.md's existing "mypy is dev-only, not
  part of the dep-free smoke.py gate" framing) + `mypy --config-file mypy.ini`.
- Job `manifest`: `claude plugin validate ./plugins/consolidate-memory --strict` +
  `claude plugin validate ./plugins/dream-beta-tester --strict` + `claude plugin
  validate .` (marketplace) — **guarded**: the `claude` CLI's availability in a bare
  Actions runner is unverified; this job is written to install it if a documented
  install method exists, else to `continue-on-error: true` with a comment explaining
  why, rather than blocking every PR on an unverified toolchain step. *(Implementation
  note for whoever picks this up: resolve this ONE question empirically — is there an
  npm/curl installer for the `claude` CLI suitable for CI — before finalizing; the
  Python-suite jobs are the load-bearing gate either way and must not be blocked by it.)*

**Non-goal, explicit:** a 3.8/3.9 interpreter job. The floor is a *code-discipline* claim
(no 3.9+-only syntax), not a currently-CI-tested one, and adding untested-until-now
interpreters mid-audit risks surfacing unrelated failures out of this track's scope. Track
D (1.0 criteria) is where "restate the floor as 3.10+ or actually test 3.8" gets decided
— flagging it there, not silently resolving it here.

**Acceptance.** Workflow file is valid YAML (`python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`
— acceptable one-off use of PyYAML if available, else a plain structural read); a
throwaway PR (or `act`, if available locally) shows all matrix legs green on the current
tree (which is already smoke/mypy/manifest-clean).

## C2 — uninstall / data-purge instructions

**Change.** Add a subsection under **Install** (after the existing install block):
"### Uninstall / purge your data" — `/plugin uninstall consolidate-memory` removes the
code; your consolidated memory is separate and untouched by uninstall (the whole privacy
posture depends on this being explicit) — to also purge data: remove `~/.claude/memory/`
(the global cross-project store) and/or `~/.claude/projects/<slug>/memory/` per project
(the per-project store), both plain directories of markdown, safe to `rm -rf` by hand.
Explicitly warn these are NOT recoverable once removed.

**Acceptance.** Section present; names both store locations correctly (cross-check
against `harness-map.md`'s path table — no drift from the actual paths the scripts use).

## C3 — platform-support statement

**Change.** One line in **Privacy & security** (which already states stdlib-only/3.8+/no
network): "Portable by construction — pure Python + read-only `git`, no POSIX-only
modules (`fcntl`/`pwd`/`grp`/`termios`) — works on Linux and macOS; on native Windows, run
it under WSL (the `cm` dev CLI is a POSIX shell script; end users interact only through
the skill, not `cm`)." *(Gate-1C correction: the draft originally also claimed "UTF-8 I/O
throughout … every file op passes `encoding=`" — FALSE on main today: four `read_text`/
`write_text` calls omit it — `extract_signals.py:309`, `memory_status.py:1612`,
`sync_global.py:689`, `sync_global.py:695`. Track C is docs-only and can't fix runtime
code, so the claim is DROPPED rather than shipped false; the surviving no-POSIX-modules
claim is independently true and doesn't depend on the encoding sub-claim. The encoding gap
itself is a real, if minor, robustness item — Track D follow-up, not Track C's to fix or
claim away.)* This is a claim I can back with the runtime audit's own verified findings,
not a new claim — no untested assertion.

**Acceptance.** Statement present; every sub-claim traceable to an audit finding already
confirmed (this spec doesn't introduce a new portability test — Track D/CI's matrix is
the actual multi-version proof; this is prose, gated by "don't claim what wasn't shown").
Verify at implementation time: re-run the no-POSIX-modules grep fresh (the shipped claim) —
don't rely on this spec's citation going stale; separately, `grep -rn 'read_text\|write_text'
plugins/consolidate-memory/scripts/*.py` re-checks the correction-note's four DROPPED-claim
citations above are still accurate (not the shipped line itself, which no longer asserts it).

## C4 — architecture tree completeness

**Change.** Add `dashboard.template.html` as a line under `scripts/` in README's tree
(a real tracked dependency of `render_html.py`, currently omitted from both README and
CLAUDE.md's trees — CLAUDE.md's copy is fixed by C6).

**Acceptance.** `dashboard.template.html` appears in the rendered tree with a one-line
role description ("the HTML shell `render_html.py` fills").

## C5 — mention the second plugin

**Change.** One short paragraph (placed after **Install**, before **Usage**): "This repo
ships a second, optional plugin — **`dream-beta-tester`** — a QA companion that
beta-tests consolidate-memory *itself* (a deterministic regression oracle + an agent-
driven judgment-lens pass, `/dream-beta-test`). It's for maintainers/contributors
validating a change, not needed for normal day-to-day `dream` use; install it the same
way (`/plugin install dream-beta-tester@zenetusken-plugins`) if you want to help QA new
versions." Keeps the pitch focused (README's whole voice is about the memory tool) while
closing the "the second plugin doesn't exist in end-user docs" gap.

**Acceptance.** Paragraph present, correctly distinguishes "optional/maintainer-facing"
from the core plugin so a first-time reader isn't confused about which one they need.

## C6 — CLAUDE.md Layout: add the missing plugin

**Current.** CLAUDE.md's `## Layout` tree (:34-59) documents ONLY
`plugins/consolidate-memory/` — the entire `plugins/dream-beta-tester/` tree (its own
`.claude-plugin/plugin.json`, `scripts/`, `skills/dream-beta-test/`, `fixtures/`,
`maintainer/`, `docs/`) is unmentioned, despite CLAUDE.md's own framing ("This repo is
both the plugin and its marketplace") implying a complete map. A maintainer reading
CLAUDE.md for orientation has no idea the second plugin exists until they `ls plugins/`.

**Change.** Two edits to the Layout tree:
1. *(Gate-1C correction: C4 claimed this item also fixes CLAUDE.md's `dashboard.template.html`
   omission — it didn't, until now.)* In the EXISTING `plugins/consolidate-memory/` block,
   insert one line right after `CLAUDE.md:49`'s `render_html.py` row (same terse style):
   `    dashboard.template.html         the HTML shell render_html.py fills`.
2. Add a second top-level block to the Layout tree (same terse style as the existing one,
   pointing at `plugins/dream-beta-tester/docs/STATUS.md` for the full design rather than
   duplicating it — mirrors how the existing block points at SKILL.md/harness-map.md
   instead of inlining them):
```
plugins/dream-beta-tester/          QA companion plugin — beta-tests the dream skill itself
  .claude-plugin/plugin.json        plugin manifest
  skills/dream-beta-test/SKILL.md   the judgment-lens pass (/dream-beta-test)
  scripts/                          the deterministic oracle (beta_checks.py) + snapshot/report/run
  maintainer/                       the continuous-QA pre-push gate (ci_check.sh/install-gate.sh)
  docs/STATUS.md                    full design + validation matrix (see there, not here)
```

**Acceptance.** Layout tree lists both plugins; the existing consolidate-memory block now
names `dashboard.template.html` (making C4's "fixed by C6" claim true — `grep -n
'dashboard.template' CLAUDE.md` → ≥1 hit); no duplication of Track B's STATUS.md content
(a pointer, per the existing convention for the first plugin).

## C7 — correct the byte-pin wording

**Current.** `CLAUDE.md:51` says `render_dashboard` "keeps byte-pinned copies" of `_ui`'s
vocabulary. The packaging audit confirmed the actual guard (`tests/smoke.py`'s drift-pin)
asserts *behavioral* equality (`ui.rule() == rd._rule()`, `ui.CODES == rd._CODES`, etc.),
not a literal source-byte comparison — arguably a better guard (semantics survive a
reformat) but "byte-pinned" overclaims what it checks.

**Change.** Reword to: "render_dashboard keeps its OWN copies of `_ui`'s vocabulary,
behaviorally drift-pinned against it by a smoke test (output equality, not literal source
bytes)."

**Acceptance.** No remaining "byte-pinned" claim in CLAUDE.md; the corrected sentence
accurately describes `tests/smoke.py`'s actual assertion shape (already verified by the
packaging audit — this is a doc-only fix, no test change needed).

**Known residual (Gate-1C, deliberately deferred):** the identical "byte-pinned"/
"byte-identical" overclaim also appears in `plugins/consolidate-memory/scripts/_ui.py:8,10`
(a docstring) and `tests/smoke.py:898` (a comment) — both script/test files, outside this
docs-only track's remit. After C7, CLAUDE.md will correctly say "behavioral" while these
two still say "byte-identical" — a residual internal disagreement, left for whoever next
touches those files (or a Track-D sweep) rather than smuggled into a docs-only PR.

## C8 — repo topics

**Change.** `gh repo edit Zenetusken/consolidate-memory --add-topic claude-code
--add-topic claude-code-plugin --add-topic memory --add-topic ai-agents --add-topic
context-management` — discoverability only, no functional effect. Executed as part of
this track's landing (a `gh` command, not a code change), recorded in the PR body rather
than run ad hoc, so it's reviewable alongside everything else in Track C rather than a
silent out-of-band edit to shared GitHub state.

**Acceptance.** `gh repo view --json repositoryTopics` shows the five topics post-run.

## Non-goals (deliberate)

- **Resolving the CI-floor question (3.8 vs 3.10+ as the tested floor)** — Track D/1.0
  decision, explicitly deferred (see C1).
- **A full private-security-posture rewrite** — SECURITY.md is already public-audit-grade
  per the packaging lens; this track only touches README/CLAUDE.md.
- **Anything in `plugins/dream-beta-tester/`'s own docs** — that's Track B's file scope
  (CONTRACT.md/STATUS.md/SPEC.md); C5/C6 here only ADD a pointer to it from the top-level
  repo docs, never edit its internals.

## Rollout

- Branch `fix/ci-docs-hygiene` off main — **not gated on PR-1/PR-2 merging** (Gate-1C
  correction: Track A's README/CLAUDE.md diff is empty and Track B never touches top-level
  docs, so nothing here actually depends on either landing first; C7's wording fix is
  unrelated to Track B entirely, and C6 only adds a stable pointer to STATUS.md, never its
  content). Landing it after A/B is a discretionary PR-queue choice — the low-risk polish
  reviewed last so attention goes to the two behavioral tracks first — not a technical
  requirement; starting Track C sooner (even in parallel) is equally valid.
- One PR (PR-3), full body (CI run screenshot/link + topics-set confirmation); merge
  reserved.
- No version bump — CI/docs/metadata only, nothing in `plugins/consolidate-memory/` or
  `plugins/dream-beta-tester/` changes, so neither plugin's `plugin.json` moves.
- Gates: this is the lowest-risk track (no runtime code touched) — Gate 2a can run at a
  lighter proportionate cut per the user's own calibration language ("full fan-out" is
  for behavior-changing diffs; a prose+CI-yaml diff is a natural candidate to ask about
  scope when Gate 2a starts, rather than assume). Gate 2b (PR review) still runs full.
