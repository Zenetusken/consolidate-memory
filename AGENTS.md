# AGENTS.md — consolidate-memory

Agent operating manual for this repo, authored from a 5-agent codebase map and
verified against the live tree at **v0.4.5** (2026-09-03). `CLAUDE.md` holds the
same conventions with more narrative; where they disagree, the live files win.
Under the plugin's own tier model this file is an on-demand store — read it when
you work here; the always-loaded store is `CLAUDE.md` + the auto-memory
`MEMORY.md` index.

## What this is

A **Claude Code plugin**: cross-project, verification-first memory for agents — the
layer beyond Claude Code's built-in per-project Auto Dream, adding a governed
cross-project store plus verification against the live code. This repo is both the
plugin and its marketplace. Two plugins ship from it:

| Plugin | Version | Role |
|---|---|---|
| `consolidate-memory` | 0.4.5 | The product: a 6-phase `dream` workflow, StoreContext-resolved native stores, operator-enrolled domain isolation, SQLite control plane + journal (sole authority for holders/grants/migration state per ADR 023), sole canonical writer, `cm local` native writer (local recall-key pointer + `extract_wikilinks` as pull), facts-manifest beacon/pull cache, paginated journal inventory, tiered context-budget accounting. Unenrolled projects are local-only. |
| `dream-beta-tester` | 0.1.8 | The QA companion: beta-tests the dream skill itself — deterministic invariant oracle + judgment-lens pass + maintainer pre-push gate |

End users install with `/plugin marketplace add Zenetusken/consolidate-memory` +
`/plugin install consolidate-memory@zenetusken-plugins`. The marketplace must be
added via Git `owner/repo` shorthand — never a URL to `marketplace.json` (its
relative source paths only resolve over Git).

## Commands you will actually run

**Dev loop** — after any change to `plugins/consolidate-memory/scripts/`:

```bash
python3 tests/smoke.py                          # the zero-dep gate — ~1505 assertions over every script's
                                                # pure functions + the cross-module pins; exit 1 on any failure
python3 tests/simulate_accumulation.py          # lifecycle accumulation sim (probes A–W + X–AF) — the
                                                # store-mechanics gate; CI runs it too
mypy --config-file mypy.ini                     # dev-only TypedDict contract check (mypy is NOT a runtime dep)
./cm status                                     # spot-check Phase-0 output
python3 tests/validate_manifests.py             # portable manifest checker (it has NO --strict flag;
                                                # --strict belongs to the claude CLI)
claude plugin validate ./plugins/consolidate-memory --strict   # when iterating on the published artifact
```

CI (`.github/workflows/ci.yml`, one workflow, **6** jobs) runs the same gates: `test`
(smoke + manifests + sim on Python **3.8–3.13**, with 3.8/3.9 pinned to
ubuntu-22.04, **no pip install — that IS the stdlib-only proof**), `test-macos`
(Python 3.12), `concurrency` (process-level races, Python 3.12), `typecheck` (mypy,
dev-only label), `manifest` (`claude plugin
validate --strict`, a real blocking gate — no continue-on-error), `bench` (the
capacity SLO corner: `bench_phase5.py --quick`, measured — not gated — with the
report stored as a run artifact).

**Dogfood / dev install**: `claude plugin marketplace add ./` then
`claude plugin install consolidate-memory@zenetusken-plugins`. Script edits are
live on the next run (exec'd fresh); SKILL.md body edits need `/reload-plugins` or
a new session; `plugin.json`/`marketplace.json` edits need
`claude plugin marketplace update` + `/reload-plugins`.

**`cm`** — maintainer CLI over the scripts, symlink-safe via `readlink -f` (install:
`ln -s "$(pwd)/cm" ~/.local/bin/cm`); end users never touch it — they open
`~/.claude/projects/<slug>/dashboards/index.html`. Subcommands:
`status` `seed` `extract` `distill` `sync` `pull` `gc` `promote` `tokens`
`utility` `harvest` `staleness` `workflows` `calibration` `beacon` `network`
`render` `report` `log` `doctor` `conflicts` `resolve` `repair-mirror`
`canonical` `migrate` `data` `journal` `forget` `project`. Native paths come from `cm doctor`
(`StoreContext`); never hand-build `~/.claude/projects/<slug>/memory`.

## Layout

```
.claude-plugin/marketplace.json   the marketplace catalog (zenetusken-plugins; NO version field —
                                  version lives only in plugin.json)
plugins/consolidate-memory/       the main plugin (= ${CLAUDE_PLUGIN_ROOT})
  .claude-plugin/plugin.json      manifest; its version is THE release trigger (startup auto-update reads it)
  skills/consolidate-memory/
    SKILL.md                      the 6-phase dream workflow + tier model + cycle-record schema block
                                  (smoke-pinned to CycleRecord.__annotations__ — edit together or fail)
    references/harness-map.md     paths, fact schema, verification recipes, cross-project model
  hooks/hooks.json                SessionStart hook (matchers startup+resume, 2s timeout) → session_beacon.py
  scripts/                        stdlib-only runtime: store_context.py (sole native/canonical path
                                  constructor), identifiers.py (contained domain/stem/project ids),
                                  domain_policy.py, control_plane.py (SQLite + locks +
                                  journal), canonical_ingress.py (sole canonical writer),
                                  mirror_conflict.py, index_admission.py, capabilities.py,
                                  retention.py, local_ingress.py, cm_ops.py (doctor/conflicts/resolve/
                                  migrate/data/project enroll/journal/local), memory_status.py (contract seed + audit),
                                  extract_signals.py, sync_global.py, distill_scan.py,
                                  render_dashboard.py, render_html.py, render_log.py, _ui.py,
                                  session_beacon.py, dashboard.template.html
plugins/dream-beta-tester/        QA companion plugin
  .claude-plugin/plugin.json      manifest (v0.1.8)
  skills/dream-beta-test/         judgment-lens skill (/dream-beta-test) + references/lenses.md (7 lenses)
  scripts/                        deterministic oracle (beta_checks.py) + run/render/emit helpers
  fixtures/                       make_fixture.py + make_cycle_probe.py + canary-v0.1.19/ (VENDORED
                                  tag-faithful known-bad scripts, SHA256SUMS-manifested) — the generated
                                  STORES live under ~/.dream-beta-test/, never committed
  maintainer/                     ci_check.sh + install-gate.sh — the pre-push gate
  docs/                           SPEC.md (design-of-record) · STATUS.md (validation matrix + defect log)
                                  · CONTRACT.md (reports/latest.json schema + self-heal contract)
cm                                 dev CLI over the scripts (doctor/conflicts/canonical/migrate/data
                                  /project enroll included; symlink-safe)
docs/adr/                         001 empty-set judgment · 002 StoreContext · 003 domain isolation ·
                                  004 stable identity · 005 three-way mirrors · 006 control plane ·
                                  007 schema v2 / migrate · 008–016 0.3.0 hardening ·
                                  017 journal complete-old · 018 StoreContext authorization ·
                                  019 forget-ack / domain lifecycle
tests/                             smoke.py · simulate_accumulation.py · validate_manifests.py
memory/                            GITIGNORED placeholder (.gitkeep only) — the real global store lives at
                                   ~/.claude/memory (a real dir, decoupled from this repo)
```

## Core contracts — do not break these

1. **The cycle record is the contract.** `memory_status.py --seed` seeds it, the
   phases fill it, `render_dashboard.py` renders it. Shape = `TypedDict`s in
   `memory_status.py` (`CycleRecord`, 20 top-level keys, all `total=False`).
   `validate_cycle_record` warns (stderr, never blocks) on wrong container types
   and impossible counts beyond the scanner caps (`_DISTILL_CAPS = (40, 20)`).
   Changing the schema means updating the seed, the renderer, the TypedDicts, and
   SKILL.md's schema block together — a smoke test pins the SKILL block to
   `CycleRecord.__annotations__`, so they cannot silently drift.
2. **Zero runtime dependencies.** Scripts are stdlib-only, Python 3.8+ (TypedDict
   and type hints are stdlib + runtime-invisible). CI's test job installs nothing.
   mypy is a dev-only maintainer tool.
3. **Model produces data, scripts produce presentation.** Never hand-write report
   prose — emit a cycle record and render it.
4. **Cross-module drift pins exist because real drift happened.** smoke.py
   behaviorally pins `_ui.py` ↔ `render_dashboard.py` (output equality, not source
   bytes), `_DISTILL_CAPS` ↔ `distill_scan.py` caps, a 5-way `slug_for` agreement
   (memory_status / dream-beta snapshot / beta_checks / render_beta_report /
   make_fixture — make_fixture drifted in v0.1.40), and single-source identity
   (`sg._frontmatter is ms._frontmatter` etc.). If you reimplement a shared helper
   as a local copy, the gate fails by design — alias it instead.
5. **StoreContext is the only native/canonical path constructor** (ADR 002). Do not
   build `~/.claude/projects/<slug_for(cwd)>/memory`. Managed settings win over
   user/project/local/`--settings`. Writes fail closed on disagreement or disabled
   auto-memory. `cm canonical upsert` is the sole canonical writer. Native 200-line/25KB
   caps apply only to a project's `MEMORY.md`, not the generated global catalog.
6. **Public-repo safety.** Never commit personal memory — the shared store lives at
   `~/.claude/memory` (outside the repo; dual-read with domain dirs until
   `cm migrate --apply`); repo-root `memory/` is a gitignored
   placeholder. Verify with
   `git ls-tree -r --name-only origin/main | grep memory` (expect only
   `memory/.gitkeep`). Keep the skill generic: placeholders, no real user paths —
   smoke.py's genericity scan enforces this over both plugins, tests/, and docs/.
   Don't weaken the secrets firewall: `extract_signals.py` drops credential-shaped
   turns to `(omitted: …)` labels at retrieval, and the same `_looks_secret` gate
   covers commit subjects and distill emission.
7. **The only hook is the SessionStart beacon.** `hooks/hooks.json`
   (matchers exactly `startup`+`resume`, 2s timeout) runs `session_beacon.py`,
   which injects at most ONE factual line when this store is measurably behind the
   fleet; read-only, advisory-only, never pulls; any failure → empty stdout, exit
   0. It never runs `detect_stacks` — it reads the `stacks` state that
   `sync_global.py --pull` wrote into `.consolidation-state.json`.
8. **Verification-first is the product.** Phase 3 checks every candidate claim
   against the live tree (file/symbol existence via `test -e` / `grep -rn`,
   `git log -S '<string>'`, doc self-consistency); unverifiable → flagged or
   dropped, never silently kept. Apply the same law to your own work in this repo.

## The dream workflow, one breath

Six phases, 0–5 (there is no phase 6), driven from SKILL.md:

- **Phase 0 — locate + high-water mark**: inventory both stores + git range since
  the `.consolidation-state.json` marker; `memory_status.py --seed` (per-slug
  record) and `--snapshot` (BEFORE hashes). No-op rule: stop only when the local
  store is empty AND the network is empty — a non-empty store with 0 commits is a
  MAINTENANCE pass and an empty store with a rich network is a COLD-START
  bootstrap; both proceed.
- **Phase 1 — orient**: read both `MEMORY.md`s + facts; `sync_global.py --list → --pull → --harvest`
  replicates relevant globals (M1-holds past the hard ceiling); then
  detect-and-offer demotion/promotion re-audits (never auto).
- **Phase 2 — gather claims (claims-first)**: `git log <marker>..HEAD` commit
  bodies → project facts; `extract_signals.py --json` session signal →
  feedback/preference/gotcha facts; re-verification candidates. Assign `scope`
  via the hard cascade Gates 0/1/2; finalize rigor.
- **Phase 3 — verify (the heart)**: every candidate against the LIVE tree — inline
  at LIGHT; SUBSTANTIAL+ fans out subagents with the specific claim lists (never
  "read the transcript"); 2-source check for always-loaded-bound facts.
- **Phase 4 — consolidate**: SURFACING beat + fully-plain proposal = the approval
  gate for irreversible writes; place by tier; every decision → one `entries[]`
  row.
- **Phase 5 — prune/GC/measure/render**: remediation gate (always-on staleness
  sweep); `--gc [--apply]` orphan mirrors; health + dangling links; `--tokens` +
  `--recalls` usage capture; marker merge; distill scan (`--from/--into --verdict`);
  `render_dashboard.py --persist` (procedure-integrity gate — exit 3 on a
  measured lazy-skip); `--diffs` sidecar; mandatory `render_html.py --latest`
  archive; WAKE + structured debrief.

**Rigor** — `magnitude = git_commits + session_candidates` (flow, not stock):
**LIGHT ≤ 2 · SUBSTANTIAL 3–7 · HEAVY ≥ 8**. A hint, never a gate; derived at
render from `scope`, never stored. **Budgets** — index 1500 est tokens,
CLAUDE.md 4000, hard ceiling ≈3840 (= 0.6 × the 25 KB native cap; past it
`--pull` M1-holds new pulls), prune-pressure at 40 facts. The dream-timing
advisory is a no-nag nudge (commits-since-marker crossing the SUBSTANTIAL band),
advisory-only — the skill never auto-fires; it is explicit-trigger-only by
design.

## Releasing

- **A release = a bumped version landing on `main`.** Installed plugins
  auto-update at Claude Code startup when `plugins/consolidate-memory/.claude-plugin/plugin.json`'s
  `version` changes. Keep `version` ONLY in `plugin.json`, never in
  `marketplace.json`.
- **Deterministic versioning (pre-1.0, decide in order):** (1) first
  stable/committed-API release → major (→ 1.0.0); (2) breaks an existing install
  (incompatible cycle-record schema, removed/renamed script or CLI flag, changed
  manifest/marketplace contract) → minor; (3) otherwise backward-compatible
  additive change → patch. Releases v0.1.1–v0.2.1 were patches. **v0.3.0 is the
  first minor** (removes v0.2.1 unenrolled A→B sharing).
- **Author the CHANGELOG `## [X.Y.Z]` section first** — it is the single source of
  truth. Then release in two phases with a human merge between them (`main` requires
  PRs): `./release.sh --stage` (guards, bumps `plugin.json` if needed, commits
  `release: vX.Y.Z`, pushes `release/vX.Y.Z`, opens the release PR — re-runnable, it
  reuses the branch/PR) → **YOU merge the release PR** → `./release.sh --finalize`
  (verifies `main`'s `plugin.json` == the CHANGELOG version, tags the PR's merge
  commit, pushes the tag, cuts the GH Release — re-runnable, reports already-done).
  **Pre-bump preferred:** if `plugin.json` already equals the CHANGELOG version,
  `--stage` is a no-op that says so and `--finalize` alone tags the merged HEAD (the
  bump rides the feature PR — zero release PRs); the release PR is the fallback for a
  last-minute bump. `--expect patch|minor|major` asserts the computed bump matches
  intent. The harness refuses a non-forward/multi-step version, an unfilled CHANGELOG
  stub, a dirty tree (untracked files count) or existing tag, and `--finalize` refuses
  a `main` whose version didn't land or an unmerged release PR. (`release.sh` is a
  local, gitignored maintainer artifact — never published.)
- **Stacked PR chains merge oldest-first:** retarget each PR's base to `main`
  (`gh pr edit N --base main`), wait on checks, then `gh pr merge N --merge`
  (merge commits — the repo convention). The v0.4.0 chain (#128→#154→…→#160)
  merged this way under the user's delegation.
- **Required checks on `main` (the #152 operator leg):** the `protect-main`
  ruleset should require the check-run **display names** (GitHub matches those,
  never job keys) with a review count ≥ 1: `test (python 3.8)`–`test (python
  3.13)`, `test (macos python 3.12)`, `concurrency (linux python 3.12)`,
  `typecheck (mypy, dev-only contract check)`, `plugin manifest validation
  (claude CLI)`, and `bench (linux python 3.12)` (after PR #180 lands). The CI
  job list in the Commands section is the authoritative enumeration.

## The QA companion (dream-beta-tester)

- **Two co-equal detectors.** The deterministic oracle (`beta_checks.py`) runs the
  dream skill's own read-only scripts against a repo and checks 9 invariant
  families (quantity registry, cycle identity, recommendation coherence, safe
  suggestion, closure reachability, calibration, remediation coherence,
  maintenance-pivot coherence, capture completeness) — exit 1 iff any FAIL,
  missing inputs → SKIP never crash, absent store = valid clean outcome. The
  judgment-lens pass (`/dream-beta-test`) promotes or downgrades each oracle
  finding and reduces every lens hit to a reproducible deterministic check or a
  quoted source-contradiction — unreduced findings are shipped as hypotheses,
  never counted. "The oracle is a hypothesis too."
- **Pre-push gate**: `maintainer/install-gate.sh` generates the fixture store,
  grafts the v0.1.19 canary, and installs a `.git/hooks/pre-push` hook;
  `ci_check.sh` runs the oracle against your working-tree scripts. It blocks only
  on verdict `regression`; it self-tests first — the canary must FAIL by defect
  identity (`CHK-GATE-BACKFILL`, `CHK-EVICT-STAGE` present in the FAIL ids) —
  otherwise it alerts and fails open (`selftest_broken`). Verdict ladder:
  `selftest_broken` > `harness_error` > `regression` > `clean`; override with
  `git push --no-verify`. The orchestrator contract
  (`reports/latest.json`, CONTRACT.md) maps `clean→ship`,
  `regression→patch by defect_ref`, harness failures → STOP, never patch the
  skill.

## Deep docs

- `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md` — the full
  6-phase workflow, tier model, gate cascade.
- `…/references/harness-map.md` — fact schema, store topology, verification
  recipes, cross-project model (the authoritative mechanism spec).
- `plugins/dream-beta-tester/docs/SPEC.md` — QA design-of-record; `STATUS.md` —
  validation matrix + fixed-vs-open defect log; `CONTRACT.md` — latest.json
  self-heal contract.
- `CHANGELOG.md` — full per-version precedent (versioning policy §Releasing).
- `SECURITY.md` — public threat model + enforced properties.
