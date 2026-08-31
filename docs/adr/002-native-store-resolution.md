# 002. Native store resolution (StoreContext)

Status: Accepted

## Context

Every scripted read and write of Claude Code auto-memory used a hard-coded
construction `~/.claude/projects/<slug_for(cwd)>/memory`. That matched a
default one-user layout and is now incomplete against the public contract:
auto-memory is derived from the Git repository (worktrees and nested
subdirectories share one store); `CLAUDE_CONFIG_DIR` and
`CLAUDE_CODE_PROJECT_DIR_NAME` remap the config and projects slot;
`autoMemoryDirectory` may be set from user, project, local, policy, or
`--settings`; auto-memory can be disabled; hook input already carries
`session_id`, `transcript_path`, and `cwd`.

A command that reports a healthy plugin store while Claude loads another, or
that creates a shadow store Claude never reads, is a release blocker. The
SessionStart beacon is budgeted at 2s with no subprocesses, so resolution
cannot shell out to `git`.

Constraints: one operator, stdlib-only, Python 3.8+, existing hermetic tests
that set `HOME` at call time and expect the default layout for non-Git
fixtures. Reversal cost is high for a wrong default path (split-brain
stores). Public 1.0 stays HOLD.

## Decision

We will introduce one authoritative `StoreContext` resolver used by every
scripted native or canonical path:

1. `config_root` honours `CLAUDE_CONFIG_DIR`, else `Path.home() / ".claude"`.
2. Git identity is the Git **common directory** discovered by walking `.git`
   (directory, gitfile, `commondir`) — no subprocess. Worktrees and nested
   subdirs of one repo share one native store keyed on the main working tree.
3. Outside Git, the given project root is the stable identity (not `/`).
4. The projects slot is `CLAUDE_CODE_PROJECT_DIR_NAME` when set, else
   `slug_for(git_root or project_root)` — the existing slug rule, aliased,
   never reimplemented.
5. Effective `autoMemoryDirectory` is merged **lowest → highest** to match
   Claude Code: user → project → local → reconstructed `--settings`
   (`CLAUDE_CODE_SETTINGS`) → **managed policy last** (`managed-settings.json`,
   then `/etc/claude-code/managed-settings.json`). Managed keys cannot be
   overwritten by user/project/local/`--settings`. The value must be absolute
   or `~/`.
6. `autoMemoryEnabled` / `CLAUDE_CODE_DISABLE_AUTO_MEMORY` disable writes and
   mirror injection; absence is not drift.
7. Hook `session_id` / `transcript_path` / `cwd` are session observations,
   not an alternate store.
8. Writes fail closed when resolution sources disagree (two live `MEMORY.md`
   stores, or ephemeral `--settings` that cannot be reconstructed). An
   explicit store override is required in that mode.
9. `cm doctor` prints the resolved native store, source, profile, domain,
   enabled state, and any ambiguity. Doctor itself is read-only.

Business logic must not construct `~/.claude/projects/<slug>/memory` except
through this resolver (the default *output* of the resolver on an unset
layout remains that path so existing fixtures keep working).

## Alternatives

- **Keep cwd-slug paths and document the gap.** Rejected: the gap is the
  product — Claude and the plugin must share a store.
- **Call `git rev-parse` from every script.** Rejected: the beacon cannot
  afford a subprocess inside a 2s hook; filesystem `.git` discovery is the
  same answer everywhere.
- **A per-script override flag instead of one resolver.** Rejected: five
  `slug_for` copies already drifted once; a sixth construction is the bug.

## Consequences

Positive: worktrees, nested cwd, profiles, custom memory dirs, and disabled
auto-memory stop silently forking stores. Doctor makes disagreement visible.

Negative: a fixture that `git init`s a parent and then addresses a nested
directory by cwd-slug will now share the parent's store (correct per Claude,
a behavior change vs cwd-slug). Dual-read of legacy paths stays until
migration (ADR 007).

Neutral: `slug_for` remains the projects-slot encoding. Dream-beta-tester
call sites alias it rather than copy it. 1.0 remains HOLD.

## Revisit trigger

Reopen if Claude documents a new memory-resolution input this resolver does
not honour, if filesystem gitfile parsing mis-identifies a common dir on a
supported hosting, or if fail-closed writes block a reconstructible `--settings`
source we could have read.
