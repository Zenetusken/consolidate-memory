#!/usr/bin/env python3
"""Maintainer CLI for StoreContext, conflicts, canonical ingress, migrate, retention."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# scripts/ is sys.path[0] when exec'd.
from store_context import (StoreContext, WriteRefused, assert_writable, doctor_dict,
                           doctor_report, resolve_store)


def _ctx(project: str, extra_env=None) -> StoreContext:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return resolve_store(Path(project).resolve(), environ=env)


def cmd_doctor(args: argparse.Namespace) -> int:
    ctx = _ctx(args.project)
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
        from control_plane import connect_if_exists, db_path, mark_conflict_resolved
        clean = demirror_text(local)
        out = upsert(ctx, stem, clean, origin_local=native)
        if out.get("ok"):
            conn = connect_if_exists(db_path(ctx))
            if conn is not None:
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
    from control_plane import connect, db_path, set_migration_mode, transact
    from canonical_ingress import insert_frontmatter_key
    from domain_policy import fact_domain
    from memory_status import _frontmatter
    ctx = _ctx(args.project)
    legacy = ctx.config_root / "memory"
    facts = []
    if legacy.is_dir():
        facts = [p for p in sorted(legacy.glob("*.md")) if p.name != "MEMORY.md"]
    plan = {
        "legacy_store": str(legacy),
        "domain_dir": str(ctx.canonical_domain_dir),
        "n_facts": len(facts),
        "mode_after": "enforced" if args.apply else "dual-read",
        "assignment": "legacy-unassigned (NOT silently personal/universal)",
        "reversible": True,
    }
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(f"migrate plan: {plan['n_facts']} legacy facts → {plan['domain_dir']}")
        print("  assignment: legacy-unassigned (review required; not a universal domain)")
        print("  dual-read remains until --apply")
    if args.apply:
        copied_holder: list = []

        def mutate(conn, temps):
            facts_dir = ctx.canonical_domain_dir
            facts_dir.mkdir(parents=True, exist_ok=True)
            copied: list = []
            for p in facts:
                dest = facts_dir / p.name
                if dest.exists():
                    continue
                raw = p.read_text(encoding="utf-8", errors="replace")
                body = raw
                if not fact_domain(_frontmatter(raw)):
                    body = insert_frontmatter_key(raw, "domain", "legacy-unassigned")
                temps[str(dest)] = body if body.endswith("\n") else body + "\n"
                copied.append(str(dest))
            lines = ["# Memory Index", "",
                     "<!-- generated by cm canonical upsert; do not hand-edit -->", ""]
            stems: dict = {}
            if facts_dir.is_dir():
                for f in facts_dir.glob("*.md"):
                    if f.name != "MEMORY.md":
                        stems[f.stem] = f
            for dest_s in list(temps):
                dp = Path(dest_s)
                if dp.name != "MEMORY.md":
                    stems[dp.stem] = dp
            for stem in sorted(stems):
                text = temps.get(str(facts_dir / f"{stem}.md"))
                if text is None:
                    try:
                        text = (facts_dir / f"{stem}.md").read_text(
                            encoding="utf-8", errors="replace")
                    except OSError:
                        text = ""
                desc = ""
                for ln in (text or "").splitlines():
                    if ln.strip().startswith("description:"):
                        desc = ln.split(":", 1)[1].strip()
                        break
                lines.append(f"- [{stem}]({stem}.md) — {desc}".rstrip(" —"))
            temps[str(facts_dir / "MEMORY.md")] = "\n".join(lines) + "\n"
            set_migration_mode(conn, "enforced")
            copied_holder.extend(copied)
            return {"copied": copied}

        try:
            transact(ctx, "migrate-apply", {"n": len(facts)}, mutate)
        except WriteRefused as e:
            print(f"migrate apply: {e}", file=sys.stderr)
            return 2
        rb = {
            "mode_before": "dual-read",
            "copied": list(copied_holder),
            "domain_dir": str(ctx.canonical_domain_dir),
        }
        rb_path = ctx.plugin_data_dir / "migrate-rollback.json"
        rb_path.parent.mkdir(parents=True, exist_ok=True)
        rb_path.write_text(json.dumps(rb, indent=2) + "\n", encoding="utf-8")
        print("migrate apply: dual-read closed; facts copied as legacy-unassigned")
        print(f"  rollback file: {rb_path}")
    elif getattr(args, "rollback", False):
        rb_path = ctx.plugin_data_dir / "migrate-rollback.json"
        if not rb_path.exists():
            print("migrate rollback: no rollback file", file=sys.stderr)
            return 1
        conn = connect(db_path(ctx))
        rb = json.loads(rb_path.read_text(encoding="utf-8"))
        for p in rb.get("copied") or []:
            Path(p).unlink(missing_ok=True)
        set_migration_mode(conn, str(rb.get("mode_before") or "dual-read"))
        conn.commit()
        conn.close()
        print("migrate rollback: restored dual-read; copied facts removed")
    else:
        print("migrate: dry (pass --apply to copy + close dual-read)")
    return 0


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
        from identifiers import IdentifierRefused, validate_domain_id, validate_project_id
        conn = connect(db_path(ctx))
        if args.purge_project:
            try:
                args.purge_project = validate_project_id(args.purge_project)
            except IdentifierRefused as e:
                print(f"data purge: {e}", file=sys.stderr)
                conn.close()
                return 2
            row = conn.execute(
                "SELECT native_memory_dir FROM projects WHERE project_id=?",
                (args.purge_project,),
            ).fetchone()
            native = Path(row["native_memory_dir"]) if row and row["native_memory_dir"] else (
                ctx.native_memory_dir if args.purge_project == ctx.project_id else None)
            print(json.dumps(purge_project(ctx.plugin_data_dir, args.purge_project, native)))
        elif args.purge_domain:
            try:
                args.purge_domain = validate_domain_id(args.purge_domain)
            except IdentifierRefused as e:
                print(f"data purge: {e}", file=sys.stderr)
                conn.close()
                return 2
            print(json.dumps(purge_domain(ctx.plugin_data_dir, args.purge_domain, conn)))
        else:
            print("data purge: pass --project-id or --domain", file=sys.stderr)
            conn.close()
            return 2
        conn.close()
        return 0
    return 2


def cmd_project(args: argparse.Namespace) -> int:
    from control_plane import connect, db_path, enroll_project, enrolled_domain, unenroll_project
    from identifiers import IdentifierRefused, validate_domain_id
    ctx = _ctx(args.project)
    conn = connect(db_path(ctx))
    try:
        if args.project_cmd == "show":
            got = enrolled_domain(conn, ctx.project_id)
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
        if args.project_cmd == "enroll":
            if not args.domain:
                print("project enroll: pass --domain", file=sys.stderr)
                return 2
            try:
                d = validate_domain_id(args.domain)
            except IdentifierRefused as e:
                print(f"project enroll: {e}", file=sys.stderr)
                return 2
            enroll_project(conn, ctx, d)
            print(f"enrolled {ctx.project_id} → domain {d}")
            return 0
        if args.project_cmd == "unenroll":
            unenroll_project(conn, ctx.project_id)
            print(f"unenrolled {ctx.project_id}")
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

    pr = sub.add_parser("project")
    pr.add_argument("project_cmd", choices=["enroll", "show", "unenroll"])
    pr.add_argument("project", nargs="?", default=".")
    pr.add_argument("--domain")
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
