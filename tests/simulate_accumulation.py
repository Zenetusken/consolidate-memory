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
  F per-node + total network token consumption is observable.

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

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNC = ROOT / "skill" / "scripts" / "sync_global.py"


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


def _make_project(home: Path, name: str, stack_hint: str) -> Path:
    """A fake project dir with enough surface for detect_stacks() to bite."""
    p = home / "projects-src" / name
    p.mkdir(parents=True, exist_ok=True)
    # CLAUDE.md keywords drive stack detection; vary them per project.
    (p / "CLAUDE.md").write_text(f"# {name}\nStack hints: {stack_hint}\n", encoding="utf-8")
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

        # M projects with varied stack hints. "py" projects all trip the loose
        # `python`/`.claude`/`skill` keywords, so stack-general facts spread widely.
        projects = [
            _make_project(home, "alpha", "python pyproject ruff pytest"),
            _make_project(home, "beta", "rag embedding vector lancedb"),
            _make_project(home, "gamma", "cuda vllm vram torch gpu"),
            # hyphenated name: guards against _node_label mislabeling it "memory"
            _make_project(home, "delta-svc", "playwright scraper browser"),
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

        # ── Probe D: word-boundary stack matching kills substring false-positives (FIX D) ─
        # Old substring matching let 'skill' match 'reskilling', so a project that
        # merely mentions an unrelated word inherited claude-code stack facts. Now
        # matching is token-bounded: a substring-only mention no longer triggers, while
        # a genuine '.claude' mention still does (fleet-wide stacks stay broad BY DESIGN).
        print("\n── Probe D: stack matching precision (FIX D) ──")
        false_pos = _make_project(home, "epsilon", "our reskilling and upskilling roadmap")
        genuine = _make_project(home, "zeta", "this repo ships a .claude skill")
        _write_global(home, "cc-only", "stack-general", stacks="claude-code")
        _pull(home, false_pos)
        _pull(home, genuine)
        fp_got = (_store(home, false_pos) / "cc-only.md").exists()
        gen_got = (_store(home, genuine) / "cc-only.md").exists()
        print(f"  'reskilling'-only project inherited claude-code fact : {fp_got}  (want False)")
        print(f"  genuine '.claude skill' project inherited it          : {gen_got}  (want True)")
        _verdict("D", "stack matching is token-bounded — substring false-positives eliminated",
                 (not fp_got) and gen_got,
                 "genuine fleet-wide stacks (e.g. claude-code) stay broad by design; "
                 "spurious substring spread is gone")

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
        print(f"  TOTAL always-loaded ≈{t['always_loaded_tokens']} tok · "
              f"recall-pool ≈{t['recall_tokens']} tok")
        for n in sorted(net["nodes"], key=lambda d: -d["always_loaded_tokens"])[:6]:
            print(f"    {n['node'][:26]:<26} always ≈{n['always_loaded_tokens']:>5} · "
                  f"recall ≈{n['recall_tokens']:>6} · {n['facts']} facts ({n['shared']} shared)")
        measurable = t["nodes"] >= 1 and t["always_loaded_tokens"] > 0
        _verdict("F", "network token consumption is observable per-node and in total",
                 measurable,
                 f"{t['nodes']} nodes measured; the always-loaded total is the per-session "
                 "tax paid across the whole fleet — now a number, not a guess")

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
