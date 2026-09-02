#!/usr/bin/env python3
"""Authoritative StoreContext resolver — the only native/canonical path constructor.

Claude Code's auto-memory directory is NOT `slug_for(cwd)`. It is repository-derived
(worktrees and nested subdirs share one store), remappable via CLAUDE_CONFIG_DIR /
CLAUDE_CODE_PROJECT_DIR_NAME / autoMemoryDirectory (every settings scope), and
disableable. This module is the single construction site. slug_for is ALIASED from
memory_status (no sixth copy). Git identity is filesystem-only (no subprocess) so
the SessionStart beacon can call it inside a 2s budget.

Writes fail closed when resolution sources disagree or an ephemeral --settings path
cannot be reconstructed. cm doctor is read-only and still prints the ambiguity.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional, TextIO

SCHEMA_VERSION = "2"
PLUGIN_ID = "consolidate-memory"
VOLATILE_FRONTMATTER = (
    "modified", "mirrored_at", "projects", "last_used", "last_read",
    "usage", "global_ref_since", "content_modified", "verified_at",
    "last_observed_at", "canonical_fact_id", "canonical_domain",
    "base_revision", "canonical_revision",
)


class WriteRefused(RuntimeError):
    """Raised when a mutation is refused (disagreement, disabled auto-memory, no override)."""


# 0.2.2: unknown is a local-only sentinel (ADR 008). Do not soften the wording.
UNENROLLED_SHARE_WARNING = (
    "UNENROLLED LOCAL-ONLY: this project cannot create or pull cross-project "
    "canonicals until it is enrolled in a named domain "
    "(cm project enroll --domain personal --apply). First enroll grants the "
    "domain and revokes managed mirrors the destination does not admit. Use "
    "move-domain to switch; unenroll to go local-only. Do not run migrate "
    "apply/rollback or domain switches on irreplaceable stores. 1.0 remains HOLD."
)


def is_unenrolled_share(ctx: "StoreContext") -> bool:
    return (not ctx.enrolled) or ctx.domain_id == "unknown"


def warn_unenrolled_share(ctx: "StoreContext", stream: Optional[TextIO] = None) -> None:
    """Loud, deterministic warning for doctor/pull/promote/upsert/dashboards."""
    if not is_unenrolled_share(ctx):
        return
    print(UNENROLLED_SHARE_WARNING, file=stream if stream is not None else sys.stderr)


def identity_snapshot(ctx: "StoreContext") -> dict:
    """Path-free identity for cycle records and the HTML archive (v0.3.0).

    The HTML file is often shared; this never embeds filesystem paths. `conflicts`
    is best-effort (omitted when the registry cannot be read — absent ≠ zero).
    """
    out: dict = {
        "domain_id": ctx.domain_id or "unknown",
        "enrolled": bool(ctx.enrolled),
        "registry_state": getattr(ctx, "registry_state", "absent") or "absent",
        "cross_project_allowed": bool(getattr(ctx, "cross_project_allowed", False)),
        "domain_lifecycle": str(getattr(ctx, "domain_lifecycle", "active") or "active"),
    }
    try:
        from control_plane import connect_if_exists, list_conflicts
        conn = connect_if_exists(ctx.plugin_data_dir / "control.sqlite")
        if conn is not None:
            try:
                out["conflicts"] = len(list_conflicts(conn, ctx.project_id))
            finally:
                conn.close()
    except Exception:
        pass
    return out


@dataclass(frozen=True)
class StoreContext:
    config_root: Path
    native_memory_dir: Path
    canonical_domain_dir: Path
    plugin_data_dir: Path
    git_common_dir: Optional[Path]
    project_id: str
    profile_id: str
    domain_id: str
    auto_memory_enabled: bool
    resolution_source: str
    session_dir: Path
    project_root: Path
    write_allowed: bool
    ambiguity: tuple
    settings_sources: tuple
    display_name: str
    remote_fingerprint: str
    project_slot: str
    store_override: Optional[Path]
    requested_domain: str = "unknown"
    enrolled: bool = False
    registry_state: str = "absent"
    cross_project_allowed: bool = False
    registry_error: str = ""
    domain_lifecycle: str = "active"


def slug_for(project_dir: Path) -> str:
    """Alias of memory_status.slug_for — imported lazily to avoid a load-time cycle."""
    from memory_status import slug_for as _slug_for
    return _slug_for(project_dir)


def _home_dir(environ: Any = None) -> Path:
    """Honor the passed environ's HOME (hermetic tests pass a dict, not os.environ)."""
    env = environ if environ is not None else os.environ
    h = str(env.get("HOME") or "").strip()
    if h:
        return Path(h).expanduser()
    return Path.home()


def config_root(environ: Optional[dict] = None) -> Path:
    env = environ if environ is not None else os.environ
    raw = str(env.get("CLAUDE_CONFIG_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _home_dir(env) / ".claude"


def plugin_data_dir(cfg: Optional[Path] = None, environ: Optional[dict] = None) -> Path:
    """${CLAUDE_PLUGIN_DATA} analogue: <config-root>/plugins/data/consolidate-memory."""
    root = cfg if cfg is not None else config_root(environ)
    env = environ if environ is not None else os.environ
    explicit = str(env.get("CLAUDE_PLUGIN_DATA") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return root / "plugins" / "data" / PLUGIN_ID


def _norm_path(p: Path) -> str:
    try:
        return str(p.resolve()).replace("\\", "/")
    except OSError:
        return str(p).replace("\\", "/")


def profile_id_for(cfg: Path, environ: Optional[dict] = None) -> str:
    default = _home_dir(environ) / ".claude"
    try:
        if cfg.resolve() == default.resolve():
            return "default"
    except OSError:
        pass
    return "cfg_" + hashlib.sha256(_norm_path(cfg).encode("utf-8")).hexdigest()[:12]


def _load_json(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _path_contained(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _read_plain_path_file(path: Path) -> Optional[Path]:
    """Read a Git `gitdir`/`commondir` file that stores a raw path (not `gitdir:`)."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = path.parent / p
    try:
        return p.resolve()
    except OSError:
        return p


def _gitdir_layout_ok(worktree: Path, gitfile: Path, gitdir: Path) -> bool:
    """Accept only in-tree .git, registered worktrees, or submodule gitdirs.

    Path *shape* is not enough: a crafted gitfile can point at another
    repository's worktrees/ or modules/ directory. Require the administrative
    dir's gitdir backlink (when present), modules-relative path match, and
    commondir containment. A symlinked `.git` is never Git (P0-2).
    """
    try:
        if gitfile.is_symlink() or gitdir.is_symlink():
            return False
        gd = gitdir.resolve()
        wt = worktree.resolve()
        gf = gitfile.resolve()
    except OSError:
        return False
    try:
        dotgit = wt / ".git"
        if dotgit.is_symlink():
            return False
        in_tree = gd == dotgit.resolve() or _path_contained(gd, wt / ".git")
    except OSError:
        in_tree = gd == wt / ".git" or _path_contained(gd, wt / ".git")
    if in_tree:
        common = _common_from_gitdir(gd)
        return common == gd or _path_contained(common, gd)

    def _backlink_ok() -> bool:
        back = gd / "gitdir"
        if not back.is_file():
            return False
        pointed = _read_plain_path_file(back)
        return pointed is not None and pointed == gf

    # linked worktree: <repo>/.git/worktrees/<name>
    if gd.parent.name == "worktrees" and gd.parent.parent.name == ".git":
        if not _backlink_ok():
            return False
        admin = gd.parent.parent
        common = _common_from_gitdir(gd)
        return common == admin or _path_contained(common, admin)

    # submodule: <super>/.git/modules/<rel> must match worktree relpath
    cur = gd
    while cur != cur.parent:
        if cur.name == "modules" and cur.parent.name == ".git":
            super_git = cur.parent
            super_wt = super_git.parent
            try:
                wt_rel = wt.relative_to(super_wt)
                gd_rel = gd.relative_to(cur)
            except ValueError:
                return False
            if wt_rel.parts != gd_rel.parts:
                return False
            if (gd / "gitdir").is_file() and not _backlink_ok():
                return False
            common = _common_from_gitdir(gd)
            return (common == gd or common == super_git
                    or _path_contained(common, super_git))
        cur = cur.parent
    return False


def _read_gitdir_pointer(gitfile: Path) -> Optional[Path]:
    try:
        for line in gitfile.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("gitdir:"):
                raw = line.split(":", 1)[1].strip()
                p = Path(raw)
                if not p.is_absolute():
                    p = (gitfile.parent / p)
                try:
                    return p.resolve()
                except OSError:
                    return p
    except OSError:
        return None
    return None


def _common_from_gitdir(gitdir: Path) -> Path:
    commondir = gitdir / "commondir"
    if commondir.is_file():
        try:
            rel = commondir.read_text(encoding="utf-8", errors="replace").strip()
            c = Path(rel)
            if not c.is_absolute():
                c = gitdir / c
            return c.resolve()
        except OSError:
            pass
    if gitdir.parent.name == "worktrees":
        return gitdir.parent.parent
    return gitdir


def _is_junk_git_root(root: Path) -> bool:
    """A git repo at / or /tmp is a junk drawer, not a Claude project (hermetic
    TemporaryDirectory fixtures live under /tmp; a `git init` there must not fuse them)."""
    try:
        r = str(root.resolve()).replace("\\", "/").rstrip("/") or "/"
    except OSError:
        r = str(root).replace("\\", "/").rstrip("/") or "/"
    return r in ("/", "/tmp", "/var/tmp", "/private/tmp")


def find_git_common_dir(start: Path) -> Optional[Path]:
    """Filesystem-only Git common-dir discovery (no subprocess)."""
    try:
        cur = start.resolve()
    except OSError:
        cur = start
    chain = [cur]
    chain.extend(list(cur.parents))
    for p in chain:
        git = p / ".git"
        try:
            if git.is_symlink():
                continue
            if git.is_file():
                gitdir = _read_gitdir_pointer(git)
                if gitdir is None:
                    continue
                if not _gitdir_layout_ok(p, git, gitdir):
                    continue
                common = _common_from_gitdir(gitdir)
                if _is_junk_git_root(discover_git_working_tree(p, git, gitdir, common)):
                    continue
                return common
            if git.is_dir():
                common = _common_from_gitdir(git)
                if not _gitdir_layout_ok(p, git, git):
                    continue
                if _is_junk_git_root(git_working_tree_root(common)):
                    continue
                return common
        except OSError:
            continue
    return None


def discover_git_working_tree(worktree: Path, gitfile: Path, gitdir: Path,
                              common: Path) -> Path:
    """Working tree for a gitfile. Submodule gitdirs are NOT super/.git.parent.

    Linked worktrees keep the main-repo working tree so they share the native
    store (project_id hashes git_common_dir; slug follows the main tree).
    """
    del gitfile
    try:
        gd = gitdir.resolve()
    except OSError:
        gd = gitdir
    cur = gd
    while cur != cur.parent:
        if cur.name == "modules" and cur.parent.name == ".git":
            return worktree
        cur = cur.parent
    return git_working_tree_root(common)


def git_working_tree_root(common: Path) -> Path:
    if common.name == ".git":
        return common.parent
    return common


def remote_fingerprint(common: Optional[Path]) -> str:
    if common is None:
        return ""
    cfg = common / "config"
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    in_origin = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_origin = "remote" in s.lower() and "origin" in s.lower()
            continue
        if in_origin and s.lower().startswith("url"):
            url = s.split("=", 1)[-1].strip()
            if url:
                return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return ""


def project_id_for(profile: str, domain: str, git_common: Optional[Path],
                   root: Path, remote_fp: str = "") -> str:
    """Stable id. Domain is a registry attribute (enroll), not part of identity —
    otherwise `cm project enroll` would mint a new project.
    `domain` is accepted for call-site compatibility and ignored in the hash.
    """
    del domain
    del remote_fp  # descriptive metadata only (P1-8); not part of identity
    if git_common is not None:
        payload = "\n".join([
            SCHEMA_VERSION, profile, _norm_path(git_common),
        ])
        return "p_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    key = f"cm:{SCHEMA_VERSION}:{profile}:{_norm_path(root)}"
    return "p_" + uuid.uuid5(uuid.NAMESPACE_URL, key).hex


STORE_GRANTS_NAME = "store-grants.json"


def store_grants_path(pdata: Path) -> Path:
    return pdata / STORE_GRANTS_NAME


def _grants_from_json(pdata: Path) -> list:
    data = _load_json(store_grants_path(pdata))
    grants = data.get("grants") if isinstance(data, dict) else None
    if not isinstance(grants, list):
        return []
    out: list = []
    for g in grants:
        if isinstance(g, dict) and str(g.get("project_id") or "").strip() and str(
                g.get("path") or "").strip():
            out.append(g)
    return out


def load_store_grants(pdata: Path) -> list:
    """Operator-enrolled native-store grants. SQLite is authority; JSON is dual-read."""
    from control_plane import connect_if_exists
    conn = connect_if_exists(pdata / "control.sqlite")
    if conn is not None:
        try:
            rows = conn.execute(
                "SELECT normalized_path, project_id, created_at, adopted_nonempty "
                "FROM native_store_grants").fetchall()
            return [{
                "project_id": str(r["project_id"] or ""),
                "path": str(r["normalized_path"] or ""),
                "created_at": str(r["created_at"] or ""),
                "adopted_nonempty": int(r["adopted_nonempty"] or 0),
            } for r in rows]
        except Exception:
            pass
        finally:
            conn.close()
    return _grants_from_json(pdata)


def _grant_path_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def grant_covers(grants: list, project_id: str, custom: Path) -> bool:
    want = _grant_path_key(custom)
    for g in grants:
        if str(g.get("project_id") or "") != project_id:
            continue
        raw = str(g.get("path") or "").strip()
        if not raw:
            continue
        if _grant_path_key(Path(raw)) == want:
            return True
    return False


def _grant_lock(pdata: Path):
    from control_plane import FileLock
    return FileLock(pdata / "locks" / "global.lock")


def _migrate_json_grants(conn, pdata: Path) -> None:
    """One-shot JSON → SQLite ingest — delegates to the registry's single ingester
    (the v0.4.0 single-enumerator rule applied to grant ingestion: one reader)."""
    from control_plane import _ingest_json_grants
    _ingest_json_grants(conn, pdata)


def write_store_grant(pdata: Path, project_id: str, path: Path,
                      *, config_root: Optional[Path] = None,
                      adopt: bool = False) -> dict:
    """Record an operator grant. One owner per normalized path (SQLite)."""
    resolved_check = Path(_grant_path_key(path))
    if _path_contained(resolved_check, pdata):
        raise WriteRefused("grant cannot target plugin-data")
    if config_root is not None:
        if _path_contained(resolved_check, config_root / "consolidate-memory"):
            raise WriteRefused("grant cannot target domain canonicals")
        if _path_contained(resolved_check, config_root / "memory"):
            raise WriteRefused("grant cannot target leftover global memory")
    nonempty = False
    try:
        nonempty = resolved_check.is_dir() and any(resolved_check.iterdir())
    except OSError:
        nonempty = False
    if nonempty and not adopt:
        raise WriteRefused("grant of nonempty path requires --adopt")
    pdata.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(pdata), 0o700)
    except OSError:
        pass
    resolved = _grant_path_key(path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    from control_plane import connect
    lock = _grant_lock(pdata)
    lock.acquire()
    try:
        conn = connect(pdata / "control.sqlite")
        try:
            _migrate_json_grants(conn, pdata)
            row = conn.execute(
                "SELECT project_id FROM native_store_grants WHERE normalized_path=?",
                (resolved,)).fetchone()
            if row is not None and str(row["project_id"] or "") != project_id:
                raise WriteRefused(
                    "path already granted to " + str(row["project_id"]))
            conn.execute(
                "INSERT INTO native_store_grants(normalized_path, project_id, "
                "created_at, adopted_nonempty) VALUES (?,?,?,?) "
                "ON CONFLICT(normalized_path) DO UPDATE SET "
                "project_id=excluded.project_id, "
                "adopted_nonempty=excluded.adopted_nonempty",
                (resolved, project_id, now, 1 if (nonempty and adopt) else 0))
            conn.commit()
        finally:
            conn.close()
    finally:
        lock.release()
    try:
        resolved_check.mkdir(parents=True, exist_ok=True)
        os.chmod(str(resolved_check), 0o700)
    except OSError:
        pass
    return {"ok": True, "project_id": project_id, "path": resolved,
            "adopted_nonempty": bool(nonempty and adopt)}


def revoke_store_grant(pdata: Path, project_id: str, path: Path) -> dict:
    resolved = _grant_path_key(path)
    from control_plane import connect
    lock = _grant_lock(pdata)
    lock.acquire()
    removed = 0
    try:
        conn = connect(pdata / "control.sqlite")
        try:
            _migrate_json_grants(conn, pdata)
            cur = conn.execute(
                "DELETE FROM native_store_grants WHERE normalized_path=? "
                "AND project_id=?",
                (resolved, project_id))
            removed = int(cur.rowcount or 0)
            conn.commit()
        finally:
            conn.close()
    finally:
        lock.release()
    return {"ok": True, "project_id": project_id, "path": resolved,
            "removed": removed}


def transfer_store_grant(pdata: Path, path: Path, to_project_id: str) -> dict:
    resolved = _grant_path_key(path)
    from control_plane import connect
    lock = _grant_lock(pdata)
    lock.acquire()
    try:
        conn = connect(pdata / "control.sqlite")
        try:
            row = conn.execute(
                "SELECT project_id FROM native_store_grants WHERE normalized_path=?",
                (resolved,)).fetchone()
            if row is None:
                raise WriteRefused("no grant for " + resolved)
            conn.execute(
                "UPDATE native_store_grants SET project_id=? WHERE normalized_path=?",
                (to_project_id, resolved))
            conn.commit()
            return {"ok": True, "path": resolved, "from": str(row["project_id"] or ""),
                    "to": to_project_id}
        finally:
            conn.close()
    finally:
        lock.release()


def _protected_config_target(custom: Path, cfg: Path, default_native: Path,
                             pdata: Path) -> bool:
    """True if custom is another config-root store, a canonical dir, or plugin-data.

    Exact current-project default native is not protected (it is the allow).
    """
    try:
        c = custom.resolve()
        if c == default_native.resolve():
            return False
    except OSError:
        return True
    if _path_contained(custom, pdata):
        return True
    if _path_contained(custom, cfg / "consolidate-memory"):
        return True
    if _path_contained(custom, cfg / "projects"):
        return True
    if _path_contained(custom, cfg):
        return True
    return False


def _project_local_mem_ok(custom: Path, cfg: Path, root: Path,
                          default_native: Path, *, pdata: Path,
                          project_id: str) -> bool:
    """Project/local autoMemoryDirectory may not select another config-root store.

    Allow: exact current-project native, an in-tree directory that is not a
    protected config-root path, or a separately stored operator grant.
    """
    try:
        if custom.resolve() == default_native.resolve():
            return True
    except OSError:
        pass
    if grant_covers(load_store_grants(pdata), project_id, custom):
        return True
    if _path_contained(custom, root) and not _protected_config_target(
            custom, cfg, default_native, pdata):
        return True
    return False


def _expand_mem_dir(raw: str) -> Optional[Path]:
    s = (raw or "").strip()
    if not s:
        return None
    if s.startswith("~/") or s == "~":
        return Path(s).expanduser()
    p = Path(s)
    if p.is_absolute():
        return p
    return None  # Claude requires absolute or ~/


def _merge_settings(cfg: Path, project_root: Path, environ: dict,
                    settings_path: Optional[Path]) -> tuple:
    """Return (merged dict, source names, ephemeral_unreadable, mem_dir_source).

    `mem_dir_source` is the last settings scope that set `autoMemoryDirectory`
    (empty if none did). Project/local paths must stay contained; user/managed
    may name an explicit absolute dir.
    """
    sources: list = []
    merged: dict = {}
    ephemeral_unreadable = False
    mem_dir_source = ""

    def _apply(label: str, path: Path) -> None:
        nonlocal mem_dir_source
        if not path.is_file():
            return
        data = _load_json(path)
        if not data:
            return
        merged.update(data)
        sources.append(label)
        if "autoMemoryDirectory" in data:
            mem_dir_source = label

    # Lowest → highest, matching Claude Code: user, project, local, --settings,
    # then managed policy (highest; not overridden by any of the above).
    # If the git root is $HOME, project `.claude/settings.json` IS the user
    # file — do not treat that operator file as repository-controlled.
    user_settings = cfg / "settings.json"
    project_settings = project_root / ".claude" / "settings.json"
    local_settings = project_root / ".claude" / "settings.local.json"
    _apply("user", user_settings)
    try:
        same_project = project_settings.resolve() == user_settings.resolve()
    except OSError:
        same_project = False
    if not same_project:
        _apply("project", project_settings)
    try:
        same_local = local_settings.resolve() == user_settings.resolve()
    except OSError:
        same_local = False
    if not same_local:
        _apply("local", local_settings)

    cli = settings_path
    env_settings = str(environ.get("CLAUDE_CODE_SETTINGS") or "").strip()
    if cli is None and env_settings:
        cli = Path(env_settings).expanduser()
    if cli is not None:
        if cli.is_file():
            _apply("settings-flag", cli)
        else:
            ephemeral_unreadable = True
            sources.append("settings-flag-missing")
    _apply("policy", cfg / "managed-settings.json")
    etc = Path("/etc/claude-code/managed-settings.json")
    if etc.is_file():
        _apply("policy-etc", etc)
    return merged, tuple(sources), ephemeral_unreadable, mem_dir_source


def _requested_domain(project_root: Path, cfg: Path, environ: dict) -> str:
    """Suggestion only — never a grant.

    CM_DOMAIN, managed-settings, user settings, domain.json, and repo
    project/local settings may *request* a domain. Admission `domain_id`
    comes only from registry `status=enrolled` (`enrolled_domain`).
    """
    from identifiers import IdentifierRefused, validate_domain_id

    def _from(data: dict) -> str:
        cm = data.get("consolidateMemory")
        if isinstance(cm, dict) and str(cm.get("domain") or "").strip():
            return str(cm.get("domain")).strip()
        return ""

    candidates = [
        str(environ.get("CM_DOMAIN") or "").strip(),
        _from(_load_json(cfg / "managed-settings.json")),
        _from(_load_json(Path("/etc/claude-code/managed-settings.json"))),
        _from(_load_json(cfg / "settings.json")),
        str(_load_json(cfg / "consolidate-memory" / "domain.json").get("domain") or "").strip(),
        _from(_load_json(project_root / ".claude" / "settings.json")),
        _from(_load_json(project_root / ".claude" / "settings.local.json")),
    ]
    for raw in candidates:
        if not raw:
            continue
        try:
            return validate_domain_id(raw)
        except IdentifierRefused:
            continue
    return "unknown"


def _operator_domain(settings: dict, cfg: Path, environ: dict,
                     setting_sources: tuple) -> str:
    """Deprecated alias: operator files are requests, not grants."""
    del settings, setting_sources
    return "unknown"


def _requested_domain_from_repo(project_root: Path) -> str:
    """Suggestion only — never a grant."""
    data = _load_json(project_root / ".claude" / "settings.json")
    cm = data.get("consolidateMemory")
    if isinstance(cm, dict) and str(cm.get("domain") or "").strip():
        return str(cm.get("domain")).strip()
    data = _load_json(project_root / ".claude" / "settings.local.json")
    cm = data.get("consolidateMemory")
    if isinstance(cm, dict) and str(cm.get("domain") or "").strip():
        return str(cm.get("domain")).strip()
    return ""


def _auto_memory_enabled(settings: dict, environ: dict) -> bool:
    flag = str(environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return False
    if flag in ("0", "false", "no", "off"):
        return True
    if "autoMemoryEnabled" in settings:
        return bool(settings.get("autoMemoryEnabled"))
    return True


def resolve_store(project_dir: Path, *, cwd: Optional[Path] = None,
                  hook: Optional[dict] = None, settings_path: Optional[Path] = None,
                  store_override: Optional[Path] = None,
                  environ: Optional[dict] = None) -> StoreContext:
    """Resolve the native + canonical + control-plane locations for `project_dir`."""
    env = dict(environ) if environ is not None else dict(os.environ)
    start = Path(project_dir)
    if hook and isinstance(hook.get("cwd"), str) and hook["cwd"]:
        # session observation — does not replace project_dir, but can fill cwd
        cwd = cwd or Path(hook["cwd"])
    try:
        start = start.resolve()
    except OSError:
        pass

    cfg = config_root(env)
    profile = profile_id_for(cfg, env)
    common = find_git_common_dir(start)
    if common is not None:
        git = None
        try:
            cur = start.resolve()
        except OSError:
            cur = start
        for p in [cur, *list(cur.parents)]:
            gf = p / ".git"
            try:
                if gf.is_symlink():
                    continue
                if gf.is_file():
                    gitdir = _read_gitdir_pointer(gf)
                    if gitdir is not None and _gitdir_layout_ok(p, gf, gitdir):
                        root = discover_git_working_tree(p, gf, gitdir, common)
                        git = gf
                        break
                if gf.is_dir() and _gitdir_layout_ok(p, gf, gf):
                    root = git_working_tree_root(common)
                    git = gf
                    break
            except OSError:
                continue
        if git is None:
            root = git_working_tree_root(common)
    else:
        root = start
    remote_fp = remote_fingerprint(common)

    settings, setting_sources, ephemeral_unreadable, mem_dir_source = _merge_settings(
        cfg, root, env, settings_path)
    requested_domain = _requested_domain(root, cfg, env)
    domain = "unknown"
    enabled = _auto_memory_enabled(settings, env)

    slot_env = str(env.get("CLAUDE_CODE_PROJECT_DIR_NAME") or "").strip()
    default_slot = slug_for(root)
    project_slot = slot_env or default_slot
    session_dir = cfg / "projects" / project_slot
    default_native = session_dir / "memory"
    pdata = plugin_data_dir(cfg, env)
    pid = project_id_for(profile, domain, common, root, remote_fp)
    enrolled = False
    life = "active"
    from control_plane import (classify_registry, connect_if_exists,
                               domain_lifecycle as _domain_lifecycle,
                               enrolled_domain, resolve_project_alias)
    _db = pdata / "control.sqlite"
    reg_state, reg_err = classify_registry(_db)
    if reg_state == "healthy":
        _c = connect_if_exists(_db)
        if _c is not None:
            try:
                aliased = resolve_project_alias(_c, pid)
                if aliased:
                    pid = aliased
                got = enrolled_domain(_c, pid)
                if not got and common is not None:
                    rows = _c.execute(
                        "SELECT project_id FROM projects WHERE status='enrolled' "
                        "AND profile_id=? AND git_common_dir=?",
                        (profile, str(common))).fetchall()
                    if len(rows) == 1:
                        old_pid = str(rows[0]["project_id"] or "")
                        if old_pid:
                            pid = old_pid
                        got = enrolled_domain(_c, pid)
                if got:
                    domain = got
                    enrolled = True
                if domain and domain != "unknown":
                    life = _domain_lifecycle(_c, domain)
            finally:
                _c.close()

    custom = _expand_mem_dir(str(settings.get("autoMemoryDirectory") or ""))
    override = store_override
    ov_env = str(env.get("CM_STORE_OVERRIDE") or "").strip()
    if override is None and ov_env:
        override = Path(ov_env).expanduser()

    ambiguity: list = []
    source = "default-git-root" if common is not None else "default-path"
    native = default_native

    cwd_slot_dir: Optional[Path] = None
    if cwd is not None:
        try:
            cwd_res = cwd.resolve()
        except OSError:
            cwd_res = cwd
        if slug_for(cwd_res) != default_slot:
            cwd_slot_dir = cfg / "projects" / slug_for(cwd_res) / "memory"

    if slot_env:
        source = "CLAUDE_CODE_PROJECT_DIR_NAME"
        native = default_native
    if custom is not None:
        source = "autoMemoryDirectory"
        native = custom
        if mem_dir_source in ("project", "local"):
            if not _project_local_mem_ok(
                    custom, cfg, root, default_native, pdata=pdata, project_id=pid):
                ambiguity.append(
                    "project/local autoMemoryDirectory escapes this project's "
                    "native store and project tree: " + str(custom))
                native = default_native
                if slot_env:
                    source = "CLAUDE_CODE_PROJECT_DIR_NAME"
                elif common is not None:
                    source = "default-git-root"
                else:
                    source = "default-path"
    if override is not None:
        source = "store-override"
        native = override

    def _live(p: Path) -> bool:
        try:
            return (p / "MEMORY.md").is_file()
        except OSError:
            return False

    git_slot_native = cfg / "projects" / default_slot / "memory"
    candidates = [default_native, git_slot_native]
    if custom is not None:
        candidates.append(custom)
    if cwd_slot_dir is not None:
        candidates.append(cwd_slot_dir)
    live = []
    seen = set()
    for c in candidates:
        try:
            key = str(c.resolve())
        except OSError:
            key = str(c)
        if key in seen:
            continue
        seen.add(key)
        if _live(c):
            live.append(c)
    chosen_key = _norm_path(native)
    if override is None:
        for c in live:
            if _norm_path(c) != chosen_key:
                ambiguity.append(
                    "live MEMORY.md at " + str(c) + " is not the chosen native " + str(native))
                break
    if ephemeral_unreadable and override is None:
        ambiguity.append("ephemeral --settings path cannot be reconstructed")

    write_allowed = enabled and not ambiguity
    if override is not None:
        write_allowed = enabled  # explicit override wins disagreement
    from identifiers import IdentifierRefused, safe_child, validate_domain_id
    try:
        dname = validate_domain_id(domain, allow_unknown=True)
        droot = (cfg / "consolidate-memory" / "domains")
        canon = safe_child(droot, dname) / "facts"
    except IdentifierRefused:
        domain = "unknown"
        canon = cfg / "consolidate-memory" / "domains" / "unknown" / "facts"
    cross_project_allowed = (
        reg_state == "healthy" and enrolled and domain != "unknown"
        and life == "active"
    )

    return StoreContext(
        config_root=cfg,
        native_memory_dir=native,
        canonical_domain_dir=canon,
        plugin_data_dir=pdata,
        git_common_dir=common,
        project_id=pid,
        profile_id=profile,
        domain_id=domain,
        auto_memory_enabled=enabled,
        resolution_source=source,
        session_dir=session_dir,
        project_root=root,
        write_allowed=write_allowed,
        ambiguity=tuple(ambiguity),
        settings_sources=setting_sources,
        display_name=root.name,
        remote_fingerprint=remote_fp,
        project_slot=project_slot,
        store_override=override,
        requested_domain=requested_domain or "unknown",
        enrolled=enrolled,
        registry_state=reg_state,
        cross_project_allowed=cross_project_allowed,
        registry_error=reg_err,
        domain_lifecycle=life,
    )


def store_context_from_registry(row: Any, *, template: StoreContext) -> StoreContext:
    """Build a StoreContext from a registry projects row (P0-9).

    Uses the recorded project_id, native store, root, and domain. Never treats
    native_memory_dir as a project root (that minted a different project id).
    """
    from identifiers import IdentifierRefused, safe_child, validate_domain_id

    def _col(name: str, default: str = "") -> str:
        if hasattr(row, "keys"):
            try:
                val = row[name]
            except (KeyError, IndexError):
                return default
            return str(val or "").strip()
        return default

    pid = _col("project_id")
    native_s = _col("native_memory_dir")
    root_s = _col("current_root")
    git_s = _col("git_common_dir")
    did = _col("domain_id") or "unknown"
    sess_s = _col("session_dir")
    display = _col("display_name")
    status = _col("status")
    if not native_s:
        raise WriteRefused("registry row missing native_memory_dir")
    native = Path(native_s)
    root = Path(root_s) if root_s else template.project_root
    git: Optional[Path] = Path(git_s) if git_s else None
    session = Path(sess_s) if sess_s else template.session_dir
    try:
        dname = validate_domain_id(did, allow_unknown=True)
        canon = safe_child(
            template.config_root / "consolidate-memory" / "domains", dname) / "facts"
    except IdentifierRefused:
        dname = "unknown"
        canon = (template.config_root / "consolidate-memory" / "domains"
                 / "unknown" / "facts")
    enrolled = status == "enrolled"
    life = "active"
    if dname and dname != "unknown":
        from control_plane import connect_if_exists as _cie, domain_lifecycle as _dlife
        _c = _cie(template.plugin_data_dir / "control.sqlite")
        if _c is not None:
            try:
                life = _dlife(_c, dname)
            finally:
                _c.close()
    return replace(
        template,
        native_memory_dir=native,
        canonical_domain_dir=canon,
        git_common_dir=git,
        project_id=pid or template.project_id,
        domain_id=dname,
        project_root=root,
        session_dir=session,
        display_name=display or template.display_name,
        enrolled=enrolled,
        domain_lifecycle=life,
        cross_project_allowed=(
            template.registry_state == "healthy" and enrolled and dname != "unknown"
            and life == "active"
        ),
        resolution_source="registry-row",
        store_override=native,
    )


def assert_writable(ctx: StoreContext) -> None:
    if not ctx.auto_memory_enabled:
        raise WriteRefused("auto-memory is disabled (autoMemoryEnabled / CLAUDE_CODE_DISABLE_AUTO_MEMORY)")
    if not ctx.write_allowed:
        raise WriteRefused("resolution sources disagree: " + "; ".join(ctx.ambiguity)
                           + " — pass an explicit store override")


def _registry_state_line(ctx: StoreContext) -> str:
    err = getattr(ctx, "registry_error", "") or ""
    state = getattr(ctx, "registry_state", "absent") or "absent"
    return state if not err else f"{state}: {err}"


def _integrity_check(ctx: StoreContext) -> str:
    from control_plane import connect_if_exists
    conn = connect_if_exists(ctx.plugin_data_dir / "control.sqlite")
    if conn is None:
        return "absent"
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0] if row is not None else "unknown")
    except Exception:
        return "error"
    finally:
        conn.close()


def doctor_report(ctx: StoreContext) -> str:
    """Stable key: value lines (twice-run equality)."""
    amb = "; ".join(ctx.ambiguity) if ctx.ambiguity else "(none)"
    rows = [
        ("config_root", str(ctx.config_root)),
        ("native_memory_dir", str(ctx.native_memory_dir)),
        ("canonical_domain_dir", str(ctx.canonical_domain_dir)),
        ("plugin_data_dir", str(ctx.plugin_data_dir)),
        ("session_dir", str(ctx.session_dir)),
        ("project_root", str(ctx.project_root)),
        ("git_common_dir", str(ctx.git_common_dir) if ctx.git_common_dir else "(none)"),
        ("project_id", ctx.project_id),
        ("profile_id", ctx.profile_id),
        ("domain_id", ctx.domain_id),
        ("requested_domain", ctx.requested_domain),
        ("enrolled", "true" if ctx.enrolled else "false"),
        ("domain_lifecycle", str(getattr(ctx, "domain_lifecycle", "active") or "active")),
        ("registry_state", _registry_state_line(ctx)),
        ("cross_project_allowed", "true" if getattr(ctx, "cross_project_allowed", False) else "false"),
        ("auto_memory_enabled", "true" if ctx.auto_memory_enabled else "false"),
        ("resolution_source", ctx.resolution_source),
        ("write_allowed", "true" if ctx.write_allowed else "false"),
        ("ambiguity", amb),
        ("display_name", ctx.display_name),
        ("project_slot", ctx.project_slot),
        ("remote_fingerprint", ctx.remote_fingerprint or "(none)"),
        ("settings_sources", ",".join(ctx.settings_sources) if ctx.settings_sources else "(none)"),
        ("unenrolled_share_warning",
         UNENROLLED_SHARE_WARNING if is_unenrolled_share(ctx) else "(none)"),
        ("integrity_check", _integrity_check(ctx)),
    ]
    computed = project_id_for(ctx.profile_id, ctx.domain_id, ctx.git_common_dir,
                              ctx.project_root, ctx.remote_fingerprint)
    if computed != ctx.project_id:
        rows.append(("computed_project_id", computed))
        rows.append(("enrolled_project_id", ctx.project_id))
    return "\n".join(f"{k}: {v}" for k, v in rows) + "\n"


def doctor_dict(ctx: StoreContext) -> dict:
    return {
        "config_root": str(ctx.config_root),
        "native_memory_dir": str(ctx.native_memory_dir),
        "canonical_domain_dir": str(ctx.canonical_domain_dir),
        "plugin_data_dir": str(ctx.plugin_data_dir),
        "git_common_dir": str(ctx.git_common_dir) if ctx.git_common_dir else None,
        "project_id": ctx.project_id,
        "profile_id": ctx.profile_id,
        "domain_id": ctx.domain_id,
        "requested_domain": ctx.requested_domain,
        "enrolled": ctx.enrolled,
        "domain_lifecycle": str(getattr(ctx, "domain_lifecycle", "active") or "active"),
        "registry_state": _registry_state_line(ctx),
        "cross_project_allowed": getattr(ctx, "cross_project_allowed", False),
        "auto_memory_enabled": ctx.auto_memory_enabled,
        "resolution_source": ctx.resolution_source,
        "write_allowed": ctx.write_allowed,
        "ambiguity": list(ctx.ambiguity),
        "display_name": ctx.display_name,
        "project_slot": ctx.project_slot,
        "unenrolled_share_warning": (
            UNENROLLED_SHARE_WARNING if is_unenrolled_share(ctx) else None),
        "integrity_check": _integrity_check(ctx),
    }


def repair_permissions(ctx: StoreContext) -> dict:
    """chmod 0700 on plugin-data/domain dirs and 0600 on files written there."""
    n_dirs = n_files = 0
    roots = [ctx.plugin_data_dir]
    droot = ctx.config_root / "consolidate-memory" / "domains"
    if droot.exists():
        roots.append(droot)
    if ctx.canonical_domain_dir.parent.exists():
        roots.append(ctx.canonical_domain_dir.parent)
    seen: set = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key in seen or not root.exists():
            continue
        seen.add(key)
        try:
            os.chmod(str(root), 0o700)
            n_dirs += 1
        except OSError:
            pass
        for p in root.rglob("*"):
            try:
                if p.is_dir():
                    os.chmod(str(p), 0o700)
                    n_dirs += 1
                elif p.is_file():
                    os.chmod(str(p), 0o600)
                    n_files += 1
            except OSError:
                continue
    return {"ok": True, "dirs": n_dirs, "files": n_files}


# Identity helper used by tests that must not go through resolve_store's settings I/O.
def same_native_store(a: Path, b: Path, environ: Optional[dict] = None) -> bool:
    return (resolve_store(a, environ=environ).native_memory_dir.resolve()
            == resolve_store(b, environ=environ).native_memory_dir.resolve())
