#!/usr/bin/env python3
"""Transactional native-store writer: cm local upsert/update/archive/forget/rebuild-index.

Project-local facts are not domain canonicals. Same codec, secret check, index
admission, and journaled fact+pointer publication as the canonical writer.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from store_context import StoreContext, WriteRefused, assert_writable

# Placeholder [[wikilink]] targets that almost always mean "I wrote a format example".
_PLACEHOLDER_LINK_TARGETS = frozenset({"link", "name", "wikilink", "stem", "target"})


def _looks_secret_fn():
    from memory_status import _looks_secret
    return _looks_secret


def _fit_hook(prefix: str, desc: str, suffix: str, budget: int) -> str:
    """Word-boundary truncate so est_tokens(prefix + hook + suffix) ≤ budget."""
    from memory_status import est_tokens
    if est_tokens(prefix + desc + suffix) <= budget:
        return desc
    lo, hi = 0, len(desc)
    best_n = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if est_tokens(prefix + desc[:mid] + "…" + suffix) <= budget:
            best_n = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if best_n <= 0:
        return "…"
    chunk = desc[:best_n].rstrip()
    sp = max(chunk.rfind(" "), chunk.rfind("\t"))
    if sp >= 1:
        chunk = chunk[:sp].rstrip()
    if not chunk:
        chunk = desc[:best_n].rstrip()
    return chunk + "…"


def _pointer(stem: str, description: str, scope: str = "") -> str:
    """Always-loaded index line for a project-authored local fact.

    Not `_pointer_line`: that constructor is the global injection sanitizer
    (strips `[]()` and 88-char truncates, mid-token). Locals keep `()` so a
    recall cue like `(OPEN: 1.0 HOLD)` survives, strip `[]` (spoof `](url)`),
    word-boundary truncate so the WHOLE line is ≤ HOOK_TOKEN_WARN, and attach
    the frontmatter scope tag when present.
    """
    from memory_status import HOOK_TOKEN_WARN
    desc = (description or "").strip().strip('"')
    desc = " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f\[\]]", " ", desc).split())
    suffix = f" [{scope}]" if scope else ""
    prefix = f"- [{stem}]({stem}.md) — "
    hook = _fit_hook(prefix, desc, suffix, HOOK_TOKEN_WARN)
    return prefix + hook + suffix


def _warn_fat_hook(ptr: str, stem: str) -> None:
    from sync_global import _fat_hook_warning
    lint = _fat_hook_warning(ptr, stem)
    if lint:
        print(f"  {lint}", file=sys.stderr)


def _validate_local(stem: str, text: str) -> Optional[str]:
    from identifiers import IdentifierRefused, validate_fact_stem
    from memory_status import _frontmatter
    try:
        validate_fact_stem(stem)
    except IdentifierRefused as e:
        return str(e)
    if _looks_secret_fn()(text):
        return "secret-shaped content refused"
    fm = _frontmatter(text)
    if not str(fm.get("description") or "").strip():
        return "description is required"
    name = str(fm.get("name") or "").strip()
    if name and name != stem:
        return f"name {name!r} does not match stem {stem!r}"
    return None


def _local_link_err(ctx: StoreContext, stem: str, text: str) -> Optional[str]:
    from canonical_ingress import link_targets
    native = ctx.native_memory_dir
    for target in link_targets(text):
        if target == stem:
            continue
        if not (native / f"{target}.md").is_file():
            err = f"dangling link [[{target}]]"
            if target.lower() in _PLACEHOLDER_LINK_TARGETS:
                err += " — format examples belong in backticks (`[[link]]`)"
            return err
    return None


def local_upsert(ctx: StoreContext, stem: str, text: str, *,
                 create_only: bool = False) -> dict:
    """Create or replace a native fact file and its MEMORY.md pointer."""
    from control_plane import ABSENT, transact
    from identifiers import IdentifierRefused, validate_fact_stem
    from index_admission import apply_pointer, project_index
    from memory_status import _frontmatter
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    text = text if text.endswith("\n") else text + "\n"
    err = _validate_local(stem, text)
    if err:
        return {"ok": False, "error": err}
    lerr = _local_link_err(ctx, stem, text)
    if lerr:
        return {"ok": False, "error": lerr}
    dest = ctx.native_memory_dir / f"{stem}.md"
    if dest.exists():
        from sync_global import _is_mirror
        try:
            cur = dest.read_text(encoding="utf-8", errors="replace")
        except OSError:
            cur = ""
        if _is_mirror(cur):
            return {"ok": False, "error":
                    "managed mirror; use cm resolve / demote, not cm local"}
    if create_only and dest.exists():
        return {"ok": False, "error": "local fact already exists"}
    idxp = ctx.native_memory_dir / "MEMORY.md"
    fm = _frontmatter(text)
    ptr = _pointer(stem, str(fm.get("description") or stem), str(fm.get("scope") or "").strip().strip('"'))
    _warn_fat_hook(ptr, stem)
    expected = {}
    from control_plane import _file_hash
    if dest.exists():
        h = _file_hash(dest)
        if h:
            expected[str(dest)] = h
    elif create_only:
        expected[str(dest)] = ABSENT
    if idxp.exists():
        h = _file_hash(idxp)
        if h:
            expected[str(idxp)] = h

    def mutate(conn, temps):
        del conn
        idx = idxp.read_text(encoding="utf-8", errors="replace") if idxp.exists() else (
            "# Memory Index\n\n")
        future = apply_pointer(idx, ptr, stem)
        adm = project_index(future)
        if not adm["admitted"]:
            raise WriteRefused("index admission refused: " + adm["reason"])
        temps[str(dest)] = text
        temps[str(idxp)] = future if future.endswith("\n") else future + "\n"
        modes = {}
        extra = {}
        if not dest.exists():
            modes[str(dest)] = "create"
            extra[str(dest)] = ABSENT
        if not idxp.exists():
            modes[str(idxp)] = "create"
            extra[str(idxp)] = ABSENT
        return {"stem": stem, "dest_modes": modes, "expected_revisions": extra}

    try:
        out = transact(ctx, "local-upsert", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id")}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def local_forget(ctx: StoreContext, stem: str) -> dict:
    from control_plane import transact, _file_hash
    from identifiers import IdentifierRefused, validate_fact_stem
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    dest = ctx.native_memory_dir / f"{stem}.md"
    idxp = ctx.native_memory_dir / "MEMORY.md"
    if not dest.exists():
        return {"ok": False, "error": "no such local fact"}
    from sync_global import _is_mirror
    try:
        if _is_mirror(dest.read_text(encoding="utf-8", errors="replace")):
            return {"ok": False, "error":
                    "managed mirror; use cm resolve / demote, not cm local"}
    except OSError:
        pass
    expected = {}
    h = _file_hash(dest)
    if h:
        expected[str(dest)] = h
    if idxp.exists():
        h = _file_hash(idxp)
        if h:
            expected[str(idxp)] = h

    def mutate(conn, temps):
        del conn
        idx = idxp.read_text(encoding="utf-8", errors="replace") if idxp.exists() else (
            "# Memory Index\n")
        idx = "\n".join(ln for ln in idx.splitlines() if f"]({stem}.md)" not in ln)
        temps[str(idxp)] = idx.rstrip() + "\n"
        return {"stem": stem, "deletes": [{"path": str(dest),
                                           "preimage": expected.get(str(dest), "")}]}

    try:
        out = transact(ctx, "local-forget", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {})}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def local_archive(ctx: StoreContext, stem: str) -> dict:
    """Move the always-loaded pointer MEMORY.md → SHIPPED.md; body stays."""
    from control_plane import transact, _file_hash
    from identifiers import IdentifierRefused, validate_fact_stem
    from index_admission import apply_pointer, project_index
    from memory_status import _frontmatter
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    dest = ctx.native_memory_dir / f"{stem}.md"
    if not dest.exists():
        return {"ok": False, "error": "no such local fact"}
    from sync_global import _is_mirror
    try:
        if _is_mirror(dest.read_text(encoding="utf-8", errors="replace")):
            return {"ok": False, "error":
                    "managed mirror; use cm resolve / demote, not cm local"}
    except OSError:
        pass
    idxp = ctx.native_memory_dir / "MEMORY.md"
    arch = ctx.native_memory_dir / "SHIPPED.md"
    text = dest.read_text(encoding="utf-8", errors="replace")
    fm = _frontmatter(text)
    ptr = _pointer(stem, str(fm.get("description") or stem), str(fm.get("scope") or "").strip().strip('"'))
    _warn_fat_hook(ptr, stem)
    expected = {}
    for p in (idxp, arch):
        if p.exists():
            h = _file_hash(p)
            if h:
                expected[str(p)] = h

    def mutate(conn, temps):
        del conn
        idx = idxp.read_text(encoding="utf-8", errors="replace") if idxp.exists() else (
            "# Memory Index\n")
        idx = "\n".join(ln for ln in idx.splitlines() if f"]({stem}.md)" not in ln)
        temps[str(idxp)] = idx.rstrip() + "\n"
        at = arch.read_text(encoding="utf-8", errors="replace") if arch.exists() else (
            "# Shipped\n\n")
        future = apply_pointer(at, ptr, stem)
        adm = project_index(future)
        if not adm["admitted"]:
            raise WriteRefused("archive index admission refused: " + adm["reason"])
        temps[str(arch)] = future if future.endswith("\n") else future + "\n"
        modes = {}
        extra = {}
        if not arch.exists():
            from control_plane import ABSENT
            modes[str(arch)] = "create"
            extra[str(arch)] = ABSENT
        return {"stem": stem, "dest_modes": modes, "expected_revisions": extra}

    try:
        out = transact(ctx, "local-archive", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {})}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def local_rebuild_index(ctx: StoreContext) -> dict:
    """Rebuild MEMORY.md from native fact files (skip quarantine / SHIPPED)."""
    from control_plane import ABSENT, transact, _file_hash
    from index_admission import project_index
    from memory_status import _frontmatter
    from sync_global import _is_mirror
    assert_writable(ctx)
    native = ctx.native_memory_dir
    idxp = native / "MEMORY.md"
    expected = {}
    if idxp.exists():
        h = _file_hash(idxp)
        if h:
            expected[str(idxp)] = h

    def mutate(conn, temps):
        del conn
        lines = ["# Memory Index", ""]
        if native.is_dir():
            for f in sorted(native.glob("*.md")):
                if f.name in ("MEMORY.md", "SHIPPED.md") or "/quarantine/" in str(f):
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if _is_mirror(text):
                    from sync_global import _pointer_line
                    fm = _frontmatter(text)
                    ptr = _pointer_line(f.stem, fm)
                    _warn_fat_hook(ptr, f.stem)
                    lines.append(ptr)
                    continue
                err = _validate_local(f.stem, text)
                if err:
                    continue
                fm = _frontmatter(text)
                ptr = _pointer(f.stem, str(fm.get("description") or f.stem),
                               str(fm.get("scope") or "").strip().strip('"'))
                _warn_fat_hook(ptr, f.stem)
                lines.append(ptr)
        future = "\n".join(lines) + "\n"
        adm = project_index(future)
        if not adm["admitted"]:
            raise WriteRefused("rebuild admission refused: " + adm["reason"])
        temps[str(idxp)] = future
        modes = {}
        extra = {}
        if not idxp.exists():
            modes[str(idxp)] = "create"
            extra[str(idxp)] = ABSENT
        return {"rebuilt": True, "dest_modes": modes, "expected_revisions": extra}

    try:
        out = transact(ctx, "local-rebuild-index", {"stem": "*"}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {})}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}
