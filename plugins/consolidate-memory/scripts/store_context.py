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
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "2"
PLUGIN_ID = "consolidate-memory"
VOLATILE_FRONTMATTER = (
    "modified", "mirrored_at", "projects", "last_used", "last_read",
    "usage", "global_ref_since", "content_modified", "verified_at",
    "last_observed_at",
)


class WriteRefused(RuntimeError):
    """Raised when a mutation is refused (disagreement, disabled auto-memory, no override)."""


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
            if git.is_file():
                gitdir = _read_gitdir_pointer(git)
                if gitdir is None:
                    continue
                common = _common_from_gitdir(gitdir)
                if _is_junk_git_root(git_working_tree_root(common)):
                    continue
                return common
            if git.is_dir():
                common = _common_from_gitdir(git)
                if _is_junk_git_root(git_working_tree_root(common)):
                    continue
                return common
        except OSError:
            continue
    return None


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
    if git_common is not None:
        payload = "\n".join([
            SCHEMA_VERSION, profile, _norm_path(git_common), remote_fp or "",
        ])
        return "p_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    key = f"cm:{SCHEMA_VERSION}:{profile}:{_norm_path(root)}"
    return "p_" + uuid.uuid5(uuid.NAMESPACE_URL, key).hex


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
    """Return (merged dict, source names in order, ephemeral_unreadable)."""
    sources: list = []
    merged: dict = {}
    ephemeral_unreadable = False

    def _apply(label: str, path: Path) -> None:
        if not path.is_file():
            return
        data = _load_json(path)
        if not data:
            return
        merged.update(data)
        sources.append(label)

    # Lowest → highest, matching Claude Code: user, project, local, --settings,
    # then managed policy (highest; not overridden by any of the above).
    _apply("user", cfg / "settings.json")
    _apply("project", project_root / ".claude" / "settings.json")
    _apply("local", project_root / ".claude" / "settings.local.json")

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
    return merged, tuple(sources), ephemeral_unreadable


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
        root = git_working_tree_root(common)
    else:
        root = start
    remote_fp = remote_fingerprint(common)

    settings, setting_sources, ephemeral_unreadable = _merge_settings(
        cfg, root, env, settings_path)
    requested_domain = _requested_domain(root, cfg, env)
    domain = "unknown"
    enabled = _auto_memory_enabled(settings, env)

    slot_env = str(env.get("CLAUDE_CODE_PROJECT_DIR_NAME") or "").strip()
    default_slot = slug_for(root)
    project_slot = slot_env or default_slot
    session_dir = cfg / "projects" / project_slot
    default_native = session_dir / "memory"

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
    if override is not None:
        source = "store-override"
        native = override

    def _live(p: Path) -> bool:
        try:
            return (p / "MEMORY.md").is_file()
        except OSError:
            return False

    candidates = [default_native]
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
    if len(live) > 1 and override is None:
        ambiguity.append(
            "multiple live MEMORY.md stores: " + ", ".join(str(x) for x in live))
    if ephemeral_unreadable and override is None:
        ambiguity.append("ephemeral --settings path cannot be reconstructed")

    write_allowed = enabled and not ambiguity
    if override is not None:
        write_allowed = enabled  # explicit override wins disagreement

    pid = project_id_for(profile, domain, common, root, remote_fp)
    enrolled = False
    pdata = plugin_data_dir(cfg, env)
    try:
        from control_plane import connect_if_exists, enrolled_domain
        _db = pdata / "control.sqlite"
        _c = connect_if_exists(_db)
        if _c is not None:
            try:
                got = enrolled_domain(_c, pid)
                if got:
                    domain = got
                    enrolled = True
            finally:
                _c.close()
    except Exception:
        pass
    from identifiers import IdentifierRefused, safe_child, validate_domain_id
    try:
        dname = validate_domain_id(domain, allow_unknown=True)
        droot = (cfg / "consolidate-memory" / "domains")
        canon = safe_child(droot, dname) / "facts"
    except IdentifierRefused:
        domain = "unknown"
        canon = cfg / "consolidate-memory" / "domains" / "unknown" / "facts"

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
    )


def assert_writable(ctx: StoreContext) -> None:
    if not ctx.auto_memory_enabled:
        raise WriteRefused("auto-memory is disabled (autoMemoryEnabled / CLAUDE_CODE_DISABLE_AUTO_MEMORY)")
    if not ctx.write_allowed:
        raise WriteRefused("resolution sources disagree: " + "; ".join(ctx.ambiguity)
                           + " — pass an explicit store override")


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
        ("auto_memory_enabled", "true" if ctx.auto_memory_enabled else "false"),
        ("resolution_source", ctx.resolution_source),
        ("write_allowed", "true" if ctx.write_allowed else "false"),
        ("ambiguity", amb),
        ("display_name", ctx.display_name),
        ("project_slot", ctx.project_slot),
        ("remote_fingerprint", ctx.remote_fingerprint or "(none)"),
        ("settings_sources", ",".join(ctx.settings_sources) if ctx.settings_sources else "(none)"),
    ]
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
        "auto_memory_enabled": ctx.auto_memory_enabled,
        "resolution_source": ctx.resolution_source,
        "write_allowed": ctx.write_allowed,
        "ambiguity": list(ctx.ambiguity),
        "display_name": ctx.display_name,
        "project_slot": ctx.project_slot,
    }


# Identity helper used by tests that must not go through resolve_store's settings I/O.
def same_native_store(a: Path, b: Path, environ: Optional[dict] = None) -> bool:
    return (resolve_store(a, environ=environ).native_memory_dir.resolve()
            == resolve_store(b, environ=environ).native_memory_dir.resolve())
