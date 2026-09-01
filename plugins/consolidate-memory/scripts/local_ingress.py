#!/usr/bin/env python3
"""Transactional native-store writer: cm local upsert/update/archive/forget/rebuild-index.

Project-local facts are not domain canonicals. Same codec, secret check, index
admission, and journaled fact+pointer publication as the canonical writer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from store_context import StoreContext, WriteRefused, assert_writable


def _looks_secret_fn():
    from memory_status import _looks_secret
    return _looks_secret


def _pointer(stem: str, description: str) -> str:
    hook = (description or stem).strip() or stem
    return f"- [{stem}]({stem}.md) — {hook}"


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
            return f"dangling link [[{target}]]"
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
    if create_only and dest.exists():
        return {"ok": False, "error": "local fact already exists"}
    idxp = ctx.native_memory_dir / "MEMORY.md"
    fm = _frontmatter(text)
    ptr = _pointer(stem, str(fm.get("description") or stem))
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
    idxp = ctx.native_memory_dir / "MEMORY.md"
    arch = ctx.native_memory_dir / "SHIPPED.md"
    text = dest.read_text(encoding="utf-8", errors="replace")
    fm = _frontmatter(text)
    ptr = _pointer(stem, str(fm.get("description") or stem))
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
                    fm = _frontmatter(text)
                    lines.append(_pointer(f.stem, str(fm.get("description") or f.stem)))
                    continue
                err = _validate_local(f.stem, text)
                if err:
                    continue
                fm = _frontmatter(text)
                lines.append(_pointer(f.stem, str(fm.get("description") or f.stem)))
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
