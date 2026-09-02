#!/usr/bin/env python3
"""Process-level races for Phase 1 (ADR 010: two processes + a barrier, not sleeps).

Run: python3 tests/concurrency.py
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "consolidate-memory" / "scripts"))

passed = failed = 0


def check(name: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")


def _enroll(proj: Path) -> None:
    import control_plane as cp
    import store_context as sc
    ctx = sc.resolve_store(proj)
    conn = cp.connect(cp.db_path(ctx))
    try:
        cp.enroll_project(conn, ctx, "personal")
        conn.commit()
    finally:
        conn.close()


def _setup():
    td = tempfile.TemporaryDirectory(prefix="cm-conc-")
    home = Path(td.name)
    proj = (home / "src" / "p").resolve()
    proj.mkdir(parents=True)
    os.environ["HOME"] = str(home)
    import memory_status as ms
    store = home / ".claude" / "projects" / ms.slug_for(proj) / "memory"
    store.mkdir(parents=True)
    _enroll(proj)
    return td, home, proj, store


def _justify_child(home: str, proj: str, barrier, q) -> None:
    os.environ["HOME"] = home
    import memory_status as ms
    barrier.wait()
    out = ms.run_justify_demotion(Path(proj), ["cadence-fact"], force=True)
    q.put(("justify", out.get("ok"), out.get("error")))


def _stacks_child(home: str, proj: str, barrier, q) -> None:
    os.environ["HOME"] = home
    import sync_global as sg
    barrier.wait()
    sg._write_stacks_cache(
        Path(home) / ".claude" / "projects" / __import__("memory_status").slug_for(Path(proj)) / "memory",
        Path(proj), {"python", "git"})
    q.put(("stacks", True, ""))


def test_justify_vs_stacks() -> None:
    td, home, proj, store = _setup()
    try:
        (store / ".consolidation-state.json").write_text(
            '{"commit": "deadbeef", "timestamp": "2026-01-01T00:00:00Z"}\n',
            encoding="utf-8")
        ctx = mp.get_context("fork")
        barrier = ctx.Barrier(2)
        q: mp.Queue = ctx.Queue()
        p1 = ctx.Process(target=_justify_child, args=(str(home), str(proj), barrier, q))
        p2 = ctx.Process(target=_stacks_child, args=(str(home), str(proj), barrier, q))
        p1.start(); p2.start()
        p1.join(30); p2.join(30)
        results = [q.get(timeout=1), q.get(timeout=1)]
        marker = json.loads((store / ".consolidation-state.json").read_text(encoding="utf-8"))
        check("concurrency: justify vs stacks-cache preserves both changes",
              p1.exitcode == 0 and p2.exitcode == 0
              and marker.get("commit") == "deadbeef"
              and "cadence-fact" in (marker.get("demotion_justify") or {})
              and marker.get("stacks") == ["git", "python"]
              and all(r[1] for r in results))
    finally:
        td.cleanup()


def _upsert_child(home: str, proj: str, stem: str, body: str, barrier, q) -> None:
    os.environ["HOME"] = home
    import local_ingress as li
    import store_context as sc
    barrier.wait()
    ctx = sc.resolve_store(Path(proj))
    out = li.local_upsert(ctx, stem, body)
    q.put((body[:8], bool(out.get("ok")), str(out.get("error") or "")))


def test_two_upserts() -> None:
    td, home, proj, store = _setup()
    try:
        ctx = mp.get_context("fork")
        barrier = ctx.Barrier(2)
        q: mp.Queue = ctx.Queue()
        a = "---\nname: race-stem\ndescription: writer A\n---\nA\n"
        b = "---\nname: race-stem\ndescription: writer B\n---\nB\n"
        p1 = ctx.Process(target=_upsert_child, args=(str(home), str(proj), "race-stem", a, barrier, q))
        p2 = ctx.Process(target=_upsert_child, args=(str(home), str(proj), "race-stem", b, barrier, q))
        p1.start(); p2.start()
        p1.join(30); p2.join(30)
        results = [q.get(timeout=1), q.get(timeout=1)]
        oks = [r for r in results if r[1]]
        fails = [r for r in results if not r[1]]
        body = (store / "race-stem.md").read_text(encoding="utf-8") if (store / "race-stem.md").is_file() else ""
        check("concurrency: two local upserts of an absent stem: one wins, one refuses",
              p1.exitcode == 0 and p2.exitcode == 0
              and len(oks) == 1 and len(fails) == 1
              and ("writer A" in body or "writer B" in body)
              and not ("writer A" in body and "writer B" in body))
    finally:
        td.cleanup()


def _rebuild_child(home: str, proj: str, barrier, q) -> None:
    os.environ["HOME"] = home
    import local_ingress as li
    import store_context as sc
    barrier.wait()
    ctx = sc.resolve_store(Path(proj))
    out = li.local_rebuild_index(ctx, apply=True, confirm="rebuild-local-index")
    q.put(("rebuild", bool(out.get("ok")), str(out.get("error") or "")))


def _edit_child(home: str, store: str, barrier, q) -> None:
    os.environ["HOME"] = home
    p = Path(store) / "live-rb.md"
    barrier.wait()
    try:
        p.write_text("---\nname: live-rb\ndescription: changed under rebuild\n---\nZ\n",
                     encoding="utf-8")
        q.put(("edit", True, ""))
    except OSError as e:
        q.put(("edit", False, str(e)))


def test_rebuild_vs_edit() -> None:
    td, home, proj, store = _setup()
    try:
        (store / "live-rb.md").write_text(
            "---\nname: live-rb\ndescription: original\n---\nO\n", encoding="utf-8")
        (store / "MEMORY.md").write_text(
            "# Memory Index\n\n- [live-rb](live-rb.md) — original\n", encoding="utf-8")
        ctx = mp.get_context("fork")
        barrier = ctx.Barrier(2)
        q: mp.Queue = ctx.Queue()
        p1 = ctx.Process(target=_rebuild_child, args=(str(home), str(proj), barrier, q))
        p2 = ctx.Process(target=_edit_child, args=(str(home), str(store), barrier, q))
        p1.start(); p2.start()
        p1.join(30); p2.join(30)
        got = [q.get(timeout=1), q.get(timeout=1)]
        idx = (store / "MEMORY.md").read_text(encoding="utf-8")
        body = (store / "live-rb.md").read_text(encoding="utf-8")
        # Mixed snapshot: body was edited but the published index still describes
        # the pre-edit bytes. That is the defect. A refused rebuild (index unchanged
        # while the body changed) is acceptable; a successful rebuild must hash the
        # bytes it published.
        mixed = ("changed under rebuild" in body
                 and "](live-rb.md)" in idx
                 and "changed under rebuild" not in idx
                 and "original" in idx)
        check("concurrency: rebuild-index vs fact edit does not publish a mixed snapshot",
              p1.exitcode == 0 and p2.exitcode == 0
              and len(got) == 2
              and not mixed)
    finally:
        td.cleanup()


def main() -> int:
    if os.name == "nt":
        print("concurrency: skipped on Windows (POSIX flock)")
        return 0
    test_justify_vs_stacks()
    test_two_upserts()
    test_rebuild_vs_edit()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
