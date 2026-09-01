# 018. StoreContext authorization (Git relationship + project/local allowlist)

Status: Accepted
Extends: ADR 002

## Context

v0.3.3 `_gitdir_layout_ok` accepted any path whose parent chain looked like
`.git/worktrees/<name>` or `.git/modules/<name>`. A crafted `.git` file could
point at another repository's worktree administrative directory and inherit
that repository's Git common dir, project id, native store, and enrollment.
A `.git` directory symlink resolved to a victim `.git` and passed containment
after `resolve()`.

Project/local `autoMemoryDirectory` was accepted if contained in the project
tree **or the entire Claude config root**. The config root contains every
project's `projects/<slot>/memory`, domain canonicals, and plugin-data.

## Decision

1. A `.git` **symlink** (file or directory) is not Git. A regular gitfile is
   still valid.
2. Linked worktree: the administrative directory's `gitdir` file must resolve
   to this worktree's `.git` gitfile. `commondir` must resolve inside the
   owning repository's main `.git`.
3. Submodule: `gitdir` is `<super>/.git/modules/<rel>` where `<rel>` is the
   worktree path relative to the super. A `gitdir` backlink, when present,
   must match this gitfile.
4. Disagreement ⇒ skip this `.git` (continue the walk). Do not inherit the
   victim identity.

For `mem_dir_source in ("project", "local")`:

```text
allow:  exact current-project native, in-tree directory that is not a
        protected config-root path, or operator grant
        (plugin-data/store-grants.json via cm project grant-native)
deny:   other projects/<slot>/memory, domain canonicals, plugin-data,
        any other config-root path
```

User and managed settings may still name an absolute directory. When the git
root is `$HOME`, `~/.claude/settings.json` is not treated as project settings.

Submodule gitdirs must match the worktree's modules-relative path. A `.git`
symlink (file or directory) is never Git.

## Alternatives

- Keep path-shape Git checks. Rejected: the worktree-shaped pointer was the
  remaining steal.
- Allow any in-tree path even when it resolves into config-root. Rejected:
  `$HOME` as a git repo would authorize every `projects/<slot>/memory`.

## Consequences

Positive: a malicious repo cannot select another project's native store or
inherit a victim Git identity via a crafted `.git`.

Negative: unusual layouts that symlink `.git` or point project settings at
another config-root slot fail closed (`write_allowed` false).

## Revisit trigger

Reopen if Claude documents a Git identity we should adopt instead of
filesystem discovery.
