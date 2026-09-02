#!/usr/bin/env python3
"""Phase-5 capacity benchmark — zero-dep, runs against the CHECKOUT's scripts.

Measures the plan's matrix (projects × canonicals × native facts × transcripts ×
journal rows, one axis swept at a time from a baseline) against the practical
SLOs: SessionStart beacon p99 < 2s · no-change pull < 1s · journal inventory at
1M bounded/paginated · zero full-store transcript/fact-body preload.

Fresh-process ops (beacon, pull, gc) run as clean subprocesses with HOME /
CLAUDE_CONFIG_DIR pointed at the synthetic root; pure-function ops (conflict
classification, journal recovery, export, purge) are timed in-process. The
beacon is driven through its real hook-stdin path.

Usage: python3 tests/bench_phase5.py [--quick] [--json REPORT.json]
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "plugins" / "consolidate-memory" / "scripts"
sys.path.insert(0, str(SCRIPTS))

# ── matrix ─────────────────────────────────────────────────────────────────────
BASELINE = {"projects": 10, "canonicals": 100, "facts": 100, "transcripts": 100,
            "journal": 10_000}
AXES = {
    "projects": [1, 10, 100, 1_000],
    "canonicals": [10, 100, 1_000, 10_000],
    "facts": [10, 100, 1_000],
    "transcripts": [10, 100, 1_000],
    "journal": [100, 10_000, 1_000_000],
}
SLO_BEACON_P99_MS = 2000.0
SLO_PULL_MS = 1000.0
BEACON_RUNS = 7


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _fact(name: str, body: str = "body\n") -> str:
    """Valid active schema-v3 canonical (the shape the pull actually replicates)."""
    from fact_schema import stable_fact_id
    fid = stable_fact_id("personal", name)
    now = _now_iso()
    if not str(body).endswith("\n"):
        body = str(body) + "\n"
    return (f"---\nschema_version: 3\nfact_id: {fid}\nname: {name}\n"
            f"description: \"d {name}\"\ndomain: personal\nsensitivity: internal\n"
            f"scope: user-global\nstatus: active\n"
            f"applies_any: []\napplies_all: []\napplies_exclude: []\n"
            f"content_modified: {now}\nlast_observed_at: {now}\n---\n{body}")


def _seed_point(root: Path, p: dict) -> dict:
    """Build a synthetic fleet at one matrix point. Returns {ctx0, ...}."""
    import control_plane as cp
    import store_context as sc
    # canonicals
    cdir = root / ".claude" / "consolidate-memory" / "domains" / "personal" / "facts"
    cdir.mkdir(parents=True)
    for i in range(p["canonicals"]):
        (cdir / f"c{i:05d}.md").write_text(_fact(f"c{i:05d}"), encoding="utf-8")
    # projects: enroll in control.sqlite (one conn), stores + transcripts
    proj_dirs = []
    for i in range(p["projects"]):
        pd = root / f"proj{i:04d}"
        (pd / ".git").mkdir(parents=True)
        (pd / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        proj_dirs.append(pd)
    # enroll the FIRST project only (one enrolled node suffices for pull/gc timing;
    # 1k enrollments would dominate the seed and not the measured ops)
    ctx0 = sc.resolve_store(proj_dirs[0])
    conn = cp.connect(cp.db_path(ctx0))
    try:
        cp.enroll_project(conn, ctx0, "personal")
        conn.commit()
    finally:
        conn.close()
    # native facts + MEMORY.md + transcript lines for the enrolled store
    store0 = ctx0.native_memory_dir
    store0.mkdir(parents=True, exist_ok=True)
    idx_lines = ["# Memory Index\n"]
    for i in range(p["facts"]):
        (store0 / f"f{i:04d}.md").write_text(
            f"---\nname: f{i:04d}\nmetadata:\n  node_type: memory\n  scope: project-local\n"
            f"  type: project\n---\nbody {i}\n", encoding="utf-8")
        idx_lines.append(f"- [f{i:04d}](f{i:04d}.md) — hook {i}\n")
    (store0 / "MEMORY.md").write_text("".join(idx_lines), encoding="utf-8")
    ts_lines = []
    line_t = ('{"timestamp":"2026-01-01T00:00:00.000Z","type":"assistant","message":'
              '{"role":"assistant","content":[{"type":"text","text":"bench line"}]},"sessionId":"s"}\n')
    for i in range(p["transcripts"]):
        ts_lines.append(line_t)
    (root / ".claude" / "projects" / sc.slug_for(proj_dirs[0]) / "bench.jsonl").write_text(
        "".join(ts_lines), encoding="utf-8")
    # journal rows (complete receipts; a small pending slice for recovery timing)
    jdb = root / ".claude" / "plugins" / "data" / "consolidate-memory" / "journal.sqlite"
    jdb.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3 as sq
    jc = sq.connect(str(jdb))
    jc.executescript(
        "CREATE TABLE IF NOT EXISTS journal (op_id TEXT PRIMARY KEY, kind TEXT, "
        "payload TEXT, status TEXT, step TEXT, created_at TEXT, completed_at TEXT);"
        "CREATE TABLE IF NOT EXISTS journal_metadata (k TEXT PRIMARY KEY, v TEXT);")
    rows = []
    for i in range(p["journal"]):
        rows.append((f"op{i:08d}", "bench", '{"receipt":1}', "complete", "complete",
                     "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
    jc.executemany("INSERT INTO journal VALUES (?,?,?,?,?,?,?)", rows)
    for i in range(min(100, p["journal"])):
        jc.execute("UPDATE journal SET status='pending', step='pending' WHERE op_id=?",
                   (f"op{i:08d}",))
    jc.commit()
    jc.close()
    return {"ctx0": ctx0, "proj0": proj_dirs[0], "cdir": cdir, "jdb": jdb}


def _run(args: list, cwd: Path, env: dict, stdin: str = "") -> "tuple[float, float]":
    """Run a fresh subprocess; return (wall_ms, child_maxrss_kb)."""
    t0 = time.monotonic()
    pr = subprocess.run([sys.executable, *args], cwd=str(cwd), env=env,
                        input=stdin, capture_output=True, text=True, timeout=1200)
    wall = (time.monotonic() - t0) * 1000.0
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if pr.returncode != 0:
        raise RuntimeError(f"{args} rc={pr.returncode}: {pr.stderr[-300:]}")
    return wall, float(rss)


def _timeit(fn) -> float:
    t0 = time.monotonic()
    fn()
    return (time.monotonic() - t0) * 1000.0


def _measure_point(root: Path, seed: dict, p: dict, env: dict) -> dict:
    import mirror_conflict as mc
    import retention as ret
    import sync_global as sg
    from pathlib import Path as _P
    ctx0, proj0, cdir, jdb = seed["ctx0"], seed["proj0"], seed["cdir"], seed["jdb"]
    out: dict = {"point": p.copy()}
    # beacon — real hook-stdin path, 7 runs for p50/p95/p99
    hook = json.dumps({"cwd": str(proj0), "session_id": "bench", "transcript_path": "",
                       "reason": "startup"})
    btimes = []
    for _ in range(BEACON_RUNS):
        w, _ = _run([str(SCRIPTS / "session_beacon.py")], proj0, env, stdin=hook)
        btimes.append(w)
    out["beacon_p50"], out["beacon_p95"], out["beacon_p99"] = (
        statistics.median(btimes),
        statistics.quantiles(btimes, n=20)[18],
        max(btimes))
    # initial pull (mirror seeding) then NO-CHANGE pull
    _run([str(SCRIPTS / "sync_global.py"), "--pull", "."], proj0, env)
    w_nc, rss_nc = _run([str(SCRIPTS / "sync_global.py"), "--pull", "."], proj0, env)
    out["pull_nochange_ms"] = w_nc
    out["peak_rss_kb"] = rss_nc
    # ONE-FACT pull: touch one canonical (description bump), then pull
    first = sorted(cdir.glob("*.md"))[0]
    txt = first.read_text(encoding="utf-8")
    first.write_text(txt.replace('description: "d ', 'description: "d2 '), encoding="utf-8")
    w_1, _ = _run([str(SCRIPTS / "sync_global.py"), "--pull", "."], proj0, env)
    out["pull_onefact_ms"] = w_1
    # conflict classification — pure fn on a conflicting mirror pair
    body_old = _fact("c00000", "old body\n")
    body_new = _fact("c00000", "new body\n")
    w_conf = _timeit(lambda: mc.classify_mirror(body_old, body_new))
    out["conflict_classify_ms"] = w_conf
    # journal recovery over the pending slice
    import control_plane as cp
    from store_context import resolve_store as _rs
    jctx = _rs(proj0)
    def _recover():
        conn = cp.connect_journal(jctx)
        try:
            cp.recover_pending(conn, ctx=jctx)
        finally:
            conn.close()
    out["journal_recovery_ms"] = _timeit(_recover)
    # journal inventory (bounded check)
    import io as _io, contextlib as _cl
    import cm_ops as cmo
    buf = _io.StringIO()
    w_inv = 0.0
    with _cl.redirect_stdout(buf):
        t0 = time.monotonic()
        cmo.main(["journal", "inventory", "--project", str(proj0)])
        w_inv = (time.monotonic() - t0) * 1000.0
    out["journal_inventory_ms"] = w_inv
    out["journal_inventory_lines"] = len(buf.getvalue().splitlines())
    # gc
    w_gc, _ = _run([str(SCRIPTS / "sync_global.py"), "--gc", "."], proj0, env)
    out["gc_ms"] = w_gc
    # export
    out["export_ms"] = _timeit(lambda: ret.export_ops(jctx.plugin_data_dir,
                                                      jctx.plugin_data_dir / "bench.tar.gz"))
    # disk amplification: the SHARED layer — mirrored-canonical bytes in the
    # enrolled store (incl. index pointer lines) / canonical bytes.
    canon_bytes = sum(f.stat().st_size for f in cdir.glob("*.md"))
    mirror_bytes = sum(f.stat().st_size for f in ctx0.native_memory_dir.glob("c*.md"))
    out["disk_amplification"] = (mirror_bytes / canon_bytes) if canon_bytes else 0.0
    return out


def main() -> int:
    if "--slo" in sys.argv:
        return _run_slo_check()
    quick = "--quick" in sys.argv
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]
    results: list = []
    points: list = []
    for axis, values in AXES.items():
        for v in values:
            pt = dict(BASELINE)
            pt[axis] = v
            points.append((axis, v, pt))
    # baseline measured twice (once via each axis's baseline value) — dedupe
    seen = set()
    uniq = []
    for axis, v, pt in points:
        key = tuple(sorted(pt.items()))
        if key not in seen:
            seen.add(key)
            uniq.append((axis, v, pt))
    points = uniq
    if quick:
        points = [a for a in points if a[1] in (1, 10, 100, 1_000)][:3] + \
                 [("journal", 10_000, dict(BASELINE))]
    print(f"Phase-5 capacity benchmark · {len(points)} point(s) · "
          f"scripts @ {SCRIPTS} · quick={quick}")
    _old_home = os.environ.get("HOME")
    _old_cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    for axis, v, pt in points:
        with tempfile.TemporaryDirectory(prefix="bench5-") as td:
            root = Path(td)
            env = dict(os.environ)
            env["HOME"] = str(root)
            env["CLAUDE_CONFIG_DIR"] = str(root / ".claude")
            # in-process seeding + measures resolve the SAME synthetic root
            os.environ["HOME"] = str(root)
            os.environ["CLAUDE_CONFIG_DIR"] = str(root / ".claude")
            try:
                t0 = time.monotonic()
                seed = _seed_point(root, pt)
                seed_s = (time.monotonic() - t0)
                m = _measure_point(root, seed, pt, env)
            except Exception as exc:  # one point must not kill the sweep
                print(f"  ✗ {axis}={v}: {exc}")
                continue
            finally:
                if _old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = _old_home
                if _old_cfg is None:
                    os.environ.pop("CLAUDE_CONFIG_DIR", None)
                else:
                    os.environ["CLAUDE_CONFIG_DIR"] = _old_cfg
            m["seed_seconds"] = round(seed_s, 1)
            results.append(m)
            print(f"  {axis:12} = {v:>7}:  beacon p50/p95/p99 "
                  f"{m['beacon_p50']:7.1f}/{m['beacon_p95']:7.1f}/{m['beacon_p99']:7.1f} ms"
                  f" · pull(no-change) {m['pull_nochange_ms']:8.1f} ms"
                  f" · pull(1-fact) {m['pull_onefact_ms']:8.1f} ms"
                  f" · journal inv {m['journal_inventory_ms']:9.1f} ms "
                  f"({m['journal_inventory_lines']} ln)"
                  f" · rec {m['journal_recovery_ms']:8.1f} ms"
                  f" · gc {m['gc_ms']:8.1f} ms · export {m['export_ms']:8.1f} ms"
                  f" · amp {m['disk_amplification']:.2f}x · seed {seed_s:.1f}s")
    # SLO verdicts
    print("\n── SLO verdicts ─────────────────────────────────────────────")
    if not results:
        print("no points measured")
        return 1
    w_beacon = max(r["beacon_p99"] for r in results)
    w_pull = max(r["pull_nochange_ms"] for r in results)
    print(f"SessionStart beacon p99 worst: {w_beacon:7.1f} ms  "
          f"({'PASS' if w_beacon < SLO_BEACON_P99_MS else 'FAIL'} — SLO < {SLO_BEACON_P99_MS:.0f} ms)")
    print(f"no-change pull worst:        {w_pull:7.1f} ms  "
          f"({'PASS' if w_pull < SLO_PULL_MS else 'FAIL'} — SLO < {SLO_PULL_MS:.0f} ms)")
    inv = [r for r in results if r["point"]["journal"] == 1_000_000]
    inv_small = [r for r in results if r["point"]["journal"] == 10_000]
    if inv and inv_small:
        big, small = inv[0]["journal_inventory_ms"], inv_small[0]["journal_inventory_ms"]
        ok = big < 2000.0 and big < small * 5
        print(f"journal inventory @1M rows:  {big:7.1f} ms  "
              f"({'PASS' if ok else 'FAIL'} — bounded/paginated; 10k → {small:.1f} ms)")
    c10 = [r for r in results if r["point"]["canonicals"] == 10]
    c10k = [r for r in results if r["point"]["canonicals"] == 10_000]
    if c10 and c10k:
        flat = c10k[0]["beacon_p50"] < max(250.0, c10[0]["beacon_p50"] * 2.0)
        print(f"beacon flat vs canonicals:   {c10[0]['beacon_p50']:7.1f} ms (C=10) → "
              f"{c10k[0]['beacon_p50']:7.1f} ms (C=10k)  "
              f"({'PASS' if flat else 'FAIL'} — zero full-store preload)")
    print(f"peak child RSS observed:     {max(r['peak_rss_kb'] for r in results):7.0f} KB")
    if json_out:
        Path(json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"report → {json_out}")
    return 0


def _run_slo_check() -> int:
    """The Phase-5 decisive check: C=10k with a WARM manifest — the beacon and
    the no-change pull must meet their SLOs. Exits non-zero on any miss."""
    pt = dict(BASELINE)
    pt["canonicals"] = 10_000
    with tempfile.TemporaryDirectory(prefix="bench5-slo-") as td:
        root = Path(td)
        env = dict(os.environ)
        env["HOME"] = str(root)
        env["CLAUDE_CONFIG_DIR"] = str(root / ".claude")
        os.environ["HOME"] = str(root)
        os.environ["CLAUDE_CONFIG_DIR"] = str(root / ".claude")
        seed = _seed_point(root, pt)
        # warm pass: first pull builds the manifest (and mirrors)
        _run([str(SCRIPTS / "sync_global.py"), "--pull", "."], seed["proj0"], env)
        m = _measure_point(root, seed, pt, env)
    ok = True
    print(f"C=10k warm-manifest: beacon p99 {m['beacon_p99']:.1f} ms (SLO < {SLO_BEACON_P99_MS:.0f}) "
          f"· no-change pull {m['pull_nochange_ms']:.1f} ms (SLO < {SLO_PULL_MS:.0f})")
    if m["beacon_p99"] >= SLO_BEACON_P99_MS:
        print("FAIL: beacon p99 over SLO")
        ok = False
    if m["pull_nochange_ms"] >= SLO_PULL_MS:
        print("FAIL: no-change pull over SLO")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
