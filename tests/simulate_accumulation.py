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
    (in-sync follow-up pull, no dup/orphan; never clobbers an existing canonical),
  L remediation triage stages an inherited over-budget backlog (mechanical A/B/C ranking +
    projected lean rebuild), routes the lever (prune/gc/justify), and NEVER deletes.

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
    slug = ms.slug_for(project_dir)   # single source (v0.1.17: '/'+'_' → '-'); matches what the child CLI computes
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


def _promote_racing(home: Path, project_dir: Path, local_fact: str, canon_name: str,
                     winner_text: str) -> subprocess.CompletedProcess:
    """v0.1.71 Gate-2a (Track D-2b): exercise `promote()`'s create-create race INTEGRATION, not
    just `_create_exclusive` in isolation (the gap the review found — the isolated helper had
    teeth, but nothing proved `promote()` actually wires it up / handles a `False` return
    correctly end-to-end). `promote()` is a single, synchronous function call, so a REAL two-
    process race is non-deterministic to reproduce in a test; instead this runs `promote()`
    directly (not via the CLI's `main()`, which reads `sys.argv`) in a FRESH subprocess (still
    HOME-sandboxed — `sync_global.GLOBAL` computes correctly from the overridden $HOME at import
    time, same hermetic guarantee `_promote` gets) with `_nonglobal_wikilinks` monkeypatched to
    inject the race deterministically: it's called (Guard 4) AFTER the `reconcile` check but
    BEFORE the write this item hardens, with `global_dir`/`exclude` already equal to
    `GLOBAL`/`canon_name` — exactly the ingredients needed to plant a "winner" canonical at the
    precise moment another process would have. Returns a `CompletedProcess`-shaped result
    (`returncode`, `stderr`) so callers can assert identically to `_promote`."""
    script = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(SYNC.parent)!r})
import sync_global as sg

_orig = sg._nonglobal_wikilinks
def _patched(text, global_dir, exclude=""):
    (global_dir / (exclude + ".md")).write_text({winner_text!r}, encoding="utf-8")
    return _orig(text, global_dir, exclude=exclude)
sg._nonglobal_wikilinks = _patched

rc = sg.promote(Path({str(project_dir)!r}), {local_fact!r}, {canon_name!r})
sys.exit(rc)
"""
    return subprocess.run([sys.executable, "-c", script],
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
        # M2 (v0.1.39): a DIVERGENT reconcile (the dupe's body ≠ the canonical's — _local_fact embeds the stem)
        # is REFUSED without --prefer-canonical (the silent-data-loss guard), leaving the dupe untouched.
        _m2 = _promote(home, promo, "rag_overlap_dupe", "rag-chunk-overlap")
        m2_refuses_divergent = (_m2.returncode != 0 and "differs" in _m2.stderr.lower()
                                and (pstore / "rag_overlap_dupe.md").exists())
        # the DEDUP intent (canonical is authoritative, drop the local body) proceeds WITH --prefer-canonical.
        _promote(home, promo, "rag_overlap_dupe", "rag-chunk-overlap", "--prefer-canonical")
        not_clobbered = (g / "rag-chunk-overlap.md").read_text(encoding="utf-8") == existing
        dupe_gone = not (pstore / "rag_overlap_dupe.md").exists()
        recon_mirror = _bytes("rag-chunk-overlap") if (pstore / "rag-chunk-overlap.md").exists() else ""
        # teeth: the re-created mirror carries the CANONICAL's body, never the dup's — proving reconcile
        # mirrored the existing canonical (a residue-only pass would leave the dup's marker, or nothing).
        dupe_mirrored = "global_ref:" in recon_mirror and "rag_overlap_dupe" not in recon_mirror
        reconcile_ok = m2_refuses_divergent and not_clobbered and dupe_gone and dupe_mirrored

        # (4) GUARD: re-promoting an already-mirror local fact is refused (the idempotency guard).
        r_mirror = _promote(home, promo, "rag-chunk-overlap")
        refused_mirror = r_mirror.returncode != 0 and "already a managed mirror" in r_mirror.stderr

        # (5) GUARD: a stack-general fact with NO `stacks:` matches no project → refused, no canonical.
        _local_fact("stackless-rule", "stack-general")
        r_dead = _promote(home, promo, "stackless-rule")
        refused_dead = (r_dead.returncode != 0 and "declares no `stacks:`" in r_dead.stderr
                        and not (g / "stackless-rule.md").exists())
        # (5b) GUARD (M4, v0.1.39): a stack-general fact whose stacks: are UNDETECTABLE (detect_stacks can't
        # emit them — e.g. `release`) also matches no project → refused, no canonical.
        _local_fact("undetectable-rule", "stack-general", stacks="release")
        r_undet = _promote(home, promo, "undetectable-rule")
        refused_undetectable = (r_undet.returncode != 0 and "never emit" in r_undet.stderr.lower()
                                and not (g / "undetectable-rule.md").exists())

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

        # (9) GUARD (v0.1.71 Gate-2a, Track D-2b): two processes racing to CREATE the same NEW
        # canon_name — the loser must be refused, not silently clobber the winner's canonical NOR
        # have its own local fact erased via the follow-on mirror write. `_create_exclusive` alone
        # had a unit test (smoke.py); this exercises it THROUGH `promote()`'s actual control flow,
        # closing the coverage gap the review found (nothing previously proved the integration
        # point — the `if not reconcile and not _create_exclusive(...)` branch — works end to end).
        _local_fact("race-fact", "user-global")
        _race_local_before = _bytes("race-fact")
        _winner_text = "---\nname: race-canon\nmetadata:\n  scope: user-global\n---\nWINNER (another process)\n"
        r_race = _promote_racing(home, promo, "race-fact", "race-canon", _winner_text)
        refused_race = (r_race.returncode != 0 and "concurrently" in r_race.stderr
                        and (g / "race-canon.md").read_text(encoding="utf-8") == _winner_text
                        and (pstore / "race-fact.md").exists() and _bytes("race-fact") == _race_local_before
                        and not list(g.glob("race-canon.md.tmp*")))

        print(f"  create+norename={create_ok} · create+rename={rename_ok} · reconcile/dedup={reconcile_ok}")
        print(f"  guards: re-promote-mirror={refused_mirror} · dead-stack-general={refused_dead} · "
              f"undetectable-stack={refused_undetectable} · scopeless={refused_scope} · "
              f"no-clobber={refused_clobber} · reserved-MEMORY={refused_memory} · "
              f"create-create-race={refused_race}")
        _verdict("K", "--promote hands a local fact to the canonical store + mirrors the origin atomically "
                 "(in-sync follow-up pull, no dup/orphan); a divergent reconcile is refused (M2; "
                 "--prefer-canonical to dedup); its 7 guards refuse a re-promote, a non-replicable scope, a "
                 "dead stack-general (empty OR undetectable stacks), a destination-clobber, `MEMORY`, and a "
                 "concurrent create-create race onto the same NEW canon_name (v0.1.71, Track D-2b)",
                 create_ok and rename_ok and reconcile_ok and refused_mirror and refused_dead
                 and refused_undetectable and refused_scope and refused_clobber and refused_memory
                 and refused_race,
                 "canonical written, origin converted to a POST-provenance mirror (follow-up --pull is "
                 "in-sync, not STALE), a rename removes the old file + pointer, an existing canonical is "
                 "never clobbered, the guards block every unsafe/unreplicable promotion, and a racing "
                 "concurrent create is refused rather than silently destroying the loser's own fact")

        # ── Probe L: inherited-backlog remediation triage (v0.1.18) ────────────
        # The app PREVENTS incremental bloat but must also REMEDIATE a backlog inherited from CC's
        # Auto-Dream (memex: 110 facts, index 5.5× over, 30 orphans; the one dream that ran GREW the index).
        # Build an Auto-Dream-style bloated store and assert `remediation_triage`: (1) over-budget → staged
        # candidates by MECHANICAL membership (A orphans / B trackers / C dated-oversized, content_review-
        # flagged) + a projected lean-rebuild under budget; (2) lever ROUTED (local→prune, mirror-dominated→
        # gc, all-durable→justify — no deadlock); (3) NEVER deletes (pure analysis); (4) a clean under-budget
        # store → {} (no false alarm). Calls the pure fn directly (no CLI/slug).
        print("\n── Probe L: inherited-backlog remediation triage (v0.1.18) ──")
        bl = home / ".claude" / "projects" / "-bloated" / "memory"
        bl.mkdir(parents=True, exist_ok=True)

        def _wf(name: str, body_lines: int, mirror: bool = False) -> None:
            fm = ["---"]
            if mirror:
                fm.append(f"# global_ref: {name}")          # col-0 first frontmatter line → _is_mirror True
            fm += [f"name: {name}", "metadata:", "  node_type: memory", "  type: project", "---", ""]
            fm += [f"durable body line {i} about {name}." for i in range(body_lines)]
            (bl / f"{name}.md").write_text("\n".join(fm) + "\n", encoding="utf-8")

        trackers = ["build_status", "p1_tracker", "shipped_log", "roadmap_notes", "next_priorities", "progress_main"]
        dated = ["alpha_2026_05_28", "beta_2026_06_01", "gamma_2026_05_15", "delta_2026_06_07"]
        oversized = ["bigdump_one", "bigdump_two"]          # non-dated non-tracker, huge body → class C
        durable = ["use-placeholders", "prefer-x", "avoid-y", "do-z"]
        mirrors = ["mir-one", "mir-two"]
        orphans = ["orphan_a_2026_05_01", "orphan_b", "orphan_c", "orphan_d", "orphan_e"]   # NOT indexed → A
        for n in trackers + dated:
            _wf(n, 30)
        for n in oversized:
            _wf(n, 900)                                     # ~> _OVERSIZED_TOK
        for n in durable:
            _wf(n, 3)
        for n in mirrors:
            _wf(n, 3, mirror=True)
        for n in orphans:
            _wf(n, 20)
        idx = ["# Memory Index", ""]
        for n in trackers + dated + oversized + durable + mirrors:   # index everything EXCEPT the orphans
            idx.append(f"- [{n}]({n}.md) — " + ("a long verbose recall hook about " + n + " that wastes always-loaded budget ") * 4)  # *4 keeps the fixture > the 1500 budget (v0.1.x re-ground)
        (bl / "MEMORY.md").write_text("\n".join(idx) + "\n", encoding="utf-8")

        facts = [f for f in bl.glob("*.md") if f.name != "MEMORY.md"]
        before_n = len(facts)
        idx_names = ms.index_fact_names(bl / "MEMORY.md")
        idx_tok = ms.est_tokens((bl / "MEMORY.md").read_text(encoding="utf-8"))
        mir_stems = {f.stem for f in facts if ms._is_mirror(f.read_text(encoding="utf-8"))}
        mir_lines = [ln for ln in (bl / "MEMORY.md").read_text(encoding="utf-8").splitlines()
                     if any(f"]({s}.md)" in ln for s in mir_stems)]
        mir_tok = ms.est_tokens("\n".join(mir_lines))
        tri = ms.remediation_triage(facts, idx_names, idx_tok, mir_tok)
        st = tri.get("stages", {})
        over = idx_tok > ms.INDEX_TOKEN_BUDGET
        members_ok = (len(st.get("A_orphans", [])) == len(orphans)
                      and len(st.get("B_trackers", [])) == len(trackers)
                      and len(st.get("C_dated_oversized", [])) == len(dated) + len(oversized))
        c_flagged = bool(st.get("C_dated_oversized")) and all(c.get("content_review") for c in st["C_dated_oversized"])
        keep_ok = tri.get("keep_core") == len(durable) + len(mirrors)
        lever_ok = tri.get("lever") == "prune"                                   # local-dominated (tiny mirror share)
        proj_ok = 0 < tri.get("projected_index", 1 << 30) < ms.INDEX_TOKEN_BUDGET  # lean rebuild back under budget
        no_delete = len([f for f in bl.glob("*.md") if f.name != "MEMORY.md"]) == before_n
        # clean under-budget store → {} (no false alarm)
        cl = home / ".claude" / "projects" / "-cleanrem" / "memory"
        cl.mkdir(parents=True, exist_ok=True)
        (cl / "a.md").write_text("---\nname: a\nmetadata:\n  node_type: memory\n---\nx\n", encoding="utf-8")
        (cl / "MEMORY.md").write_text("# Memory Index\n- [a](a.md) — hook\n", encoding="utf-8")
        clf = [f for f in cl.glob("*.md") if f.name != "MEMORY.md"]
        clean_quiet = ms.remediation_triage(clf, ms.index_fact_names(cl / "MEMORY.md"),
                                            ms.est_tokens((cl / "MEMORY.md").read_text(encoding="utf-8")), 0) == {}
        # mirror-dominated routing → gc (same store, mirror share forced > 50%)
        gc_route = ms.remediation_triage(facts, idx_names, idx_tok, int(idx_tok * 0.6)).get("lever") == "gc"
        # all-durable over-budget → justify (no deadlock): only durable facts, but a bloated index
        nd = home / ".claude" / "projects" / "-alldurable" / "memory"
        nd.mkdir(parents=True, exist_ok=True)
        for n in durable:
            (nd / f"{n}.md").write_text("---\nname: " + n + "\nmetadata:\n  node_type: memory\n---\nshort\n", encoding="utf-8")
        ndi = ["# Memory Index", ""] + [f"- [{n}]({n}.md) — " + ("verbose hook " * 120) for n in durable]
        (nd / "MEMORY.md").write_text("\n".join(ndi) + "\n", encoding="utf-8")
        ndf = [f for f in nd.glob("*.md") if f.name != "MEMORY.md"]
        justify_route = ms.remediation_triage(ndf, ms.index_fact_names(nd / "MEMORY.md"),
                                              ms.est_tokens((nd / "MEMORY.md").read_text(encoding="utf-8")), 0).get("lever") == "justify"
        print(f"  over-budget={over} · members(A/B/C)={members_ok} · C-flagged={c_flagged} · keep={keep_ok} · "
              f"lever=prune={lever_ok} · projected<budget={proj_ok}")
        print(f"  never-delete={no_delete} · clean-quiet={clean_quiet} · mirror→gc={gc_route} · all-durable→justify={justify_route}")
        _verdict("L", "remediation triage stages an over-budget backlog (mechanical A/B/C + projected lean "
                 "rebuild), routes the lever (prune/gc/justify, no deadlock), NEVER deletes, stays quiet on a "
                 "healthy store",
                 over and members_ok and c_flagged and keep_ok and lever_ok and proj_ok and no_delete
                 and clean_quiet and gc_route and justify_route,
                 "the inherited-backlog remediation: surfaces ranked candidates for the operator to judge "
                 "(pure — never auto-deletes), with the over-budget gate + mirror-vs-local lever routing")

        # ── Probe M: v0.1.18 beta-patch fixes (C1 archive-exclude · C2 multi-surface orphan · E · G) ──────
        # First-party beta on memex surfaced: the triage globbed SHIPPED.md (a relocated archive) as a fact →
        # B-tracker → "evict" (would nuke it); and flagged CLAUDE.md-referenced facts as evict-able orphans
        # (would dangle the committed guest file). Build a store + a CLAUDE.md + a SHIPPED.md archive and assert
        # the fixes. Uses a real project dir under the hermetic HOME so build_context resolves the slug.
        print("\n── Probe M: v0.1.18 beta-patch (archive-exclude · multi-surface orphan · seed) ──")
        proj = home / "projects-src" / "memexlike"
        proj.mkdir(parents=True, exist_ok=True)
        store = home / ".claude" / "projects" / ms.slug_for(proj) / "memory"
        store.mkdir(parents=True, exist_ok=True)

        def _mf(name: str, body: int = 60) -> None:
            (store / f"{name}.md").write_text(
                "---\nname: " + name + "\nmetadata:\n  node_type: memory\n  type: project\n---\n"
                + "\n".join(f"body line {i} of {name}" for i in range(body)) + "\n", encoding="utf-8")

        indexed = ["durable-a", "durable-b"]
        unindexed_true = ["orphan_true_one", "orphan_true_two"]            # referenced nowhere → A
        unindexed_ref = ["referenced_in_claude_2026_05_01"]                # in CLAUDE.md prose → R, NOT A
        trackers = ["build_status", "p1_tracker"]
        for n in indexed + unindexed_true + unindexed_ref + trackers:
            _mf(n)
        idx = ["# Memory Index", ""] + [f"- [{n}]({n}.md) — " + ("verbose hook " * 120) for n in indexed + trackers]
        (store / "MEMORY.md").write_text("\n".join(idx) + "\n", encoding="utf-8")   # over budget, leaves orphans/ref unindexed
        (store / "SHIPPED.md").write_text("# Shipped\n" + "\n".join(f"- [item {i}](shipped_{i}.md) — done" for i in range(10)) + "\n", encoding="utf-8")
        (proj / "CLAUDE.md").write_text("# Conventions\n\nSee referenced_in_claude_2026_05_01 for the X approach.\n" + ("filler " * 200) + "\n", encoding="utf-8")

        _rh = os.environ.get("HOME")
        os.environ["HOME"] = str(home)            # build_context uses Path.home() — point it at the hermetic store
        ctxm = ms.build_context(proj)
        stm = ctxm["remediation"].get("stages", {})
        a_stems = [c["stem"] for c in stm.get("A_orphans", [])]
        r_stems = [c["stem"] for c in stm.get("R_referenced", [])]
        c1 = (not any(f.name == "SHIPPED.md" for f in ctxm["fact_files"])
              and not any(c["stem"] == "SHIPPED" for s in stm.values() for c in s))      # archive never a fact/candidate
        c2_ref = "referenced_in_claude_2026_05_01" in r_stems and "referenced_in_claude_2026_05_01" not in a_stems
        c2_true = set(unindexed_true) <= set(a_stems)                                     # genuine orphans still in A
        seedm = ms.seed_record(ctxm).get("remediation", {})
        g_omit = ("pruned" not in seedm and "achieved_index" not in seedm
                  and "achieved_recall" not in seedm and "projected_index" in seedm)
        # E (discriminating): simulate the write-truncate RACE — first index read 0, re-read = real over-budget.
        # FAILS if the re-read guard is removed (the transient 0 would clear the gate). The over-budget index
        # written above stays in place.
        _real_measure = ms._measure
        _idx_path = store / "MEMORY.md"
        _seen = {"n": 0}

        def _racy_measure(p: Path) -> tuple:
            if p == _idx_path:
                _seen["n"] += 1
                if _seen["n"] == 1:
                    return (0, 0, 0)                                                       # the truncate-window read
            return _real_measure(p)
        ms._measure = _racy_measure
        try:
            ctxe = ms.build_context(proj)
        finally:
            ms._measure = _real_measure
        e_ok = ctxe["remediation"] != {} and bool(ctxe["remediation"].get("required"))     # re-read settled → gate still fires
        if _rh is not None:
            os.environ["HOME"] = _rh                                                       # restore the real HOME
        else:
            os.environ.pop("HOME", None)
        print(f"  C1 archive-excluded={c1} · C2 ref→R-not-A={c2_ref} · C2 true-orphan-in-A={c2_true} · "
              f"G seed-omits-achieved={g_omit} · E race-settled={e_ok}")
        _verdict("M", "beta patch: archive-index docs excluded from facts (C1); CLAUDE.md-referenced facts are "
                 "NOT safe-evict orphans, true orphans still are (C2); seed omits achieved_* (G); a write-truncate "
                 "race (first index read 0) is settled by the re-read so the gate still fires (E)",
                 c1 and c2_ref and c2_true and g_omit and e_ok,
                 "the multi-surface orphan safety + archive protection + honest seed — never dangle the guest "
                 "file or nuke the archive")

        # ── Probe N: v0.1.21 defect-patch (standing-justify · D4 wikilink · D5 · D8 · resolve_wikilink) ──
        # A v0.1.19 beta on memex surfaced 9 defects. Build a bloated store + assert: resolve_wikilink resolves
        # slug-drift; a [[wikilinked]] fact is R (not a safe-evict orphan) — D4; the triage leads with index-relief
        # stages — D8; reaches_budget reflects whether a prune can reach budget — D5; and the standing-justify
        # delta-detector suppresses within Δ, fires past Δ, and FAILS OPEN on garbage — D6/D7.
        print("\n── Probe N: v0.1.21 (standing-justify · wikilink-aware orphan · D5/D8) ──")
        _rw = {"qwen_migration_research_2026_05_26", "keyfigures-example-hallucination", "use-placeholders"}
        rw_ok = (ms.resolve_wikilink("qwen-migration-research", _rw) == "qwen_migration_research_2026_05_26"
                 and ms.resolve_wikilink("keyfigures-example-hallucination-2026-05-28", _rw) == "keyfigures-example-hallucination"
                 and ms.resolve_wikilink("use-placeholders", _rw) == "use-placeholders"
                 and ms.resolve_wikilink("nonexistent-xyz-thing", _rw) is None)
        fo_ok = ms._standing_baseline("garbage") is None and ms._standing_baseline({"facts": 50}) == 50 and ms._standing_baseline({}) is None
        pn = home / "projects-src" / "memexN"
        pn.mkdir(parents=True, exist_ok=True)
        nstore = home / ".claude" / "projects" / ms.slug_for(pn) / "memory"
        nstore.mkdir(parents=True, exist_ok=True)

        def _nf(name: str, body: int, link: str = "") -> None:
            b = ["---", f"name: {name}", "metadata:", "  node_type: memory", "  type: project", "---", ""]
            if link:
                b.append(f"see [[{link}]] for the details")
            b += [f"line {i} of {name}" for i in range(body)]
            (nstore / f"{name}.md").write_text("\n".join(b) + "\n", encoding="utf-8")

        _nf("hub_fact", 40, link="form-research")          # INDEXED, wikilinks (across drift) to the unindexed dated fact
        _nf("form_research_2026_06_15", 30)                # unindexed BUT wikilinked → must be R, not A (D4)
        _nf("lonely_orphan_2026_06_01", 30)               # unindexed, unreferenced → A (true orphan)
        _nf("build_status", 40)                            # tracker → B
        _nf("dur-a", 3)
        _nf("dur-b", 3)
        (nstore / "MEMORY.md").write_text("\n".join(["# Memory Index", ""] + [
            f"- [{n}]({n}.md) — " + ("verbose hook " * 120) for n in ["hub_fact", "build_status", "dur-a", "dur-b"]]) + "\n", encoding="utf-8")

        _rh = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        ctxn = ms.build_context(pn)
        stn = ctxn["remediation"].get("stages", {})
        A = [c["stem"] for c in stn.get("A_orphans", [])]
        R = [c["stem"] for c in stn.get("R_referenced", [])]
        d4_ok = "form_research_2026_06_15" in R and "form_research_2026_06_15" not in A and "lonely_orphan_2026_06_01" in A
        d5_ok = ctxn["remediation"].get("reaches_budget") is True   # small keep core → a prune CAN reach budget
        _sec = ms._remediation_section(ctxn["remediation"])
        d8_ok = bool(ctxn["remediation"].get("required")) and not any("TRUE orphans" in str(s) for s in _sec[:3])
        _nfacts = len(ctxn["fact_files"])
        _mk = nstore / ".consolidation-state.json"
        _mk.write_text(json.dumps({"commit": "x", "timestamp": "2026-06-20T00:00:00Z",
                                   "standing_justify": {"facts": _nfacts, "index_tokens": 10**9, "at": "2026-06-20T00:00:00Z"}}), encoding="utf-8")  # v0.1.23: generous token baseline isolates the FACT-axis (the token-axis is Probe P)
        sj_suppressed = ms.build_context(pn)["remediation"].get("standing_justified") is True
        _mk.write_text(json.dumps({"commit": "x", "timestamp": "2026-06-20T00:00:00Z",
                                   "standing_justify": {"facts": _nfacts - ms._STANDING_JUSTIFY_DELTA - 1, "index_tokens": 10**9, "at": "2026-06-20T00:00:00Z"}}), encoding="utf-8")  # v0.1.23: generous token baseline isolates the FACT-axis (the token-axis is Probe P)
        _gr = ms.build_context(pn)["remediation"]
        sj_fires = _gr.get("required") is True and not _gr.get("standing_justified")
        _mk.write_text(json.dumps({"commit": "x", "timestamp": "2026-06-20T00:00:00Z", "standing_justify": "garbage"}), encoding="utf-8")
        sj_failopen = ms.build_context(pn)["remediation"].get("required") is True
        if _rh is not None:
            os.environ["HOME"] = _rh
        else:
            os.environ.pop("HOME", None)
        print(f"  resolve_wikilink={rw_ok} · fail-open-helper={fo_ok} · D4 wikilinked→R-not-A={d4_ok} · "
              f"D8 index-relief-first={d8_ok} · D5 reaches_budget={d5_ok}")
        print(f"  standing-justify: suppressed-within-Δ={sj_suppressed} · fires-past-Δ={sj_fires} · fail-open-garbage={sj_failopen}")
        _verdict("N", "v0.1.21 defects: resolve_wikilink resolves slug-drift; a [[wikilinked]] fact is R not a "
                 "safe-evict orphan (D4); triage leads with index-relief stages (D8); reaches_budget set (D5); the "
                 "standing-justify delta-detector suppresses within Δ, fires past Δ, fails OPEN on garbage (D6/D7)",
                 rw_ok and fo_ok and d4_ok and d8_ok and d5_ok and sj_suppressed and sj_fires and sj_failopen,
                 "the over-budget gate becomes a delta-detector (keeps teeth, kills alarm fatigue) + reachability-aware orphans")

        # ── Probe O: v0.1.22 foundation (whole-CLAUDE.md-hierarchy measure + deterministic audit trail) ──
        # The empirics showed memex pays ~54k tok of nested CLAUDE.md/turn, invisible to the tool. Assert the
        # hierarchy measure computes the heaviest root→leaf chain (excl .venv), and the audit trail detects
        # created/modified/deleted via content-hash (unchanged ≠ op; infra excluded; measuring is read-only).
        print("\n── Probe O: v0.1.22 (CLAUDE.md hierarchy measure · deterministic audit trail) ──")
        repoO = home / "repoO"
        (repoO / "a" / "b").mkdir(parents=True, exist_ok=True)
        (repoO / ".venv").mkdir(parents=True, exist_ok=True)
        (repoO / "CLAUDE.md").write_text("root " * 20, encoding="utf-8")
        (repoO / "a" / "CLAUDE.md").write_text("mid " * 200, encoding="utf-8")
        (repoO / "a" / "b" / "CLAUDE.md").write_text("leaf " * 80, encoding="utf-8")
        (repoO / ".venv" / "CLAUDE.md").write_text("vendored " * 999, encoding="utf-8")   # excluded
        hO = ms.claude_md_hierarchy(repoO)
        chainO = sum(ms.est_tokens((repoO / p).read_text()) for p in ("CLAUDE.md", "a/CLAUDE.md", "a/b/CLAUDE.md"))
        hier_ok = (hO["total_files"] == 3 and hO["worst_path"].replace("\\", "/") == "a/b"
                   and hO["worst_path_tokens"] == chainO)
        projO = home / "projects-src" / "auditO"
        projO.mkdir(parents=True, exist_ok=True)
        (projO / "CLAUDE.md").write_text("conv\n", encoding="utf-8")
        stO = home / ".claude" / "projects" / ms.slug_for(projO) / "memory"
        stO.mkdir(parents=True, exist_ok=True)
        for _n, _b in (("keep", "keep body\n"), ("edit", "v1\n"), ("gone", "delete me\n")):
            (stO / f"{_n}.md").write_text(_b, encoding="utf-8")
        (stO / ".consolidation-log.jsonl").write_text('{"x":1}\n', encoding="utf-8")       # infra → must NOT snapshot
        _rhO = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        before = ms.audit_snapshot(projO)
        infra_excluded = not any("consolidation-log" in k or "mutation-log" in k for k in before)
        (stO / "edit.md").write_text("v2 a longer body now\n", encoding="utf-8")           # modified
        (stO / "gone.md").unlink()                                                          # deleted
        (stO / "new.md").write_text("brand new fact\n", encoding="utf-8")                   # created
        diffO = ms.audit_diff(before, ms.audit_snapshot(projO))
        opmap = {o["path"].rsplit("/", 1)[-1]: o["op"] for o in diffO["operations"]}
        audit_ok = (opmap.get("edit.md") == "modified" and opmap.get("gone.md") == "deleted"
                    and opmap.get("new.md") == "created" and "keep.md" not in opmap
                    and diffO["memory"]["created"] == 1 and diffO["memory"]["modified"] == 1
                    and diffO["memory"]["deleted"] == 1)
        snap_a = ms.audit_snapshot(projO)
        ms.claude_md_hierarchy(repoO)                                                       # measuring must not mutate
        readonly_ok = snap_a == ms.audit_snapshot(projO) and not (stO / ".mutation-log.jsonl").exists()
        if _rhO is not None:
            os.environ["HOME"] = _rhO
        else:
            os.environ.pop("HOME", None)
        print(f"  hierarchy worst-path={hier_ok} (worst {hO['worst_path']} ≈{hO['worst_path_tokens']} tok, .venv excluded) · "
              f"infra-excluded={infra_excluded}")
        print(f"  audit created/modified/deleted={audit_ok} · unchanged≠op · measuring-is-read-only={readonly_ok}")
        _verdict("O", "v0.1.22 foundation: claude_md_hierarchy computes the heaviest root→leaf chain (excl .venv); "
                 "the audit trail detects created/modified/deleted via content-hash (unchanged ≠ op, infra excluded); "
                 "measuring is READ-ONLY (no mutation, no log written)",
                 hier_ok and infra_excluded and audit_ok and readonly_ok,
                 "surfaces the ~54k nested-CLAUDE.md cost + a deterministic mutation trail — the safety substrate for v0.1.23")

        # ── Probe P: v0.1.23 memory-index residuals (D6 standing-justify TOKEN-axis · D10 archive-target wikilinks) ──
        # The beta-harness WARNed D6 (token bloat with flat fact-count stayed suppressed) + D10 ([[SHIPPED]] archive
        # ref flagged dangling). Assert: the gate now re-fires on token growth AND still on fact growth (independent),
        # fails open on missing/zero token baseline; and an archive/index ref is a valid wikilink target, not dangling.
        print("\n── Probe P: v0.1.23 (standing-justify token-axis · archive-target wikilinks) ──")
        projP = home / "projects-src" / "residP"
        projP.mkdir(parents=True, exist_ok=True)
        stP = home / ".claude" / "projects" / ms.slug_for(projP) / "memory"
        stP.mkdir(parents=True, exist_ok=True)
        for _n in ("a", "b", "c", "d", "e"):
            (stP / f"{_n}.md").write_text(f"---\nname: {_n}\nmetadata:\n  node_type: memory\n  type: project\n---\nbody\n", encoding="utf-8")
        (stP / "SHIPPED.md").write_text("# Shipped\n" + "\n".join(f"- [{n}]({n}.md) — done" for n in ("x", "y", "z")), encoding="utf-8")
        (stP / "MEMORY.md").write_text("# Memory Index\n" + "\n".join(
            f"- [{n}]({n}.md) — " + ("verbose hook " * 60) for n in ("a", "b", "c", "d", "e", "f", "g", "h")), encoding="utf-8")
        _rhP = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        idxP = ms.build_context(projP)["index_lb"][2]
        nfP = len(ms.build_context(projP)["fact_files"])

        def _sj(facts: int, tokens=None) -> dict:
            sj: dict = {"facts": facts}
            if tokens is not None:
                sj["index_tokens"] = tokens
            (stP / ".consolidation-state.json").write_text(
                json.dumps({"commit": "x", "timestamp": "2026-06-20T00:00:00Z", "standing_justify": sj}), encoding="utf-8")
            return ms.build_context(projP)["remediation"]

        over_budget = idxP > ms.INDEX_TOKEN_BUDGET                       # fixture must be over budget for the gate to engage
        d6_suppress = _sj(nfP, idxP).get("standing_justified") is True   # both axes within bound → SUPPRESSED
        d6_token_fires = _sj(nfP, idxP // 2).get("required") is True     # tokens > (idx/2)×1.25, flat facts → token-axis FIRES
        d6_fact_fires = _sj(nfP - ms._STANDING_JUSTIFY_DELTA - 1, idxP * 10).get("required") is True  # facts grew, tokens generous → fact-axis FIRES
        d6_zero_fires = _sj(nfP, 0).get("required") is True              # baseline tokens 0 → FIRES
        d6_failopen = _sj(nfP).get("required") is True                   # marker missing index_tokens → fail-open FIRES
        d6_helper = (ms._standing_baseline_tokens({"index_tokens": 9}) == 9 and ms._standing_baseline_tokens("x") is None
                     and ms._standing_baseline_tokens({}) is None and ms._standing_baseline_tokens({"index_tokens": "12"}) is None
                     and ms._standing_baseline_tokens(None) is None)
        vtP = ms.valid_link_targets(stP)
        d10_ok = ("SHIPPED" in vtP and "MEMORY" in vtP and ms.resolve_wikilink("SHIPPED", vtP) == "SHIPPED"
                  and ms.resolve_wikilink("MEMORY", vtP) == "MEMORY" and ms.resolve_wikilink("no-such-target-xyz", vtP) is None)
        if _rhP is not None:
            os.environ["HOME"] = _rhP
        else:
            os.environ.pop("HOME", None)
        print(f"  D6: over-budget-fixture={over_budget} · suppress-both-within={d6_suppress} · token-axis-fires={d6_token_fires} · "
              f"fact-axis-fires={d6_fact_fires} · zero-tokens-fires={d6_zero_fires} · fail-open-missing={d6_failopen} · helper={d6_helper}")
        print(f"  D10: archive/index are valid wikilink targets (not dangling) + resolve={d10_ok}")
        _verdict("P", "v0.1.23 residuals: standing-justify re-fires on TOKEN bloat (flat facts) AND still on fact growth "
                 "(independent axes), fails open on missing/zero token baseline (D6); valid_link_targets makes "
                 "[[SHIPPED]]/[[MEMORY]] real targets, not dangling (D10)",
                 over_budget and d6_suppress and d6_token_fires and d6_fact_fires and d6_zero_fires and d6_failopen and d6_helper and d10_ok,
                 "closes the beta-harness D6/D10 WARNs — token bloat no longer hides, archive refs aren't false-dangling")

        # ── Probe Q: v0.1.24 CLAUDE.md mutation — the MECHANICAL safety halves (enforcement-preservation itself is
        # SKILL judgment, not unit-testable). Assert: the normative-marker backstop catches a directive in the
        # moving chunk; valid_relocate_target firewalls gitignored/private/outside/escape targets; claude_md_sections
        # splits mechanically; the audit conservation check passes a relocate but flags an eviction as possible loss.
        print("\n── Probe Q: v0.1.24 (normative backstop · relocate firewall · sections · conservation) ──")
        repoQ = home / "repoQ"
        repoQ.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=repoQ, check=False)
        subprocess.run(["git", "config", "user.email", "x@x"], cwd=repoQ, check=False)
        subprocess.run(["git", "config", "user.name", "x"], cwd=repoQ, check=False)
        (repoQ / ".gitignore").write_text("secret/\n", encoding="utf-8")
        (repoQ / "CLAUDE.md").write_text("# conv\n## Type\n- pyright is a gate.\n" + "elaboration rationale line\n" * 40, encoding="utf-8")
        (repoQ / "docs").mkdir(exist_ok=True)
        (repoQ / "docs" / "TYPING.md").write_text("placeholder\n", encoding="utf-8")
        (repoQ / "secret").mkdir(exist_ok=True)
        (repoQ / "secret" / "x.md").write_text("ignored\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repoQ, check=False)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=repoQ, check=False)
        nm_ok = (ms._has_normative_marker("you MUST keep it clean") and ms._has_normative_marker("never delete this")
                 and not ms._has_normative_marker("the rationale is that batching helps throughput"))
        fw_ok = (ms.valid_relocate_target("docs/TYPING.md", repoQ)                        # in-repo, not ignored → True
                 and not ms.valid_relocate_target("secret/x.md", repoQ)                   # gitignored → False
                 and not ms.valid_relocate_target(str(home / ".claude" / "x.md"), repoQ)  # private store → False
                 and not ms.valid_relocate_target("/tmp/escape-xyz.md", repoQ)            # outside repo → False
                 and not ms.valid_relocate_target("../escape.md", repoQ))                 # .. escape → False
        secsQ = ms.claude_md_sections(repoQ / "CLAUDE.md")
        sec_ok = any(s["title"] == "Type" for s in secsQ) and all("tokens" in s for s in secsQ)
        beforeQ = ms.audit_snapshot(repoQ)
        repo_doc_seen = any(v.get("store") == "repo_doc" for v in beforeQ.values())
        (repoQ / "CLAUDE.md").write_text("# conv\n## Type\n- pyright is a gate — details in docs/TYPING.md.\n", encoding="utf-8")
        (repoQ / "docs" / "TYPING.md").write_text("placeholder\n" + "elaboration rationale line\n" * 40, encoding="utf-8")
        cons_relocate = not ms.audit_diff(beforeQ, ms.audit_snapshot(repoQ))["conservation"]["possible_loss"]
        (repoQ / "docs" / "TYPING.md").write_text("placeholder\n", encoding="utf-8")      # undo growth → eviction
        cons_evict = ms.audit_diff(beforeQ, ms.audit_snapshot(repoQ))["conservation"]["possible_loss"]
        print(f"  normative-marker={nm_ok} · firewall(valid/gitignored/private/outside/escape)={fw_ok} · sections={sec_ok}")
        print(f"  audit: repo_doc-snapshotted={repo_doc_seen} · relocate-conserves={cons_relocate} · eviction-flags-loss={cons_evict}")
        _verdict("Q", "v0.1.24 CLAUDE.md mutation (mechanical halves): the normative-marker backstop catches a directive "
                 "in the moving chunk; valid_relocate_target rejects gitignored/private/outside/escape targets; "
                 "claude_md_sections splits mechanically; the audit conservation check passes a relocate but flags an "
                 "eviction as possible loss",
                 nm_ok and fw_ok and sec_ok and repo_doc_seen and cons_relocate and cons_evict,
                 "the dream can relocate-the-elaboration safely — directive stays, targets firewalled, moves conservation-checked")

        # ── Probe R / R2: v0.1.70 security — `--evict=` guards (CONFIRMED by an independent
        # DevSecOps pentest, reproduced against the live subprocess). Both `_safe_stem`/
        # `_is_reserved_stem` fire at the TOP of run()'s evict block, before any held/fit-check
        # logic ever reads the store's contents — so, per a Gate-2a re-review finding, the probes
        # need no token-budget/held-fact fixture at all (an earlier version padded MEMORY.md near
        # the ceiling and seeded a global fact "to justify eviction"; that setup was dead weight
        # for what these two probes actually assert, and looked like load-bearing precondition
        # setup to a reader). A minimal MEMORY.md is kept ONLY so R2 has real bytes to assert
        # survive unchanged.
        print("\n── Probe R: v0.1.70 security (--evict= path traversal) ──")
        victimR = home / "OUTSIDE-STORE-VICTIM.md"
        victimR.write_text("must survive\n", encoding="utf-8")
        projR = _make_project(home, "victimprojR")
        storeR = _store(home, projR)
        storeR.mkdir(parents=True, exist_ok=True)
        (storeR / "MEMORY.md").write_text("# Memory Index\n\n- [x](x.md) — y\n", encoding="utf-8")
        # the `./`-padding trick (harmless no-op path components) is the exact bypass a live pentest
        # reproduced pre-fix — inflating the evicted "pointer"'s apparent token cost past the
        # fit-check — kept here as a faithful reproduction of that PoC shape, even though the
        # charset guard alone (which fires first) already refuses this payload today.
        payloadR = "./" * 400 + os.path.relpath(str(home / "OUTSIDE-STORE-VICTIM"), str(storeR))
        procR = subprocess.run([sys.executable, str(SYNC), "--pull", f"--evict={payloadR}", str(projR)],
                               env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, check=False)
        _verdict("R", "v0.1.70 security: `--evict=` refuses a path-traversal-shaped fact name (the exact "
                 "charset guard `promote()` already applies to local_fact/canon_name) — a crafted name can "
                 "no longer walk outside the project's own store to delete an arbitrary file",
                 victimR.exists() and "not a safe fact name" in procR.stderr,
                 "the shared global store (and any other reachable file) survives a malicious/crafted --evict= value")

        # ── Probe R2: v0.1.70 Gate-2a — `--evict=MEMORY` passed the charset guard (MEMORY is a
        # valid kebab/snake stem) but targets `store / "MEMORY.md"` — the project's OWN live
        # index — same self-clobber class `promote()` already guards via `_RESERVED_STEMS`. Reuses
        # storeR's MEMORY.md from Probe R (still on disk, untouched by it).
        _idx_before_r2 = (storeR / "MEMORY.md").read_text(encoding="utf-8")
        procR2 = subprocess.run([sys.executable, str(SYNC), "--pull", "--evict=MEMORY", str(projR)],
                                env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, check=False)
        _idx_after_r2 = (storeR / "MEMORY.md").read_text(encoding="utf-8")
        _verdict("R2", "v0.1.70 Gate-2a: `--evict=MEMORY` is refused (a reserved index name, not a fact) — "
                 "the charset guard alone let it through, which would have unlink()'d and rebuilt the "
                 "project's own live index, dropping every previously-indexed pointer with rc=0",
                 "reserved index name" in procR2.stderr and _idx_after_r2 == _idx_before_r2,
                 "the project's own MEMORY.md index survives byte-for-byte against a self-targeting --evict=MEMORY")

        # ── Probe R3: v0.1.70 Gate-2a — pin the `git check-ignore -- <path>` argv-injection fix,
        # which shipped with zero regression test (every existing valid_relocate_target fixture uses
        # a path that doesn't start with '-', so the smoke suite couldn't have caught a future revert
        # of the `--` separator). Reuses repoQ (a real git repo) from Probe Q.
        (repoQ / "-dash-leading.md").write_text("not gitignored, just an odd name\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repoQ, check=False)
        subprocess.run(["git", "commit", "-qm", "dash file"], cwd=repoQ, check=False)
        _verdict("R3", "v0.1.70 Gate-2a: a relocate target whose relative path starts with '-' is judged "
                 "correctly (NOT git-flag-parsed) — `git check-ignore -- <path>` reaches the real path, "
                 "not an option",
                 ms.valid_relocate_target("-dash-leading.md", repoQ) is True,
                 "a dash-leading, un-ignored path is a VALID relocate target (was: misread as a git flag "
                 "without the `--` separator, likely fail-closed to unsafe)")

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
