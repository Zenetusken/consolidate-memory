#!/usr/bin/env python3
"""Maintainer CLI for StoreContext, conflicts, canonical ingress, migrate, retention."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

# scripts/ is sys.path[0] when exec'd.
from store_context import (StoreContext, WriteRefused, assert_writable, doctor_dict,
                           doctor_report, resolve_store)


def _mirror_plan_for_dest(ctx: StoreContext, dest_domain: str) -> dict:
    """Inventory managed mirrors: clean deletes vs locally-edited quarantine.

    Unenroll (dest unknown) plans every managed mirror. Local edits are never
    deleted — they land under native/quarantine/.
    """
    from control_plane import (connect_if_exists, db_path, holder_base_revision,
                               migration_mode_readonly, stable_fact_id)
    from domain_policy import admit_cross_project
    from memory_status import _frontmatter
    from mirror_conflict import body_hash as _bh, classify_mirror
    from sync_global import _is_mirror, _safe_read_text, global_store
    native = ctx.native_memory_dir
    plan: dict = {"deletes": [], "quarantine": [], "holders": []}
    if not native.is_dir():
        return plan
    mode = "dual-read"
    try:
        mode = migration_mode_readonly(ctx)
    except Exception:
        mode = "dual-read"
    droot = ctx.config_root / "consolidate-memory" / "domains"
    _hconn = connect_if_exists(db_path(ctx))
    try:
        for f in sorted(native.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            text = _safe_read_text(f)
            if text is None or not _is_mirror(text):
                continue
            fm = _frontmatter(text)
            cdom = str(fm.get("canonical_domain") or fm.get("domain") or "").strip()
            if dest_domain != "unknown" and admit_cross_project(
                    dest_domain, fm, migration_mode=mode):
                continue
            fid = str(fm.get("canonical_fact_id") or "").strip()
            if not fid:
                fid = stable_fact_id(cdom or ctx.domain_id or "unknown", f.stem)
            plan["holders"].append({"op": "holder_delete", "fact_id": fid,
                                    "project_id": ctx.project_id})
            canon_text = None
            if cdom and cdom != "unknown":
                from identifiers import IdentifierRefused, safe_child, validate_domain_id
                try:
                    cp = safe_child(droot, validate_domain_id(cdom)) / "facts" / f.name
                    canon_text = _safe_read_text(cp)
                except IdentifierRefused:
                    canon_text = None
            if canon_text is None:
                canon_text = _safe_read_text(global_store() / f.name)
            local_edit = False
            if canon_text:
                _hb = (holder_base_revision(_hconn, fid, ctx.project_id)
                       if _hconn is not None else None)
                dec = classify_mirror(text, canon_text, base_revision=_hb)
                local_edit = dec["action"] in ("stop-local", "conflict", "quarantine")
                if not local_edit and _bh(text) != _bh(canon_text):
                    local_edit = True
            if local_edit:
                plan["quarantine"].append((str(f), text))
            else:
                plan["deletes"].append(str(f))
    finally:
        if _hconn is not None:
            _hconn.close()
    return plan


def _revoke_unadmitted_mirrors(ctx: StoreContext, dest_domain: str,
                               extra_registry_ops: Optional[list] = None,
                               extra_domains: Optional[list] = None,
                               prepare=None) -> int:
    """Journal v3 revoke of unadmitted mirrors. Returns n files moved/deleted.

    Fail-closed: no direct unlink fallback. Quarantined bodies go to
    native/quarantine/<stem>.md (not MEMORY.md). `prepare(conn)` runs inside
    the same transact (enroll/move/unenroll registry writes).
    """
    from control_plane import transact
    from sync_global import _safe_read_text
    native = ctx.native_memory_dir
    idxp = native / "MEMORY.md"
    qdir = native / "quarantine"
    plan = _mirror_plan_for_dest(ctx, dest_domain)
    doomed_names = [Path(p).name for p in plan["deletes"]]
    doomed_names += [Path(p).name for p, _t in plan["quarantine"]]
    if not doomed_names and not extra_registry_ops and prepare is None:
        return 0

    def mutate(conn, temps):
        if prepare is not None:
            prepare(conn)
        idx = _safe_read_text(idxp) or ""
        deletes = list(plan["deletes"])
        for path_s, body in plan["quarantine"]:
            qdest = qdir / Path(path_s).name
            temps[str(qdest)] = body if body.endswith("\n") else body + "\n"
            deletes.append(path_s)
        for name in doomed_names:
            idx = "\n".join(ln for ln in idx.splitlines() if f"]({name})" not in ln)
        if doomed_names:
            temps[str(idxp)] = (idx.rstrip() + "\n") if idx.strip() else "# Memory Index\n"
        ops = list(plan["holders"]) + list(extra_registry_ops or [])
        for op in plan["holders"]:
            conn.execute(
                "DELETE FROM holders WHERE fact_id=? AND project_id=?",
                (op["fact_id"], op["project_id"]))
        return {"deletes": deletes, "revoked": len(deletes),
                "quarantined": len(plan["quarantine"]),
                "registry_ops": ops}

    out = transact(ctx, "domain-transition",
                   {"dest": dest_domain, "n": len(doomed_names)}, mutate,
                   extra_domains=extra_domains)
    return int((out.get("result") or {}).get("revoked") or 0)


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
                return data
        except (OSError, ValueError):
            pass
    facts = {row["stem"]: row for row in _migrate_sources(ctx)}
    return {"facts": facts, "applied": False, "finalized": False}


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


def _canonical_path(ctx: StoreContext, stem: str) -> Path:
    canon = ctx.canonical_domain_dir / f"{stem}.md"
    if canon.exists():
        return canon
    return ctx.config_root / "memory" / f"{stem}.md"


def _restamp_from_canonical(ctx: StoreContext, stem: str, canonical: str, native: Path,
                            how: str, extra_temps: Optional[dict] = None) -> dict:
    """Journal a keep-canonical / repair rewrite + mark the conflict resolved."""
    from control_plane import (mark_conflict_resolved, record_holder, stable_fact_id,
                               transact)
    from mirror_conflict import semantic_hash, stamp_revisions
    from sync_global import _as_mirror, _body_hash
    import time as _t
    rev = semantic_hash(canonical)
    want = _as_mirror(canonical, stem, since=_t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
                      body_hash=_body_hash(canonical))
    want = stamp_revisions(want, rev, rev)
    extras = dict(extra_temps or {})

    def mutate(conn, temps):
        temps[str(native)] = want
        for dest, text in extras.items():
            temps[str(dest)] = text
        fid = stable_fact_id(ctx.domain_id, stem)
        record_holder(conn, fid, ctx.project_id, rev, rev, rev)
        mark_conflict_resolved(conn, stem, ctx.project_id, how)
        return {"stem": stem, "how": how}

    return transact(ctx, "resolve-" + how, {"stem": stem, "how": how}, mutate)


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
    try:
        stem = validate_fact_stem(args.fact)
        native = safe_child(ctx.native_memory_dir, f"{stem}.md")
        if args.fork_local:
            validate_fact_stem(args.fork_local)
    except IdentifierRefused as e:
        print(f"resolve: {e}", file=sys.stderr)
        return 2
    canon = _canonical_path(ctx, stem)
    if not native.exists():
        print(f"resolve: no local file {native}", file=sys.stderr)
        return 1
    local = native.read_text(encoding="utf-8", errors="replace")
    canonical = canon.read_text(encoding="utf-8", errors="replace") if canon.exists() else ""
    if args.keep_canonical:
        if not canonical:
            print("resolve: no canonical to keep", file=sys.stderr)
            return 1
        try:
            _restamp_from_canonical(ctx, stem, canonical, native, "keep-canonical")
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
        extras = {dest: forked if forked.endswith("\n") else forked + "\n"}
        if not canonical:
            print("resolve: no canonical to restamp after fork", file=sys.stderr)
            return 1
        try:
            _restamp_from_canonical(ctx, stem, canonical, native, "fork-local", extras)
        except WriteRefused as e:
            print(f"resolve: {e}", file=sys.stderr)
            return 2
        print(f"resolve: forked {stem} → {args.fork_local} (project-local)")
        return 0
    if args.promote_local:
        from canonical_ingress import upsert
        from control_plane import connect, db_path, mark_conflict_resolved
        clean = demirror_text(local)
        out = upsert(ctx, stem, clean, origin_local=native)
        if out.get("ok"):
            conn = connect(db_path(ctx))
            mark_conflict_resolved(conn, stem, ctx.project_id, "promote-local")
            conn.commit()
            conn.close()
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
    try:
        stem = validate_fact_stem(args.fact)
        native = safe_child(ctx.native_memory_dir, f"{stem}.md")
    except IdentifierRefused as e:
        print(f"repair-mirror: {e}", file=sys.stderr)
        return 2
    canon = _canonical_path(ctx, stem)
    if not canon.exists():
        print("repair-mirror: no canonical", file=sys.stderr)
        return 1
    canonical = canon.read_text(encoding="utf-8", errors="replace")
    ctx.native_memory_dir.mkdir(parents=True, exist_ok=True)
    try:
        _restamp_from_canonical(ctx, stem, canonical, native, "repair-mirror")
    except WriteRefused as e:
        print(f"repair-mirror: {e}", file=sys.stderr)
        return 2
    print(f"repair-mirror: restamped {stem} from canonical")
    return 0


def cmd_canonical(args: argparse.Namespace) -> int:
    from canonical_ingress import forget, generate_catalog, upsert
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
    return 2


def cmd_migrate(args: argparse.Namespace) -> int:
    from control_plane import (assert_mutation_allowed, connect, db_path,
                               set_migration_mode, transact)
    from canonical_ingress import insert_frontmatter_key
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

    plan = _load_migrate_plan(ctx)
    # Refresh inventory of newly appeared sources without clobbering assignments.
    for row in _migrate_sources(ctx):
        cur = (plan.get("facts") or {}).get(row["stem"]) or {}
        if not cur:
            plan.setdefault("facts", {})[row["stem"]] = row
        else:
            cur["source"] = row["source"]
            cur["origin"] = row["origin"]
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
        # Re-resolve the kept origin as the source; extras are excluded.
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
        to_copy = []
        for stem, row in sorted((plan.get("facts") or {}).items()):
            dest_dom = str((row or {}).get("assignment") or "")
            if dest_dom in ("", "excluded"):
                continue
            src = Path(str((row or {}).get("source") or ""))
            if not src.is_file():
                print(f"migrate apply: missing source for {stem}", file=sys.stderr)
                return 2
            to_copy.append((stem, src, dest_dom, row))
        copied_holder: list = []
        droot = ctx.config_root / "consolidate-memory" / "domains"

        def mutate(conn, temps):
            copied: list = []
            catalogs: dict = {}
            for stem, src, dest_dom, row in to_copy:
                facts_dir = safe_child(droot, dest_dom) / "facts"
                facts_dir.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(str(facts_dir), 0o700)
                except OSError:
                    pass
                dest = facts_dir / f"{stem}.md"
                raw = src.read_text(encoding="utf-8", errors="replace")
                body = insert_frontmatter_key(raw, "domain", dest_dom)
                body = insert_frontmatter_key(body, "name", stem)
                if not body.endswith("\n"):
                    body += "\n"
                temps[str(dest)] = body
                copied.append({
                    "path": str(dest),
                    "new_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "old_sha256": None if not dest.exists() else _sha256_file(dest),
                    "source": str(src),
                    "source_sha256": str((row or {}).get("sha256") or _sha256_file(src)),
                    "domain": dest_dom,
                })
                catalogs.setdefault(str(facts_dir), set()).add(stem)
            from canonical_ingress import generate_catalog
            for facts_dir_s, stems in catalogs.items():
                facts_dir = Path(facts_dir_s)
                # Overlay: generate_catalog still reads live files; include temps.
                cat = generate_catalog(facts_dir)
                for stem in stems:
                    if f"]({stem}.md)" not in cat:
                        cat = cat.rstrip() + f"\n- [{stem}]({stem}.md)\n"
                temps[str(facts_dir / "MEMORY.md")] = cat if cat.endswith("\n") else cat + "\n"
            copied_holder.extend(copied)
            return {"copied": [c["path"] for c in copied]}

        try:
            transact(ctx, "migrate-apply", {"n": len(to_copy)}, mutate)
        except WriteRefused as e:
            print(f"migrate apply: {e}", file=sys.stderr)
            return 2
        plan["applied"] = True
        _save_migrate_plan(ctx, plan)
        rb = {
            "mode_before": "dual-read",
            "copied": list(copied_holder),
            "allowed_roots": [str(droot)],
        }
        rb_path = ctx.plugin_data_dir / "migrate-rollback.json"
        rb_path.parent.mkdir(parents=True, exist_ok=True)
        rb_path.write_text(json.dumps(rb, indent=2) + "\n", encoding="utf-8")
        print(f"migrate apply: copied {len(copied_holder)} fact(s) into assigned domains")
        print("  dual-read remains until --finalize")
        print(f"  rollback file: {rb_path}")
        return 0

    if stage == "rollback":
        try:
            assert_mutation_allowed(ctx)
        except WriteRefused as e:
            print(f"migrate rollback: {e}", file=sys.stderr)
            return 2
        rb_path = ctx.plugin_data_dir / "migrate-rollback.json"
        if not rb_path.exists():
            print("migrate rollback: no rollback file", file=sys.stderr)
            return 1
        rb = json.loads(rb_path.read_text(encoding="utf-8"))
        allowed = [Path(p) for p in (rb.get("allowed_roots") or [])]
        if not allowed:
            allowed = [ctx.config_root / "consolidate-memory" / "domains"]
        conflicts = []
        to_delete: list = []
        for item in rb.get("copied") or []:
            if isinstance(item, str):
                path = Path(item)
                want = ""
            else:
                path = Path(str(item.get("path") or ""))
                want = str(item.get("new_sha256") or "")
            if not path or not _contained_under(path, allowed):
                conflicts.append(str(path))
                continue
            if path.exists() and want and _sha256_file(path) not in (want, ""):
                conflicts.append(str(path))
                continue
            to_delete.append(str(path))
        def mutate(conn, temps):
            set_migration_mode(conn, str(rb.get("mode_before") or "dual-read"))
            return {"deletes": to_delete, "registry_ops": [
                {"op": "migration_state_set",
                 "value": str(rb.get("mode_before") or "dual-read")}]}
        try:
            transact(ctx, "migrate-rollback", {"n": len(to_delete)}, mutate)
        except WriteRefused as e:
            print(f"migrate rollback: {e}", file=sys.stderr)
            return 2
        plan["applied"] = False
        plan["finalized"] = False
        _save_migrate_plan(ctx, plan)
        print(f"migrate rollback: restored dual-read; removed {len(to_delete)} copied file(s)")
        if conflicts:
            print("  conflicts (edited after apply, not deleted): "
                  + ", ".join(conflicts[:8]), file=sys.stderr)
            return 1
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
        conn = connect(db_path(ctx))
        set_migration_mode(conn, "enforced")
        conn.commit()
        conn.close()
        plan["finalized"] = True
        _save_migrate_plan(ctx, plan)
        print("migrate finalize: dual-read closed (mode=enforced)")
        return 0

    print(f"migrate: unknown stage {stage!r}", file=sys.stderr)
    return 2


def cmd_data(args: argparse.Namespace) -> int:
    from control_plane import connect, db_path
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
            from retention import relocate_native_operational
            relocated = relocate_native_operational(
                ctx.native_memory_dir, ctx.plugin_data_dir, ctx.project_id)
            results = []
            for p in (cycle, mut, fleet):
                if p.is_file():
                    results.append(compact_jsonl(p, keep=CYCLE_CAP,
                                                 older_than_days=EVENT_RETENTION_DAYS))
            print(json.dumps({"ok": True, "relocated_from_native": relocated,
                              "compacted": results}))
        return 0
    if args.data_cmd == "export":
        dest = Path(args.dest or (ctx.plugin_data_dir / "export.json"))
        print(json.dumps(export_ops(ctx.plugin_data_dir, dest), indent=2))
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
        conn = connect(db_path(ctx))
        try:
            if scope == "managed-mirrors":
                n = _revoke_unadmitted_mirrors(ctx, "unknown")
                print(json.dumps({"ok": True, "scope": scope, "revoked": n,
                                  "native_untouched": True}))
                return 0
            if scope == "project-ops":
                pid = args.purge_project or ctx.project_id
                native: Optional[Path] = ctx.native_memory_dir
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
                facts = (ctx.canonical_domain_dir
                         if did == ctx.domain_id else None)
                print(json.dumps(purge_domain(
                    ctx.plugin_data_dir, did, conn, facts_dir=facts)))
                return 0
            if scope == "all-plugin-data":
                import shutil
                pdata = ctx.plugin_data_dir
                droot = ctx.config_root / "consolidate-memory" / "domains"
                n = 0
                if pdata.is_dir():
                    n += sum(1 for _ in pdata.rglob("*") if _.is_file())
                    shutil.rmtree(pdata, ignore_errors=True)
                if droot.is_dir():
                    n += sum(1 for _ in droot.rglob("*") if _.is_file())
                    shutil.rmtree(droot, ignore_errors=True)
                print(json.dumps({"ok": True, "scope": scope, "purged_files": n,
                                  "native_untouched": True,
                                  "native": str(ctx.native_memory_dir)}))
                return 0
            print("data purge: unknown scope", file=sys.stderr)
            return 2
        finally:
            conn.close()
    return 2


def _want_confirm(args: argparse.Namespace, phrase: str) -> Optional[str]:
    """TTY operators must pass --confirm PHRASE. Non-TTY --apply is enough (tests)."""
    if not getattr(args, "apply", False):
        return "dry"
    got = str(getattr(args, "confirm", None) or "")
    if sys.stderr.isatty() and got != phrase:
        return (f"pass --apply --confirm {phrase}")
    return None


def cmd_project(args: argparse.Namespace) -> int:
    from control_plane import (assert_mutation_allowed, connect, connect_if_exists,
                               db_path, enroll_project, enrolled_domain,
                               record_project_alias, transact, unenroll_project,
                               upsert_project)
    from identifiers import IdentifierRefused, validate_domain_id
    ctx = _ctx(args.project)
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
            print(f"project {args.project_cmd}: {e}", file=sys.stderr)
            return 2
    conn = connect(db_path(ctx))
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
            current = enrolled_domain(conn, ctx.project_id)
            if current and current != d:
                print(f"project enroll: already enrolled in {current}; "
                      f"use `cm project move-domain --to {d}`", file=sys.stderr)
                return 2
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
            ops = [{"op": "project_domain_change", "project_id": ctx.project_id,
                    "domain_id": d, "status": "enrolled"}]
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
            current = enrolled_domain(conn, ctx.project_id)
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
            current = enrolled_domain(conn, ctx.project_id) or ctx.domain_id
            if not enrolled_domain(conn, ctx.project_id):
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
            rows = conn.execute(
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
            if len(candidates) > 1:
                print("project rebind: multiple enrolled matches — refuse", file=sys.stderr)
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
                    upsert_project(c, ctx)
                    c.execute(
                        "UPDATE projects SET current_root=?, git_common_dir=?, "
                        "native_memory_dir=?, session_dir=?, display_name=?, "
                        "remote_fingerprint=? WHERE project_id=?",
                        (str(ctx.project_root),
                         str(ctx.git_common_dir) if ctx.git_common_dir else "",
                         str(ctx.native_memory_dir), str(ctx.session_dir),
                         ctx.display_name, ctx.remote_fingerprint, old))
                ops = [{"op": "project_alias", "alias_id": computed, "project_id": old}]
                transact(ctx, "project-rebind", {"old": old, "alias": computed},
                         lambda c, temps: (ops and _prep_rebind(c)) or {
                             "registry_ops": ops, "rebound": old})
                print(f"rebind: {old} now at {ctx.project_root} (alias {computed})")
                return 0
            upsert_project(conn, ctx)
            conn.commit()
            print(f"rebind: updated root/native for {ctx.project_id}")
            return 0
    finally:
        conn.close()
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
    ca.add_argument("canonical_cmd", choices=["upsert", "catalog", "forget"])
    ca.add_argument("stem", nargs="?")
    ca.add_argument("--file")
    ca.add_argument("--origin", action="store_true")
    ca.add_argument("--reason")
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
    m.add_argument("--domain")
    m.add_argument("--json", action="store_true")

    da = sub.add_parser("data")
    da.add_argument("data_cmd", choices=["inventory", "compact", "export", "purge", "retention"])
    da.add_argument("show", nargs="?", help="optional 'show' after retention (cm data retention show)")
    da.add_argument("--project", default=".")
    da.add_argument("--json", action="store_true")
    da.add_argument("--plan", action="store_true", help="explicit dry-run for compact (default is already a plan)")
    da.add_argument("--apply", action="store_true")
    da.add_argument("--dest")
    da.add_argument("--project-id", dest="purge_project")
    da.add_argument("--domain", dest="purge_domain")
    da.add_argument("--scope", dest="purge_scope",
                    choices=["managed-mirrors", "project-ops",
                             "domain-canonicals", "all-plugin-data"])
    da.add_argument("--confirm", metavar="PHRASE")

    pr = sub.add_parser("project")
    pr.add_argument("project_cmd", choices=["enroll", "show", "unenroll", "move-domain", "rebind"])
    pr.add_argument("project", nargs="?", default=".")
    pr.add_argument("--domain")
    pr.add_argument("--to", dest="to_domain")
    pr.add_argument("--apply", action="store_true")
    pr.add_argument("--confirm", metavar="PHRASE")
    pr.add_argument("--json", action="store_true")
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
        if args.cmd == "migrate":
            return cmd_migrate(args)
        if args.cmd == "data":
            return cmd_data(args)
        if args.cmd == "project":
            return cmd_project(args)
    except WriteRefused as e:
        print(f"cm: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
