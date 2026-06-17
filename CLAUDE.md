# consolidate-memory — project conventions

A **Claude Code plugin**: **sleep-time memory consolidation** for agents, with a
cross-project shared-memory layer. This repo is both the plugin and its marketplace —
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
    render_dashboard.py            the data-driven dashboard (renders a cycle record)
cm                                 dev CLI over the scripts (uses explicit paths, not ${CLAUDE_PLUGIN_ROOT})
tests/                             zero-dependency smoke + accumulation sim + manifest validation
memory/                            personal shared-memory store — GITIGNORED, NOT shipped in the plugin
```

LOCAL-only maintainer artifacts (GITIGNORED, never published): the `release.sh` release
tool (see "Releasing") and the `security/` directory (pentest tooling + audit findings).
Only `SECURITY.md` at the repo root is public.

## Conventions

- **Zero runtime dependencies.** Scripts are stdlib-only (uses 3.8+ stdlib; no pip
  installs); validated on Python 3.10–3.13. Keep it that way — it must run anywhere
  Claude Code does. (`TypedDict` and the type hints are stdlib + runtime-invisible;
  mypy is a dev-only maintainer tool, NOT a runtime dep — see the dev loop.)
- **The cycle record is the contract — now TYPED.** `memory_status.py --json` seeds it,
  the phases fill it, `render_dashboard.py` renders it. The shape is `TypedDict`s in
  `memory_status.py` (`CycleRecord` + nested, all `total=False`); a `validate_cycle_record`
  warns (stderr, never blocks) on a wrong-container-type key at runtime. Changing the
  schema means updating the seed, the renderer, the **TypedDicts**, and `SKILL.md`'s
  schema block together — a smoke test pins the SKILL block to `CycleRecord.__annotations__`,
  so they can't silently drift.
- **Model produces data, scripts produce presentation.** Don't hand-write report
  prose — emit a cycle record and render it, so output stays consistent.
- **Style:** match the existing scripts — imperative, explain *why*, type hints,
  small pure functions that the smoke tests can exercise.

## Safety (this repo is PUBLIC)

- **Never commit memory.** `memory/` (the shared-consciousness stream) is gitignored;
  it's personal. Only `memory/.gitkeep` belongs on the remote. Verify with
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
invoke the scripts by explicit path, so they work without the plugin being installed.

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
   v0.1.1 packaging · v0.1.2 dashboard · v0.1.3 rigor modes.

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
