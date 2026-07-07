# consolidate-memory — project conventions

A **Claude Code plugin**: **cross-project, verification-first memory** for agents — the layer beyond
Claude Code's built-in Auto Dream (per-project consolidation), adding a governed cross-project store +
verification against the live code. This repo is both the plugin and its marketplace —
end users install it with `/plugin marketplace add Zenetusken/consolidate-memory` +
`/plugin install consolidate-memory@zenetusken-plugins`; maintainers dogfood the same
way against this local checkout (`claude plugin marketplace add .` — see below). See `README.md` for the
user-facing pitch and `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md`
+ its `references/harness-map.md` for the full design.

## The one gotcha that matters

**This ships as a Claude Code *plugin*, not a symlinked skill.** The skill lives at
`plugins/consolidate-memory/skills/consolidate-memory/` and `SKILL.md` invokes scripts
via **`${CLAUDE_PLUGIN_ROOT}`** — a variable that is **only set when the skill loads as
a plugin**. So the old "symlink `skill/` into `~/.claude/skills`" model is dead: a bare
user-skill copy would have an unset `${CLAUDE_PLUGIN_ROOT}` and every command would
break. Dogfood by registering this repo as a local marketplace and installing the
plugin: `claude plugin marketplace add .` then `claude plugin install
consolidate-memory@zenetusken-plugins`. **Run `python3 tests/smoke.py` after any change to `scripts/`.**

How edits take effect (once installed as a local-marketplace plugin):

| You edit | Effect |
|---|---|
| `plugins/consolidate-memory/scripts/*.py` | live on next run (exec'd fresh) |
| `…/skills/consolidate-memory/SKILL.md` body | `/reload-plugins` or next session |
| `plugin.json` / `marketplace.json` | `claude plugin marketplace update` + `/reload-plugins` |

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
  scripts/
    memory_status.py               Phase 0: locate stores + git scope + `--json` cycle-record seed
    extract_signals.py             Phase 2: curated, secret-safe session signal (claims-first)
    sync_global.py                 cross-project: --list/--pull/--gc/--tokens/--network + provenance
    distill_scan.py                Phase 5 distill: recurring Bash-command templates + compound-command chains (workflow signal); `--into`/`--from` inject script-truth counts into a cycle record
    render_dashboard.py            the data-driven ASCII dashboard (renders ONE cycle record)
    render_html.py                 the self-contained HTML archive (all cycles, rich; + dashboards/diffs sidecars)
    dashboard.template.html        the HTML shell render_html.py fills
    render_log.py                  the lean per-dream audit TABLE (all cycles; powers `cm log`) — the 3rd log view
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
  skills/dream-beta-test/SKILL.md  the judgment-lens pass (/dream-beta-test)
  scripts/                         the deterministic oracle (beta_checks.py) + snapshot/report/run
  fixtures/                        the frozen synthetic gate-repo fixture + the canary-v0.1.19 self-test
  maintainer/                      the continuous-QA pre-push gate (ci_check.sh/install-gate.sh)
  docs/SPEC.md                     design-of-record (STATUS.md hands design off to this file)
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
edit plugins/consolidate-memory/… → python3 tests/smoke.py → mypy --config-file mypy.ini
→ ./cm <cmd> to spot-check → python3 tests/validate_manifests.py (+ claude plugin validate --strict)
→ (before go-live) run the local DevSecOps pentest harness → git commit && git push
```

`mypy --config-file mypy.ini` is a **dev-only** contract check (catches cycle-record
drift on the producer side — a renamed/extra/wrong-typed key in a seed/demo literal). It
is NOT a runtime dep and NOT part of the dep-free `smoke.py` gate; the config is pragmatic
(checks `scripts/` + `tests/`, not `--strict`), and must never disable the TypedDict checks
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
   working) → **patch** (`0.N.M → 0.N.M+1`). Precedent (all backward-compatible ⇒ patch):
   v0.1.1 packaging · v0.1.2 dashboard · v0.1.3 rigor modes · v0.1.4–v0.1.11 (calibration apparatus,
   orphan/drift detection, TypedDict contract, polish, governance cascade + demotion, dream-timing, docs) ·
   v0.1.12–v0.1.58 (audit follow-up, completion-driven archiving, the dream-arc CONTRACT [v0.1.54: additive
   `dream` key], the distill rebuild [v0.1.55: additive `distill` key + `--json` keys], full doc sync [v0.1.56],
   dashboard coherence + the quiet dream [v0.1.57], the distill HARDENING [v0.1.58: additive
   `Distill.window`/`secrets_omitted` schema keys + `scanned.secrets_omitted` `--json` key + `--into`/`--from`
   flags]) · v0.1.59 (full doc sync to the v0.1.58 state) · v0.1.60–61 (HTML dashboard two-column alignment)
   · v0.1.62 (the dream debrief's double sign-off fix) · v0.1.63 (index-lifecycle Phase A: recall-usage
   instrumentation, observe-only — additive `usage` block + `budget.index` keys) · v0.1.64 (WAKE is one
   line, not two — a second SKILL.md sign-off defect adjacent to v0.1.62's) · v0.1.65 (full doc sync to
   the v0.1.63/v0.1.64 state) · v0.1.66 (index-lifecycle Phase B: the HARD CEILING — a second,
   independent budget signal) · v0.1.67 (index-lifecycle Phase C: the utility policy — demotion triage ·
   the miss loop · fleet utility) · v0.1.68 (dashboard HTML: stop the masthead glow from tiling down the
   page + badge the demotion panel's dormant verdict to match distill's) · v0.1.69 (audit-hygiene
   remediation: parsed-instant window compares, TTY report sanitization, three unguarded store-scan
   read_text crashes, a labeled git-failure degradation, genericity scrub + pin, a SKILL `--list`
   correction, a schema-pin hole closed) · v0.1.70 (DevSecOps pentest remediation across both
   plugins — evict path-traversal + case-insensitive reserved-index self-clobber + mirror-anchor
   body injection + git-argv injection, all unified onto shared guards; the secrets firewall bundle
   single-sourced onto git commit subjects, closing a chunked-secret bypass + four ReDoS instances +
   several false-positive/false-negative regressions, two residual gaps accepted and documented
   rather than chased; Track D: CI floor widened to 3.8–3.13 + the v0.1.68 dashboard fixes gained
   automated regression pins) — every one an additive `total=False` schema key / additive `--json`
   key / additive flag / SKILL prose, never a break.

**The release harness (local, gitignored `./release.sh`) is deterministic by
construction:** it reads the target version from the **top `## [X.Y.Z]` CHANGELOG
section** — the single source of truth you author + review during the cycle, NOT a bump
keyword — then computes the bump TYPE from the delta and enforces the policy. So author
the `## [X.Y.Z]` CHANGELOG entry first (using the policy above), then:
- `./release.sh` — **dry-run**: prints current→target, the computed bump type, the tag,
  and the notes. No writes.
- `./release.sh --confirm` — sets `plugin.json` to the CHANGELOG version, validates
  (manifests + smoke + sim), commits `release: vX.Y.Z`, pushes `main`, tags, cuts the GH
  Release.
- `./release.sh --expect patch|minor|major [--confirm]` — also **asserts** the computed
  bump matches your intent (a second guard; aborts on mismatch).

It refuses a non-forward or multi-step version, an unfilled CHANGELOG stub, or a
dirty/out-of-sync tree / existing tag. (This replaced a keyword-driven flow after a
`minor`-vs-`patch` slip mis-shipped a version: the version is now structurally tied to the
reviewed CHANGELOG, not a release-time judgment.)
