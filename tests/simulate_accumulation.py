#!/usr/bin/env python3
"""Simulate memory accumulation over many consolidation cycles — bloat + lifecycle probe.

smoke.py guards the pure functions; THIS harness models the *lifecycle over time*:
what the script-driven machinery (cross-project replication, index pointers, GC,
provenance, token accounting) does to the always-loaded tier's per-session cost as
facts pile up across cycles and projects.

It began as a bloat demonstrator (four CONFIRMED unbounded-growth/drift vectors) and
is now a characterization of the FIXES: each probe asserts an expected lifecycle
property —
  A baseline still grows linearly (pruning is by design a human-in-the-loop call),
  B `--gc --apply` reclaims orphaned mirrors a canonical deletion leaves behind,
  C a STALE refresh upserts the always-loaded index hook (no silent tier-1 drift),
  D stack matching is token-bounded (no substring false-positives),
  E GC never touches a project-authored (non-`global_ref:`) fact,
  F per-node + total network token consumption is observable,
  K --promote hands a local fact UP to the canonical store + mirrors the origin atomically
    (in-sync follow-up pull, no dup/orphan; never clobbers an existing canonical).

Scope (stated honestly): this exercises only the SCRIPT-driven lifecycle. Phase-4
prose decisions (which facts to prune, dedup, re-verify) remain a model call, so the
baseline growth in Probe A is expected, not a bug — the fixes make it VISIBLE (token
budget + ⚠), RECLAIMABLE (--gc), and COHERENT (hook upsert), not automatic.

HERMETIC: runs the real CLI as a subprocess with HOME=<tmp>, so the child computes
its GLOBAL store fresh under tmp. A hard assertion refuses to proceed if any path
resolves outside tmp — this must NEVER write to the real ~/.claude (CLAUDE.md: the
shared-memory store is personal and gitignored; never touch it).

Run:  python3 tests/simulate_accumulation.py
No pytest, no network, no deps. Exit 0 if every property holds, 1 on a regression.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNC = ROOT / "plugins" / "consolidate-memory" / "scripts" / "sync_global.py"
sys.path.insert(0, str(ROOT / "plugins" / "consolidate-memory" / "scripts"))
import memory_status as ms  # noqa: E402  (pure rigor functions — Probe H)
import render_dashboard as rd  # noqa: E402  (_persist — Probe I)


# ── fact synthesis ────────────────────────────────────────────────────────────
def _fact(name: str, scope: str, stacks: str = "", desc: str = "") -> str:
    """A global-store fact file, in the live frontmatter schema."""
    desc = desc or f"recall key for {name} — surfaces when a task mentions {name.replace('-', ' ')}"
    fm = [
        "---",
        f"name: {name}",
        f"description: {desc}",
        "metadata:",
        "  node_type: memory",
        "  type: reference",
        f"  scope: {scope}",
    ]
    if stacks:
        fm.append(f"  stacks: [{stacks}]")
    fm.append("  projects: []")
    fm.append("---")
    fm.append("")
    # Pad the body so byte growth is realistic (a real fact is a paragraph, not a word).
    fm.append(f"The durable fact named {name}. " * 6)
    fm.append("")
    return "\n".join(fm)


def _write_global(home: Path, name: str, scope: str, stacks: str = "", desc: str = "") -> None:
    g = home / ".claude" / "memory"
    g.mkdir(parents=True, exist_ok=True)
    (g / f"{name}.md").write_text(_fact(name, scope, stacks, desc), encoding="utf-8")
    idx = g / "MEMORY.md"
    head = idx.read_text(encoding="utf-8") if idx.exists() else "# Memory Index\n\n"
    if f"({name}.md)" not in head:
        idx.write_text(head.rstrip() + f"\n- [{name}]({name}.md) — {scope} fact\n", encoding="utf-8")


def _make_project(home: Path, name: str, *, deps: tuple = (), claude: bool = False) -> Path:
    """A fake project dir with REAL detect_stacks signals (v0.1.16 — detection keys off declared
    dependencies / imports / marker dirs, NOT prose): a `main.py` (→ python), a pyproject.toml
    declaring `deps` (so they map to their stacks), and optionally a real `.claude/` dir (→ claude-code)."""
    p = home / "projects-src" / name
    p.mkdir(parents=True, exist_ok=True)
    (p / "main.py").write_text("x = 1\n", encoding="utf-8")          # a real .py → python
    if deps:
        body = ",\n  ".join(f'"{d}"' for d in deps)
        (p / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\ndependencies = [\n  {body},\n]\n', encoding="utf-8")
    if claude:
        (p / ".claude").mkdir(exist_ok=True)                          # a real marker dir → claude-code
    return p


# ── measurement ───────────────────────────────────────────────────────────────
def _store(home: Path, project_dir: Path) -> Path:
    slug = str(project_dir.resolve()).replace("/", "-")
    return home / ".claude" / "projects" / slug / "memory"


def _measure(home: Path, project_dir: Path) -> dict:
    store = _store(home, project_dir)
    idx = store / "MEMORY.md"
    facts = [f for f in store.glob("*.md") if f.name != "MEMORY.md"] if store.exists() else []
    if idx.exists():
        t = idx.read_text(encoding="utf-8")
        il, ib = len(t.splitlines()), len(t.encode())
    else:
        il = ib = 0
    # orphan = a mirror whose canonical no longer exists in the global store
    g = home / ".claude" / "memory"
    canon = {f.stem for f in g.glob("*.md") if f.name != "MEMORY.md"} if g.exists() else set()
    orphans = [f.stem for f in facts if "global_ref:" in f.read_text(encoding="utf-8")
               and f.stem not in canon]
    return {"index_lines": il, "index_bytes": ib, "facts": len(facts), "orphans": len(orphans)}


def _sync(home: Path, *cli_args: str) -> str:
    env = dict(os.environ, HOME=str(home))
    return subprocess.run([sys.executable, str(SYNC), *cli_args],
                          env=env, capture_output=True, text=True, check=False).stdout


def _pull(home: Path, project_dir: Path) -> None:
    _sync(home, "--pull", str(project_dir))


def _gc(home: Path, project_dir: Path, apply: bool) -> str:
    return _sync(home, "--gc", *(["--apply"] if apply else []), str(project_dir))


def _promote(home: Path, project_dir: Path, *rest: str) -> subprocess.CompletedProcess:
    """Run --promote and return the FULL result — Probe K asserts on returncode + stderr (the
    refusal guards) as well as the filesystem side effects."""
    return subprocess.run([sys.executable, str(SYNC), "--promote", str(project_dir), *rest],
                          env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, check=False)


def _assert_hermetic(home: Path) -> None:
    """Refuse to run if the child CLI would resolve a store outside tmp.

    We can't read the child's Path.home() directly, but the child derives GLOBAL and
    project_store from $HOME — so we confirm OUR computed paths sit under tmp AND that
    a real ~/.claude exists distinct from it (proving we're not aliasing it)."""
    g = (home / ".claude" / "memory").resolve()
    assert str(g).startswith(str(home.resolve())), f"GLOBAL would escape tmp: {g}"
    real = (Path.home() / ".claude" / "memory").resolve()
    assert g != real, "tmp GLOBAL aliases the REAL ~/.claude/memory — refusing"


# ── the simulation ──────────────────────────────────────────────────────────────
def run() -> None:
    home = Path(tempfile.mkdtemp(prefix="cm-sim-"))
    try:
        _assert_hermetic(home)
        print("=" * 72)
        print("CONSOLIDATE-MEMORY — accumulation / bloat simulation")
        print(f"hermetic HOME: {home}")
        print("=" * 72)

        # M projects with varied REAL stacks (v0.1.16: detection keys off declared deps / a .py / a
        # real .claude marker, NOT prose). alpha=python-only; beta=rag; gamma=gpu; delta=playwright —
        # so a stack-general:[python] fact reaches alpha (Probes A/C) while the others vary.
        projects = [
            _make_project(home, "alpha"),                          # python only (a .py)
            _make_project(home, "beta", deps=("lancedb",)),        # python + rag
            _make_project(home, "gamma", deps=("torch",)),         # python + gpu
            # hyphenated name: guards against _node_label mislabeling it "memory"
            _make_project(home, "delta-svc", deps=("playwright",)),  # python + playwright
        ]

        # ── Probe A: monotonic always-loaded growth across cycles ──────────────
        # Each cycle promotes a few facts UP to global (as a real pass does in
        # Phase 4), then every project pulls. Watch project "alpha"'s index.
        print("\n── Probe A: always-loaded index growth over cycles (project: alpha) ──")
        print("  Each cycle adds 1 user-global + 1 stack-general(python) fact, then pulls.")
        print(f"  {'cycle':>5} {'idx_lines':>10} {'idx_bytes':>10} {'facts':>6} {'orphans':>8}")
        curve = []
        for cycle in range(1, 9):
            _write_global(home, f"ug-pref-{cycle}", "user-global")
            _write_global(home, f"py-pattern-{cycle}", "stack-general", stacks="python")
            for p in projects:
                _pull(home, p)
            m = _measure(home, projects[0])
            curve.append(m)
            print(f"  {cycle:>5} {m['index_lines']:>10} {m['index_bytes']:>10} "
                  f"{m['facts']:>6} {m['orphans']:>8}")
        grew = curve[-1]["index_bytes"] > curve[0]["index_bytes"]
        never_shrank = all(curve[i]["index_bytes"] >= curve[i - 1]["index_bytes"]
                           for i in range(1, len(curve)))
        _verdict("A", "unmanaged baseline grows linearly (GC/budget are OPT-IN, not automatic)",
                 grew and never_shrank,
                 f"+{curve[-1]['index_bytes'] - curve[0]['index_bytes']} B over {len(curve)} cycles, "
                 f"monotonic={never_shrank} — still true by design (no auto-prune); the budget "
                 "ceiling now makes it VISIBLE (Probe F) and GC makes it reclaimable (Probe B)")

        # ── Probe B: orphan GC reclaims dead mirrors (FIX B) ───────────────────
        # Delete a canonical global fact. --pull alone can never reclaim its mirrors
        # (it only iterates LIVE globals) → they orphan in every project. `--gc --apply`
        # now finds and removes them + their index pointers.
        print("\n── Probe B: orphan GC after canonical deletion (FIX B) ──")
        victim = "ug-pref-1"
        (home / ".claude" / "memory" / f"{victim}.md").unlink()
        for p in projects:
            _pull(home, p)
        before = {p.name: _measure(home, p)["orphans"] for p in projects}
        for p in projects:
            _gc(home, p, apply=True)
        after = {p.name: _measure(home, p)["orphans"] for p in projects}
        print(f"  deleted canonical '{victim}', re-pulled → orphans per project: {before}")
        print(f"  ran --gc --apply on each      → orphans per project: {after}")
        _verdict("B", "orphan GC reclaims every dead mirror left by a canonical deletion",
                 sum(before.values()) == len(projects) and sum(after.values()) == 0,
                 f"{sum(before.values())} orphans → {sum(after.values())} after GC "
                 "(file + index pointer removed in each project)")

        # ── Probe C: STALE refresh now updates the always-loaded index hook (FIX C) ─
        print("\n── Probe C: index hook tracks canonical on description change (FIX C) ──")
        tgt = "py-pattern-2"
        _write_global(home, tgt, "stack-general", stacks="python",
                      desc="A COMPLETELY NEW RECALL KEY about deployment rollbacks")
        proj = projects[0]
        _pull(home, proj)
        store = _store(home, proj)
        body = (store / f"{tgt}.md").read_text(encoding="utf-8")
        index = (store / "MEMORY.md").read_text(encoding="utf-8")
        body_updated = "COMPLETELY NEW RECALL KEY" in body
        hook_updated = "deployment rollbacks" in index
        print(f"  changed description of canonical '{tgt}', re-pulled '{proj.name}'")
        print(f"  body mirror reflects new description : {body_updated}")
        print(f"  always-loaded index hook updated too : {hook_updated}")
        _verdict("C", "STALE refresh now upserts the index hook (no more silent tier-1 drift)",
                 body_updated and hook_updated,
                 "body AND the always-loaded index pointer both track the canonical's recall key")

        # ── Probe D: REAL-USAGE detection kills doc-mention false-positives (v0.1.16) ─
        # The old prose-keyword model let a README MENTION ('.claude', 'rag', 'scraper') confer a
        # stack — so a stdlib plugin false-matched rag/playwright and the stack-general tier collapsed
        # toward universal. Detection now keys off REAL markers: a prose-only mention no longer
        # triggers, while a genuine `.claude/` dir still does.
        print("\n── Probe D: real-usage stack detection precision (v0.1.16) ──")
        false_pos = _make_project(home, "epsilon")                # a .py, but NO .claude marker
        (false_pos / "README.md").write_text(                     # a prose-only ".claude" MENTION must NOT confer it
            "# epsilon\nThis repo merely talks about a .claude skill in prose.\n", encoding="utf-8")
        genuine = _make_project(home, "zeta", claude=True)        # a REAL .claude/ dir → claude-code
        _write_global(home, "cc-only", "stack-general", stacks="claude-code")
        _pull(home, false_pos)
        _pull(home, genuine)
        fp_got = (_store(home, false_pos) / "cc-only.md").exists()
        gen_got = (_store(home, genuine) / "cc-only.md").exists()
        print(f"  prose-only '.claude' MENTION inherited claude-code fact : {fp_got}  (want False)")
        print(f"  genuine '.claude/' DIR project inherited it             : {gen_got}  (want True)")
        _verdict("D", "stack detection keys off REAL usage — doc-mention false-positives eliminated",
                 (not fp_got) and gen_got,
                 "a prose '.claude' mention no longer confers claude-code; a real .claude/ dir does — "
                 "the precision fix that lets stack-general bind real stacks, not any repo whose README says so")

        # ── Probe E: GC never touches a project-authored (local) fact (SAFETY) ─
        print("\n── Probe E: GC safety — local facts are never reclaimed ──")
        safe = projects[0]
        local = _store(home, safe) / "ghost-canonical.md"
        # a LOCAL fact (no global_ref:) whose name collides with a non-existent canonical
        local.write_text("---\nname: ghost-canonical\nmetadata:\n  node_type: memory\n---\nmine\n",
                         encoding="utf-8")
        _gc(home, safe, apply=True)
        survived = local.exists()
        print(f"  local fact 'ghost-canonical' (no global_ref) after --gc --apply: "
              f"{'survived' if survived else 'WRONGLY DELETED'}")
        _verdict("E", "GC --apply leaves project-authored facts untouched (only mirrors)",
                 survived, "GC keys off `global_ref:`, so a name collision can't delete local work")

        # ── Probe F: network token observability + budget ceiling ──────────────
        import json as _json
        print("\n── Probe F: neural-network token observability + budget ceiling ──")
        net = _json.loads(_sync(home, "--tokens", str(projects[0]), "--json"))
        t = net["totals"]
        print(f"  nodes in network: {t['nodes']}  ·  basis: {net['basis']}")
        print(f"  TOTAL always-loaded ≈{t['always_loaded_tokens']} tok "
              f"(≈{t.get('mirror_index_tokens', 0)} mirror-driven) · "
              f"recall-pool ≈{t['recall_tokens']} tok")
        for n in sorted(net["nodes"], key=lambda d: -d["always_loaded_tokens"])[:6]:
            print(f"    {n['node'][:26]:<26} always ≈{n['always_loaded_tokens']:>5} "
                  f"(≈{n.get('mirror_index_tokens', 0)} mirror) · "
                  f"recall ≈{n['recall_tokens']:>6} · {n['facts']} facts ({n['shared']} shared)")
        measurable = t["nodes"] >= 1 and t["always_loaded_tokens"] > 0
        # The whole point of Probe A was that mirrors accumulate; the attribution must
        # therefore see them — and a node's mirror share can never exceed its total.
        mir = t.get("mirror_index_tokens", 0)
        attributed = mir > 0 and all(
            n.get("mirror_index_tokens", 0) <= n["always_loaded_tokens"] for n in net["nodes"])
        _verdict("F", "network token cost is observable per-node, in total, AND attributed "
                 "to mirror-vs-local (the over-budget lever)",
                 measurable and attributed,
                 f"{t['nodes']} nodes measured; ≈{mir} of ≈{t['always_loaded_tokens']} always-loaded "
                 "tok is mirror-driven — the share a global demote/GC (not local prune) would reclaim")

        # ── Probe G: GC refuses when the global store is ABSENT (data-loss guard) ──
        # Run-3 finding: with ~/.claude/memory missing, global_facts() returns [] →
        # empty canon → every mirror looks orphaned → gc --apply would delete them all.
        # The guard must REFUSE rather than wipe re-pullable / last-surviving memory.
        print("\n── Probe G: --gc refuses when the global store is absent (data-loss guard) ──")
        gp = projects[0]
        before_mirrors = [f for f in _store(home, gp).glob("*.md") if f.name != "MEMORY.md"]
        shutil.move(str(home / ".claude" / "memory"), str(home / ".claude" / "memory.bak"))
        out = _gc(home, gp, apply=True)
        after_mirrors = [f for f in _store(home, gp).glob("*.md") if f.name != "MEMORY.md"]
        shutil.move(str(home / ".claude" / "memory.bak"), str(home / ".claude" / "memory"))  # restore
        refused_absent = "refusing to GC" in out and len(after_mirrors) == len(before_mirrors)
        # also the EMPTY-but-present case: store dir exists with only the index, no facts
        empty = home / ".claude" / "memory-empty"
        empty.mkdir(parents=True, exist_ok=True)
        (empty / "MEMORY.md").write_text("# idx\n")
        shutil.move(str(home / ".claude" / "memory"), str(home / ".claude" / "memory.bak2"))
        shutil.move(str(empty), str(home / ".claude" / "memory"))
        out2 = _gc(home, gp, apply=True)
        after_empty = [f for f in _store(home, gp).glob("*.md") if f.name != "MEMORY.md"]
        shutil.rmtree(str(home / ".claude" / "memory"))
        shutil.move(str(home / ".claude" / "memory.bak2"), str(home / ".claude" / "memory"))  # restore
        refused_empty = "refusing to GC" in out2 and len(after_empty) == len(before_mirrors)
        print(f"  absent-store refused: {refused_absent} · empty-store refused: {refused_empty} · "
              f"mirrors preserved both times (from {len(before_mirrors)})")
        _verdict("G", "GC refuses on an absent OR empty global store (never mass-deletes mirrors)",
                 refused_absent and refused_empty and len(before_mirrors) > 0,
                 "neither a missing nor an empty store means 'all canonicals deleted' — mirrors preserved")

        # ── Probe H: rigor tier tracks FLOW magnitude, never the cumulative stock (v0.1.3) ──
        # Pure-function behavior + the F1 regression demo. NOT a claim the bands are
        # calibrated to real data — only that the function spreads and that the REJECTED
        # stock formula would collapse a mature store to HEAVY.
        print("\n── Probe H: rigor tier scales with flow magnitude, not the stock (v0.1.3) ──")
        _order = ms.TIER_ORDER  # canonical tier rank (single source in memory_status)
        grid = [ms.suggested_tier(0, m) for m in range(0, 13)]
        mono = all(_order[grid[i]] >= _order[grid[i - 1]] for i in range(1, len(grid)))
        reachable = set(grid) == {"LIGHT", "SUBSTANTIAL", "HEAVY"}
        flow_tier = ms.suggested_tier(0, 1)                  # 1 curated candidate, 0 commits → LIGHT
        stock_collapse = (0 + 104) > ms.TIER_SUBSTANTIAL_MAX  # git+reviewed magnitude → HEAVY
        print(f"  magnitude 0..12 → {grid}")
        print(f"  monotonic={mono} · all three tiers reachable={reachable}")
        print(f"  100-fact store on a 1-candidate pass: FLOW tier={flow_tier} (correct) · "
              f"git+reviewed(=104) would be {'HEAVY' if stock_collapse else '?'} (the avoided bug)")
        _verdict("H", "rigor tier scales with flow magnitude (spreads, monotonic); the rejected "
                 "stock formula would collapse a mature store to HEAVY",
                 mono and reachable and flow_tier == "LIGHT" and stock_collapse,
                 "flow keeps a 1-candidate pass LIGHT while git+memories_reviewed (=104) would "
                 "force HEAVY — the F1 stock-vs-flow defect avoided; bands are provisional/tunable")

        # ── Probe I: --persist accrues a per-project cycle log, idempotently + defensively (v0.1.4) ──
        # The apparatus that makes a future band calibration POSSIBLE: each cycle appends one
        # JSON line; a re-render of the same cycle is a no-op; an unstamped cycle is refused;
        # a malformed pre-existing line is tolerated; an absent dir is skipped (never crash).
        print("\n── Probe I: --persist cycle-log accrual (idempotent, defensive) (v0.1.4) ──")
        logdir = home / "persist-probe"
        logdir.mkdir()
        logpath = logdir / ".consolidation-log.jsonl"

        def _records() -> list:
            """Record-shaped log lines (a dict with a dict `marker` carrying a commit); junk skipped.
            Reads with errors='replace' so a non-UTF-8 byte in the log can't crash the TEST either."""
            out = []
            for ln in logpath.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and isinstance(obj.get("marker"), dict) and obj["marker"].get("commit"):
                    out.append(obj)
            return out

        rec1 = {"project": "alpha", "scope": {"git_commits": 10, "session_candidates": 3},
                "rigor": {"applied": "LIGHT", "override_reason": "already-consolidated flow"},
                "entries": [], "marker": {"commit": "aaa111", "timestamp": "2026-06-17T01:00:00Z"}}
        rec2 = {**rec1, "marker": {"commit": "bbb222", "timestamp": "2026-06-17T02:00:00Z"}}
        rd._persist(rec1, str(logdir))   # first append
        rd._persist(rec1, str(logdir))   # idempotent: same (commit, ts) → no duplicate
        rd._persist(rec2, str(logdir))   # distinct cycle → second line
        two_distinct = len(_records()) == 2
        round_trip = all(o.get("rigor", {}).get("applied") == "LIGHT" for o in _records())
        # unstamped (empty timestamp) cycle → refused (would collide on a (commit, '') key)
        rd._persist({"project": "x", "entries": [], "marker": {"commit": "ccc333", "timestamp": ""}}, str(logdir))
        refused_unstamped = len(_records()) == 2
        # EVERY malformed-line class must be tolerated by the dedup scan (it claims never-crash):
        # bad JSON, valid-JSON-non-object, a dict with a non-dict marker, AND a non-UTF-8 byte.
        with open(logpath, "a", encoding="utf-8") as fh:
            fh.write("{not valid json\n")             # JSONDecodeError
            fh.write('null\n42\n["x"]\n')              # valid JSON, non-object → .get AttributeError
            fh.write('{"marker": "not-a-dict"}\n')     # dict line, truthy non-dict marker → .get
        with open(logpath, "ab") as fhb:               # distinct name: a BINARY handle (bytes), not the text `fh` above
            fhb.write(b"\xff\xfe not utf-8\n")          # non-UTF-8 → UnicodeDecodeError (a ValueError)
        crashed = False
        try:
            rd._persist({**rec1, "marker": {"commit": "ddd444", "timestamp": "2026-06-17T03:00:00Z"}}, str(logdir))
        except Exception:  # noqa: BLE001 — ANY raise fails the tolerate-junk / never-crash contract
            crashed = True
        tolerated = (not crashed) and len(_records()) == 3
        # absent dir → skipped, never crashes, never created
        no_crash = True
        try:
            rd._persist(rec1, str(home / "nope"))
        except Exception:  # noqa: BLE001 — ANY crash fails the defensive contract
            no_crash = False
        absent_skipped = not (home / "nope").exists()
        print(f"  2 distinct + idempotent={two_distinct} · round-trip JSON={round_trip} · "
              f"unstamped refused={refused_unstamped} · all-malformed-classes tolerated={tolerated} · "
              f"absent-dir no-crash+skip={no_crash and absent_skipped}")
        _verdict("I", "--persist accrues a per-project cycle log idempotently + defensively",
                 two_distinct and round_trip and refused_unstamped and tolerated and no_crash and absent_skipped,
                 "cycles accrue for a future band refit; self-reported applied/override is the "
                 "over-rigor signal — longitudinal miss-detection (under-rigor) remains future work")

        # ── Probe J: slug-orphan + schema-drift detection on real tmp stores (v0.1.5) ──
        # smoke.py covers the PURE string/dict helpers; THIS exercises the FS-touching path:
        # near_duplicate_slugs over real sibling dirs, schema_drift reading real fact files +
        # the index, and the AC#1 "clean store → zero drift findings" (advisory absence allowed).
        print("\n── Probe J: slug-orphan + schema-drift detection (real tmp stores) (v0.1.5) ──")
        proj_root = home / ".claude" / "projects"
        # Two near-duplicate sibling slugs (the rename-orphan signature: '-' vs '_').
        twin_a = proj_root / "-home-you-project-Doc-Flo"
        twin_b = proj_root / "-home-you-project-Doc_Flo"
        for t in (twin_a, twin_b):
            (t / "memory").mkdir(parents=True, exist_ok=True)
        sibling_names = [p.name for p in proj_root.iterdir() if p.is_dir()]
        twin_hits = ms.near_duplicate_slugs(twin_a.name, sibling_names)
        orphan_detected = twin_b.name in twin_hits and twin_a.name not in twin_hits  # never flags itself

        # A DRIFTED store: one fact missing node_type, an index↔file mismatch (a fact on disk
        # with no index pointer + an index pointer to a non-existent file).
        drift_mem = twin_a / "memory"
        (drift_mem / "good-fact.md").write_text(
            "---\nname: good-fact\nmetadata:\n  node_type: memory\n  scope: project-local\n---\nbody\n",
            encoding="utf-8")
        (drift_mem / "no-node-type.md").write_text(   # missing the documented node_type
            "---\nname: no-node-type\ndescription: a fact\n---\nbody\n", encoding="utf-8")
        (drift_mem / "MEMORY.md").write_text(          # points at good-fact + a GHOST (no file)
            "# Memory Index\n\n- [good-fact](good-fact.md) — hook\n- [ghost](ghost.md) — dangling\n",
            encoding="utf-8")
        drift_facts = sorted(f for f in drift_mem.glob("*.md") if f.name != "MEMORY.md")
        drift_idx = ms.index_fact_names(drift_mem / "MEMORY.md")
        sd = ms.schema_drift(drift_facts, drift_idx)
        # missing node_type: exactly 1 (no-node-type.md). index mismatch: no-node-type (on disk,
        # not indexed) ^ ghost (indexed, no file) = 2. Advisory absence is NOT asserted against.
        drift_counts_ok = (sd["missing_node_type"] == 1 and sd["index_mismatch"] == 2
                           and ms.drift_findings(sd) == 3)  # exactly: 1 node_type + 2 index, 0 malformed

        # A CLEAN single store: every fact has node_type, the index matches the files exactly,
        # values are well-formed → drift_findings == 0 (advisory absence is permitted, NOT
        # counted as a finding — AC#1).
        clean_mem = proj_root / "-home-you-project-clean" / "memory"
        clean_mem.mkdir(parents=True, exist_ok=True)
        (clean_mem / "clean-fact.md").write_text(
            "---\nname: clean-fact\nmetadata:\n  node_type: memory\n  scope: user-global\n---\nbody\n",
            encoding="utf-8")
        (clean_mem / "MEMORY.md").write_text(
            "# Memory Index\n\n- [clean-fact](clean-fact.md) — hook\n", encoding="utf-8")
        clean_facts = sorted(f for f in clean_mem.glob("*.md") if f.name != "MEMORY.md")
        clean_sd = ms.schema_drift(clean_facts, ms.index_fact_names(clean_mem / "MEMORY.md"))
        clean_zero = ms.drift_findings(clean_sd) == 0

        print(f"  near-dup twin detected (excl. self): {orphan_detected}")
        print(f"  drifted store counts: missing_node_type={sd['missing_node_type']}, "
              f"index_mismatch={sd['index_mismatch']}, drift_findings={ms.drift_findings(sd)}")
        print(f"  clean store drift_findings: {ms.drift_findings(clean_sd)} "
              f"(advisory absent: scope={clean_sd['advisory_no_scope']}, origin={clean_sd['advisory_no_origin']})")
        _verdict("J", "Phase-0 detects a near-dup slug-orphan + counts real schema drift; a "
                 "clean single store yields ZERO drift findings (no false positives)",
                 orphan_detected and drift_counts_ok and clean_zero,
                 "near_duplicate_slugs flags the '-'/'_' twin (not itself); schema_drift counts the "
                 "missing node_type + index↔file mismatch; a documented store is drift-free "
                 "(advisory absence is allowed, not a finding)")

        # ── Probe K: local→canonical promotion hand-off (--promote) (v0.1.16) ──
        # The direction symmetric to --pull: hand a project-AUTHORED local fact UP to the canonical
        # global store + convert the origin's own copy into a managed mirror — single-shot, so a
        # completed call never leaves the dup/orphan a multi-step hand-done hand-off would. Asserts the
        # load-bearing invariant (a follow-up --pull on the origin is in-sync: the mirror is already
        # post-provenance, so no STALE rewrite) across create+norename, create+rename, and
        # reconcile/dedup onto an existing canonical — plus the FIVE refusal guards (Gate-2-hardened):
        # re-promote a mirror, a non-replicable scope, a dead stack-general (no `stacks:`), a
        # destination-clobber of a distinct local fact, and the reserved index name `MEMORY`.
        print("\n── Probe K: local→canonical promotion hand-off (--promote) (v0.1.16) ──")
        promo = projects[1]                       # beta: a lancedb dep → detect_stacks includes 'rag'
        pstore = _store(home, promo)
        pstore.mkdir(parents=True, exist_ok=True)
        g = home / ".claude" / "memory"

        def _local_fact(stem: str, scope: str, stacks: str = "") -> None:
            """Write a project-AUTHORED local fact (NO global_ref) + its index pointer into beta's store."""
            lines = ["---", f"name: {stem}", f"description: a local lesson about {stem}",
                     "metadata:", "  node_type: memory", "  type: feedback", f"  scope: {scope}"]
            if stacks:
                lines.append(f"  stacks: [{stacks}]")
            lines += ["---", "", f"The durable local fact {stem}.", ""]
            (pstore / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")
            idx = pstore / "MEMORY.md"
            head = idx.read_text(encoding="utf-8") if idx.exists() else "# Memory Index\n\n"
            if f"({stem}.md)" not in head:
                idx.write_text(head.rstrip() + f"\n- [{stem}]({stem}.md) — local\n", encoding="utf-8")

        def _bytes(name: str) -> str:
            return (pstore / f"{name}.md").read_text(encoding="utf-8")

        # (1) CREATE + no-rename: a local stack-general:[rag] fact → canonical + origin mirror.
        _local_fact("rag-chunk-overlap", "stack-general", stacks="rag")
        _promote(home, promo, "rag-chunk-overlap")
        created = (g / "rag-chunk-overlap.md").exists()
        origin_is_mirror = "global_ref:" in _bytes("rag-chunk-overlap")
        prov_has_beta = "beta" in ms._frontmatter((g / "rag-chunk-overlap.md").read_text(encoding="utf-8")).get("projects", "")
        before_pull = _bytes("rag-chunk-overlap")   # the load-bearing invariant: a follow-up --pull is …
        _pull(home, promo)
        after_pull = _bytes("rag-chunk-overlap")     # … in-sync — the post-provenance mirror is NOT rewritten
        create_ok = created and origin_is_mirror and prov_has_beta and before_pull == after_pull

        # (2) CREATE + rename: an underscored local name → a normalized canonical; the OLD-named
        # project-authored file AND its index pointer are removed (the dup/orphan guard).
        _local_fact("my_pref_note", "user-global")
        _promote(home, promo, "my_pref_note", "my-pref-note")
        renamed_canon = (g / "my-pref-note.md").exists()
        new_mirror = (pstore / "my-pref-note.md").exists() and "global_ref:" in _bytes("my-pref-note")
        old_gone = not (pstore / "my_pref_note.md").exists()
        old_ptr_gone = "(my_pref_note.md)" not in (pstore / "MEMORY.md").read_text(encoding="utf-8")
        b2 = _bytes("my-pref-note"); _pull(home, promo); a2 = _bytes("my-pref-note")
        rename_ok = renamed_canon and new_mirror and old_gone and old_ptr_gone and b2 == a2

        # (3) RECONCILE/dedup: a local dup whose CANON_NAME is an EXISTING canonical → the canonical is
        # NEVER overwritten, and the origin is (re)mirrored FROM that canonical (not the dup). Delete the
        # origin's case-(1) residual mirror first, so the re-creation is what the assertion tests (else
        # the check would pass on leftover state — a real bug a prior pass surfaced).
        existing = (g / "rag-chunk-overlap.md").read_text(encoding="utf-8")
        (pstore / "rag-chunk-overlap.md").unlink()
        _local_fact("rag_overlap_dupe", "stack-general", stacks="rag")
        _promote(home, promo, "rag_overlap_dupe", "rag-chunk-overlap")
        not_clobbered = (g / "rag-chunk-overlap.md").read_text(encoding="utf-8") == existing
        dupe_gone = not (pstore / "rag_overlap_dupe.md").exists()
        recon_mirror = _bytes("rag-chunk-overlap") if (pstore / "rag-chunk-overlap.md").exists() else ""
        # teeth: the re-created mirror carries the CANONICAL's body, never the dup's — proving reconcile
        # mirrored the existing canonical (a residue-only pass would leave the dup's marker, or nothing).
        dupe_mirrored = "global_ref:" in recon_mirror and "rag_overlap_dupe" not in recon_mirror
        reconcile_ok = not_clobbered and dupe_gone and dupe_mirrored

        # (4) GUARD: re-promoting an already-mirror local fact is refused (the idempotency guard).
        r_mirror = _promote(home, promo, "rag-chunk-overlap")
        refused_mirror = r_mirror.returncode != 0 and "already a managed mirror" in r_mirror.stderr

        # (5) GUARD: a stack-general fact with NO `stacks:` matches no project → refused, no canonical.
        _local_fact("stackless-rule", "stack-general")
        r_dead = _promote(home, promo, "stackless-rule")
        refused_dead = (r_dead.returncode != 0 and "declares no `stacks:`" in r_dead.stderr
                        and not (g / "stackless-rule.md").exists())

        # (6) GUARD: a scopeless/project-local fact is non-replicable → refused (Guard 1), no canonical.
        _local_fact("local-only-note", "project-local")
        r_scope = _promote(home, promo, "local-only-note")
        refused_scope = (r_scope.returncode != 0 and "never replicates" in r_scope.stderr
                         and not (g / "local-only-note.md").exists())

        # (7) GUARD: a RENAME whose destination already holds a DISTINCT project-authored fact must NOT
        # clobber it (Guard 3) — neither file is touched, and no canonical is written.
        _local_fact("keepme-notes", "user-global")          # a valuable, unrelated local fact
        keep_before = _bytes("keepme-notes")
        _local_fact("incoming_pref", "user-global")         # promote THIS, renamed onto keepme-notes
        r_clob = _promote(home, promo, "incoming_pref", "keepme-notes")
        refused_clobber = (r_clob.returncode != 0 and _bytes("keepme-notes") == keep_before
                           and (pstore / "incoming_pref.md").exists() and not (g / "keepme-notes.md").exists())

        # (8) GUARD: the reserved index name `MEMORY` is refused — never clobber a store's MEMORY.md index.
        _local_fact("idx-attack", "user-global")
        idx_before = (pstore / "MEMORY.md").read_text(encoding="utf-8")   # AFTER _local_fact's own pointer add
        r_mem = _promote(home, promo, "idx-attack", "MEMORY")
        refused_memory = (r_mem.returncode != 0 and "reserved index name" in r_mem.stderr
                          and (pstore / "MEMORY.md").read_text(encoding="utf-8") == idx_before)

        print(f"  create+norename={create_ok} · create+rename={rename_ok} · reconcile/dedup={reconcile_ok}")
        print(f"  guards: re-promote-mirror={refused_mirror} · dead-stack-general={refused_dead} · "
              f"scopeless={refused_scope} · no-clobber={refused_clobber} · reserved-MEMORY={refused_memory}")
        _verdict("K", "--promote hands a local fact to the canonical store + mirrors the origin "
                 "atomically (in-sync follow-up pull, no dup/orphan); its 5 guards refuse a re-promote, "
                 "a non-replicable scope, a dead stack-general, a destination-clobber, and `MEMORY`",
                 create_ok and rename_ok and reconcile_ok and refused_mirror and refused_dead
                 and refused_scope and refused_clobber and refused_memory,
                 "canonical written, origin converted to a POST-provenance mirror (follow-up --pull is "
                 "in-sync, not STALE), a rename removes the old file + pointer, an existing canonical is "
                 "never clobbered, and the five guards block every unsafe/unreplicable promotion")

        # ── Summary curve, for the audit ──────────────────────────────────────
        print("\n── Headline metric: always-loaded per-session tax (project: alpha) ──")
        first, last = curve[0], curve[-1]
        slope = (last["index_bytes"] - first["index_bytes"]) / max(len(curve) - 1, 1)
        print(f"  index bytes: {first['index_bytes']} → {last['index_bytes']} "
              f"(+{last['index_bytes'] - first['index_bytes']} B over {len(curve)} cycles, "
              f"linear ≈ +{slope:.0f} B/cycle)")
        print(f"  recall facts: {first['facts']} → {last['facts']} "
              f"(+{last['facts'] - first['facts']})")
        print("  The baseline still grows (pruning stays a human-in-the-loop call), but it is")
        print("  now VISIBLE (token budget + ⚠), RECLAIMABLE (--gc), and COHERENT (hook upsert).")
    finally:
        shutil.rmtree(home, ignore_errors=True)


_results: list[tuple[str, str, bool, str]] = []


def _verdict(tag: str, claim: str, holds: bool, detail: str) -> None:
    """Each probe asserts an EXPECTED property of the (now-fixed) lifecycle. `holds`
    True = the property is observed (good); False = a regression to investigate."""
    _results.append((tag, claim, holds, detail))
    mark = "✓ HOLDS" if holds else "✗ REGRESSION"
    print(f"  [{mark}] {claim}")
    print(f"            {detail}")


if __name__ == "__main__":
    run()
    print("\n" + "=" * 72)
    print("LIFECYCLE PROPERTIES (✓ = holds after fixes; ✗ = regression):")
    for tag, claim, holds, _ in _results:
        print(f"  {tag}: {'✓' if holds else '✗'} {claim}")
    ok = all(h for _, _, h, _ in _results)
    print("=" * 72)
    print("All lifecycle properties hold." if ok else "REGRESSION — see ✗ above.")
    raise SystemExit(0 if ok else 1)
