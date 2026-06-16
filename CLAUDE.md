# consolidate-memory — project conventions

A **Claude Code plugin**: **sleep-time memory consolidation** for agents, with a
cross-project shared-memory layer. This repo is both the plugin and its marketplace —
end users install it with `/plugin marketplace add Zenetusken/consolidate-memory` +
`/plugin install consolidate-memory@zenetusken-plugins`; `install.sh` is a maintainer
dev-install (local marketplace + plugin, not a symlink). See `README.md` for the
user-facing pitch and `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md`
+ its `references/harness-map.md` for the full design.

## The one gotcha that matters

**This ships as a Claude Code *plugin*, not a symlinked skill.** The skill lives at
`plugins/consolidate-memory/skills/consolidate-memory/` and `SKILL.md` invokes scripts
via **`${CLAUDE_PLUGIN_ROOT}`** — a variable that is **only set when the skill loads as
a plugin**. So the old "symlink `skill/` into `~/.claude/skills`" model is dead: a bare
user-skill copy would have an unset `${CLAUDE_PLUGIN_ROOT}` and every command would
break. Dogfood via `./install.sh` (registers this repo as a local marketplace +
installs the plugin). **Run `python3 tests/smoke.py` after any change to `scripts/`.**

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
security/devsecops.workflow.js     reusable multi-agent white-hat pentest gate (run before go-live)
cm                                 dev CLI over the scripts (uses explicit paths, not ${CLAUDE_PLUGIN_ROOT})
install.sh                         maintainer dev-install: local marketplace + plugin (+ --uninstall)
tests/smoke.py, tests/simulate_accumulation.py   zero-dependency smoke + accumulation sim
memory/                            personal shared-memory store — GITIGNORED, NOT shipped in the plugin
```

## Conventions

- **Zero runtime dependencies.** Scripts use the Python 3 stdlib only (no pip
  installs). Keep it that way — it must run anywhere Claude Code does.
- **The cycle record is the contract.** `memory_status.py --json` seeds it, the
  phases fill it, `render_dashboard.py` renders it. Changing the schema means
  updating the seed, the renderer, and `SKILL.md`'s schema block together.
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
edit plugins/consolidate-memory/… → python3 tests/smoke.py → ./cm <cmd> to spot-check
→ claude plugin validate ./plugins/consolidate-memory --strict
→ (before go-live) run security/devsecops.workflow.js → git commit && git push
```

This tool dogfoods itself: once dev-installed as a plugin (`./install.sh`), run `dream`
from this repo to consolidate its own development memory — written to its private store
at `~/.claude/projects/<slug>/memory/`, never to this repo. The `cm` CLI and the tests
invoke the scripts by explicit path, so they work without the plugin being installed.
