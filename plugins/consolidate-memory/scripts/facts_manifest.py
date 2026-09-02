#!/usr/bin/env python3
"""Derived facts-manifest cache for the canonical domain facts dir (Phase-5 closeout).

Markdown is the authority. This module is a REBUILDABLE cache of
(stem, mtime_ns, size, ctime_ns, body_hash, sem, class, secret, fm) per canonical
file, so readers (beacon, pull, gc, network, dream) validate by scandir stats and
read a body only when it changed or is absent. Any anomaly fails OPEN to full
enumeration — the cache can slow you down but never serves wrong facts.

Writer: invalidation rides the transact choke point (control_plane.transact +
recover_pending unlink the manifest for any published/deleted path under
domains/<d>/facts/); the few non-transact purge sites unlink explicitly. Rebuild
is lazy, double-checked, under locks/global.lock, written with atomic_write_bytes
(tmp+replace, fsync file+parent, 0600).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1
KILL_SWITCH = "CM_FACTS_MANIFEST"


def manifest_path(plugin_data_dir: Path, domain: str) -> Path:
    return Path(plugin_data_dir) / f"facts-manifest-{domain}.json"


def domain_from_path(path: Path) -> str:
    """The domain owning a canonical path: …/domains/<d>/facts/… → <d>. "" if none."""
    parts = list(Path(path).parts)
    for i in range(len(parts) - 2):
        if parts[i] == "domains" and parts[i + 2] == "facts":
            return parts[i + 1]
    return ""


def invalidate_for_paths(plugin_data_dir: Path, paths) -> int:
    """Unlink the manifest for every domain named by `paths`. Returns count."""
    n = 0
    seen: set = set()
    for p in paths or []:
        d = domain_from_path(Path(str(p)))
        if not d or d in seen:
            continue
        seen.add(d)
        try:
            manifest_path(plugin_data_dir, d).unlink(missing_ok=True)
            n += 1
        except OSError:
            pass
    return n


def invalidate_all(plugin_data_dir: Path) -> int:
    """Unlink every facts-manifest-*.json (used by the domains-root rmtree)."""
    n = 0
    pdir = Path(plugin_data_dir)
    try:
        for p in pdir.glob("facts-manifest-*.json"):
            try:
                p.unlink(missing_ok=True)
                n += 1
            except OSError:
                pass
    except OSError:
        pass
    return n


def build(facts_dir: Path) -> "tuple[list, str]":
    """Enumerate + classify the facts dir once. Returns (rows, domain).

    Per file: open + read + fstat(fd) so the stats PIN the bytes the row was
    built from. Skips MEMORY.md and reserved/unsafe stems (the exact skip set of
    `_admissible_records`).
    """
    from fact_schema import classify_canonical
    from memory_status import _frontmatter, _looks_secret
    from mirror_conflict import semantic_hash
    from sync_global import _body_hash, _is_reserved_stem, _safe_stem
    rows: list = []
    domain = Path(facts_dir).parent.name
    if not Path(facts_dir).is_dir():
        return rows, domain
    try:
        entries = list(os.scandir(facts_dir))
    except OSError:
        return rows, domain
    for ent in entries:
        if not ent.is_file(follow_symlinks=False):
            continue
        name = ent.name
        if not name.endswith(".md") or name == "MEMORY.md":
            continue
        stem = name[:-3]
        if _is_reserved_stem(stem) or not _safe_stem(stem):
            continue
        try:
            fd = os.open(ent.path, os.O_RDONLY)
        except OSError:
            continue
        try:
            st = os.fstat(fd)
            data = os.read(fd, 4 * 1024 * 1024)
        except OSError:
            data = b""
            st = None
        finally:
            os.close(fd)
        if st is None:
            continue
        text = data.decode("utf-8", errors="replace")
        fm = _frontmatter(text)
        cls = classify_canonical(text, stem=stem, domain=domain)
        rows.append({
            "stem": stem,
            "mtime_ns": int(st.st_mtime_ns),
            "size": int(st.st_size),
            "ctime_ns": int(st.st_ctime_ns),
            "body_hash": _body_hash(text),
            "sem": semantic_hash(text),
            "class": cls.get("class") or "",
            "secret": bool(_looks_secret(text)),
            "fm": fm,
        })
    rows.sort(key=lambda r: r["stem"])
    return rows, domain


def load(facts_dir: Path, plugin_data_dir: Path):
    """(rows_by_stem | None, reason). None = fail open (full enumeration)."""
    if os.environ.get(KILL_SWITCH) == "0":
        return None, "kill-switch"
    domain = Path(facts_dir).parent.name
    p = manifest_path(plugin_data_dir, domain)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return None, "absent"
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        return None, "unparseable"
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_VERSION:
        return None, "schema"
    if str(doc.get("domain") or "") != domain:
        return None, "domain-mismatch"
    files = doc.get("files")
    if not isinstance(files, list):
        return None, "files-shape"
    rows: dict = {}
    for r in files:
        if not isinstance(r, dict):
            return None, "row-shape"
        stem = str(r.get("stem") or "").strip()
        fm = r.get("fm")
        if not stem or not isinstance(fm, dict):
            return None, "row-fields"
        rows[stem] = r
    return rows, ""


def ensure(facts_dir: Path, plugin_data_dir: Path):
    """Load, or rebuild-under-lock if absent. (rows_by_stem | None, reason)."""
    rows, reason = load(facts_dir, plugin_data_dir)
    if rows is not None:
        return rows, reason
    if reason in ("absent", "unparseable", "schema", "domain-mismatch",
                  "files-shape", "row-shape"):
        rows, domain = _rebuild_locked(facts_dir, plugin_data_dir)
        if rows:
            return rows, "rebuilt"
        return None, "rebuild-failed"
    return None, reason


def _rebuild_locked(facts_dir: Path, plugin_data_dir: Path):
    from control_plane import FileLock, atomic_write_bytes
    domain = Path(facts_dir).parent.name
    pdir = Path(plugin_data_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    lock = FileLock(pdir / "locks" / "global.lock")
    lock.acquire()
    try:
        # double-checked: another reader may have rebuilt while we waited
        rows, reason = load(facts_dir, pdir)
        if rows is not None:
            return rows, domain
        built, _d = build(facts_dir)
        doc = {"schema_version": SCHEMA_VERSION, "domain": domain,
               "files": built}
        atomic_write_bytes(manifest_path(pdir, domain),
                           (json.dumps(doc, indent=1) + "\n").encode("utf-8"),
                           mode=0o600)
        rows = {r["stem"]: r for r in built}
        return rows, domain
    finally:
        lock.release()
