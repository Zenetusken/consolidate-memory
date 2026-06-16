#!/usr/bin/env python3
"""Locate both memory stores + the consolidation high-water mark + git recency.

Deterministic Phase-0 context for the consolidate-memory skill, so each run doesn't
re-derive paths/marker/git-range by hand. Read-only.

Default: human-readable report. With --json: emit the SEED of the cycle record
(project, scope, before-budget, marker) so the dashboard's data-driven fields start
from measured values, not guesses — the workflow fills in the rest (entries,
verification, after-budget, health) and renders with render_dashboard.py.

Usage: python3 memory_status.py [PROJECT_DIR] [--json]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Operational state (NOT a memory fact): the last commit/time we consolidated at.
STATE_FILE = ".consolidation-state.json"
REPO_DOCS = ("MEMORY.md", "AGENTS.md", "CLAUDE.md")


def slug_for(project_dir: Path) -> str:
    """cwd → Claude's project slug: absolute path with '/' replaced by '-'.

    e.g. /home/you/project/foo -> -home-you-project-foo. Verified empirically
    against ~/.claude/projects/ rather than assumed.
    """
    return str(project_dir.resolve()).replace("/", "-")


def _run(cmd: list[str], cwd: Path) -> str:
    try:
        out = subprocess.run(  # noqa: S603 - fixed args
            cmd, cwd=cwd, capture_output=True, text=True, timeout=15, check=False
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _lines_bytes(p: Path) -> tuple[int, int]:
    if not p.exists():
        return (0, 0)
    text = p.read_text(encoding="utf-8", errors="replace")
    return (len(text.splitlines()), len(text.encode()))


def build_context(project_dir: Path) -> dict:
    """Gather all Phase-0 facts into one dict (basis for both report and --json seed)."""
    project_dir = project_dir.resolve()
    slug = slug_for(project_dir)
    proj_root = Path.home() / ".claude" / "projects" / slug
    auto_mem = proj_root / "memory"

    repo = {name: _lines_bytes(project_dir / name) for name in REPO_DOCS}

    index_path = auto_mem / "MEMORY.md"
    index_lb = _lines_bytes(index_path)
    fact_files = sorted(
        f for f in auto_mem.glob("*.md") if f.name != "MEMORY.md"
    ) if auto_mem.exists() else []

    transcripts = sorted(proj_root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

    state_path = auto_mem / STATE_FILE
    last_commit = last_ts = ""
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text())
            last_commit, last_ts = st.get("commit", ""), st.get("timestamp", "")
        except (json.JSONDecodeError, OSError):
            pass

    head = _run(["git", "rev-parse", "HEAD"], project_dir)
    git_range = f"{last_commit[:12]}..HEAD" if last_commit else "-20"
    rng = f"{last_commit}..HEAD" if last_commit else "-20"
    log = _run(["git", "log", "--oneline", "--no-merges", rng], project_dir)
    commits = [ln for ln in log.splitlines() if ln.strip()]

    return {
        "project_dir": project_dir,
        "project": project_dir.name,
        "slug": slug,
        "proj_root": proj_root,
        "auto_mem": auto_mem,
        "repo": repo,
        "index_path": index_path,
        "index_lb": index_lb,
        "fact_files": fact_files,
        "transcripts": transcripts,
        "state_path": state_path,
        "last_commit": last_commit,
        "last_ts": last_ts,
        "head": head,
        "git_range": git_range,
        "commits": commits,
    }


def seed_record(ctx: dict) -> dict:
    """The cycle-record SEED — before-values + scope, for render_dashboard.py."""
    return {
        "project": ctx["project"],
        "session": "",  # fill with the session id when known
        "scope": {
            "git_range": ctx["git_range"],
            "git_commits": len(ctx["commits"]),
            "session_candidates": 0,  # fill in Phase 2
            "memories_reviewed": len(ctx["fact_files"]),
        },
        "verification": {"confirmed": 0, "corrected": 0, "unverifiable": 0, "method": "inline"},
        "entries": [],  # fill in Phase 4: {action,tier,store,name,reason,citation}
        "budget": {
            "claude_md": {"before": ctx["repo"]["CLAUDE.md"][0], "after": ctx["repo"]["CLAUDE.md"][0]},
            "index": {
                "before_lines": ctx["index_lb"][0], "after_lines": ctx["index_lb"][0],
                "before_bytes": ctx["index_lb"][1], "after_bytes": ctx["index_lb"][1],
            },
            "recall_facts": {"before": len(ctx["fact_files"]), "after": len(ctx["fact_files"])},
        },
        "health": {"index_pointers_ok": True, "broken": [], "dangling_links": []},
        "cross_project": {
            "global_store_facts": len(list((Path.home() / ".claude" / "memory").glob("*.md")))
            - (1 if (Path.home() / ".claude" / "memory" / "MEMORY.md").exists() else 0),
            "pulled": [],     # fill in Phase 1 (sync_global --pull): global → here
            "promoted": [],   # fill in Phase 4: here → global (new cross-project facts)
            "refreshed": 0,   # stale mirrors refreshed on pull
        },
        "marker": {
            "before_commit": ctx["last_commit"], "before_timestamp": ctx["last_ts"],
            "commit": ctx["head"], "timestamp": "",  # stamp at write time in Phase 5
        },
    }


def print_report(ctx: dict) -> None:
    print("=" * 72)
    print("CONSOLIDATE-MEMORY — Phase 0 context")
    print("=" * 72)
    print(f"project dir : {ctx['project_dir']}")
    print(f"slug        : {ctx['slug']}")
    print(f"proj_root   : {ctx['proj_root']}  ({'exists' if ctx['proj_root'].exists() else 'MISSING'})")

    print("\n--- Repo memory docs (committed) ---")
    for name, (ln, by) in ctx["repo"].items():
        loc = ctx["project_dir"] / name
        print(f"  {loc}  —  {ln} lines, {by} bytes" if ln or by else f"  (absent) {loc}")

    print("\n--- Claude auto-memory (private) ---")
    if ctx["auto_mem"].exists():
        il, ib = ctx["index_lb"]
        print(f"  index: {ctx['index_path']}  —  {il} lines, {ib} bytes  [ALWAYS-LOADED]")
        for f in ctx["fact_files"]:
            ln, by = _lines_bytes(f)
            print(f"  {f.name}  —  {ln} lines, {by} bytes")
    else:
        print(f"  (absent) {ctx['auto_mem']}")

    print("\n--- Global cross-project store (~/.claude/memory) ---")
    g = Path.home() / ".claude" / "memory"
    if g.exists():
        gfacts = [f for f in sorted(g.glob("*.md")) if f.name != "MEMORY.md"]
        print(f"  {len(gfacts)} global fact(s)  —  run sync_global.py --list . to see what applies here")
    else:
        print("  (absent — no cross-project facts yet)")

    print("\n--- Session transcripts (trajectory; do NOT bulk-read) ---")
    if ctx["transcripts"]:
        for t in ctx["transcripts"][-5:]:
            print(f"  {t.name}  —  {t.stat().st_size / 1_048_576:.1f} MB  (mtime {int(t.stat().st_mtime)})")
    else:
        print("  (none)")

    print("\n--- Consolidation high-water mark ---")
    if ctx["last_commit"]:
        print(f"  last consolidated: commit={ctx['last_commit'][:12]}  at={ctx['last_ts']}")
    else:
        print(f"  (no marker yet at {ctx['state_path']} — treat as first consolidation)")
    print(f"  current HEAD: {ctx['head'][:12] or '(not a git repo?)'}")

    print(f"\n--- git log {ctx['git_range']} ({len(ctx['commits'])} commits — scope for new facts) ---")
    print("\n".join(f"  {c}" for c in ctx["commits"]) or "  (no new commits / no range)")

    print("\n--- Next ---")
    print("  Re-run with --json to seed the cycle record, then render with render_dashboard.py.")
    print(f"  Marker to write in Phase 5: {ctx['state_path']}  commit={ctx['head'][:12]}")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    project_dir = Path(args[0]) if args else Path.cwd()
    ctx = build_context(project_dir)
    if as_json:
        print(json.dumps(seed_record(ctx), indent=2))
    else:
        print_report(ctx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
