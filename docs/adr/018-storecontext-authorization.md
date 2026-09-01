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
3. Submodule: `gitdir` is contained in `<super>/.git/modules/` and the
   worktree is contained in the super's working tree. A `gitdir` backlink,
   when present, must match this gitfile.
4. Disagreement ⇒ skip this `.git` (continue the walk). Do not inherit the
   victim identity.

For `mem_dir_source in ("project", "local")`:

```text
allow:  inside the project tree, or exactly this project's default native
deny:   other projects/<slot>/memory, domain canonicals, plugin-data,
        any other config-root path
```

User and managed settings may still name an absolute directory.

## Alternatives

- Operator-grant store for cross-project `autoMemoryDirectory`. Deferred to
  0.4.0; this slice closes the repository-controlled attack without new
  storage.
- Keep path-shape Git checks. Rejected: the worktree-shaped pointer was the
  remaining steal.

## Consequences

Positive: a malicious repo cannot select another project's native store or
inherit a victim Git identity via a crafted `.git`.

Negative: unusual layouts that symlink `.git` or point project settings at
another config-root slot fail closed (`write_allowed` false).

## Revisit trigger

Reopen when an operator-enrolled per-project namespace is required, or if
Claude documents a Git identity we should adopt instead of filesystem
discovery.
