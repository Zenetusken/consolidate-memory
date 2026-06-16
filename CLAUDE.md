# consolidate-memory — project conventions

A standalone Claude Code skill: **sleep-time memory consolidation** for agents, with
a cross-project shared-memory layer. This repo is the canonical source; `install.sh`
symlinks `skill/` → `~/.claude/skills/consolidate-memory` and `memory/` →
`~/.claude/memory`. See `README.md` for the user-facing pitch and `skill/SKILL.md` +
`skill/references/harness-map.md` for the full design.

## The one gotcha that matters

**`skill/` IS the live skill** (it's symlinked into `~/.claude/skills`). Editing it
changes behaviour in *every* project on this machine immediately — there's no build
step and no separate "installed" copy. So a broken edit breaks the skill globally
until fixed. **Run `python3 tests/smoke.py` after any change to `skill/scripts/`.**

How edits take effect:

| You edit | Effect |
|---|---|
| `skill/scripts/*.py` | live immediately (exec'd fresh each run) |
| `skill/SKILL.md` body | next skill invocation |
| `skill/SKILL.md` frontmatter (name/description) | needs `/reload-skills` to re-register |

## Layout

```
skill/SKILL.md                 6-phase workflow + the context-loading-tier model
skill/references/harness-map.md paths, fact schema, verification recipes, cross-project model
skill/scripts/
  memory_status.py             Phase 0: locate stores + git scope + `--json` cycle-record seed
  extract_signals.py           Phase 2: curated, secret-safe session signal (claims-first)
  sync_global.py               cross-project: --list/--pull/--network + provenance
  render_dashboard.py          the data-driven dashboard (renders a cycle record)
cm                             one-entry CLI over the scripts
install.sh                     idempotent symlink installer (+ --uninstall)
tests/smoke.py                 zero-dependency smoke tests
memory/                        the live shared-memory store — GITIGNORED, local only
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
edit skill/… → python3 tests/smoke.py → ./cm <cmd> to spot-check → git commit && git push
```

This tool dogfoods itself: from this repo you can run `dream` (the skill is
user-level, so it loads here too) to consolidate its own development memory — written
to its private store at `~/.claude/projects/<slug>/memory/`, never to this repo.
