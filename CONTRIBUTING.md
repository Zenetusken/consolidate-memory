# Contributing

Thanks for taking a look. This project is a **Claude Code plugin** — a six-phase `dream`
workflow, a governed cross-project store, and a self-contained HTML archive — and it holds
itself to the same standard it asks of the memory it keeps: **claims verified against the
source.**

## Getting set up

```bash
claude plugin marketplace add ./
claude plugin install consolidate-memory@zenetusken-plugins
```

That dogfoods your checkout as a local marketplace, so `dream` runs against the working
tree. Script edits are live on the next run (they are `exec`'d fresh); `SKILL.md` body edits
need `/reload-plugins` or a new session; manifest edits need
`claude plugin marketplace update` + `/reload-plugins`.

There is nothing to `pip install`. The plugin's runtime scripts are **stdlib-only on Python
3.8+**, and that is a design floor, not a preference — it has to run wherever Claude Code
does. `mypy` and Playwright are development-only tools.

## The gate list

Run these before opening a pull request. CI runs the first five; the last is a local
smoke-check of the CLI itself, with no CI equivalent.

```bash
python3 tests/smoke.py                     # the zero-dependency gate
python3 tests/simulate_accumulation.py     # lifecycle accumulation simulation
python3 tests/validate_manifests.py        # portable manifest shape check
python3 tests/docs_links.py                # badges, links, anchors, theme table
mypy --config-file mypy.ini                # dev-only cycle-record contract check
./cm status                                # local only: spot-check Phase-0 output
```

If you touched anything under `plugins/consolidate-memory/scripts/`, `smoke.py` is
mandatory — the repository convention is that it runs after every change there. If you
touched `dashboard.template.html` or a dashboard JS bundle, the browser suite is the real
gate:

```bash
python3 tests/dashboard_browser.py --out /tmp/cm-browser
```

It needs Playwright + Chromium (`python3 -m pip install playwright==1.60.0` then
`python3 -m playwright install --with-deps chromium`) and runs five themes across four
viewport widths, plus a print emulation.

## What review will ask

- **Facts, not adjectives.** A claim in a document, comment, or pull request body should be
  checkable — cite the file and line, or the measurement. "Improved performance" is not a
  finding; "render time 1.9s → 0.4s on the 120-cycle fixture" is.
- **No new runtime dependencies.** If a change needs one, open an issue first.
- **Scripts produce presentation; the model produces data.** Do not hand-write report prose
  — emit a cycle record and render it, so output stays consistent across runs.
- **The cycle record is the contract.** Changing its shape means updating the seed, the
  renderer, the `TypedDict`s, and the `SKILL.md` schema block together. A smoke test pins
  those to each other so they cannot drift silently.
- **Palette and contrast changes are gated twice** — once by `smoke.py` (RC-90) and once by
  the browser suite's own compositing check. Both must stay green, and neither passes by
  accident; see `docs/deep-field-theme.spec.md`. RC-90 also refuses a **literal hex outside a
  palette block**: a colour either names a token or it does not ship. Do not rely on the
  rendering gate to catch that — `visual_hierarchy` walks a fixed selector list, and a measured
  mutant (one rule's `--card` hardcoded) left the entire browser suite green at 1213/0 while
  collapsing visibly under Light.
- **Never commit personal memory.** The repository is public and contains none. Your facts
  live in your own store. Only `memory/.gitkeep` belongs in the tree.

## Where the conventions live

| Read this | For |
| :--- | :--- |
| [AGENTS.md](AGENTS.md) | The agent operating manual: layout, dev loop, CI jobs, the traps |
| [CLAUDE.md](CLAUDE.md) | The same conventions with more narrative |
| [SKILL.md](plugins/consolidate-memory/skills/consolidate-memory/SKILL.md) | The six-phase workflow and the context-tier model |
| [harness-map.md](plugins/consolidate-memory/skills/consolidate-memory/references/harness-map.md) | Store topology, fact schema, verification recipes |
| [docs/](docs) | Design-of-record specs, one per feature, and the ADRs |

Specs are written **before** implementation in `docs/*.spec.md`, reviewed adversarially, and
kept as the design-of-record afterwards. If you are proposing something structural, that is
the shape to bring it in.

## Reporting a bug

Open an issue with the template. The single most useful thing you can include is the
**rendered artifact** — the cycle record or the HTML archive — rather than a description of
it, because the archive is generated and a wrong-looking screen is usually a data question,
not a style question. Redact freely; `docs/previews/nocturne/` shows the fictional sample the
tests use.

For security issues, **do not open an issue** — see [SECURITY.md](SECURITY.md).

## Conduct

Participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md).
