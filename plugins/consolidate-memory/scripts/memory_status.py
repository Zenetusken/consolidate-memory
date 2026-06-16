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
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Operational state (NOT a memory fact): the last commit/time we consolidated at.
STATE_FILE = ".consolidation-state.json"
REPO_DOCS = ("MEMORY.md", "AGENTS.md", "CLAUDE.md")

# Always-loaded tier budget — heuristic ceilings (in ESTIMATED tokens) on what is
# injected into EVERY session. There is no tokenizer here (zero-dep), so these gate
# on est_tokens (≈ chars/4). Tunable; the point is to make the per-session tax
# VISIBLE and flag overflow, not to be exact. SKILL.md promised "a stated budget" —
# this is where it's stated.
INDEX_TOKEN_BUDGET = 1200       # the auto-memory MEMORY.md index (pointers only)
CLAUDE_MD_TOKEN_BUDGET = 4000   # repo CLAUDE.md (project conventions, committed)
# ~/.claude/CLAUDE.md — the USER-GLOBAL preamble, loaded in EVERY project, every session.
# Handled DIFFERENTLY from the repo file: measured READ-ONLY for honest always-loaded
# accounting (it taxes every project), but the skill NEVER writes it — it's personal,
# universal config, not a project store. Its own constant so it's tuned independently.
GLOBAL_CLAUDE_MD_TOKEN_BUDGET = 4000


def est_tokens(text: str) -> int:
    """Estimate tokens as ceil(chars/4). NOT a real tokenizer — the zero-dependency
    constraint rules one out — so it slightly over-counts prose and under-counts dense
    code. Stable and good enough to budget the always-loaded tier. Always present its
    output as '≈': it is an estimate, never an exact token count."""
    return (len(text) + 3) // 4


_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _sane(s: str) -> str:
    """Strip terminal control bytes (C0/C1/DEL, keeping tab/newline) from a string before
    PRINTING it. git commit subjects are attacker-influenceable text; a crafted message
    with an ESC sequence would otherwise inject into the terminal when this report runs."""
    return _CTRL.sub("", str(s))


def _valid_sha(s: str) -> bool:
    """True iff `s` is a plausible git commit SHA (hex, 7–40 chars). Used to reject a
    tampered/garbage `commit` from the on-disk state file before it reaches `git` argv
    (argument-injection guard — a value like '--output=…' must never be trusted)."""
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", s or ""))


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


def _measure(p: Path) -> tuple[int, int, int]:
    """(lines, bytes, est_tokens) for a file — (0,0,0) if absent."""
    if not p.exists():
        return (0, 0, 0)
    text = p.read_text(encoding="utf-8", errors="replace")
    return (len(text.splitlines()), len(text.encode()), est_tokens(text))


def build_context(project_dir: Path) -> dict:
    """Gather all Phase-0 facts into one dict (basis for both report and --json seed)."""
    project_dir = project_dir.resolve()
    slug = slug_for(project_dir)
    proj_root = Path.home() / ".claude" / "projects" / slug
    auto_mem = proj_root / "memory"

    repo = {name: _measure(project_dir / name) for name in REPO_DOCS}

    # The USER-GLOBAL CLAUDE.md (~/.claude/CLAUDE.md): loaded into EVERY session of EVERY
    # project, so it's part of THIS session's always-loaded tax even though it's neither a
    # repo doc nor an auto-memory file. Measured READ-ONLY (the skill never edits it) so
    # the per-session cost the dashboard reports is honest, not understated.
    global_claude_md = _measure(Path.home() / ".claude" / "CLAUDE.md")

    index_path = auto_mem / "MEMORY.md"
    index_lb = _measure(index_path)
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
    # Harden: the commit comes from a JSON file on disk and is passed to `git` as an
    # argv element. Even without a shell, a value like "--output=…" would be read by
    # git as an OPTION (argument injection). Accept only a real hex SHA; anything else
    # is treated as "no marker" (first-consolidation scope). Defends the one external
    # command in this tool against a tampered/garbage state file.
    if not _valid_sha(last_commit):
        last_commit = ""

    head = _run(["git", "rev-parse", "HEAD"], project_dir)
    git_range = f"{last_commit[:12]}..HEAD" if last_commit else "-20"
    rng = f"{last_commit}..HEAD" if last_commit else "-20"
    log = _run(["git", "log", "--oneline", "--no-merges", rng], project_dir)
    commits = [ln for ln in log.splitlines() if ln.strip()]

    # Re-verification signal (Fix E): facts not touched since the last consolidation
    # are candidates to RE-verify (they may have silently gone stale). mtime is a
    # cheap proxy — no per-fact `last_verified` field needed; the marker timestamp is
    # the watershed. Report-only: the model decides whether to re-check them.
    stale_facts = _stale_since(fact_files, last_ts)

    return {
        "project_dir": project_dir,
        "project": project_dir.name,
        "slug": slug,
        "proj_root": proj_root,
        "auto_mem": auto_mem,
        "repo": repo,
        "global_claude_md": global_claude_md,
        "index_path": index_path,
        "index_lb": index_lb,
        "fact_files": fact_files,
        "stale_facts": stale_facts,
        "transcripts": transcripts,
        "state_path": state_path,
        "last_commit": last_commit,
        "last_ts": last_ts,
        "head": head,
        "git_range": git_range,
        "commits": commits,
    }


def _stale_since(fact_files: list[Path], marker_ts: str) -> list[str]:
    """Names of fact files last modified at/before the marker — i.e. untouched since
    the previous consolidation, so candidates for RE-verification. Empty if no marker
    (first pass) or the timestamp can't be parsed."""
    # marker_ts comes from an on-disk JSON file; a tampered/garbage non-string value
    # (number, list) would crash `.replace`. Accept only a real string.
    if not isinstance(marker_ts, str) or not marker_ts:
        return []
    try:
        cutoff = datetime.fromisoformat(marker_ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return []
    return [f.stem for f in fact_files if f.stat().st_mtime <= cutoff]


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
            "claude_md": {
                "before": ctx["repo"]["CLAUDE.md"][0], "after": ctx["repo"]["CLAUDE.md"][0],
                "before_tokens": ctx["repo"]["CLAUDE.md"][2], "after_tokens": ctx["repo"]["CLAUDE.md"][2],
                "budget_tokens": CLAUDE_MD_TOKEN_BUDGET,
                "over": ctx["repo"]["CLAUDE.md"][2] > CLAUDE_MD_TOKEN_BUDGET,
            },
            # USER-GLOBAL ~/.claude/CLAUDE.md — read-only / no before↔after (the skill never
            # edits it); a flat per-session cost present in EVERY project. Rendered as its
            # own distinct line so the always-loaded total isn't understated.
            "global_claude_md": {
                "present": ctx["global_claude_md"][1] > 0,
                "lines": ctx["global_claude_md"][0],
                "tokens": ctx["global_claude_md"][2],
                "budget_tokens": GLOBAL_CLAUDE_MD_TOKEN_BUDGET,
                "over": ctx["global_claude_md"][2] > GLOBAL_CLAUDE_MD_TOKEN_BUDGET,
            },
            "index": {
                "before_lines": ctx["index_lb"][0], "after_lines": ctx["index_lb"][0],
                "before_bytes": ctx["index_lb"][1], "after_bytes": ctx["index_lb"][1],
                "before_tokens": ctx["index_lb"][2], "after_tokens": ctx["index_lb"][2],
                "budget_tokens": INDEX_TOKEN_BUDGET,
                "over": ctx["index_lb"][2] > INDEX_TOKEN_BUDGET,
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
            "gc_removed": 0,  # orphan mirrors reclaimed in Phase 5 (sync_global --gc --apply)
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
    for name, (ln, by, tok) in ctx["repo"].items():
        loc = ctx["project_dir"] / name
        if not (ln or by):
            print(f"  (absent) {loc}")
            continue
        over = " ⚠ OVER BUDGET" if name == "CLAUDE.md" and tok > CLAUDE_MD_TOKEN_BUDGET else ""
        budget = f" / {CLAUDE_MD_TOKEN_BUDGET} budget" if name == "CLAUDE.md" else ""
        print(f"  {loc}  —  {ln} lines, {by} bytes, ≈{tok} tok{budget}{over}")

    print("\n--- Global always-loaded (~/.claude/CLAUDE.md — every project; READ-ONLY) ---")
    gl, gb, gt = ctx["global_claude_md"]
    gpath = Path.home() / ".claude" / "CLAUDE.md"
    if gl or gb:
        heavy = " ⚠ heavy — taxes EVERY project" if gt > GLOBAL_CLAUDE_MD_TOKEN_BUDGET else ""
        print(f"  {gpath}  —  {gl} lines, {gb} bytes, ≈{gt} tok  "
              f"[the skill NEVER edits this — measured for honest cost only]{heavy}")
    else:
        print(f"  (absent — no user-global CLAUDE.md at {gpath})")

    print("\n--- Claude auto-memory (private) ---")
    if ctx["auto_mem"].exists():
        il, ib, it = ctx["index_lb"]
        over = " ⚠ OVER BUDGET" if it > INDEX_TOKEN_BUDGET else ""
        print(f"  index: {ctx['index_path']}  —  {il} lines, {ib} bytes, "
              f"≈{it}/{INDEX_TOKEN_BUDGET} tok  [ALWAYS-LOADED]{over}")
        for f in ctx["fact_files"]:
            ln, by, tok = _measure(f)
            print(f"  {f.name}  —  {ln} lines, {by} bytes, ≈{tok} tok")
    else:
        print(f"  (absent) {ctx['auto_mem']}")

    if ctx["stale_facts"]:
        print("\n--- Re-verification candidates (untouched since last consolidation) ---")
        print("  These facts predate the marker — re-verify them against the live tree:")
        for name in ctx["stale_facts"]:
            print(f"  • {name}")

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
    print("\n".join(f"  {_sane(c)}" for c in ctx["commits"]) or "  (no new commits / no range)")

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
