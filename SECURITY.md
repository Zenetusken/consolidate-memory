# Security & data handling — consolidate-memory

This plugin reads your work session and your memory stores to consolidate durable
facts. Because it touches transcripts and persistent memory, here is exactly what it
does, what it never does, and how to report a problem.

## What it touches

- **Reads (local only):** the current project's git log, the repo memory docs
  (`MEMORY.md`/`AGENTS.md`/`CLAUDE.md`), Claude Code's per-project auto-memory under
  `~/.claude/projects/<slug>/memory/`, the cross-project store `~/.claude/memory/`, and
  — via the bundled `extract_signals.py` — the *tail signal* of the active session
  transcript (it streams the `.jsonl`; it never bulk-loads or copies it).
- **Writes (local only):** memory fact files + index in the two memory stores, and the
  operational marker `~/.claude/projects/<slug>/memory/.consolidation-state.json`. All
  writes are surfaced to you in the Phase-4 report before they happen.
- **Never:** makes network calls, sends telemetry, or transmits any of your data
  anywhere. Every script is **Python 3 stdlib only** — no third-party packages, no
  `pip install`.

## Security properties (enforced in code)

- **No code execution surface:** no `eval`/`exec`/`os.system`/`shell=True`. The only
  external process is `git` (read-only: `rev-parse`, `log`), invoked with a fixed
  argument **list** (never a shell string).
- **Argument-injection guard:** the commit SHA read from the on-disk state file is
  validated as hex before being passed to `git` (`memory_status._valid_sha`), so a
  tampered state file cannot inject `git` options.
- **Secrets firewall at retrieval:** `extract_signals.py` drops any session turn that
  contains a credential-shaped value to a label — the verbatim secret never reaches a
  memory file (repo docs are committed; auto-memory persists). It records a *pointer*,
  never a value.
- **Bounded input:** transcript turns are length-capped (`_PROBE_CAP` = 4000 chars) before regex
  classification (defense-in-depth); the regexes have no catastrophic backtracking — each
  alphanumeric run and its required separator are disjoint, so there's no ambiguity to blow up —
  and the length cap bounds worst-case matching regardless.
- **Filesystem safety:** `sync_global.py --gc` only deletes files marked as managed
  mirrors (`global_ref:`) whose canonical is gone — never project-authored facts — and
  defaults to report-only (deletion requires `--apply`).

## What ships in the plugin

Only `plugins/consolidate-memory/` is packaged. Your personal memory store (`memory/`
at the repo root) is **gitignored and never published** — verify with
`git ls-tree -r --name-only origin/main | grep memory` (only `memory/.gitkeep`).
`tests/`, `security/`, and operational state stay outside the plugin directory.

## Supply chain

- Pin what you install. Install from the marketplace via Git
  (`/plugin marketplace add Zenetusken/consolidate-memory`); a tagged release or pinned
  `sha` gives reproducible installs.
- Plugins are copied to a local cache on install and run from there; this plugin adds
  no hooks, no MCP servers, and no background processes — it is skill + scripts only.

## Reporting a vulnerability

Please open a GitHub security advisory or a private issue at
<https://github.com/Zenetusken/consolidate-memory>. Do not include real credentials in
reports. We aim to acknowledge within a few days.
