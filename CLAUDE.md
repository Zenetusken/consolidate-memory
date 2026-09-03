# consolidate-memory — project conventions

**v0.4.2.** A **Claude Code plugin**: **cross-project, verification-first memory** for agents — the layer beyond
Claude Code's built-in Auto Dream (per-project consolidation), adding a governed cross-project store +
verification against the live code. This repo is both the plugin and its marketplace —
end users install it with `/plugin marketplace add Zenetusken/consolidate-memory` +
`/plugin install consolidate-memory@zenetusken-plugins`; maintainers dogfood the same
way against this local checkout (`claude plugin marketplace add ./` — see below). See `README.md` for the
user-facing pitch and `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md`
+ its `references/harness-map.md` for the full design.

## The one gotcha that matters

**This ships as a Claude Code *plugin*, not a symlinked skill.** The skill lives at
`plugins/consolidate-memory/skills/consolidate-memory/` and `SKILL.md` invokes scripts
via **`${CLAUDE_PLUGIN_ROOT}`** — a variable that is **only set when the skill loads as
a plugin**. So the old "symlink `skill/` into `~/.claude/skills`" model is dead: a bare
user-skill copy would have an unset `${CLAUDE_PLUGIN_ROOT}` and every command would
break. Dogfood by registering this repo as a local marketplace and installing the
plugin: `claude plugin marketplace add ./` then `claude plugin install
consolidate-memory@zenetusken-plugins`. **Run `python3 tests/smoke.py` after any change to `scripts/`.**

How edits take effect (once installed as a local-marketplace plugin):

| You edit | Effect |
|---|---|
| `plugins/consolidate-memory/scripts/*.py` | live on next run (exec'd fresh) |
| `…/skills/consolidate-memory/SKILL.md` body | `/reload-plugins` or next session |
| `plugin.json` / `marketplace.json` | `claude plugin marketplace update` + `/reload-plugins` |
| a release lands on `main` | installed copy re-reads its version ONLY at CC startup — mid-session: `claude plugin marketplace update` → `claude plugin update consolidate-memory@zenetusken-plugins` → `/reload-plugins` (`plugin install` no-ops when already installed) |

When iterating on the published artifact, re-validate: `claude plugin validate
./plugins/consolidate-memory --strict`.

## Layout

```
.claude-plugin/marketplace.json   the marketplace catalog (relative source → plugins/…)
plugins/consolidate-memory/        the plugin (= ${CLAUDE_PLUGIN_ROOT})
  .claude-plugin/plugin.json       plugin manifest (name, version, author, license)
  skills/consolidate-memory/
    SKILL.md                       6-phase workflow + the context-loading-tier model
    references/harness-map.md      paths, fact schema, verification recipes, cross-project model
  hooks/hooks.json                 SessionStart beacon (startup+resume, 2s timeout) → session_beacon.py
  scripts/
    session_beacon.py              ≤1 factual context-injected line when THIS store is behind the fleet
                                   (read-only, no-nag tiers, silent-exit-0 on failure; stacks via the
                                   --pull-written state cache — never detect_stacks, measured 2s on big repos)
    memory_status.py               Phase 0: locate stores + git scope + `--json` cycle-record seed
    extract_signals.py             Phase 2: curated, secret-safe session signal (claims-first)
    sync_global.py                 cross-project: --list/--pull [--evict=F | --allow-net-grow]/--promote/
                                   --gc [--edges] [--apply]/--tokens/--utility/--harvest/--staleness/
                                   --workflows/--network + provenance
    distill_scan.py                Phase 5 distill: recurring Bash-command templates + compound-command chains (workflow signal); `--into`/`--from` inject script-truth counts into a cycle record
    render_dashboard.py            the data-driven ASCII dashboard (renders ONE cycle record)
    render_html.py                 the self-contained HTML archive (all cycles, rich; + dashboards/diffs sidecars)
    dashboard.template.html        the HTML shell render_html.py fills
    render_log.py                  the lean per-dream audit TABLE (all cycles; powers `cm log`) — the 3rd log view
    store_context.py               sole native/canonical path constructor (ADR 002; managed settings win)
    domain_policy.py               domain/sensitivity admission (user-global is domain-global)
    control_plane.py               SQLite registry + fcntl locks + operation journal under plugin-data
    canonical_ingress.py           sole canonical writer (`cm canonical upsert`)
    mirror_conflict.py             three-way classifier (never silently overwrite a local edit)
    index_admission.py             native MEMORY.md 200-line/25KB admission (not the global catalog)
    identifiers.py                 contained domain / fact-stem / project-id joins
    capabilities.py / retention.py / cm_ops.py
                                   doctor, conflicts, resolve, repair-mirror, migrate, data, project enroll
    _ui.py                         shared visual vocabulary (color/rule/kv/bar/glyphs + the CM_DREAM_ARC dream-cue);
                                   render_dashboard keeps its OWN copies of this vocabulary, behaviorally
                                   drift-pinned against it by a smoke test (output equality, not literal source bytes)
cm                                 dev CLI over the scripts (uses explicit paths, not ${CLAUDE_PLUGIN_ROOT}).
                                   symlink-safe (readlink -f) → install on PATH for frictionless per-repo use:
                                   `ln -s "$(pwd)/cm" ~/.local/bin/cm` (then `cm report`/`cm status`/`cm log`
                                   from ANY repo, CWD-defaulting to that project). MAINTAINER tool — end users
                                   open ~/.claude/projects/<slug>/dashboards/index.html (see SKILL Phase 5).
tests/                             zero-dependency smoke + accumulation sim + manifest validation
memory/                            GITIGNORED placeholder (.gitkeep only) — the personal global store lives at ~/.claude/memory (a real dir, decoupled from this repo)

plugins/dream-beta-tester/         QA companion plugin — beta-tests the dream skill itself
  .claude-plugin/plugin.json       plugin manifest
  skills/dream-beta-test/SKILL.md  the judgment-lens pass (/dream-beta-test) + references/lenses.md
                                   (the 7 judgment lenses)
  scripts/                         the deterministic oracle (beta_checks.py) + snapshot/report/run
  fixtures/                        make_fixture.py (generates the frozen synthetic gate-repo store) +
                                   make_cycle_probe.py (the frozen contaminated cycle record) +
                                   canary-v0.1.19/ (VENDORED known-bad scripts, byte-faithful to the
                                   v0.1.19 tag, SHA256SUMS-manifested) — the generated STORES are
                                   grafted at install time under ~/.dream-beta-test/, never committed
  maintainer/                      the continuous-QA pre-push gate (ci_check.sh/install-gate.sh)
  docs/SPEC.md                     design-of-record (STATUS.md hands design off to this file)
  docs/CONTRACT.md                 reports/latest.json schema + the deterministic self-heal contract
  docs/STATUS.md                   validation matrix + fixed-vs-open defect log
```

LOCAL-only maintainer artifacts (GITIGNORED, never published): the `release.sh` release
tool (see "Releasing") and the `security/` directory (pentest tooling + audit findings).
Only `SECURITY.md` at the repo root is public.

## Conventions

- **Zero runtime dependencies.** Scripts are stdlib-only (uses 3.8+ stdlib; no pip
  installs); CI validates the full 3.8–3.13 range (3.8/3.9 pinned to `ubuntu-22.04` —
  actions/setup-python has no build for either on the current `ubuntu-latest`/24.04
  runner image). Keep it that way — it must run anywhere Claude Code does. (`TypedDict`
  and the type hints are stdlib + runtime-invisible;
  mypy is a dev-only maintainer tool, NOT a runtime dep — see the dev loop.)
- **The cycle record is the contract — now TYPED.** `memory_status.py --json` seeds it,
  the phases fill it, `render_dashboard.py` renders it. The shape is `TypedDict`s in
  `memory_status.py` (`CycleRecord` + nested, all `total=False`); a `validate_cycle_record`
  warns (stderr, never blocks) on a wrong-container-type key — or an impossible distill count
  above the scanner caps (`_DISTILL_CAPS`, pinned to `distill_scan` by a cross-module smoke
  test) — at runtime. Changing the
  schema means updating the seed, the renderer, the **TypedDicts**, and `SKILL.md`'s
  schema block together — a smoke test pins the SKILL block to `CycleRecord.__annotations__`,
  so they can't silently drift.
- **Model produces data, scripts produce presentation.** Don't hand-write report
  prose — emit a cycle record and render it, so output stays consistent.
- **Style:** match the existing scripts — imperative, explain *why*, type hints,
  small pure functions that the smoke tests can exercise.

## Safety (this repo is PUBLIC)

- **Never commit personal memory.** The shared-consciousness stream / global store now lives at
  `~/.claude/memory` (a real dir, outside this repo — decoupled); repo-root `memory/` is just a
  gitignored placeholder. Only `memory/.gitkeep` belongs on the remote. Verify with
  `git ls-tree -r --name-only origin/main | grep memory`.
- **Keep the skill generic.** No hardcoded user paths, project names, or identities —
  use placeholders (`/home/you/project/foo`). It's meant to be reusable by anyone.
- **Secrets firewall at retrieval.** `extract_signals.py` omits credential-shaped
  turns before they reach context; don't weaken that.

## Dev loop

```
edit plugins/consolidate-memory/… → python3 tests/smoke.py → python3 tests/simulate_accumulation.py
→ mypy --config-file mypy.ini → ./cm <cmd> to spot-check → python3 tests/validate_manifests.py
(portable, no flags — the `--strict` variant is the claude CLI: `claude plugin validate --strict`)
→ (before go-live) run the local DevSecOps pentest harness → git commit && git push
```

`mypy --config-file mypy.ini` is a **dev-only** contract check (catches cycle-record
drift on the producer side — a renamed/extra/wrong-typed key in a seed/demo literal). It
is NOT a runtime dep and NOT part of the dep-free `smoke.py` gate; the config is pragmatic
(checks both plugins' `scripts/` + dream-beta-tester `fixtures/` + `tests/`, not `--strict`), and must never disable the TypedDict checks
(`typeddict-item`/`typeddict-unknown-key` ARE the contract).

This tool dogfoods itself: once dev-installed as a plugin (local-marketplace add + `claude plugin install`), run `dream`
from this repo to consolidate its own development memory — written to its private store
at `~/.claude/projects/<slug>/memory/`, never to this repo. The `cm` CLI and the tests
invoke the scripts by explicit path, so they work without the plugin being installed. At an arc
boundary, `cm status` (any `memory_status.py` run) surfaces a **dream-timing advisory** — a no-nag
nudge when commits have accrued since the last dream — so you can catch a good consolidation boundary
*before* a compaction (advisory only; the skill never auto-fires).

## Releasing (auto-update cycle)

Installed plugins auto-update at Claude Code startup when the plugin's `version`
(`plugins/consolidate-memory/.claude-plugin/plugin.json`) changes on `main` (public
marketplace, no token needed). So a release = a bumped version landing on `main`. Keep
`version` ONLY in `plugin.json` (never also in `marketplace.json`).

**Versioning policy (pre-1.0; deterministic — decide IN ORDER):**
1. First **stable / committed-API** release → **major** (→ `1.0.0`).
2. **Breaks an existing install** — incompatible cycle-record schema, a removed/renamed
   script or CLI flag, a changed install/marketplace/manifest contract → **minor**
   (`0.N → 0.N+1.0`). (Pre-1.0, breaking changes ride a minor bump.)
3. Otherwise — additive feature, enhancement, fix, or docs that stays
   **backward-compatible** (legacy cycle records still render, existing installs keep
   working) → **patch** (`0.N.M → 0.N.M+1`). Releases v0.1.1–v0.2.1 were patches
   under this policy. **v0.3.0 is the first minor:** it removes v0.2.1 unenrolled
   A→B sharing. Full per-version precedent: `CHANGELOG.md`.

**The release harness (local, gitignored `./release.sh`) is deterministic by
construction:** it reads the target version from the **top `## [X.Y.Z]` CHANGELOG
section** — the single source of truth you author + review during the cycle, NOT a bump
keyword — then computes the bump TYPE from the delta and enforces the policy. So author
the `## [X.Y.Z]` CHANGELOG entry first (using the policy above), then release in two
phases with a human merge between them (GitHub requires PRs to `main`):
- `./release.sh` — **dry-run**: prints current→target, the computed bump type, the tag,
  and the notes. No writes.
- `./release.sh --stage` — guards (clean tree, tag free), bumps `plugin.json` if needed
  (`release: vX.Y.Z`), validates (manifests + smoke + sim), pushes
  `release/vX.Y.Z`, and opens the release PR. Re-running reuses the branch/PR.
- `./release.sh --finalize` — fetches, verifies `main`'s `plugin.json` equals the
  CHANGELOG version (the merge must have landed the bump), tags the release PR's merge
  commit, pushes the tag, and cuts the GH Release. Re-running reports already-done.
- **Pre-bump preferred:** if `plugin.json` already equals the CHANGELOG version
  (pre-bumped on the feature branch, as for v0.3.0), `--stage` is a no-op that says so,
  and `--finalize` alone tags the merged HEAD — the bump rides your feature PR, zero
  release PRs. The release-PR path is the fallback for a last-minute bump.
- `./release.sh --expect patch|minor|major [--stage|--finalize]` — also **asserts** the
  computed bump matches your intent (a second guard; aborts on mismatch).

It refuses a non-forward or multi-step version, an unfilled CHANGELOG stub, a dirty
tree (untracked files count — move session exports out first), or an existing tag —
and `--finalize` refuses when `main`'s version doesn't match the CHANGELOG or the
release PR isn't merged. (This replaced a keyword-driven flow after a
`minor`-vs-`patch` slip mis-shipped a version: the version is now structurally tied to the
reviewed CHANGELOG, not a release-time judgment.)
