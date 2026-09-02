#!/usr/bin/env python3
"""Transactional native-store writer: cm local upsert/update/archive/forget/rebuild-index.

Project-local facts are not domain canonicals. LocalFactV1 is a distinct contract
(not canonical schema v3): secret check, index admission, and journaled fact+pointer
publication share the canonical writer's *transaction* path, not its codec.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from store_context import StoreContext, WriteRefused, assert_writable

# Placeholder [[wikilink]] targets that almost always mean "I wrote a format example".
_PLACEHOLDER_LINK_TARGETS = frozenset({"link", "name", "wikilink", "stem", "target"})

LOCAL_SCHEMA_VERSION = 1
LOCAL_RESERVED = (
    "local_schema_version", "name", "description", "scope", "status",
    "sensitivity", "content_modified", "last_observed_at",
)
LOCAL_RESERVED_SET = frozenset(LOCAL_RESERVED)
LOCAL_SENSITIVITY = ("public", "internal", "confidential")
LOCAL_STATUSES = ("active", "superseded", "expired")
REBUILD_CONFIRM = "rebuild-local-index"
MIGRATE_CONFIRM = "migrate-local-schema"


def _looks_secret_fn():
    from memory_status import _looks_secret
    return _looks_secret


def _utc_now() -> str:
    from datetime import datetime, timezone
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


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
    `[project-local]` when the fact is in-contract.
    """
    from memory_status import HOOK_TOKEN_WARN
    desc = (description or "").strip().strip('"')
    desc = " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f\[\]]", " ", desc).split())
    tag = "project-local" if (scope or "").strip().strip('"') in ("", "project-local") else ""
    suffix = f" [{tag}]" if tag else ""
    prefix = f"- [{stem}]({stem}.md) — "
    hook = _fit_hook(prefix, desc, suffix, HOOK_TOKEN_WARN)
    return prefix + hook + suffix


def _warn_fat_hook(ptr: str, stem: str, *, source_path: str = "") -> None:
    from sync_global import _fat_hook_warning
    lint = _fat_hook_warning(ptr, stem, source_kind="local",
                             source_path=source_path or (stem + ".md"))
    if lint:
        print(f"  {lint}", file=sys.stderr)


def _frontmatter_entries(text: str) -> list:
    """Opening-frontmatter (key, value) pairs in order. Last-wins is the caller's problem."""
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return []
    out: list = []
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            out.append((k.strip(), v.strip()))
    return out


def _duplicate_reserved(text: str) -> Optional[str]:
    seen: set = set()
    for k, _v in _frontmatter_entries(text):
        if k in LOCAL_RESERVED_SET:
            if k in seen:
                return f"duplicate reserved key {k!r}"
            seen.add(k)
    return None


def _split_body(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = re.search(r"^---\n.*?\n---\n?", text, re.S)
    if not m:
        return text
    return text[m.end():]


def _render_local(fm: dict, body: str) -> str:
    lines = ["---"]
    for k in LOCAL_RESERVED:
        if k in fm and fm[k] is not None:
            lines.append(f"{k}: {fm[k]}")
    for k, v in fm.items():
        if k in LOCAL_RESERVED_SET:
            continue
        if v is None:
            continue
        lines.append(f"{k}: {v}")
    lines.append("---")
    body = body if body.endswith("\n") else body + "\n"
    if body and not body.startswith("\n") and not body.startswith("---"):
        pass
    return "\n".join(lines) + "\n" + body.lstrip("\n")


def prepare_local_fact(stem: str, text: str, *, now: Optional[str] = None,
                       inject: bool = True) -> dict:
    """Normalize + validate LocalFactV1. Returns {ok, text, fm, error}."""
    from fact_schema import _real_rfc3339
    from identifiers import IdentifierRefused, validate_fact_stem
    from memory_status import _frontmatter
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e), "text": text, "fm": {}}
    if _looks_secret_fn()(text):
        return {"ok": False, "error": "secret-shaped content refused", "text": text, "fm": {}}
    dup = _duplicate_reserved(text)
    if dup:
        return {"ok": False, "error": dup, "text": text, "fm": {}}
    fm = dict(_frontmatter(text))
    desc = str(fm.get("description") or "").strip().strip('"')
    if not desc:
        return {"ok": False, "error": "description is required", "text": text, "fm": fm}
    name = str(fm.get("name") or "").strip()
    if name and name != stem:
        return {"ok": False, "error": f"name {name!r} does not match stem {stem!r}",
                "text": text, "fm": fm}
    scope = str(fm.get("scope") or "").strip().strip('"')
    if scope and scope != "project-local":
        return {"ok": False, "error": f"scope must be project-local, got {scope!r}",
                "text": text, "fm": fm}
    status = str(fm.get("status") or "").strip()
    if status and status not in LOCAL_STATUSES:
        return {"ok": False, "error": f"status must be {'|'.join(LOCAL_STATUSES)}",
                "text": text, "fm": fm}
    sens = str(fm.get("sensitivity") or "").strip().lower()
    if sens and sens not in LOCAL_SENSITIVITY:
        return {"ok": False, "error": f"sensitivity must be {'|'.join(LOCAL_SENSITIVITY)}",
                "text": text, "fm": fm}
    iso = now or _utc_now()
    if inject:
        fm["local_schema_version"] = str(LOCAL_SCHEMA_VERSION)
        fm["name"] = stem
        fm["description"] = desc
        fm["scope"] = "project-local"
        fm["status"] = status or "active"
        fm["sensitivity"] = sens or "internal"
        cm = str(fm.get("content_modified") or "").strip()
        lo = str(fm.get("last_observed_at") or "").strip()
        if cm and not _real_rfc3339(cm):
            return {"ok": False, "error": f"invalid content_modified {cm!r}",
                    "text": text, "fm": fm}
        if lo and not _real_rfc3339(lo):
            return {"ok": False, "error": f"invalid last_observed_at {lo!r}",
                    "text": text, "fm": fm}
        if not cm:
            fm["content_modified"] = iso
        if not lo:
            fm["last_observed_at"] = iso
        text = _render_local(fm, _split_body(text))
        fm = dict(_frontmatter(text))
    else:
        sv = str(fm.get("local_schema_version") or "").strip()
        if sv not in ("1", "v1"):
            return {"ok": False, "error": "missing local_schema_version: 1",
                    "text": text, "fm": fm}
        if str(fm.get("scope") or "").strip() != "project-local":
            return {"ok": False, "error": "scope must be project-local",
                    "text": text, "fm": fm}
        for ts_key in ("content_modified", "last_observed_at"):
            ts = str(fm.get(ts_key) or "").strip()
            if not _real_rfc3339(ts):
                return {"ok": False, "error": f"invalid {ts_key} {ts!r}",
                        "text": text, "fm": fm}
    return {"ok": True, "error": "", "text": text if text.endswith("\n") else text + "\n",
            "fm": fm}


def _validate_local(stem: str, text: str) -> Optional[str]:
    """Compatibility wrapper: error string or None. Injects LocalFactV1 defaults."""
    out = prepare_local_fact(stem, text, inject=True)
    return None if out.get("ok") else str(out.get("error") or "invalid local fact")


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


def _expected_from_snap(snap) -> dict:
    return {str(snap.path): snap.sha256}


def local_upsert(ctx: StoreContext, stem: str, text: str, *,
                 create_only: bool = False) -> dict:
    """Create or replace a native fact file and its MEMORY.md pointer."""
    from control_plane import ABSENT, read_snapshot, transact
    from identifiers import IdentifierRefused, validate_fact_stem
    from index_admission import apply_pointer, project_index
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    prepared = prepare_local_fact(stem, text, inject=True)
    if not prepared.get("ok"):
        return {"ok": False, "error": prepared.get("error") or "invalid local fact"}
    text = prepared["text"]
    lerr = _local_link_err(ctx, stem, text)
    if lerr:
        return {"ok": False, "error": lerr}
    dest = ctx.native_memory_dir / f"{stem}.md"
    idxp = ctx.native_memory_dir / "MEMORY.md"
    dest_snap = read_snapshot(dest)
    idx_snap = read_snapshot(idxp)
    if dest_snap.exists:
        from sync_global import _is_mirror
        cur = (dest_snap.data or b"").decode("utf-8", errors="replace")
        if _is_mirror(cur):
            return {"ok": False, "error":
                    "managed mirror; use cm resolve / demote, not cm local"}
        if create_only:
            return {"ok": False, "error": "local fact already exists"}
    elif create_only:
        pass
    fm = prepared["fm"]
    ptr = _pointer(stem, str(fm.get("description") or stem), "project-local")
    _warn_fat_hook(ptr, stem, source_path=str(dest))
    expected = {}
    expected.update(_expected_from_snap(dest_snap))
    expected.update(_expected_from_snap(idx_snap))

    def mutate(conn, temps):
        del conn
        if idx_snap.exists:
            idx = (idx_snap.data or b"").decode("utf-8", errors="replace")
        else:
            idx = "# Memory Index\n\n"
        future = apply_pointer(idx, ptr, stem)
        adm = project_index(future)
        if not adm["admitted"]:
            raise WriteRefused("index admission refused: " + adm["reason"])
        temps[str(dest)] = text
        temps[str(idxp)] = future if future.endswith("\n") else future + "\n"
        modes = {}
        extra = {}
        if not dest_snap.exists:
            modes[str(dest)] = "create"
            extra[str(dest)] = ABSENT
        if not idx_snap.exists:
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
    from control_plane import read_snapshot, transact
    from identifiers import IdentifierRefused, validate_fact_stem
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    dest = ctx.native_memory_dir / f"{stem}.md"
    idxp = ctx.native_memory_dir / "MEMORY.md"
    dest_snap = read_snapshot(dest)
    idx_snap = read_snapshot(idxp)
    if not dest_snap.exists:
        return {"ok": False, "error": "no such local fact"}
    from sync_global import _is_mirror
    if _is_mirror((dest_snap.data or b"").decode("utf-8", errors="replace")):
        return {"ok": False, "error":
                "managed mirror; use cm resolve / demote, not cm local"}
    expected = {}
    expected.update(_expected_from_snap(dest_snap))
    expected.update(_expected_from_snap(idx_snap))

    def mutate(conn, temps):
        del conn
        if idx_snap.exists:
            idx = (idx_snap.data or b"").decode("utf-8", errors="replace")
        else:
            idx = "# Memory Index\n"
        idx = "\n".join(ln for ln in idx.splitlines() if f"]({stem}.md)" not in ln)
        temps[str(idxp)] = idx.rstrip() + "\n"
        extra = {}
        modes = {}
        if not idx_snap.exists:
            from control_plane import ABSENT as _A
            modes[str(idxp)] = "create"
            extra[str(idxp)] = _A
        return {"stem": stem, "deletes": [{"path": str(dest),
                                           "preimage": dest_snap.sha256}],
                "dest_modes": modes, "expected_revisions": extra}

    try:
        out = transact(ctx, "local-forget", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id")}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def local_archive(ctx: StoreContext, stem: str) -> dict:
    """Move the always-loaded pointer MEMORY.md → SHIPPED.md; body stays."""
    from control_plane import ABSENT, read_snapshot, transact
    from identifiers import IdentifierRefused, validate_fact_stem
    from index_admission import apply_pointer, archive_index, project_index
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    dest = ctx.native_memory_dir / f"{stem}.md"
    idxp = ctx.native_memory_dir / "MEMORY.md"
    arch = ctx.native_memory_dir / "SHIPPED.md"
    dest_snap = read_snapshot(dest)
    if not dest_snap.exists:
        return {"ok": False, "error": "no such local fact"}
    from sync_global import _is_mirror
    body = (dest_snap.data or b"").decode("utf-8", errors="replace")
    if _is_mirror(body):
        return {"ok": False, "error":
                "managed mirror; use cm resolve / demote, not cm local"}
    prepared = prepare_local_fact(stem, body, inject=True)
    if not prepared.get("ok"):
        return {"ok": False, "error": prepared.get("error") or "invalid local fact"}
    fm = prepared["fm"]
    ptr = _pointer(stem, str(fm.get("description") or stem), "project-local")
    _warn_fat_hook(ptr, stem, source_path=str(dest))
    idx_snap = read_snapshot(idxp)
    arch_snap = read_snapshot(arch)
    expected = {}
    expected.update(_expected_from_snap(dest_snap))
    expected.update(_expected_from_snap(idx_snap))
    expected.update(_expected_from_snap(arch_snap))

    def mutate(conn, temps):
        del conn
        if idx_snap.exists:
            idx = (idx_snap.data or b"").decode("utf-8", errors="replace")
        else:
            idx = "# Memory Index\n"
        idx = "\n".join(ln for ln in idx.splitlines() if f"]({stem}.md)" not in ln)
        temps[str(idxp)] = idx.rstrip() + "\n"
        idx_adm = project_index(temps[str(idxp)])
        if not idx_adm["admitted"]:
            raise WriteRefused("index admission refused: " + idx_adm["reason"])
        if arch_snap.exists:
            at = (arch_snap.data or b"").decode("utf-8", errors="replace")
        else:
            at = "# Shipped\n\n"
        future = apply_pointer(at, ptr, stem)
        adm = archive_index(future)
        if not adm["admitted"]:
            raise WriteRefused("archive index admission refused: " + adm["reason"])
        temps[str(arch)] = future if future.endswith("\n") else future + "\n"
        modes = {}
        extra = {}
        if not arch_snap.exists:
            modes[str(arch)] = "create"
            extra[str(arch)] = ABSENT
        if not idx_snap.exists:
            modes[str(idxp)] = "create"
            extra[str(idxp)] = ABSENT
        return {"stem": stem, "dest_modes": modes, "expected_revisions": extra,
                "source_sha256": dest_snap.sha256}

    try:
        out = transact(ctx, "local-archive", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id")}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def _rebuild_plan(ctx: StoreContext) -> dict:
    """Scan native facts. Never writes. Pins every source hash."""
    from control_plane import read_snapshot
    from identifiers import IdentifierRefused, validate_fact_stem
    from memory_status import _frontmatter
    from sync_global import _is_mirror, _pointer_line
    native = ctx.native_memory_dir
    idxp = native / "MEMORY.md"
    idx_snap = read_snapshot(idxp)
    included: list = []
    invalid: list = []
    unreadable: list = []
    mirrors: list = []
    snaps: dict = {str(idxp): idx_snap}
    existing_ptrs: set = set()
    if idx_snap.exists:
        idx_text = (idx_snap.data or b"").decode("utf-8", errors="replace")
        for ln in idx_text.splitlines():
            m = re.search(r"\]\(([^)]+)\.md\)", ln)
            if m:
                existing_ptrs.add(m.group(1))
    lines = ["# Memory Index", ""]
    if native.is_dir():
        for f in sorted(native.glob("*.md")):
            if f.name in ("MEMORY.md", "SHIPPED.md") or "/quarantine/" in str(f):
                continue
            try:
                snap = read_snapshot(f)
            except WriteRefused as e:
                unreadable.append({"stem": f.stem, "error": str(e)})
                continue
            snaps[str(f)] = snap
            if not snap.exists:
                continue
            try:
                text = (snap.data or b"").decode("utf-8")
            except UnicodeDecodeError as e:
                unreadable.append({"stem": f.stem, "error": str(e)})
                continue
            try:
                validate_fact_stem(f.stem)
            except IdentifierRefused as e:
                invalid.append({"stem": f.stem, "error": str(e),
                                "sha256": snap.sha256})
                continue
            if _is_mirror(text):
                fm = _frontmatter(text)
                ptr = _pointer_line(f.stem, fm)
                _warn_fat_hook(ptr, f.stem, source_path=str(f))
                lines.append(ptr)
                mirrors.append({"stem": f.stem, "sha256": snap.sha256})
                continue
            prepared = prepare_local_fact(f.stem, text, inject=True)
            if not prepared.get("ok"):
                invalid.append({"stem": f.stem,
                                "error": prepared.get("error") or "invalid",
                                "sha256": snap.sha256})
                continue
            fm = prepared["fm"]
            ptr = _pointer(f.stem, str(fm.get("description") or f.stem),
                           "project-local")
            _warn_fat_hook(ptr, f.stem, source_path=str(f))
            lines.append(ptr)
            included.append({"stem": f.stem, "sha256": snap.sha256})
    future = "\n".join(lines) + "\n"
    planned = {row["stem"] for row in included} | {row["stem"] for row in mirrors}
    would_remove = sorted(existing_ptrs - planned)
    return {
        "included": included,
        "invalid": invalid,
        "unreadable": unreadable,
        "mirrors": mirrors,
        "would_remove_existing_pointers": would_remove,
        "future": future,
        "snaps": snaps,
        "idx_snap": idx_snap,
    }


def local_rebuild_index(ctx: StoreContext, *, apply: bool = False,
                        skip_invalid: bool = False, confirm: str = "") -> dict:
    """Rebuild MEMORY.md from native fact files (skip quarantine / SHIPPED).

    Default is plan-only. `--apply` requires `--confirm rebuild-local-index`.
    Any invalid/unreadable fact fails closed unless skip_invalid=True.
    """
    from control_plane import ABSENT, transact
    from index_admission import project_index
    assert_writable(ctx)
    plan = _rebuild_plan(ctx)
    report = {k: plan[k] for k in (
        "included", "invalid", "unreadable", "mirrors",
        "would_remove_existing_pointers")}
    blocked = bool(plan["invalid"] or plan["unreadable"]) and not skip_invalid
    if not apply:
        return {"ok": not blocked, "plan": True, "error":
                ("invalid or unreadable facts; pass --skip-invalid to omit them"
                 if blocked else ""),
                **report}
    if confirm != REBUILD_CONFIRM:
        return {"ok": False, "error":
                f"rebuild-index --apply requires --confirm {REBUILD_CONFIRM}",
                **report}
    if blocked:
        return {"ok": False, "error":
                "invalid or unreadable facts; index unchanged",
                **report}
    omitted = []
    if skip_invalid:
        omitted = [r["stem"] for r in plan["invalid"] + plan["unreadable"]]
    native = ctx.native_memory_dir
    idxp = native / "MEMORY.md"
    future = plan["future"]
    adm = project_index(future)
    if not adm["admitted"]:
        return {"ok": False, "error": "rebuild admission refused: " + adm["reason"],
                **report}
    idx_snap = plan["idx_snap"]
    expected = {str(idxp): idx_snap.sha256}
    for p, snap in plan["snaps"].items():
        expected[p] = snap.sha256

    def mutate(conn, temps):
        del conn
        temps[str(idxp)] = future
        modes = {}
        extra = {}
        if not idx_snap.exists:
            modes[str(idxp)] = "create"
            extra[str(idxp)] = ABSENT
        return {"rebuilt": True, "dest_modes": modes, "expected_revisions": extra,
                "omitted": omitted}

    try:
        out = transact(ctx, "local-rebuild-index", {"stem": "*"}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id"),
                "omitted": omitted, **report}
    except WriteRefused as e:
        return {"ok": False, "error": str(e), **report}


def local_migrate_schema(ctx: StoreContext, *, apply: bool = False,
                         confirm: str = "") -> dict:
    """Inject LocalFactV1 fields into legacy local facts. Plan-first."""
    from control_plane import read_snapshot, transact
    assert_writable(ctx)
    native = ctx.native_memory_dir
    planned: list = []
    invalid: list = []
    expected: dict = {}
    bodies: dict = {}
    if native.is_dir():
        from sync_global import _is_mirror
        for f in sorted(native.glob("*.md")):
            if f.name in ("MEMORY.md", "SHIPPED.md"):
                continue
            snap = read_snapshot(f)
            if not snap.exists:
                continue
            text = (snap.data or b"").decode("utf-8", errors="replace")
            if _is_mirror(text):
                continue
            prepared = prepare_local_fact(f.stem, text, inject=True)
            if not prepared.get("ok"):
                invalid.append({"stem": f.stem, "error": prepared.get("error")})
                continue
            new = prepared["text"]
            if new.encode("utf-8") == (snap.data or b""):
                continue
            planned.append({"stem": f.stem, "sha256": snap.sha256})
            expected[str(f)] = snap.sha256
            bodies[str(f)] = new
    report = {"planned": planned, "invalid": invalid}
    if not apply:
        return {"ok": not invalid, "plan": True, **report,
                "error": ("invalid facts; migrate refused" if invalid else "")}
    if confirm != MIGRATE_CONFIRM:
        return {"ok": False, "error":
                f"migrate-schema --apply requires --confirm {MIGRATE_CONFIRM}",
                **report}
    if invalid:
        return {"ok": False, "error": "invalid facts; migrate refused", **report}
    if not bodies:
        return {"ok": True, "migrated": 0, **report}

    def mutate(conn, temps):
        del conn
        temps.update(bodies)
        return {"migrated": len(bodies)}

    try:
        out = transact(ctx, "local-migrate-schema", {"stem": "*"}, mutate,
                       expected_revisions=expected)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id"),
                **report}
    except WriteRefused as e:
        return {"ok": False, "error": str(e), **report}
