#!/usr/bin/env python3
"""Maintainer CLI for StoreContext, conflicts, canonical ingress, migrate, retention."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# scripts/ is sys.path[0] when exec'd.
from store_context import (StoreContext, WriteRefused, assert_writable, doctor_dict,
                           doctor_report, resolve_store)


def _lookup_canonical_text(ctx: StoreContext, fm: dict, fname: str) -> Optional[str]:
    """Named-domain canonical only (never leftover ~/.claude/memory)."""
    from identifiers import IdentifierRefused, safe_child, validate_domain_id
    from sync_global import _safe_read_text
    droot = ctx.config_root / "consolidate-memory" / "domains"
    cdom = str(fm.get("canonical_domain") or fm.get("domain") or "").strip()
    if cdom and cdom != "unknown":
        try:
            cp = safe_child(droot, validate_domain_id(cdom)) / "facts" / fname
            text = _safe_read_text(cp)
            if text is not None:
                return text
        except IdentifierRefused:
            pass
    return None


def _mirror_plan_for_dest(ctx: StoreContext, dest_domain: str, conn=None) -> dict:
    """Inventory managed mirrors: clean deletes vs locally-edited quarantine.

    Unenroll (dest unknown) plans every managed mirror. Local edits are never
    deleted — they land under native/quarantine/. When `conn` is provided the
    holder table is read from that connection (under lock).
    """
    from control_plane import (connect_if_exists, db_path, holder_base_revision,
                               stable_fact_id)
    from memory_status import _frontmatter
    from mirror_conflict import body_hash as _bh, classify_mirror
    from sync_global import _is_mirror, _safe_read_text
    native = ctx.native_memory_dir
    plan: dict = {"deletes": [], "quarantine": [], "holders": [], "source_hashes": {}}
    if not native.is_dir():
        return plan
    own = conn is None
    _hconn = conn if conn is not None else connect_if_exists(db_path(ctx))
    try:
        for f in sorted(native.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                continue
            except OSError:
                from store_context import WriteRefused as _WRPlan
                raise _WRPlan(f"unreadable native pointer: {f.name}")
            if not _is_mirror(text):
                continue
            fm = _frontmatter(text)
            fid = str(fm.get("canonical_fact_id") or "").strip()
            cdom = str(fm.get("canonical_domain") or fm.get("domain") or "").strip()
            if not fid:
                fid = stable_fact_id(cdom or ctx.domain_id or "unknown", f.stem)
            # Keep only if the DEST domain has a canonical on disk and
            # three-way says in-sync. Mirror `domain:` is locally editable
            # and is not an admission grant (ADR 012).
            dest_canon_text = None
            if dest_domain != "unknown":
                from identifiers import IdentifierRefused, safe_child, validate_domain_id
                droot = ctx.config_root / "consolidate-memory" / "domains"
                try:
                    dpath = (safe_child(droot, validate_domain_id(dest_domain))
                             / "facts" / f.name)
                    dest_canon_text = _safe_read_text(dpath)
                except IdentifierRefused:
                    dest_canon_text = None
                if dest_canon_text is not None:
                    _hb_keep = (holder_base_revision(_hconn, fid, ctx.project_id)
                                if _hconn is not None else None)
                    _v3k = bool(fm.get("canonical_fact_id") or fm.get("schema_version"))
                    _dec_k = classify_mirror(text, dest_canon_text,
                                             base_revision=_hb_keep,
                                             allow_legacy_fallback=not _v3k)
                    if _dec_k["action"] not in (
                            "stop-local", "conflict", "quarantine") and _bh(
                                text) == _bh(dest_canon_text):
                        continue
            plan["holders"].append({"op": "holder_delete", "fact_id": fid,
                                    "project_id": ctx.project_id})
            plan["source_hashes"][str(f)] = hashlib.sha256(
                text.encode("utf-8")).hexdigest()
            canon_text = dest_canon_text if dest_domain != "unknown" else _lookup_canonical_text(ctx, fm, f.name)
            v3 = bool(fm.get("canonical_fact_id") or fm.get("schema_version"))
            local_edit = False
            if canon_text is None:
                local_edit = True
            else:
                _hb = (holder_base_revision(_hconn, fid, ctx.project_id)
                       if _hconn is not None else None)
                dec = classify_mirror(text, canon_text, base_revision=_hb,
                                      allow_legacy_fallback=not v3)
                local_edit = dec["action"] in ("stop-local", "conflict", "quarantine")
                if not local_edit and _bh(text) != _bh(canon_text):
                    local_edit = True
            if local_edit:
                plan["quarantine"].append((str(f), text))
            else:
                plan["deletes"].append(str(f))
    finally:
        if own and _hconn is not None:
            _hconn.close()
    return plan


def _quarantine_dest(qdir: Path, stem: str, temps: dict) -> Path:
    """Collision-safe quarantine path: never overwrite an existing copy."""
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = qdir / f"{stem}.{ts}.md"
    n = 0
    while dest.exists() or str(dest) in temps:
        n += 1
        dest = qdir / f"{stem}.{ts}.{n}.md"
    return dest


def _stage_revoke_plan(ctx: StoreContext, dest_domain: str, conn, temps: dict) -> dict:
    """Apply a classify-under-lock revoke plan into temps/deletes (no transact)."""
    from sync_global import _safe_read_text
    native = ctx.native_memory_dir
    idxp = native / "MEMORY.md"
    qdir = native / "quarantine"
    plan = _mirror_plan_for_dest(ctx, dest_domain, conn=conn)
    doomed_names = [Path(p).name for p in plan["deletes"]]
    doomed_names += [Path(p).name for p, _t in plan["quarantine"]]
    idx = _safe_read_text(idxp) or ""
    deletes = list(plan["deletes"])
    dest_modes: dict = {}
    if plan["quarantine"]:
        qdir.mkdir(parents=True, exist_ok=True)
    for path_s, body in plan["quarantine"]:
        qdest = _quarantine_dest(qdir, Path(path_s).stem, temps)
        temps[str(qdest)] = body if body.endswith("\n") else body + "\n"
        dest_modes[str(qdest)] = "create"
        deletes.append(path_s)
    for name in doomed_names:
        idx = "\n".join(ln for ln in idx.splitlines() if f"]({name})" not in ln)
    if doomed_names:
        temps[str(idxp)] = (idx.rstrip() + "\n") if idx.strip() else "# Memory Index\n"
    ops = list(plan["holders"])
    for op in plan["holders"]:
        conn.execute(
            "DELETE FROM holders WHERE fact_id=? AND project_id=?",
            (op["fact_id"], op["project_id"]))
    return {"deletes": deletes, "dest_modes": dest_modes, "registry_ops": ops,
            "expected_revisions": plan.get("source_hashes") or {},
            "revoked": len(deletes), "quarantined": len(plan["quarantine"])}


def _revoke_unadmitted_mirrors(ctx: StoreContext, dest_domain: str,
                               extra_registry_ops: Optional[list] = None,
                               extra_domains: Optional[list] = None,
                               prepare=None) -> int:
    """Journal v3 revoke. Classify UNDER the lock (ADR 012). Returns n files."""
    from control_plane import transact
    native = ctx.native_memory_dir
    if not native.is_dir() and not extra_registry_ops and prepare is None:
        return 0

    def mutate(conn, temps):
        if prepare is not None:
            prepare(conn)
        staged = _stage_revoke_plan(ctx, dest_domain, conn, temps)
        ops = list(staged["registry_ops"]) + list(extra_registry_ops or [])
        return {"deletes": staged["deletes"], "revoked": staged["revoked"],
                "quarantined": staged["quarantined"],
                "registry_ops": ops, "dest_modes": staged["dest_modes"],
                "expected_revisions": staged["expected_revisions"]}

    out = transact(ctx, "domain-transition",
                   {"dest": dest_domain}, mutate,
                   extra_domains=extra_domains)
    return int((out.get("result") or {}).get("revoked") or 0)


def _enrolled_rows(conn, domain_id: Optional[str] = None) -> list:
    q = ("SELECT project_id, display_name, current_root, git_common_dir, "
         "remote_fingerprint, profile_id, domain_id, native_memory_dir, "
         "session_dir, status FROM projects WHERE status='enrolled'")
    args: tuple = ()
    if domain_id:
        q += " AND domain_id=?"
        args = (domain_id,)
    return list(conn.execute(q, args).fetchall())


def _canonical_and_ops_deletes(ctx: StoreContext, conn, domain_id: str,
                               facts_dir: Path) -> dict:
    from retention import operational_dir, _ops_slot
    deletes: list = []
    expected: dict = {}
    ops: list = []
    n_ops = 0
    if facts_dir.is_dir():
        for f in sorted(facts_dir.glob("*.md")):
            h = _sha256_file(f)
            if f.exists() and not h:
                raise WriteRefused("cannot hash purge target: " + str(f))
            deletes.append({"path": str(f), "preimage": h})
            if h:
                expected[str(f)] = h
    fids = [str(r["fact_id"]) for r in conn.execute(
        "SELECT fact_id FROM facts WHERE domain_id=?", (domain_id,)).fetchall()]
    for fid in fids:
        ops.append({"op": "fact_delete", "fact_id": fid})
        ops.append({"op": "holder_delete", "fact_id": fid, "project_id": "*"})
    ops.append({"op": "tombstone_delete", "domain_id": domain_id})
    for r in conn.execute(
            "SELECT project_id, native_memory_dir FROM projects WHERE domain_id=?",
            (domain_id,)).fetchall():
        native = Path(r["native_memory_dir"]) if r["native_memory_dir"] else None
        dirs = [operational_dir(ctx.plugin_data_dir, r["project_id"])]
        if native is not None:
            slot = _ops_slot(native)
            if slot and slot != r["project_id"]:
                dirs.append(operational_dir(ctx.plugin_data_dir, slot))
        for d in dirs:
            if not d.is_dir():
                continue
            for f in sorted(p for p in d.rglob("*") if p.is_file()):
                h = _sha256_file(f)
                if f.exists() and not h:
                    raise WriteRefused("cannot hash ops file: " + str(f))
                deletes.append({"path": str(f), "preimage": h})
                if h:
                    expected[str(f)] = h
                n_ops += 1
    return {"deletes": deletes, "expected_revisions": expected,
            "registry_ops": ops, "purged_ops": n_ops}


def _rmtree_empty_domain_dir(facts_dir: Path, domain_id: str) -> int:
    n = 0
    if facts_dir.is_dir():
        leftover = [p for p in facts_dir.rglob("*") if p.is_file()]
        n += len(leftover)
        parent = facts_dir.parent
        if parent.name == domain_id and not leftover:
            import shutil
            try:
                shutil.rmtree(parent)
            except OSError:
                pass
    return n


def _fleet_purge_domain(ctx: StoreContext, domain_id: str, facts_dir: Path,
                        rows: list) -> dict:
    """One transact: revoke every enrolled native, then delete canonicals (P0-9)."""
    from control_plane import transact
    from store_context import store_context_from_registry
    from sync_global import _is_mirror, _safe_read_text
    from memory_status import _frontmatter
    pids = [str(r["project_id"]) for r in rows]
    if ctx.project_id not in pids:
        pids.append(ctx.project_id)

    def mutate(conn, temps):
        deletes: list = []
        expected: dict = {}
        dest_modes: dict = {}
        ops: list = []
        revoked = 0
        for r in rows:
            pid = str(r["project_id"])
            native_s = str(r["native_memory_dir"] or "").strip()
            root_s = str(r["current_root"] or "").strip()
            if not native_s and not root_s:
                raise WriteRefused(
                    f"cannot revoke project {pid}: missing current_root and "
                    "native_memory_dir")
            pctx = store_context_from_registry(r, template=ctx)
            staged = _stage_revoke_plan(pctx, "unknown", conn, temps)
            deletes.extend(staged["deletes"])
            dest_modes.update(staged["dest_modes"])
            expected.update(staged["expected_revisions"])
            ops.extend(staged["registry_ops"])
            ops.append({"op": "project_domain_change", "project_id": pid,
                        "domain_id": "unknown", "status": "inactive"})
            revoked += int(staged["revoked"])
            native = pctx.native_memory_dir
            doomed = {str(d) for d in staged["deletes"]}
            if native.is_dir():
                leftover = []
                for f in native.glob("*.md"):
                    if f.name == "MEMORY.md":
                        continue
                    try:
                        text = f.read_text(encoding="utf-8", errors="replace")
                    except FileNotFoundError:
                        continue
                    except OSError:
                        raise WriteRefused(
                            f"unreadable native pointer: {f.name}")
                    if not _is_mirror(text):
                        continue
                    fm = _frontmatter(text)
                    cdom = str(fm.get("canonical_domain") or fm.get("domain") or "").strip()
                    if cdom == domain_id and str(f) not in doomed:
                        leftover.append(f.name)
                if leftover:
                    raise WriteRefused(
                        "native pointers remain after revoke: "
                        + ", ".join(leftover[:8]))
        extra = _canonical_and_ops_deletes(ctx, conn, domain_id, facts_dir)
        deletes.extend(extra["deletes"])
        expected.update(extra["expected_revisions"])
        ops.extend(extra["registry_ops"])
        ops.append({"op": "domain_status_set", "domain_id": domain_id,
                    "status": "deleted"})
        return {"deletes": deletes, "expected_revisions": expected,
                "registry_ops": ops, "dest_modes": dest_modes,
                "purged_ops": extra["purged_ops"], "revoked": revoked}

    out = transact(ctx, "purge-domain", {"domain": domain_id}, mutate,
                   extra_domains=[domain_id], extra_project_ids=pids)
    n = int((out.get("result") or {}).get("purged_ops") or 0)
    n += _rmtree_empty_domain_dir(facts_dir, domain_id)
    # Phase-5 closeout: the domain dir rmtree is non-transact — unlink the
    # manifest explicitly (the transact hook only sees the file deletes).
    try:
        from facts_manifest import manifest_path
        manifest_path(ctx.plugin_data_dir, domain_id).unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True, "purged_files": n, "domain_id": domain_id,
            "revoked_mirrors": int((out.get("result") or {}).get("revoked") or 0),
            "unenrolled": len(rows)}


def _purge_fence_root(ctx: StoreContext) -> Path:
    return ctx.config_root / "consolidate-memory-purge"


def _write_purge_fence(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def _read_purge_fence(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _incomplete_purge_fences(ctx: StoreContext) -> list:
    root = _purge_fence_root(ctx)
    if not root.is_dir():
        return []
    out: list = []
    for p in sorted(root.glob("*.json")):
        data = _read_purge_fence(p)
        if data and str(data.get("state") or "") not in ("complete", ""):
            out.append((p, data))
    return out


def domain_purge_status(ctx: StoreContext, domain_id: str) -> dict:
    from control_plane import connect_if_exists, db_path, domain_lifecycle
    conn = connect_if_exists(db_path(ctx))
    life = "active"
    enrolled: list = []
    if conn is not None:
        try:
            life = domain_lifecycle(conn, domain_id)
            enrolled = [str(r["project_id"]) for r in _enrolled_rows(conn, domain_id)]
        finally:
            conn.close()
    facts = ctx.config_root / "consolidate-memory" / "domains" / domain_id / "facts"
    remaining = 0
    if facts.is_dir():
        remaining = sum(1 for p in facts.glob("*.md") if p.name != "MEMORY.md")
    return {
        "domain_id": domain_id,
        "lifecycle": life,
        "enrolled_projects": enrolled,
        "canonicals_remaining": remaining,
        "resumable": life == "deleting",
        "cancellable": life == "deleting",
    }


def _run_domain_purge(ctx: StoreContext, domain_id: str) -> dict:
    from control_plane import connect, db_path, transact as _tx_del
    conn = connect(db_path(ctx))
    try:
        rows = _enrolled_rows(conn, domain_id)
        pids = [str(r["project_id"]) for r in rows]
        if ctx.project_id not in pids:
            pids.append(ctx.project_id)

        def _mark_deleting(_c, _t):
            del _c, _t
            return {"registry_ops": [
                {"op": "domain_status_set", "domain_id": domain_id,
                 "status": "deleting"}]}
        _tx_del(ctx, "domain-deleting", {"domain_id": domain_id}, _mark_deleting,
                extra_domains=[domain_id], extra_project_ids=pids)
        facts = (ctx.config_root / "consolidate-memory" / "domains" / domain_id / "facts")
        return _fleet_purge_domain(ctx, domain_id, facts, rows)
    finally:
        conn.close()


def domain_purge_resume(ctx: StoreContext, domain_id: str) -> dict:
    st = domain_purge_status(ctx, domain_id)
    if st["lifecycle"] == "deleted":
        return {"ok": True, "resumed": False, "already": "deleted", **st}
    if st["lifecycle"] != "deleting":
        raise WriteRefused(
            "purge-resume: domain %s is %s (need deleting)"
            % (domain_id, st["lifecycle"]))
    out = _run_domain_purge(ctx, domain_id)
    return {"ok": True, "resumed": True, **out}


def domain_purge_cancel(ctx: StoreContext, domain_id: str, *,
                        accept_partial: bool = False) -> dict:
    from control_plane import transact
    st = domain_purge_status(ctx, domain_id)
    if st["lifecycle"] != "deleting":
        raise WriteRefused(
            "purge-cancel: domain %s is %s (need deleting)"
            % (domain_id, st["lifecycle"]))
    if int(st["canonicals_remaining"] or 0) == 0 and not accept_partial:
        raise WriteRefused(
            "purge-cancel: canonicals already gone; pass --accept-partial "
            "to unstick deleting (does not restore facts)")

    def mutate(_c, _t):
        del _c, _t
        return {"registry_ops": [
            {"op": "domain_status_set", "domain_id": domain_id, "status": "active"}]}

    transact(ctx, "purge-cancel", {"domain_id": domain_id}, mutate,
             extra_domains=[domain_id])
    return {"ok": True, "cancelled": True, "domain_id": domain_id,
            "accept_partial": accept_partial}


def _rmtree_target(target: Path) -> list:
    """Delete a tree. Returns leftover file paths (empty means gone)."""
    import shutil
    failed: list = []
    if not target.exists():
        return failed
    try:
        shutil.rmtree(target)
    except OSError as e:
        failed.append("%s: %s" % (target, e))
    if target.exists():
        try:
            leftover = [str(p) for p in target.rglob("*") if p.is_file()]
        except OSError:
            leftover = [str(target)]
        failed.extend(leftover[:16])
    return failed


def _all_plugin_data_targets(ctx: StoreContext) -> dict:
    pdata = ctx.plugin_data_dir
    droot = ctx.config_root / "consolidate-memory" / "domains"
    return {"plugin_data": str(pdata), "domains": str(droot)}


def run_all_plugin_data_purge(ctx: StoreContext, *, rows: list,
                              seen_dom: list, pids: list) -> dict:
    """Journaled revoke then fenced rmtree. Resume from the external fence (P1-8)."""
    from control_plane import transact as _tx_all
    from store_context import store_context_from_registry
    fence_root = _purge_fence_root(ctx)
    existing = _incomplete_purge_fences(ctx)
    if existing:
        fence_path, fence = existing[0]
        purge_id = str(fence.get("purge_id") or fence_path.stem)
    else:
        purge_id = "all-" + uuid.uuid4().hex[:12]
        fence_path = fence_root / (purge_id + ".json")
        fence = {
            "purge_id": purge_id,
            "state": "planned",
            "targets": _all_plugin_data_targets(ctx),
            "domains": list(seen_dom),
            "projects": list(pids),
        }
        _write_purge_fence(fence_path, fence)

    state = str(fence.get("state") or "planned")
    targets = fence.get("targets") or _all_plugin_data_targets(ctx)
    pdata = Path(str(targets.get("plugin_data") or ctx.plugin_data_dir))
    droot = Path(str(targets.get("domains") or (
        ctx.config_root / "consolidate-memory" / "domains")))

    if state in ("planned",):
        if pdata.is_dir() and (pdata / "control.sqlite").is_file():
            def _revoke_all(conn2, temps):
                deletes: list = []
                expected: dict = {}
                dest_modes: dict = {}
                ops: list = []
                for r in rows:
                    pid = str(r["project_id"])
                    native_s = str(r["native_memory_dir"] or "").strip()
                    root_s = str(r["current_root"] or "").strip()
                    if not native_s and not root_s:
                        raise WriteRefused(
                            f"cannot revoke project {pid}: missing current_root "
                            "and native_memory_dir")
                    pctx = store_context_from_registry(r, template=ctx)
                    staged = _stage_revoke_plan(pctx, "unknown", conn2, temps)
                    deletes.extend(staged["deletes"])
                    dest_modes.update(staged["dest_modes"])
                    expected.update(staged["expected_revisions"])
                    ops.extend(staged["registry_ops"])
                    ops.append({"op": "project_domain_change", "project_id": pid,
                                "domain_id": "unknown", "status": "inactive"})
                for d in seen_dom:
                    ops.append({"op": "domain_status_set", "domain_id": d,
                                "status": "deleted"})
                return {"deletes": deletes, "expected_revisions": expected,
                        "registry_ops": ops, "dest_modes": dest_modes,
                        "revoked": len(deletes)}
            _tx_all(ctx, "purge-all-plugin-data", {"scope": "all"}, _revoke_all,
                    extra_domains=seen_dom, extra_project_ids=pids)
        fence["state"] = "mirrors-revoked"
        _write_purge_fence(fence_path, fence)
        state = "mirrors-revoked"

    errors: list = []
    n = 0
    if state in ("mirrors-revoked", "plugin-data-deleting"):
        fence["state"] = "plugin-data-deleting"
        _write_purge_fence(fence_path, fence)
        if pdata.is_dir():
            n += sum(1 for _ in pdata.rglob("*") if _.is_file())
        errors.extend(_rmtree_target(pdata))
        if not errors:
            fence["state"] = "canonical-data-deleting"
            _write_purge_fence(fence_path, fence)
            state = "canonical-data-deleting"

    if state in ("canonical-data-deleting",):
        if droot.is_dir():
            n += sum(1 for _ in droot.rglob("*") if _.is_file())
        errors.extend(_rmtree_target(droot))
        if not errors:
            # Phase-5 closeout: the domains-root rmtree is non-transact and may
            # precede plugin-data deletion — unlink every manifest explicitly.
            try:
                from facts_manifest import invalidate_all
                invalidate_all(ctx.plugin_data_dir)
            except Exception:
                pass
            fence["state"] = "verified"
            _write_purge_fence(fence_path, fence)
            state = "verified"

    if state == "verified":
        leftover: list = []
        for t in (pdata, droot):
            if t.exists():
                try:
                    leftover.extend(str(p) for p in t.rglob("*") if p.is_file())
                except OSError:
                    leftover.append(str(t))
        if leftover:
            errors.extend(leftover[:16])
        else:
            fence["state"] = "complete"
            _write_purge_fence(fence_path, fence)
            state = "complete"

    if errors or state != "complete":
        raise WriteRefused("all-plugin-data purge incomplete: " + "; ".join(errors[:8])
                           if errors else "state=" + state)
    return {"ok": True, "scope": "all-plugin-data", "purged_files": n,
            "managed_mirrors_revoked": True, "purge_id": purge_id,
            "native": str(ctx.native_memory_dir)}


def _ctx(project: str, extra_env=None) -> StoreContext:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return resolve_store(Path(project).resolve(), environ=env)


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _migrate_plan_path(ctx: StoreContext) -> Path:
    return ctx.plugin_data_dir / "migrate-plan.json"


def _migrate_sources(ctx: StoreContext) -> list:
    """Legacy ~/.claude/memory + 0.2.1 unknown pool. Does not mint sqlite."""
    roots = [
        ("legacy", ctx.config_root / "memory"),
        ("unknown-pool", ctx.config_root / "consolidate-memory" / "domains"
         / "unknown" / "facts"),
    ]
    out: list = []
    by_stem: dict = {}
    for label, root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.glob("*.md")):
            if p.name == "MEMORY.md":
                continue
            row: dict = {
                "stem": p.stem,
                "source": str(p),
                "origin": label,
                "sha256": _sha256_file(p),
                "assignment": None,
                "collisions": [],
            }
            if p.stem in by_stem:
                by_stem[p.stem]["collisions"].append({
                    "origin": label, "source": str(p), "sha256": row["sha256"]})
                continue
            by_stem[p.stem] = row
            out.append(row)
    return out


def _load_migrate_plan(ctx: StoreContext) -> dict:
    path = _migrate_plan_path(ctx)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("facts"), dict):
                if not str(data.get("migration_id") or "").strip():
                    data["migration_id"] = "mig_" + uuid.uuid4().hex[:16]
                return data
        except (OSError, ValueError):
            pass
    facts = {row["stem"]: row for row in _migrate_sources(ctx)}
    return {"facts": facts, "applied": False, "finalized": False,
            "migration_id": "mig_" + uuid.uuid4().hex[:16]}


def _save_migrate_plan(ctx: StoreContext, plan: dict) -> None:
    path = _migrate_plan_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(path.parent), 0o700)
    except OSError:
        pass
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def _unresolved_migrate(plan: dict) -> list:
    out = []
    for stem, row in sorted((plan.get("facts") or {}).items()):
        row = row or {}
        if row.get("collisions"):
            out.append(stem)
        elif not row.get("assignment"):
            out.append(stem)
    return out


def _contained_under(path: Path, roots: list) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def _migrate_source_roots(ctx: StoreContext) -> list:
    return [
        ctx.config_root / "memory",
        ctx.config_root / "consolidate-memory" / "domains" / "unknown" / "facts",
    ]


def _b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")


def _unb64(s: str) -> Optional[bytes]:
    import base64
    if not s:
        return None
    try:
        return base64.b64decode(s.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return None


def cmd_doctor(args: argparse.Namespace) -> int:
    from store_context import repair_permissions
    ctx = _ctx(args.project)
    if getattr(args, "repair_permissions", False):
        print(json.dumps(repair_permissions(ctx)))
        return 0
    if args.json:
        print(json.dumps(doctor_dict(ctx), indent=2, sort_keys=True))
    else:
        sys.stdout.write(doctor_report(ctx))
    return 0


def cmd_conflicts(args: argparse.Namespace) -> int:
    from control_plane import connect_if_exists, db_path, list_conflicts
    ctx = _ctx(args.project)
    conn = connect_if_exists(db_path(ctx))
    rows = list_conflicts(conn, ctx.project_id if not args.all else None) if conn else []
    if conn is not None:
        conn.close()
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        if not rows:
            print("conflicts: (none)")
        for r in rows:
            print(f"{r.get('fact_stem')}  {r.get('action')}  project={r.get('project_id')[:12]}…")
    return 0


def _canonical_for_repair(ctx: StoreContext, stem: str) -> Optional[str]:
    """Current-domain CanonicalRef only. Legacy files are migrate inputs, not repair sources."""
    from fact_schema import validate_canonical_frontmatter
    from memory_status import _frontmatter
    from domain_policy import fact_domain
    canon = ctx.canonical_domain_dir / f"{stem}.md"
    if not canon.is_file():
        return None
    try:
        text = canon.read_text(encoding="utf-8")
    except OSError:
        return None
    fm = _frontmatter(text)
    fdom = fact_domain(fm)
    if fdom and fdom != ctx.domain_id:
        return None
    st = str(fm.get("status") or "active").strip() or "active"
    if st != "active":
        return None
    if str(fm.get("schema_version") or "").strip() in ("3", "v3"):
        err = validate_canonical_frontmatter(fm, stem=stem, domain=ctx.domain_id)
        if err:
            return None
    return text


def _restamp_from_canonical(ctx: StoreContext, stem: str, canonical: str, native: Path,
                            how: str, extra_temps: Optional[dict] = None,
                            create_paths: Optional[list] = None,
                            canonical_path: Optional[Path] = None) -> dict:
    """Journal a keep-canonical / repair rewrite + mark the conflict resolved."""
    from control_plane import ABSENT as _ABS, stable_fact_id, transact, _file_hash
    from mirror_conflict import semantic_hash, stamp_revisions
    from sync_global import _as_mirror, _body_hash
    import time as _t
    rev = semantic_hash(canonical)
    fid = stable_fact_id(ctx.domain_id, stem)
    want = _as_mirror(canonical, stem, since=_t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
                      body_hash=_body_hash(canonical),
                      fact_id=fid, domain=ctx.domain_id)
    want = stamp_revisions(want, rev, rev)
    extras = dict(extra_temps or {})
    creates = {str(p) for p in (create_paths or [])}
    expected: dict = {}
    dest_modes_pre: dict = {}
    if canonical_path is not None and canonical_path.exists():
        ch = _file_hash(canonical_path)
        if ch:
            expected[str(canonical_path)] = ch
    if native.exists():
        h = _file_hash(native)
        if h:
            expected[str(native)] = h
    else:
        expected[str(native)] = _ABS
        dest_modes_pre[str(native)] = "create"
        creates.add(str(native))
    for dest in extras:
        if dest in creates:
            expected[dest] = _ABS
        else:
            dp = Path(dest)
            if dp.exists():
                h = _file_hash(dp)
                if h:
                    expected[dest] = h

    def mutate(conn, temps):
        del conn
        temps[str(native)] = want
        dest_modes: dict = dict(dest_modes_pre)
        extra_expected: dict = {}
        if str(native) in creates:
            dest_modes[str(native)] = "create"
            extra_expected[str(native)] = _ABS
        for dest, text in extras.items():
            temps[dest] = text
            if dest in creates:
                dest_modes[dest] = "create"
                extra_expected[dest] = _ABS
        ops = [
            {"op": "holder_upsert", "fact_id": fid, "project_id": ctx.project_id,
             "base_revision": rev, "canonical_revision": rev, "semantic_hash": rev},
            {"op": "conflict_resolve", "stem": stem, "project_id": ctx.project_id,
             "resolved": how, "domain_id": ctx.domain_id, "fact_id": fid},
        ]
        return {"stem": stem, "how": how, "registry_ops": ops,
                "dest_modes": dest_modes, "expected_revisions": extra_expected}

    return transact(ctx, "resolve-" + how, {"stem": stem, "how": how,
                                            "domain_id": ctx.domain_id}, mutate,
                    expected_revisions=expected or None)


def cmd_resolve(args: argparse.Namespace) -> int:
    from canonical_ingress import demirror_text, insert_frontmatter_key
    from identifiers import IdentifierRefused, safe_child, validate_fact_stem
    from store_context import assert_writable
    ctx = _ctx(args.project)
    try:
        assert_writable(ctx)
    except WriteRefused as e:
        print(f"resolve: {e}", file=sys.stderr)
        return 2
    if not getattr(ctx, "cross_project_allowed", False):
        print("resolve: cross-project writes require enrollment into a named domain "
              "(cm project enroll --domain NAME --apply)", file=sys.stderr)
        return 2
    try:
        stem = validate_fact_stem(args.fact)
        native = safe_child(ctx.native_memory_dir, f"{stem}.md")
        if args.fork_local:
            validate_fact_stem(args.fork_local)
    except IdentifierRefused as e:
        print(f"resolve: {e}", file=sys.stderr)
        return 2
    canonical = _canonical_for_repair(ctx, stem)
    canon_path = ctx.canonical_domain_dir / f"{stem}.md"
    if not native.exists():
        print(f"resolve: no local file {native}", file=sys.stderr)
        return 1
    local = native.read_text(encoding="utf-8", errors="replace")
    if args.keep_canonical:
        if not canonical:
            print("resolve: no current-domain canonical to keep", file=sys.stderr)
            return 1
        try:
            _restamp_from_canonical(ctx, stem, canonical, native, "keep-canonical",
                                    canonical_path=canon_path)
        except WriteRefused as e:
            print(f"resolve: {e}", file=sys.stderr)
            return 2
        print(f"resolve: kept canonical for {stem}")
        return 0
    if args.fork_local:
        dest = safe_child(ctx.native_memory_dir, f"{args.fork_local}.md")
        if dest.exists():
            print(f"resolve: fork target {args.fork_local} exists", file=sys.stderr)
            return 1
        forked = insert_frontmatter_key(demirror_text(local), "name", args.fork_local)
        extras = {str(dest): forked if forked.endswith("\n") else forked + "\n"}
        if not canonical:
            print("resolve: no current-domain canonical to restamp after fork", file=sys.stderr)
            return 1
        try:
            _restamp_from_canonical(ctx, stem, canonical, native, "fork-local", extras,
                                    create_paths=[dest], canonical_path=canon_path)
        except WriteRefused as e:
            print(f"resolve: {e}", file=sys.stderr)
            return 2
        print(f"resolve: forked {stem} → {args.fork_local} (project-local)")
        return 0
    if args.promote_local:
        from canonical_ingress import upsert
        clean = demirror_text(local)
        out = upsert(ctx, stem, clean, origin_local=native, extra_registry_ops=[{
            "op": "conflict_resolve", "stem": stem, "project_id": ctx.project_id,
            "resolved": "promote-local", "domain_id": ctx.domain_id,
        }])
        print(json.dumps(out) if args.json else (out if out.get("ok") else out.get("error")))
        return 0 if out.get("ok") else 1
    print("resolve: pass --keep-canonical, --fork-local NAME, or --promote-local", file=sys.stderr)
    return 2


def cmd_repair_mirror(args: argparse.Namespace) -> int:
    from identifiers import IdentifierRefused, safe_child, validate_fact_stem
    from store_context import assert_writable
    ctx = _ctx(args.project)
    try:
        assert_writable(ctx)
    except WriteRefused as e:
        print(f"repair-mirror: {e}", file=sys.stderr)
        return 2
    if not getattr(ctx, "cross_project_allowed", False):
        print("repair-mirror: cross-project writes require enrollment into a named domain "
              "(cm project enroll --domain NAME --apply)", file=sys.stderr)
        return 2
    try:
        stem = validate_fact_stem(args.fact)
        native = safe_child(ctx.native_memory_dir, f"{stem}.md")
    except IdentifierRefused as e:
        print(f"repair-mirror: {e}", file=sys.stderr)
        return 2
    canonical = _canonical_for_repair(ctx, stem)
    if not canonical:
        print("repair-mirror: no current-domain canonical", file=sys.stderr)
        return 1
    ctx.native_memory_dir.mkdir(parents=True, exist_ok=True)
    try:
        _restamp_from_canonical(ctx, stem, canonical, native, "repair-mirror",
                                canonical_path=ctx.canonical_domain_dir / f"{stem}.md")
    except WriteRefused as e:
        print(f"repair-mirror: {e}", file=sys.stderr)
        return 2
    print(f"repair-mirror: restamped {stem} from canonical")
    return 0


def cmd_canonical(args: argparse.Namespace) -> int:
    from canonical_ingress import forget, generate_catalog, set_canonical_status, upsert
    ctx = _ctx(args.project)
    if args.canonical_cmd == "upsert":
        text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
        origin = ctx.native_memory_dir / f"{args.stem}.md" if args.origin else None
        out = upsert(ctx, args.stem, text, origin_local=origin, crash_after=args.crash_after)
        msg = "ok" if out.get("ok") else str(out.get("error") or "error")
        print(json.dumps(out, indent=2) if args.json else f"canonical upsert {args.stem}: {msg}")
        return 0 if out.get("ok") else 1
    if args.canonical_cmd == "catalog":
        cat = generate_catalog(ctx.canonical_domain_dir)
        print(cat)
        return 0
    if args.canonical_cmd == "forget":
        out = forget(ctx, args.stem, reason=args.reason or "user-forget")
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if args.canonical_cmd in ("supersede", "expire", "reactivate"):
        st = {"supersede": "superseded", "expire": "expired",
              "reactivate": "active"}[args.canonical_cmd]
        out = set_canonical_status(ctx, args.stem or "", st,
                                   replacement_id=getattr(args, "replacement", None) or "")
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if args.canonical_cmd == "resurrect":
        from canonical_ingress import resurrect as _resurrect
        if not args.stem:
            print("canonical resurrect: pass STEM --file PATH", file=sys.stderr)
            return 2
        if not args.file:
            print("canonical resurrect: pass --file PATH", file=sys.stderr)
            return 2
        text = Path(args.file).read_text(encoding="utf-8")
        out = _resurrect(ctx, args.stem, text)
        print(json.dumps(out, indent=2) if args.json else out)
        return 0 if out.get("ok") else 1
    return 2


def cmd_marker(args: argparse.Namespace) -> int:
    from memory_status import stamp_project_marker
    cmd = args.marker_cmd
    if cmd == "stamp":
        if not args.commit:
            print("marker stamp: pass --commit SHA", file=sys.stderr)
            return 2
        out = stamp_project_marker(Path(args.project), commit=args.commit,
                                   timestamp=args.timestamp)
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if cmd == "standing-justify":
        if args.facts is None:
            print("marker standing-justify: pass --facts N", file=sys.stderr)
            return 2
        sj = {"facts": int(args.facts),
              "index_tokens": int(args.index_tokens or 0),
              "at": args.timestamp or ""}
        if not sj["at"]:
            from memory_status import _utc_iso_now
            sj["at"] = _utc_iso_now()
        out = stamp_project_marker(Path(args.project), standing_justify=sj)
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if cmd == "snooze":
        if not args.until:
            print("marker snooze: pass --until ISO", file=sys.stderr)
            return 2
        out = stamp_project_marker(Path(args.project), snooze_until=args.until)
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    return 2


def cmd_local(args: argparse.Namespace) -> int:
    from local_ingress import (local_archive, local_forget, local_migrate_schema,
                               local_rebuild_index, local_upsert)
    ctx = _ctx(args.project)
    cmd = args.local_cmd
    if cmd == "rebuild-index":
        out = local_rebuild_index(
            ctx, apply=bool(args.apply), skip_invalid=bool(args.skip_invalid),
            confirm=str(args.confirm or ""))
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if cmd == "migrate-schema":
        out = local_migrate_schema(
            ctx, apply=bool(args.apply), confirm=str(args.confirm or ""))
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if not args.stem:
        print(f"local {cmd}: pass STEM", file=sys.stderr)
        return 2
    if cmd in ("upsert", "update"):
        if not args.file:
            print(f"local {cmd}: pass --file PATH", file=sys.stderr)
            return 2
        dest = ctx.native_memory_dir / f"{args.stem}.md"
        if cmd == "update" and not dest.exists():
            print("local update: no such fact", file=sys.stderr)
            return 2
        text = Path(args.file).read_text(encoding="utf-8")
        out = local_upsert(ctx, args.stem, text)
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if cmd == "forget":
        out = local_forget(ctx, args.stem)
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    if cmd == "archive":
        out = local_archive(ctx, args.stem)
        print(json.dumps(out) if args.json else out)
        return 0 if out.get("ok") else 1
    return 2


def cmd_migrate(args: argparse.Namespace) -> int:
    from control_plane import (assert_mutation_allowed, connect, connect_if_exists,
                               db_path, is_tombstoned, set_migration_mode, transact)
    from identifiers import IdentifierRefused, safe_child, validate_domain_id
    ctx = _ctx(args.project)
    stage = getattr(args, "migrate_cmd", None) or "inventory"
    if getattr(args, "apply", False):
        stage = "apply"
    if getattr(args, "rollback", False):
        stage = "rollback"
    if getattr(args, "finalize", False):
        stage = "finalize"
    if getattr(args, "status", False):
        stage = "status"
    if getattr(args, "assign", None):
        stage = "assign"
    if getattr(args, "exclude", None):
        stage = "exclude"
    if getattr(args, "validate", False):
        stage = "validate"
    if getattr(args, "resolve_collision", None):
        stage = "resolve-collision"

    if getattr(args, "apply", False) and getattr(args, "rollback", False):
        print("migrate: pass only one of --apply or --rollback", file=sys.stderr)
        return 2
    plan = _load_migrate_plan(ctx)
    # Refresh inventory of newly appeared sources without clobbering a
    # reviewed assignment / --keep unknown-pool origin (ADR 013).
    for row in _migrate_sources(ctx):
        cur = (plan.get("facts") or {}).get(row["stem"]) or {}
        if not cur:
            plan.setdefault("facts", {})[row["stem"]] = row
            continue
        members = [{"origin": row["origin"], "source": row["source"],
                    "sha256": row["sha256"]}] + list(row.get("collisions") or [])
        kept = str(cur.get("origin") or "")
        resolved = bool(kept) and not cur.get("collisions")
        if resolved:
            for m in members:
                if str(m.get("origin") or "") == kept:
                    cur["source"] = m.get("source") or cur.get("source")
                    break
        elif kept:
            cur["collisions"] = [m for m in members
                                 if str(m.get("origin") or "") != kept]
            for m in members:
                if str(m.get("origin") or "") == kept:
                    cur["source"] = m.get("source") or cur.get("source")
                    if m.get("sha256"):
                        cur["sha256"] = m["sha256"]
                    break
        else:
            cur["source"] = row["source"]
            cur["origin"] = row["origin"]
            cur["collisions"] = list(row.get("collisions") or [])
            if not cur.get("sha256"):
                cur["sha256"] = row["sha256"]
        plan["facts"][row["stem"]] = cur

    if stage in ("inventory", "review"):
        unresolved = _unresolved_migrate(plan)
        summary = {
            "n_facts": len(plan.get("facts") or {}),
            "unresolved": unresolved,
            "applied": bool(plan.get("applied")),
            "finalized": bool(plan.get("finalized")),
            "mode_after": "dual-read until finalize",
        }
        if args.json:
            print(json.dumps({"plan": summary, "facts": plan.get("facts")}, indent=2))
        else:
            print(f"migrate plan: {summary['n_facts']} facts "
                  f"({len(unresolved)} unresolved) → assign each to a named domain")
            print("  assignment: none until `cm migrate --assign STEM --domain NAME`")
            print("  dual-read remains until --finalize")
            print("migrate: dry (pass --assign / --apply after every fact is resolved)")
        _save_migrate_plan(ctx, plan)
        return 0

    if stage == "status":
        unresolved = _unresolved_migrate(plan)
        payload = {
            "n_facts": len(plan.get("facts") or {}),
            "unresolved": unresolved,
            "applied": bool(plan.get("applied")),
            "finalized": bool(plan.get("finalized")),
        }
        print(json.dumps(payload, indent=2) if args.json else
              f"migrate status: {payload['n_facts']} facts, "
              f"{len(unresolved)} unresolved, applied={payload['applied']}, "
              f"finalized={payload['finalized']}")
        return 0

    if stage == "assign":
        stem = getattr(args, "assign", None) or getattr(args, "fact", None)
        domain = getattr(args, "domain", None)
        if not stem or not domain:
            print("migrate assign: pass --assign STEM --domain NAME", file=sys.stderr)
            return 2
        try:
            domain = validate_domain_id(domain)
        except IdentifierRefused as e:
            print(f"migrate assign: {e}", file=sys.stderr)
            return 2
        facts = plan.setdefault("facts", {})
        if stem not in facts:
            facts[stem] = {"stem": stem, "source": "", "assignment": domain}
        else:
            facts[stem]["assignment"] = domain
        _save_migrate_plan(ctx, plan)
        print(f"migrate assign: {stem} → domain {domain}")
        return 0

    if stage == "exclude":
        stem = getattr(args, "exclude", None) or getattr(args, "fact", None)
        if not stem:
            print("migrate exclude: pass --exclude STEM", file=sys.stderr)
            return 2
        facts = plan.setdefault("facts", {})
        if stem not in facts:
            facts[stem] = {"stem": stem, "source": "", "assignment": "excluded"}
        else:
            facts[stem]["assignment"] = "excluded"
        _save_migrate_plan(ctx, plan)
        print(f"migrate exclude: {stem}")
        return 0

    if stage == "resolve-collision":
        stem = getattr(args, "resolve_collision", None)
        keep = str(getattr(args, "keep", None) or "")
        if not stem or keep not in ("legacy", "unknown-pool"):
            print("migrate resolve-collision: --resolve-collision STEM --keep legacy|unknown-pool",
                  file=sys.stderr)
            return 2
        facts = plan.setdefault("facts", {})
        row = facts.get(stem)
        if not row:
            print(f"migrate resolve-collision: unknown stem {stem}", file=sys.stderr)
            return 2
        extras = list(row.get("collisions") or [])
        if keep == str(row.get("origin") or ""):
            row["collisions"] = []
        else:
            for extra in extras:
                if str(extra.get("origin") or "") == keep:
                    row["source"] = extra.get("source") or row.get("source")
                    row["origin"] = keep
                    row["sha256"] = extra.get("sha256") or row.get("sha256")
            row["collisions"] = [c for c in extras if str(c.get("origin") or "") != keep]
        facts[stem] = row
        _save_migrate_plan(ctx, plan)
        print(f"migrate resolve-collision: {stem} kept {keep}")
        return 0

    if stage == "validate":
        unresolved = _unresolved_migrate(plan)
        if unresolved:
            print(f"migrate validate: {len(unresolved)} unresolved: "
                  + ", ".join(unresolved[:12]), file=sys.stderr)
            return 2
        print("migrate validate: ok")
        return 0

    if stage == "apply":
        try:
            assert_mutation_allowed(ctx)
        except WriteRefused as e:
            print(f"migrate apply: {e}", file=sys.stderr)
            return 2
        unresolved = _unresolved_migrate(plan)
        if unresolved:
            print("migrate apply: refusing — unresolved facts remain "
                  f"({len(unresolved)}). Assign or exclude each first "
                  "(ADR 013; no silent legacy-unassigned).", file=sys.stderr)
            return 2
        if not getattr(ctx, "cross_project_allowed", False):
            print("migrate apply: cross-project writes require enrollment into a named domain "
                  "(cm project enroll --domain NAME --apply)", file=sys.stderr)
            return 2
        _mode_now = "dual-read"
        _mc = connect_if_exists(db_path(ctx))
        try:
            if _mc is not None:
                from control_plane import get_migration_mode as _gmm
                _mode_now = _gmm(_mc)
        finally:
            if _mc is not None:
                _mc.close()
        if plan.get("finalized") or _mode_now == "enforced":
            print("migrate apply: already finalized; start a new inventory", file=sys.stderr)
            return 2
        if plan.get("applied") and not plan.get("finalized"):
            print("migrate apply: already applied; rollback or finalize first", file=sys.stderr)
            return 2
        need_m = _want_confirm(args, "migrate-apply")
        if need_m == "dry":
            print("migrate apply: dry (pass --apply --confirm migrate-apply)")
            return 0
        if need_m:
            print(f"migrate apply: {need_m}", file=sys.stderr)
            return 2
        on_existing = str(getattr(args, "on_existing", None) or "")
        to_copy = []
        src_roots = _migrate_source_roots(ctx)
        from identifiers import IdentifierRefused, validate_fact_stem as _vfs
        for stem, row in sorted((plan.get("facts") or {}).items()):
            dest_dom = str((row or {}).get("assignment") or "")
            if dest_dom in ("", "excluded"):
                continue
            try:
                stem = _vfs(stem)
            except IdentifierRefused as e:
                print(f"migrate apply: {e}", file=sys.stderr)
                return 2
            src = Path(str((row or {}).get("source") or ""))
            if not src.is_file():
                print(f"migrate apply: missing source for {stem}", file=sys.stderr)
                return 2
            if not _contained_under(src, src_roots):
                print(f"migrate apply: source for {stem} is outside approved roots",
                      file=sys.stderr)
                return 2
            to_copy.append((stem, src, dest_dom, row))
        copied_holder: list = []
        catalog_holder: list = []
        droot = ctx.config_root / "consolidate-memory" / "domains"

        def mutate(conn, temps):
            from canonical_ingress import generate_catalog, prepare_migrated_canonical, validate_links
            from control_plane import ABSENT as _ABS, stable_fact_id as _sf_m
            from domain_policy import fact_sensitivity as _fs_m
            from fact_schema import CLASS_ACTIVE, CLASS_INACTIVE, classify_canonical
            from memory_status import _frontmatter as _fm_m
            from mirror_conflict import semantic_hash as _sem_m
            copied: list = []
            staged: list = []
            catalogs: dict = {}
            dest_modes: dict = {}
            expected: dict = {}
            ops: list = []
            dispositions: list = []
            for stem, row in sorted((plan.get("facts") or {}).items()):
                if str((row or {}).get("assignment") or "") == "excluded":
                    dispositions.append({
                        "stem": stem, "disposition": "excluded",
                        "path": "", "sha256": "", "fact_id": "",
                        "domain": "", "status": "",
                    })
            for stem, src, dest_dom, row in to_copy:
                facts_dir = safe_child(droot, dest_dom) / "facts"
                facts_dir.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(str(facts_dir), 0o700)
                except OSError:
                    pass
                dest = facts_dir / f"{stem}.md"
                tomb = is_tombstoned(conn, stem, dest_dom)
                if tomb and not getattr(args, "resurrect", False):
                    raise WriteRefused(
                        f"migrate apply: {stem} is tombstoned in {dest_dom}; "
                        "pass --resurrect to copy over the tombstone")
                if dest.exists() and on_existing not in (
                        "replace-with-migrated", "keep-existing", "exclude"):
                    raise WriteRefused(
                        f"migrate apply: dest exists for {stem}; pass "
                        "--on-existing keep-existing|replace-with-migrated|exclude")
                if dest.exists() and on_existing in ("keep-existing", "exclude"):
                    if on_existing == "exclude":
                        dispositions.append({
                            "stem": stem, "disposition": "excluded",
                            "path": str(dest), "sha256": _sha256_file(dest),
                            "fact_id": _sf_m(dest_dom, stem),
                            "domain": dest_dom, "status": "",
                        })
                    else:
                        from control_plane import read_snapshot as _rs_ke
                        _snap_ke = _rs_ke(dest)
                        live = (_snap_ke.data or b"").decode("utf-8", errors="replace")
                        cls = classify_canonical(live, stem=stem, domain=dest_dom)
                        if cls["class"] not in (CLASS_ACTIVE, CLASS_INACTIVE):
                            raise WriteRefused(
                                "keep-existing dest is not a valid v3 canonical: "
                                + stem + " (" + str(cls.get("error") or cls["class"]) + ")")
                        fm_dom = str((cls.get("fm") or {}).get("domain") or "")
                        if fm_dom and fm_dom != dest_dom:
                            raise WriteRefused(
                                "keep-existing dest domain "
                                + fm_dom + " != " + dest_dom)
                        fid = _sf_m(dest_dom, stem)
                        have = conn.execute(
                            "SELECT fact_id FROM facts WHERE fact_id=?", (fid,)
                        ).fetchone()
                        fm_k = cls.get("fm") or {}
                        if cls["class"] == CLASS_ACTIVE:
                            catalogs.setdefault(str(facts_dir), set()).add(stem)
                        if tomb:
                            if cls["class"] != CLASS_ACTIVE:
                                from canonical_ingress import insert_frontmatter_key
                                live = insert_frontmatter_key(live, "status", "active")
                                temps[str(dest)] = live
                                dest_modes[str(dest)] = "replace"
                                expected[str(dest)] = _snap_ke.sha256
                                cls = classify_canonical(
                                    live, stem=stem, domain=dest_dom)
                                fm_k = cls.get("fm") or {}
                            catalogs.setdefault(str(facts_dir), set()).add(stem)
                            ops.append({"op": "tombstone_delete", "fact_id": fid})
                        ops.append({
                            "op": "fact_upsert", "fact_id": fid, "stem": stem,
                            "domain_id": dest_dom, "canonical_path": str(dest),
                            "revision": _sem_m(live),
                            "status": str(fm_k.get("status") or "active"),
                            "sensitivity": _fs_m(fm_k),
                        })
                        dispositions.append({
                            "stem": stem, "disposition": "kept-existing",
                            "path": str(dest),
                            "sha256": hashlib.sha256(
                                live.encode("utf-8")).hexdigest(),
                            "fact_id": fid, "domain": dest_dom,
                            "status": str(fm_k.get("status") or ""),
                            "class": cls["class"],
                            "revision": _sem_m(live),
                        })
                    continue
                src_hash = str((row or {}).get("sha256") or _sha256_file(src))
                if src_hash:
                    expected[str(src)] = src_hash
                old_bytes = dest.read_bytes() if dest.exists() else None
                raw = src.read_text(encoding="utf-8")
                body, serr = prepare_migrated_canonical(
                    raw, stem=stem, domain=dest_dom, facts_dir=None)
                if serr:
                    raise WriteRefused("migrate apply schema: " + serr)
                staged.append((stem, src, dest_dom, dest, body, src_hash, old_bytes, facts_dir, tomb))
            overlay_by_dir: dict = {}
            for stem, src, dest_dom, dest, body, src_hash, old_bytes, facts_dir, tomb in staged:
                overlay_by_dir.setdefault(str(facts_dir), {})[stem] = body
            for stem, src, dest_dom, dest, body, src_hash, old_bytes, facts_dir, tomb in staged:
                fm_m = _fm_m(body)
                lerr = validate_links(body, str(fm_m.get("scope") or ""), facts_dir,
                                      overlay=overlay_by_dir.get(str(facts_dir)) or {})
                if lerr:
                    raise WriteRefused("migrate apply links: " + lerr)
                temps[str(dest)] = body
                if dest.exists():
                    dest_modes[str(dest)] = "replace"
                    expected[str(dest)] = _sha256_file(dest)
                else:
                    dest_modes[str(dest)] = "create"
                    expected[str(dest)] = _ABS
                fid = _sf_m(dest_dom, stem)
                old_row = conn.execute(
                    "SELECT fact_id, stem, domain_id, canonical_path, revision, status, "
                    "sensitivity FROM facts WHERE fact_id=?", (fid,)).fetchone()
                ops.append({
                    "op": "fact_upsert", "fact_id": fid, "stem": stem,
                    "domain_id": dest_dom, "canonical_path": str(dest),
                    "revision": _sem_m(body),
                    "status": str(fm_m.get("status") or "active"),
                    "sensitivity": _fs_m(fm_m),
                })
                if tomb:
                    ops.append({"op": "tombstone_delete", "fact_id": fid})
                    ops.append({"op": "fact_status_change", "fact_id": fid,
                                "status": "active"})
                dispositions.append({
                    "stem": stem,
                    "disposition": "replaced" if dest.exists() else "migrated",
                    "path": str(dest),
                    "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "fact_id": fid, "domain": dest_dom,
                    "status": str(fm_m.get("status") or "active"),
                    "revision": _sem_m(body),
                })
                copied.append({
                    "path": str(dest),
                    "new_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "old_sha256": None if old_bytes is None else hashlib.sha256(old_bytes).hexdigest(),
                    "old_bytes_b64": None if old_bytes is None else _b64(old_bytes),
                    "source": str(src),
                    "source_sha256": src_hash,
                    "domain": dest_dom,
                    "fact_id": fid,
                    "old_fact": dict(old_row) if old_row is not None else None,
                })
                catalogs.setdefault(str(facts_dir), set()).add(stem)
            overlay = {c["path"]: temps.get(c["path"], "") for c in copied}
            for pth, txt in temps.items():
                if str(pth).endswith(".md") and Path(pth).name != "MEMORY.md":
                    overlay.setdefault(pth, txt)
            catalog_snaps: list = []
            for facts_dir_s, stems in catalogs.items():
                facts_dir = Path(facts_dir_s)
                stem_overlay = {Path(p).name: t for p, t in overlay.items()
                                if Path(p).parent == facts_dir}
                catp = facts_dir / "MEMORY.md"
                old_cat_b = catp.read_bytes() if catp.exists() else None
                cat = generate_catalog(facts_dir, overlay=stem_overlay)
                new_cat = cat if cat.endswith("\n") else cat + "\n"
                catalog_snaps.append({
                    "path": str(catp),
                    "old_bytes_b64": None if old_cat_b is None else _b64(old_cat_b),
                    "old_sha256": None if old_cat_b is None else hashlib.sha256(old_cat_b).hexdigest(),
                    "new_sha256": hashlib.sha256(new_cat.encode("utf-8")).hexdigest(),
                })
                temps[str(catp)] = new_cat
                dest_modes[str(catp)] = "replace" if catp.exists() else "create"
                if not catp.exists():
                    expected[str(catp)] = _ABS
                elif str(catp) not in expected:
                    expected[str(catp)] = _sha256_file(catp)
            copied_holder.extend(copied)
            catalog_holder.extend(catalog_snaps)
            rb = {
                "mode_before": "dual-read",
                "copied": list(copied),
                "catalogs": list(catalog_snaps),
                "allowed_roots": [str(droot)],
            }
            rb_path = ctx.plugin_data_dir / "migrate-rollback.json"
            temps[str(rb_path)] = json.dumps(rb, indent=2) + "\n"
            plan_next = dict(plan)
            plan_next["applied"] = True
            plan_next["finalized"] = False
            plan_path = ctx.plugin_data_dir / "migrate-plan.json"
            temps[str(plan_path)] = json.dumps(plan_next, indent=2) + "\n"
            if plan_path.exists():
                expected[str(plan_path)] = _sha256_file(plan_path)
            dest_modes[str(plan_path)] = "replace" if plan_path.exists() else "create"
            if not plan_path.exists():
                expected[str(plan_path)] = _ABS
            man = {
                "migration_id": str(plan.get("migration_id") or ""),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "dispositions": dispositions,
            }
            man_path = ctx.plugin_data_dir / "migrate-manifest.json"
            temps[str(man_path)] = json.dumps(man, indent=2, sort_keys=True) + "\n"
            dest_modes[str(man_path)] = "replace" if man_path.exists() else "create"
            if man_path.exists():
                expected[str(man_path)] = _sha256_file(man_path)
            else:
                expected[str(man_path)] = _ABS
            ops.append({"op": "migration_state_set", "value": "dual-read"})
            return {"copied": [c["path"] for c in copied],
                    "dest_modes": dest_modes, "expected_revisions": expected,
                    "registry_ops": ops}

        try:
            transact(ctx, "migrate-apply", {"n": len(to_copy)}, mutate,
                     extra_domains=sorted({d for _, _, d, _ in to_copy}))
        except WriteRefused as e:
            print(f"migrate apply: {e}", file=sys.stderr)
            return 2
        print(f"migrate apply: copied {len(copied_holder)} fact(s) into assigned domains")
        print("  dual-read remains until --finalize")
        print(f"  rollback file: {ctx.plugin_data_dir / 'migrate-rollback.json'}")
        return 0

    if stage == "rollback":
        try:
            assert_mutation_allowed(ctx)
        except WriteRefused as e:
            print(f"migrate rollback: {e}", file=sys.stderr)
            return 2
        _mc_rb = connect_if_exists(db_path(ctx))
        _mode_rb = "dual-read"
        try:
            if _mc_rb is not None:
                from control_plane import get_migration_mode as _gmm_rb
                _mode_rb = _gmm_rb(_mc_rb)
        finally:
            if _mc_rb is not None:
                _mc_rb.close()
        if plan.get("finalized") or _mode_rb == "enforced":
            print("migrate rollback: already finalized; refused", file=sys.stderr)
            return 2
        got_rb = str(getattr(args, "confirm", None) or "")
        if got_rb != "migrate-rollback":
            if not got_rb:
                print("migrate rollback: dry (pass --rollback --confirm migrate-rollback)")
                return 0
            print("migrate rollback: pass --confirm migrate-rollback", file=sys.stderr)
            return 2
        rb_path = ctx.plugin_data_dir / "migrate-rollback.json"
        if not rb_path.exists():
            print("migrate rollback: no rollback file", file=sys.stderr)
            return 1
        rb = json.loads(rb_path.read_text(encoding="utf-8"))
        allowed = [Path(p) for p in (rb.get("allowed_roots") or [])]
        if not allowed:
            allowed = [ctx.config_root / "consolidate-memory" / "domains"]

        def mutate(conn, temps):
            from control_plane import ABSENT as _ABS_RB
            set_migration_mode(conn, str(rb.get("mode_before") or "dual-read"))
            deletes: list = []
            dest_modes: dict = {}
            expected: dict = {}
            ops: list = [{"op": "migration_state_set",
                          "value": str(rb.get("mode_before") or "dual-read")}]
            conflicts: list = []
            planned: list = []

            def _classify(path: Path, want: str, old_b64, old_fact, fact_id: str) -> None:
                if not path or not _contained_under(path, allowed):
                    conflicts.append(str(path))
                    return
                live = _sha256_file(path) if path.exists() else ""
                if path.exists() and want and live not in (want, ""):
                    conflicts.append(str(path))
                    return
                planned.append((path, want, old_b64, old_fact, fact_id, live))

            for item in rb.get("copied") or []:
                if isinstance(item, str):
                    _classify(Path(item), "", None, None, "")
                else:
                    _classify(Path(str(item.get("path") or "")),
                              str(item.get("new_sha256") or ""),
                              item.get("old_bytes_b64") or item.get("old_text"),
                              item.get("old_fact"),
                              str(item.get("fact_id") or ""))
            for cat in rb.get("catalogs") or []:
                _classify(Path(str(cat.get("path") or "")),
                          str(cat.get("new_sha256") or ""),
                          cat.get("old_bytes_b64") if "old_bytes_b64" in cat else cat.get("old_text"),
                          None, "")
            if conflicts:
                raise WriteRefused(
                    "rollback conflicted (no files changed): " + ", ".join(conflicts[:8]))
            for path, want, old_b64, old_fact, fact_id, live in planned:
                if want:
                    expected[str(path)] = want
                old_bytes = None
                if isinstance(old_b64, (bytes, bytearray)):
                    old_bytes = bytes(old_b64)
                elif isinstance(old_b64, str) and old_b64:
                    old_bytes = _unb64(old_b64)
                    if old_bytes is None:
                        old_bytes = old_b64.encode("utf-8")
                if old_bytes is not None:
                    temps[str(path)] = old_bytes
                    dest_modes[str(path)] = "replace" if path.exists() else "create"
                    if not path.exists():
                        expected[str(path)] = _ABS_RB
                    if old_fact:
                        ops.append({
                            "op": "fact_upsert",
                            "fact_id": str(old_fact.get("fact_id") or fact_id),
                            "stem": str(old_fact.get("stem") or path.stem),
                            "domain_id": str(old_fact.get("domain_id") or ""),
                            "canonical_path": str(old_fact.get("canonical_path") or path),
                            "revision": str(old_fact.get("revision") or ""),
                            "status": str(old_fact.get("status") or "active"),
                            "sensitivity": str(old_fact.get("sensitivity") or "internal"),
                        })
                    elif fact_id:
                        ops.append({"op": "fact_delete", "fact_id": fact_id})
                else:
                    if path.exists():
                        deletes.append({"path": str(path), "preimage": want or live})
                    if fact_id:
                        ops.append({"op": "fact_delete", "fact_id": fact_id})
            plan_next = dict(plan)
            plan_next["applied"] = False
            plan_next["finalized"] = False
            plan_path = ctx.plugin_data_dir / "migrate-plan.json"
            temps[str(plan_path)] = json.dumps(plan_next, indent=2) + "\n"
            dest_modes[str(plan_path)] = "replace" if plan_path.exists() else "create"
            if plan_path.exists():
                expected[str(plan_path)] = _sha256_file(plan_path)
            else:
                expected[str(plan_path)] = _ABS_RB
            return {"deletes": deletes, "dest_modes": dest_modes,
                    "expected_revisions": expected, "registry_ops": ops}

        try:
            transact(ctx, "migrate-rollback", {"n": len(rb.get("copied") or [])}, mutate)
        except WriteRefused as e:
            print(f"migrate rollback: {e}", file=sys.stderr)
            return 2
        print("migrate rollback: restored dual-read, catalogs, and fact rows")
        return 0

    if stage == "finalize":
        try:
            assert_mutation_allowed(ctx)
        except WriteRefused as e:
            print(f"migrate finalize: {e}", file=sys.stderr)
            return 2
        if _unresolved_migrate(plan):
            print("migrate finalize: unresolved facts remain", file=sys.stderr)
            return 2
        if not plan.get("applied"):
            print("migrate finalize: apply first", file=sys.stderr)
            return 2
        man_fin = ctx.plugin_data_dir / "migrate-manifest.json"
        if not man_fin.is_file():
            print("migrate finalize: missing immutable migrate-manifest.json",
                  file=sys.stderr)
            return 2
        try:
            manifest = json.loads(man_fin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            print("migrate finalize: unreadable migrate-manifest.json", file=sys.stderr)
            return 2
        plan_mid = str(plan.get("migration_id") or "")
        man_mid = str(manifest.get("migration_id") or "")
        if not plan_mid or not man_mid or plan_mid != man_mid:
            print("migrate finalize: migration_id mismatch", file=sys.stderr)
            return 2
        by_stem = {str(d.get("stem") or ""): d
                   for d in (manifest.get("dispositions") or []) if isinstance(d, dict)}
        from fact_schema import CLASS_ACTIVE, CLASS_INACTIVE, classify_canonical
        from control_plane import connect as _cf, db_path as _df
        _fconn = _cf(_df(ctx))
        try:
            for stem, row in sorted((plan.get("facts") or {}).items()):
                assignment = str((row or {}).get("assignment") or "")
                disp = by_stem.get(stem)
                if disp is None:
                    print(f"migrate finalize: no disposition for {stem}", file=sys.stderr)
                    return 2
                kind = str(disp.get("disposition") or "")
                if assignment == "excluded":
                    if kind != "excluded":
                        print(f"migrate finalize: {stem} assigned excluded, "
                              f"disposition {kind}", file=sys.stderr)
                        return 2
                    continue
                if kind not in ("migrated", "kept-existing", "replaced"):
                    print(f"migrate finalize: {stem} unexpected disposition {kind}",
                          file=sys.stderr)
                    return 2
                p = Path(str(disp.get("path") or ""))
                if not p.is_file():
                    print(f"migrate finalize: missing dest {p}", file=sys.stderr)
                    return 2
                want = str(disp.get("sha256") or "")
                if want and _sha256_file(p) != want:
                    print(f"migrate finalize: dest hash mismatch {p}", file=sys.stderr)
                    return 2
                live = p.read_text(encoding="utf-8", errors="replace")
                cls = classify_canonical(
                    live, stem=stem, domain=str(disp.get("domain") or ""))
                if cls["class"] not in (CLASS_ACTIVE, CLASS_INACTIVE):
                    print(f"migrate finalize: {stem} is not a valid v3 canonical "
                          f"({cls.get('error')})", file=sys.stderr)
                    return 2
                fm = cls.get("fm") or {}
                if str(fm.get("domain") or "") != str(disp.get("domain") or ""):
                    print(f"migrate finalize: {stem} domain mismatch", file=sys.stderr)
                    return 2
                fid = str(disp.get("fact_id") or "")
                rowf = _fconn.execute(
                    "SELECT fact_id, status, domain_id FROM facts WHERE fact_id=?",
                    (fid,)).fetchone() if fid else None
                if rowf is None:
                    print(f"migrate finalize: missing registry row for {stem}",
                          file=sys.stderr)
                    return 2
                if str(rowf["status"] or "") != str(fm.get("status") or ""):
                    print(f"migrate finalize: {stem} registry status mismatch",
                          file=sys.stderr)
                    return 2
                if str(rowf["domain_id"] or "") != str(disp.get("domain") or ""):
                    print(f"migrate finalize: {stem} registry domain mismatch",
                          file=sys.stderr)
                    return 2
                want_rev = str(disp.get("revision") or "")
                if want_rev:
                    from mirror_conflict import semantic_hash as _sem_fin
                    if _sem_fin(live) != want_rev:
                        print(f"migrate finalize: {stem} revision mismatch",
                              file=sys.stderr)
                        return 2
                if str(rowf["status"] or "") == "active" and cls["class"] != CLASS_ACTIVE:
                    print(f"migrate finalize: {stem} registry active but file is not",
                          file=sys.stderr)
                    return 2
                if cls["class"] == CLASS_ACTIVE:
                    cat = p.parent / "MEMORY.md"
                    hook = f"]({stem}.md)"
                    if not cat.is_file() or hook not in cat.read_text(
                            encoding="utf-8", errors="replace"):
                        print(f"migrate finalize: active {stem} missing catalog pointer",
                              file=sys.stderr)
                        return 2
        finally:
            _fconn.close()
        rb_fin = ctx.plugin_data_dir / "migrate-rollback.json"
        if rb_fin.exists():
            try:
                rbv = json.loads(rb_fin.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                rbv = {}
            for item in list(rbv.get("copied") or []) + list(rbv.get("catalogs") or []):
                if not isinstance(item, dict):
                    continue
                p = Path(str(item.get("path") or ""))
                want = str(item.get("new_sha256") or "")
                if not p.is_file():
                    print(f"migrate finalize: missing dest {p}", file=sys.stderr)
                    return 2
                if want and _sha256_file(p) != want:
                    print(f"migrate finalize: dest hash mismatch {p}", file=sys.stderr)
                    return 2
        def mutate(conn, temps):
            del temps
            deletes: list = []
            expected: dict = {}
            rb_del = ctx.plugin_data_dir / "migrate-rollback.json"
            if rb_del.is_file():
                h = _sha256_file(rb_del)
                deletes.append({"path": str(rb_del), "preimage": h})
                if h:
                    expected[str(rb_del)] = h
            set_migration_mode(conn, "enforced")
            return {"registry_ops": [{"op": "migration_state_set", "value": "enforced"}],
                    "deletes": deletes, "expected_revisions": expected}
        try:
            transact(ctx, "migrate-finalize", {"applied": True}, mutate)
        except WriteRefused as e:
            print(f"migrate finalize: {e}", file=sys.stderr)
            return 2
        plan["finalized"] = True
        _save_migrate_plan(ctx, plan)
        print("migrate finalize: dual-read closed (mode=enforced)")
        return 0

    print(f"migrate: unknown stage {stage!r}", file=sys.stderr)
    return 2


def cmd_data(args: argparse.Namespace) -> int:
    from control_plane import connect, connect_if_exists, db_path
    from retention import (compact_jsonl, CYCLE_CAP, EVENT_RETENTION_DAYS, export_ops,
                           inventory, purge_domain, purge_project,
                           retention_show)
    ctx = _ctx(args.project)
    if args.data_cmd == "inventory":
        inv = inventory(ctx.plugin_data_dir, ctx.canonical_domain_dir, ctx.native_memory_dir)
        print(json.dumps(inv, indent=2) if args.json else
              f"control_plane: {inv['control_plane']}\n"
              f"canonical:     {inv['canonical']}\n"
              f"native:        {inv['native']}\n"
              f"native_clean:  {inv['native_clean']}\n"
              f"canonical_inside_plugin_data: {inv['canonical_inside_plugin_data']}")
        return 0
    if args.data_cmd == "retention":
        print(json.dumps(retention_show(), indent=2))
        return 0
    if args.data_cmd == "compact":
        from retention import (cycle_log_write_path, fleet_ledger_write_path,
                               mutation_log_write_path)
        cycle = cycle_log_write_path(ctx.native_memory_dir, plugin_data=ctx.plugin_data_dir)
        mut = mutation_log_write_path(ctx.native_memory_dir, plugin_data=ctx.plugin_data_dir)
        fleet = fleet_ledger_write_path(plugin_data=ctx.plugin_data_dir)
        plan = {
            "cycle_log": str(cycle),
            "mutation_log": str(mut),
            "fleet_ledger": str(fleet),
            "keep": CYCLE_CAP,
            "older_than_days": EVENT_RETENTION_DAYS,
        }
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print(f"compact plan: tail {CYCLE_CAP} of cycle/mutation/fleet logs "
                  f"(drop events > {EVENT_RETENTION_DAYS}d)")
            print(f"  cycle:    {cycle}")
            print(f"  mutation: {mut}")
            print(f"  fleet:    {fleet}")
        if args.apply:
            need_c = _want_confirm(args, "compact-apply")
            if need_c == "dry":
                print("compact: dry (pass --apply --confirm compact-apply)")
                return 0
            if need_c:
                print(f"data compact: {need_c}", file=sys.stderr)
                return 2
            from retention import _with_ops_lock, relocate_native_operational
            from control_plane import compact_journal as _jcompact
            lock = None
            try:
                lock = _with_ops_lock(ctx.plugin_data_dir)
            except Exception as e:
                print(f"data compact: ops lock: {e}", file=sys.stderr)
                return 2
            try:
                relocated = relocate_native_operational(
                    ctx.native_memory_dir, ctx.plugin_data_dir, ctx.project_id)
                results = []
                for p in (cycle, mut, fleet):
                    if p.is_file():
                        results.append(compact_jsonl(p, keep=CYCLE_CAP,
                                                     older_than_days=EVENT_RETENTION_DAYS))
                jout = _jcompact(ctx)
            finally:
                if lock is not None:
                    lock.release()
            print(json.dumps({"ok": True, "relocated_from_native": relocated,
                              "compacted": results, "journal": jout}))
        return 0
    if args.data_cmd == "export":
        dest = Path(args.dest or (ctx.plugin_data_dir / "export.json"))
        print(json.dumps(export_ops(ctx.plugin_data_dir, dest), indent=2))
        return 0
    if args.data_cmd == "import":
        from retention import import_ops as _import_ops
        src = Path(getattr(args, "file", None) or "")
        # v0.4.0 review: this command's --json success path emitted an envelope
        # while its error paths printed bare stderr — standardize both.
        def _imp_err(msg: str) -> int:
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": msg, "code": 2}))
            else:
                print("data import: " + msg, file=sys.stderr)
            return 2
        if not src or not str(src):
            return _imp_err("pass --file ARCHIVE.tar.gz")
        dest = Path(args.dest) if args.dest else ctx.plugin_data_dir
        need = _want_confirm(args, "data-import")
        if need == "dry":
            print("data import plan: %s → %s (pass --apply --confirm data-import)"
                  % (src, dest))
            return 0
        if need:
            return _imp_err(need)
        out = _import_ops(src, dest)
        print(json.dumps(out, indent=2 if args.json else None, default=str))
        return 0 if out.get("ok") else 2
    if args.data_cmd in ("purge-status", "purge-resume", "purge-cancel"):
        from identifiers import IdentifierRefused, validate_domain_id
        did = getattr(args, "purge_domain", None) or ctx.domain_id
        if not did or did == "unknown":
            print(f"data {args.data_cmd}: pass --domain NAME", file=sys.stderr)
            return 2
        try:
            did = validate_domain_id(did)
        except IdentifierRefused as e:
            print(f"data {args.data_cmd}: {e}", file=sys.stderr)
            return 2
        if args.data_cmd == "purge-status":
            print(json.dumps(domain_purge_status(ctx, did), indent=2 if args.json else None,
                             default=str))
            return 0
        from control_plane import assert_mutation_allowed
        try:
            assert_mutation_allowed(ctx)
        except WriteRefused as e:
            print(f"data {args.data_cmd}: {e}", file=sys.stderr)
            return 2
        phrase = f"{args.data_cmd}-{did}"
        need = _want_confirm(args, phrase)
        if need == "dry":
            print(f"{args.data_cmd} plan: domain={did} "
                  f"(pass --apply --confirm {phrase})")
            return 0
        if need:
            print(f"data {args.data_cmd}: {need}", file=sys.stderr)
            return 2
        try:
            if args.data_cmd == "purge-resume":
                out = domain_purge_resume(ctx, did)
            else:
                out = domain_purge_cancel(
                    ctx, did, accept_partial=bool(getattr(args, "accept_partial", False)))
        except WriteRefused as e:
            print(f"data {args.data_cmd}: {e}", file=sys.stderr)
            return 2
        print(json.dumps(out, default=str))
        return 0
    if args.data_cmd == "purge":
        from control_plane import assert_mutation_allowed
        from identifiers import IdentifierRefused, validate_domain_id, validate_project_id
        try:
            assert_mutation_allowed(ctx)
        except WriteRefused as e:
            print(f"data purge: {e}", file=sys.stderr)
            return 2
        if args.purge_project:
            try:
                args.purge_project = validate_project_id(args.purge_project)
            except IdentifierRefused as e:
                print(f"data purge: {e}", file=sys.stderr)
                return 2
        if args.purge_domain:
            try:
                args.purge_domain = validate_domain_id(args.purge_domain)
            except IdentifierRefused as e:
                print(f"data purge: {e}", file=sys.stderr)
                return 2
        scope = getattr(args, "purge_scope", None)
        if not scope:
            if args.purge_project:
                scope = "project-ops"
            elif args.purge_domain:
                scope = "domain-canonicals"
        if not scope:
            print("data purge: pass --scope or --project-id/--domain", file=sys.stderr)
            return 2
        phrase = f"purge-{scope}"
        need = _want_confirm(args, phrase)
        if need == "dry":
            print(f"purge plan: scope={scope} (pass --apply --confirm {phrase})")
            return 0
        if need:
            print(f"data purge: {need}", file=sys.stderr)
            return 2
        # v0.4.0 review: resuming an all-plugin-data purge after plugin-data was
        # already deleted must not MINT a fresh control.sqlite (connect() creates
        # the dir/DB the state machine then re-deletes) — read-only if absent.
        conn = connect_if_exists(db_path(ctx))
        if conn is None and scope != "all-plugin-data":
            print(f"data purge: control.sqlite absent (scope={scope})", file=sys.stderr)
            return 2
        try:
            if scope == "managed-mirrors":
                n = _revoke_unadmitted_mirrors(ctx, "unknown")
                print(json.dumps({"ok": True, "scope": scope, "revoked": n,
                                  "native_untouched": True}))
                return 0
            if scope == "project-ops":
                pid = args.purge_project or ctx.project_id
                native: Optional[Path] = ctx.native_memory_dir
                if conn is None:  # reachable only via the type — scopes that need the DB refuse above
                    return 2
                if args.purge_project and args.purge_project != ctx.project_id:
                    row = conn.execute(
                        "SELECT native_memory_dir FROM projects WHERE project_id=?",
                        (pid,)).fetchone()
                    native = (Path(row["native_memory_dir"])
                              if row and row["native_memory_dir"] else None)
                print(json.dumps(purge_project(ctx.plugin_data_dir, pid, native)))
                return 0
            if scope == "domain-canonicals":
                did = args.purge_domain or ctx.domain_id
                if did == "unknown" or not did:
                    print("data purge: domain-canonicals requires a named domain",
                          file=sys.stderr)
                    return 2
                try:
                    out = _run_domain_purge(ctx, did)
                except WriteRefused as e:
                    print(f"data purge: {e}", file=sys.stderr)
                    return 2
                print(json.dumps(out))
                return 0
            if scope == "all-plugin-data":
                from control_plane import transact as _tx_all
                if conn is not None:
                    rows = _enrolled_rows(conn)
                else:
                    # plugin-data (and its DB) already deleted by the interrupted
                    # purge — the remaining stages are fence-driven FS work.
                    rows = []
                pids = [str(r["project_id"]) for r in rows]
                if ctx.project_id not in pids:
                    pids.append(ctx.project_id)
                seen_dom: list = []
                for r in rows:
                    did_r = str(r["domain_id"] or "")
                    if did_r and did_r != "unknown" and did_r not in seen_dom:
                        seen_dom.append(did_r)
                try:
                    if conn is not None and not _incomplete_purge_fences(ctx) and seen_dom:
                        def _mark_all(_c, _t):
                            del _c, _t
                            return {"registry_ops": [
                                {"op": "domain_status_set", "domain_id": d,
                                 "status": "deleting"} for d in seen_dom]}
                        _tx_all(ctx, "domain-deleting", {"domains": seen_dom}, _mark_all,
                                extra_domains=seen_dom, extra_project_ids=pids)
                    out = run_all_plugin_data_purge(
                        ctx, rows=rows, seen_dom=seen_dom, pids=pids)
                except WriteRefused as e:
                    print(f"data purge: {e}", file=sys.stderr)
                    return 2
                print(json.dumps(out, default=str))
                return 0 if out.get("ok") else 2
            print("data purge: unknown scope", file=sys.stderr)
            return 2
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
    return 2


def _want_confirm(args: argparse.Namespace, phrase: str) -> Optional[str]:
    """`--apply` always requires the exact confirmation phrase (TTY or not)."""
    if not getattr(args, "apply", False):
        return "dry"
    got = str(getattr(args, "confirm", None) or "")
    if got != phrase:
        return (f"pass --apply --confirm {phrase}")
    return None


def cmd_journal(args: argparse.Namespace) -> int:
    from control_plane import (compact_journal, connect_journal, journal_abandon,
                               journal_cleanup, journal_inventory, journal_retry,
                               journal_rollback, journal_show)
    ctx = _ctx(args.project)
    cmd = args.journal_cmd
    if cmd == "inventory":
        conn = connect_journal(ctx)
        try:
            rows = journal_inventory(conn)
        finally:
            conn.close()
        if args.json:
            print(json.dumps(rows, indent=2))
        elif not rows:
            print("(empty journal)")
        else:
            for r in rows:
                body = " body" if r.get("has_body") else ""
                print(f"{r['op_id']}  {r['status']:12}  {r['kind']}  "
                      f"p={r['publishes']} d={r['deletes']}{body}")
        return 0
    if cmd == "show":
        if not args.op_id:
            print("journal show: pass OP-ID", file=sys.stderr)
            return 2
        conn = connect_journal(ctx)
        try:
            row = journal_show(conn, args.op_id)
        finally:
            conn.close()
        if row is None:
            print("journal show: unknown op", file=sys.stderr)
            return 2
        print(json.dumps(row, indent=2, default=str))
        return 0
    if cmd == "compact":
        need = _want_confirm(args, "journal-compact")
        if need == "dry":
            print("journal compact: redact completed payloads, collapse 90-day "
                  "receipts, expire recovery "
                  "(pass --apply --confirm journal-compact)")
            return 0
        if need:
            print(f"journal compact: {need}", file=sys.stderr)
            return 2
        print(json.dumps(compact_journal(ctx)))
        return 0
    if cmd == "cleanup":
        all_stores = bool(getattr(args, "scan_all_stores", False))
        if not args.apply:
            out = journal_cleanup(ctx, apply=False, all_stores=all_stores)
            print(json.dumps(out, indent=2, default=str))
            return 0
        need = _want_confirm(args, "journal-cleanup")
        if need:
            print(f"journal cleanup: {need}", file=sys.stderr)
            return 2
        out = journal_cleanup(ctx, apply=True, all_stores=all_stores)
        print(json.dumps(out, default=str))
        return 0 if out.get("ok") else 2
    if not args.op_id:
        print(f"journal {cmd}: pass OP-ID", file=sys.stderr)
        return 2
    phrase = f"journal-{cmd}"
    need = _want_confirm(args, phrase)
    if need == "dry":
        print(f"journal {cmd} {args.op_id} (pass --apply --confirm {phrase})")
        return 0
    if need:
        print(f"journal {cmd}: {need}", file=sys.stderr)
        return 2
    try:
        if cmd == "retry":
            out = journal_retry(ctx, args.op_id)
        elif cmd == "rollback":
            out = journal_rollback(ctx, args.op_id)
        else:
            out = journal_abandon(ctx, args.op_id,
                                  accept_fs=bool(getattr(args, "accept_fs", False)))
    except WriteRefused as e:
        print(f"journal {cmd}: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out))
    return 0


def cmd_project(args: argparse.Namespace) -> int:
    from control_plane import (assert_mutation_allowed, connect, connect_if_exists,
                               db_path, enroll_project, enrolled_domain,
                               project_upsert_op, record_project_alias, transact,
                               unenroll_project, upsert_project)
    from identifiers import IdentifierRefused, validate_domain_id
    ctx = _ctx(args.project)
    if args.project_cmd == "grants":
        from store_context import load_store_grants
        rows = load_store_grants(ctx.plugin_data_dir)
        print(json.dumps({"ok": True, "grants": rows}, indent=2 if args.json else None))
        return 0
    if args.project_cmd in ("grant-native", "revoke-native", "transfer-native"):
        from store_context import revoke_store_grant, transfer_store_grant, write_store_grant
        # v0.4.0 review (#11): every error exit in the grant family emits the
        # machine-readable envelope under --json (not just the WriteRefused).
        def _grant_err(msg: str) -> int:
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": msg, "code": 2}))
            else:
                print(f"project {args.project_cmd}: {msg}", file=sys.stderr)
            return 2
        path_s = str(getattr(args, "grant_path", None) or "").strip()
        if not path_s:
            return _grant_err("pass --path")
        if not (path_s.startswith("~/") or path_s.startswith("/")):
            return _grant_err("path must be absolute or ~/")
        path = Path(path_s).expanduser()
        phrase = args.project_cmd
        need = _want_confirm(args, phrase)
        if need == "dry":
            print(f"{args.project_cmd} plan: {ctx.project_id} → {path} "
                  f"(pass --apply --confirm {phrase})")
            return 0
        if need:
            return _grant_err(need)
        try:
            if args.project_cmd == "grant-native":
                out = write_store_grant(
                    ctx.plugin_data_dir, ctx.project_id, path,
                    config_root=ctx.config_root,
                    adopt=bool(getattr(args, "adopt", False)))
            elif args.project_cmd == "transfer-native":
                to_pid = str(getattr(args, "to_domain", None) or "")
                if not to_pid:
                    return _grant_err("pass --to PROJECT_ID")
                out = transfer_store_grant(ctx.plugin_data_dir, path, to_pid)
            else:
                out = revoke_store_grant(ctx.plugin_data_dir, ctx.project_id, path)
        except WriteRefused as e:
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": str(e), "code": 2}))
            else:
                print(f"project {args.project_cmd}: {e}", file=sys.stderr)
            return 2
        print(json.dumps(out))
        return 0
    if args.project_cmd == "show":
        conn_ro = connect_if_exists(db_path(ctx))
        try:
            got = enrolled_domain(conn_ro, ctx.project_id) if conn_ro else None
            payload = {
                "project_id": ctx.project_id,
                "domain_id": ctx.domain_id,
                "requested_domain": ctx.requested_domain,
                "enrolled": bool(got) or ctx.enrolled,
                "enrolled_domain": got,
            }
            print(json.dumps(payload, indent=2) if args.json else
                  f"project {ctx.display_name}\n  project_id: {ctx.project_id}\n"
                  f"  domain_id: {ctx.domain_id}\n  enrolled: {payload['enrolled']}\n"
                  f"  requested_domain: {ctx.requested_domain}")
            return 0
        finally:
            if conn_ro is not None:
                conn_ro.close()
    if args.project_cmd in ("enroll", "unenroll", "move-domain", "rebind"):
        try:
            assert_mutation_allowed(ctx)
        except WriteRefused as e:
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": str(e), "code": 2}))
            else:
                print(f"project {args.project_cmd}: {e}", file=sys.stderr)
            return 2
        # Dry-run / plan must not mint control.sqlite (connect() runs SCHEMA_SQL).
        ro = connect_if_exists(db_path(ctx))
        try:
            if args.project_cmd == "enroll":
                if not args.domain:
                    print("project enroll: pass --domain", file=sys.stderr)
                    return 2
                try:
                    d = validate_domain_id(args.domain)
                except IdentifierRefused as e:
                    print(f"project enroll: {e}", file=sys.stderr)
                    return 2
                current = enrolled_domain(ro, ctx.project_id) if ro else None
                from control_plane import domain_lifecycle as _dlife
                dest_life = _dlife(ro, d) if ro is not None else "active"
                if dest_life in ("deleting", "deleted"):
                    print(f"project enroll: domain {d} is {dest_life}", file=sys.stderr)
                    return 2
                if current and current != d:
                    print(f"project enroll: already enrolled in {current}; "
                          f"use `cm project move-domain --to {d}`", file=sys.stderr)
                    return 2
                if current == d:
                    print(f"project enroll: already in {d}")
                    return 0
                plan = _mirror_plan_for_dest(ctx, d)
                n_plan = len(plan["deletes"]) + len(plan["quarantine"])
                print(f"enroll plan: {ctx.project_id} → domain {d} "
                      f"(revoke {n_plan} unadmitted mirror(s), "
                      f"quarantine {len(plan['quarantine'])})")
                need = _want_confirm(args, f"enroll-{d}")
                if need == "dry":
                    print("  dry (pass --apply --confirm enroll-<domain>)")
                    return 0
                if need:
                    print(f"project enroll: {need}", file=sys.stderr)
                    return 2
                ops = [
                    project_upsert_op(ctx, domain_id=d, status="enrolled"),
                    {"op": "project_domain_change", "project_id": ctx.project_id,
                     "domain_id": d, "status": "enrolled"},
                ]
                try:
                    n = _revoke_unadmitted_mirrors(
                        ctx, d, extra_registry_ops=ops, extra_domains=[d],
                        prepare=lambda c: enroll_project(c, ctx, d))
                except WriteRefused as e:
                    print(f"project enroll: {e}", file=sys.stderr)
                    return 2
                print(f"enrolled {ctx.project_id} → domain {d}; revoked {n} unauthorized mirror(s)")
                return 0
            if args.project_cmd == "move-domain":
                dest = args.to_domain or args.domain
                if not dest:
                    print("project move-domain: pass --to DOMAIN", file=sys.stderr)
                    return 2
                try:
                    dest = validate_domain_id(dest)
                except IdentifierRefused as e:
                    print(f"project move-domain: {e}", file=sys.stderr)
                    return 2
                current = enrolled_domain(ro, ctx.project_id) if ro else None
                from control_plane import domain_lifecycle as _dlife_m
                dest_life = _dlife_m(ro, dest) if ro is not None else "active"
                if dest_life in ("deleting", "deleted"):
                    print(f"project move-domain: domain {dest} is {dest_life}",
                          file=sys.stderr)
                    return 2
                if not current:
                    print("project move-domain: not enrolled; use enroll", file=sys.stderr)
                    return 2
                if current == dest:
                    print(f"project move-domain: already in {dest}")
                    return 0
                plan = _mirror_plan_for_dest(ctx, dest)
                n_plan = len(plan["deletes"]) + len(plan["quarantine"])
                print(f"move-domain plan: {current} → {dest} "
                      f"(revoke {n_plan}, quarantine {len(plan['quarantine'])})")
                need = _want_confirm(args, f"move-{current}-to-{dest}")
                if need == "dry":
                    print("  dry (pass --apply --confirm move-<from>-to-<to>)")
                    return 0
                if need:
                    print(f"project move-domain: {need}", file=sys.stderr)
                    return 2

                def _prep_move(c):
                    c.execute(
                        "UPDATE projects SET domain_id=?, status='enrolled' WHERE project_id=?",
                        (dest, ctx.project_id))
                ops = [{"op": "project_domain_change", "project_id": ctx.project_id,
                        "domain_id": dest, "status": "enrolled"}]
                n = _revoke_unadmitted_mirrors(
                    ctx, dest, extra_registry_ops=ops,
                    extra_domains=[current, dest], prepare=_prep_move)
                print(f"moved {ctx.project_id} {current} → {dest}; revoked {n} unauthorized mirror(s)")
                return 0
            if args.project_cmd == "unenroll":
                current = (enrolled_domain(ro, ctx.project_id) if ro else None) or ctx.domain_id
                if not (ro and enrolled_domain(ro, ctx.project_id)):
                    print("project unenroll: not enrolled")
                    return 2
                plan = _mirror_plan_for_dest(ctx, "unknown")
                n_plan = len(plan["deletes"]) + len(plan["quarantine"])
                print(f"unenroll plan: leave {current} (revoke {n_plan} managed mirror(s), "
                      f"quarantine {len(plan['quarantine'])})")
                need = _want_confirm(args, f"unenroll-{current}")
                if need == "dry":
                    print("  dry (pass --apply --confirm unenroll-<domain>)")
                    return 0
                if need:
                    print(f"project unenroll: {need}", file=sys.stderr)
                    return 2
                ops = [{"op": "project_domain_change", "project_id": ctx.project_id,
                        "domain_id": "unknown", "status": "active"}]
                n = _revoke_unadmitted_mirrors(
                    ctx, "unknown", extra_registry_ops=ops,
                    extra_domains=[current],
                    prepare=lambda c: unenroll_project(c, ctx.project_id))
                print(f"unenrolled {ctx.project_id}; revoked {n} managed mirror(s)")
                return 0
            if args.project_cmd == "rebind":
                computed = ctx.project_id
                rows = []
                if ro is not None:
                    rows = ro.execute(
                        "SELECT project_id, current_root, git_common_dir, remote_fingerprint, "
                        "profile_id, status FROM projects WHERE status='enrolled' "
                        "AND profile_id=?",
                        (ctx.profile_id,),
                    ).fetchall()
                candidates = []
                for r in rows:
                    pid = str(r["project_id"])
                    if pid == computed:
                        continue
                    fp = str(r["remote_fingerprint"] or "")
                    if ctx.remote_fingerprint and fp == ctx.remote_fingerprint:
                        candidates.append(pid)
                print(f"rebind plan: computed {computed}; candidates {candidates or '(none)'}")
                need = _want_confirm(args, "rebind")
                if need == "dry":
                    print("  dry (pass --apply --confirm rebind)")
                    return 0
                if need:
                    print(f"project rebind: {need}", file=sys.stderr)
                    return 2
                conn = connect(db_path(ctx))
                try:
                    if len(candidates) > 1:
                        print("project rebind: multiple enrolled matches — refuse",
                              file=sys.stderr)
                        return 2
                    if len(candidates) == 1:
                        old = candidates[0]
                        collide = conn.execute(
                            "SELECT project_id FROM projects WHERE current_root=? AND project_id!=?",
                            (str(ctx.project_root), old)).fetchone()
                        if collide:
                            print("project rebind: would collide with another project_id",
                                  file=sys.stderr)
                            return 2

                        def _prep_rebind(c):
                            record_project_alias(c, computed, old)
                            c.execute(
                                "UPDATE projects SET current_root=?, git_common_dir=?, "
                                "native_memory_dir=?, session_dir=?, display_name=?, "
                                "remote_fingerprint=? WHERE project_id=?",
                                (str(ctx.project_root),
                                 str(ctx.git_common_dir) if ctx.git_common_dir else "",
                                 str(ctx.native_memory_dir), str(ctx.session_dir),
                                 ctx.display_name, ctx.remote_fingerprint, old))
                            c.execute("DELETE FROM projects WHERE project_id=?", (computed,))
                        ops = [{"op": "project_rebind", "project_id": old,
                                "retire_id": computed, "alias_id": computed,
                                "current_root": str(ctx.project_root),
                                "git_common_dir": str(ctx.git_common_dir) if ctx.git_common_dir else "",
                                "native_memory_dir": str(ctx.native_memory_dir),
                                "session_dir": str(ctx.session_dir),
                                "display_name": ctx.display_name}]
                        transact(ctx, "project-rebind", {"old": old, "alias": computed},
                                 lambda c, temps: (_prep_rebind(c) or True) and {
                                     "registry_ops": ops, "rebound": old})
                        print(f"rebind: {old} now at {ctx.project_root} (alias {computed})")
                        return 0
                    upsert_project(conn, ctx)
                    conn.commit()
                    print(f"rebind: updated root/native for {ctx.project_id}")
                    return 0
                finally:
                    conn.close()
        finally:
            if ro is not None:
                ro.close()
        return 2
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cm_ops")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("doctor")
    d.add_argument("project", nargs="?", default=".")
    d.add_argument("--json", action="store_true")
    d.add_argument("--repair-permissions", action="store_true")

    c = sub.add_parser("conflicts")
    c.add_argument("project", nargs="?", default=".")
    c.add_argument("--all", action="store_true")
    c.add_argument("--json", action="store_true")

    r = sub.add_parser("resolve")
    r.add_argument("fact")
    r.add_argument("--keep-canonical", action="store_true")
    r.add_argument("--fork-local", metavar="NAME")
    r.add_argument("--promote-local", action="store_true")
    r.add_argument("--project", default=".")
    r.add_argument("--json", action="store_true")

    rm = sub.add_parser("repair-mirror")
    rm.add_argument("fact")
    rm.add_argument("--project", default=".")

    ca = sub.add_parser("canonical")
    ca.add_argument("canonical_cmd", choices=["upsert", "catalog", "forget",
                                              "supersede", "expire", "reactivate",
                                              "resurrect"])
    ca.add_argument("stem", nargs="?")
    ca.add_argument("--file")
    ca.add_argument("--origin", action="store_true")
    ca.add_argument("--reason")
    ca.add_argument("--replacement", help="replacement stem or fact_id for supersede")
    ca.add_argument("--project", default=".")
    ca.add_argument("--json", action="store_true")
    ca.add_argument("--crash-after")

    m = sub.add_parser("migrate")
    m.add_argument("project", nargs="?", default=".")
    m.add_argument("--plan", action="store_true", default=True)
    m.add_argument("--apply", action="store_true")
    m.add_argument("--rollback", action="store_true")
    m.add_argument("--finalize", action="store_true")
    m.add_argument("--status", action="store_true")
    m.add_argument("--validate", action="store_true")
    m.add_argument("--assign", metavar="STEM")
    m.add_argument("--exclude", metavar="STEM")
    m.add_argument("--resolve-collision", metavar="STEM", dest="resolve_collision")
    m.add_argument("--keep", metavar="ORIGIN", help="legacy|unknown-pool")
    m.add_argument("--on-existing", dest="on_existing",
                   choices=["keep-existing", "replace-with-migrated", "exclude"])
    m.add_argument("--resurrect", action="store_true",
                   help="allow migrate apply to copy a tombstoned stem")
    m.add_argument("--domain")
    m.add_argument("--json", action="store_true")
    m.add_argument("--confirm", metavar="PHRASE")

    da = sub.add_parser("data")
    da.add_argument("data_cmd", choices=["inventory", "compact", "export", "import",
                                         "purge", "purge-status", "purge-resume",
                                         "purge-cancel", "retention"])
    da.add_argument("show", nargs="?", help="optional 'show' after retention (cm data retention show)")
    da.add_argument("--project", default=".")
    da.add_argument("--json", action="store_true")
    da.add_argument("--plan", action="store_true", help="explicit dry-run for compact (default is already a plan)")
    da.add_argument("--apply", action="store_true")
    da.add_argument("--dest")
    da.add_argument("--file")
    da.add_argument("--project-id", dest="purge_project")
    da.add_argument("--domain", dest="purge_domain")
    da.add_argument("--scope", dest="purge_scope",
                    choices=["managed-mirrors", "project-ops",
                             "domain-canonicals", "all-plugin-data"])
    da.add_argument("--confirm", metavar="PHRASE")
    da.add_argument("--accept-partial", action="store_true",
                    help="purge-cancel when canonicals are already gone")

    pr = sub.add_parser("project")
    pr.add_argument("project_cmd", choices=["enroll", "show", "unenroll", "move-domain",
                                            "rebind", "grant-native", "revoke-native",
                                            "transfer-native", "grants"])
    pr.add_argument("project", nargs="?", default=".")
    pr.add_argument("--domain")
    pr.add_argument("--to", dest="to_domain")
    pr.add_argument("--path", dest="grant_path",
                    help="absolute native-store path for grant-native/revoke-native")
    pr.add_argument("--apply", action="store_true")
    pr.add_argument("--confirm", metavar="PHRASE")
    pr.add_argument("--json", action="store_true")
    pr.add_argument("--adopt", action="store_true",
                    help="grant-native of a nonempty destination")

    mk = sub.add_parser("marker")
    mk.add_argument("marker_cmd", choices=["stamp", "standing-justify", "snooze"])
    mk.add_argument("--commit")
    mk.add_argument("--timestamp")
    mk.add_argument("--facts", type=int)
    mk.add_argument("--index-tokens", type=int, dest="index_tokens")
    mk.add_argument("--until")
    mk.add_argument("--project", default=".")
    mk.add_argument("--json", action="store_true")

    loc = sub.add_parser("local")
    loc.add_argument("local_cmd", choices=["upsert", "update", "archive",
                                           "forget", "rebuild-index",
                                           "migrate-schema"])
    loc.add_argument("stem", nargs="?")
    loc.add_argument("--file")
    loc.add_argument("--project", default=".")
    loc.add_argument("--json", action="store_true")
    loc.add_argument("--apply", action="store_true")
    loc.add_argument("--skip-invalid", action="store_true")
    loc.add_argument("--confirm", metavar="PHRASE")

    j = sub.add_parser("journal")
    j.add_argument("journal_cmd", choices=["inventory", "show", "retry",
                                           "rollback", "abandon", "compact",
                                           "cleanup"])
    j.add_argument("op_id", nargs="?")
    j.add_argument("--project", default=".")
    j.add_argument("--json", action="store_true")
    j.add_argument("--apply", action="store_true")
    j.add_argument("--confirm", metavar="PHRASE")
    j.add_argument("--accept-fs", action="store_true")
    j.add_argument("--scan-all-stores", action="store_true")
    return p


def main(argv: Optional[list] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 2
    try:
        if args.cmd == "doctor":
            return cmd_doctor(args)
        if args.cmd == "conflicts":
            return cmd_conflicts(args)
        if args.cmd == "resolve":
            return cmd_resolve(args)
        if args.cmd == "repair-mirror":
            return cmd_repair_mirror(args)
        if args.cmd == "canonical":
            return cmd_canonical(args)
        if args.cmd == "local":
            return cmd_local(args)
        if args.cmd == "marker":
            return cmd_marker(args)
        if args.cmd == "migrate":
            return cmd_migrate(args)
        if args.cmd == "data":
            return cmd_data(args)
        if args.cmd == "journal":
            return cmd_journal(args)
        if args.cmd == "project":
            return cmd_project(args)
    except WriteRefused as e:
        payload = {"ok": False, "error": str(e), "code": 2}
        if getattr(args, "json", False):
            print(json.dumps(payload))
        else:
            print(f"cm: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
