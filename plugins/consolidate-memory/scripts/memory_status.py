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

# ── Rigor tier (v0.1.3): scale pass ceremony with an EARLY magnitude signal ──────────
# magnitude = git_commits (Phase-0 flow since the marker) + session_candidates (the
# Phase-2 CURATED candidate-fact count). It DELIBERATELY excludes memories_reviewed:
# that is a cumulative STOCK, so folding it in pegs any mature store (100+ facts) to
# HEAVY regardless of how much work THIS pass did — empirically confirmed against the
# live corpus. The stock instead drives a SEPARATE prune-pressure flag (below). The
# bands are roadmap-inherited PROVISIONAL defaults: the curated input was never recorded
# historically, so they are not yet calibrated. The record EXPOSES the magnitude (+ phase) a
# future calibration could refit against — but only once cycle records are PERSISTED (they
# render and are discarded today; persisting them is a roadmap prerequisite). The tier is a
# HINT (derived at render from the model's curated session_candidates), never a hard gate.
TIER_LIGHT_MAX = 2        # magnitude ≤ 2 → LIGHT
TIER_SUBSTANTIAL_MAX = 7  # 3..7 → SUBSTANTIAL ; ≥ 8 → HEAVY
TIER_ORDER = {"LIGHT": 0, "SUBSTANTIAL": 1, "HEAVY": 2}  # canonical rank (sorts / monotonicity checks)
# Prune-pressure: a near/over-budget index OR an already-large store needs prune rigor on
# ANY pass (orthogonal to magnitude). LEVER HIERARCHY (measured 2026-06): INDEX_TOKEN_BUDGET
# is the BINDING primary lever — at real pointer cost (~45-60 tok/fact) the index trips 1200
# tokens at ~20-27 facts, well before this count — so PRUNE_PRESSURE_FACTS is a terse-pointer
# BACKSTOP, not the primary trigger. Observed store sizes cluster at {6,7} and {100,104}; any
# value in the open interval (7, 100) yields the identical partition — 40 is a tunable
# midpoint, not a calibrated precision point.
PRUNE_PRESSURE_FACTS = 40


def suggested_tier(git_commits: int, session_candidates: int) -> str:
    """EARLY pass-magnitude → rigor tier (LIGHT/SUBSTANTIAL/HEAVY). magnitude =
    git_commits + session_candidates, both FLOWS (work THIS cycle). Takes NO
    memories_reviewed argument by design: that cumulative STOCK belongs on the
    prune-pressure axis, not here (folding it in pegs every mature store to HEAVY — the
    bug this avoids). Pure + total so the smoke tests can sweep it."""
    magnitude = git_commits + session_candidates
    if magnitude <= TIER_LIGHT_MAX:
        return "LIGHT"
    if magnitude <= TIER_SUBSTANTIAL_MAX:
        return "SUBSTANTIAL"
    return "HEAVY"


def prune_pressure(index_over: bool, memories_reviewed: int) -> tuple[bool, str]:
    """Whether the pass MUST prune-or-propose regardless of magnitude tier, plus the
    reason. Set when the always-loaded index is over budget OR the store already holds a
    large number of facts. Orthogonal to suggested_tier: a 100-fact store needs prune
    rigor even on a 1-candidate pass."""
    if index_over:
        return (True, "index-over-budget")
    if memories_reviewed >= PRUNE_PRESSURE_FACTS:
        return (True, "many-facts")
    return (False, "")


def _provisional_rigor(ctx: dict) -> dict:
    """The Phase-0 PROVISIONAL rigor block stored in the cycle record: `phase`, the
    prune-pressure flag/reason, and the realized-rigor `applied`/`override_reason` (seeded
    EMPTY here; the model fills them in Phase 2/4). It deliberately stores **no suggested
    tier** — that tier is DERIVED from `scope` (git_commits + session_candidates) at render,
    so the label can never drift from its own magnitude. `applied` (the ceremony actually
    run) is a genuine decision NOT derivable from magnitude, so storing it introduces no
    drift. The model sets `phase="final"` in Phase 2 after curating `session_candidates`.
    (The Phase-0 *report* computes a provisional tier for the operator to read — an
    operational hint, separate from the record.)"""
    pp_flag, pp_reason = prune_pressure(ctx["index_lb"][2] > INDEX_TOKEN_BUDGET, len(ctx["fact_files"]))
    return {"phase": "provisional", "prune_pressure": pp_flag, "prune_reason": pp_reason,
            "applied": "", "override_reason": ""}


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


_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")
_LINK_RE = re.compile(r"\]\(([^)]+)\.md\)")        # MEMORY.md pointer link target (stem)
_SCOPES = ("project-local", "stack-general", "user-global")


def _valid_uuid(s: object) -> bool:
    """True iff `s` is a full 8-4-4-4-12 hex UUID (an originSessionId). Regex, no `uuid`
    import — mirrors `_valid_sha`. Used to flag a MALFORMED (present-but-wrong) originSessionId."""
    return bool(isinstance(s, str) and _UUID_RE.match(s.strip()))


def _frontmatter(text: str) -> dict:
    """Parse a fact file's YAML-ish frontmatter to a flat dict. Lives here (the dependency root)
    so sync_global imports it — single definition. Tolerant at the model→file boundary: strips a
    leading BOM + normalizes CRLF (a healthy CRLF/BOM file must not read as EMPTY, else
    schema_drift miscounts it as fully missing); NEVER raises (returns {} on anything odd)."""
    if text.startswith("﻿"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out: dict = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            v = v.strip()
            if v in (">", ">-", ">+", "|", "|-", "|+"):   # folded/block scalar
                buf, j = [], i + 1
                while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
                    if lines[j].strip():
                        buf.append(lines[j].strip())
                    j += 1
                out[k.strip()] = " ".join(buf)
                i = j
                continue
            out[k.strip()] = v
        else:
            m2 = re.match(r"\s+(scope|stacks|type|projects|node_type|originSessionId):\s*(.+)", line)
            if m2:
                out[m2.group(1)] = m2.group(2).strip()
        i += 1
    return out


def index_fact_names(index_path: Path) -> set:
    """Fact stems the always-loaded index points at, via the SAME `](<stem>.md)` link anchor
    sync_global uses — NOT a naive line parse, so the `# Memory Index` header/blank lines don't
    inflate an index<->files mismatch. Empty set if absent/unreadable."""
    if not index_path.exists():
        return set()
    try:
        return set(_LINK_RE.findall(index_path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return set()


def near_duplicate_slugs(slug: str, sibling_slugs: list) -> list:
    """Sibling project slugs differing from `slug` only by '-'/'_'/case — the rename-orphan
    signature (`…-Doc-Flo` vs `…-Doc_Flo`). EXCLUDES `slug` itself (a project never flags
    itself). `slug_for` is lossy, so near-dup is the robust signal vs path reconstruction."""
    def norm(s: str) -> str:
        return s.replace("_", "-").lower()
    target = norm(slug)
    return sorted(s for s in sibling_slugs if s != slug and norm(s) == target)


def schema_drift(fact_files: list, index_names: set) -> dict:
    """DRIFT (always reported) + optional backfill ADVISORY (absence). DRIFT = documented field
    `node_type` MISSING, a present-but-MALFORMED `scope`/`originSessionId`, or an index<->file
    mismatch. Advisory = facts merely LACKING scope/originSessionId (injected/optional → absence
    is noise, not drift). Pure; never raises."""
    missing_node_type = malformed_scope = malformed_origin = 0
    advisory_no_scope = advisory_no_origin = 0
    stems = set()
    for f in fact_files:
        stems.add(f.stem)
        try:
            fm = _frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            fm = {}
        if "node_type" not in fm:
            missing_node_type += 1
        if "scope" in fm:
            if fm["scope"] not in _SCOPES:
                malformed_scope += 1
        else:
            advisory_no_scope += 1
        if "originSessionId" in fm:
            if not _valid_uuid(fm["originSessionId"]):
                malformed_origin += 1
        else:
            advisory_no_origin += 1
    return {"missing_node_type": missing_node_type, "malformed_scope": malformed_scope,
            "malformed_origin": malformed_origin, "index_mismatch": len(stems ^ index_names),
            "advisory_no_scope": advisory_no_scope, "advisory_no_origin": advisory_no_origin}


def drift_findings(d: dict) -> int:
    """Count of DRIFT findings (NOT advisory) — the AC#1 'clean store' gate."""
    return (int(d.get("missing_node_type", 0)) + int(d.get("malformed_scope", 0))
            + int(d.get("malformed_origin", 0)) + int(d.get("index_mismatch", 0)))


def _newest_mtime(base: Path, pattern: str) -> float:
    """Newest mtime among base/pattern files, 0.0 if none/absent (slug-orphan liveness signal)."""
    if not base.exists():
        return 0.0
    return max((f.stat().st_mtime for f in base.glob(pattern)), default=0.0)


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

    # Schema drift (C2): structural/malformed-field findings vs the index — always
    # reported; advisory absence-counts are surfaced separately (NOT a drift finding).
    index_names = index_fact_names(index_path)
    drift = schema_drift(fact_files, index_names)

    # Slug-orphan / near-duplicate-store detection (C1): a renamed project dir orphans
    # its slug-scoped memory under the OLD slug. Guard the projects-root scan (mirrors
    # build_context's auto_mem guard / sync_global's _network_nodes); enumerate sibling
    # slugs, then gather the liveness signal (newest transcript + fact mtime) LAZILY —
    # only for the matched twins, never every sibling. Read-only.
    projects_root = Path.home() / ".claude" / "projects"
    siblings = [p.name for p in projects_root.iterdir() if p.is_dir()] if projects_root.exists() else []
    dups = near_duplicate_slugs(slug, siblings)
    slug_orphans = [{"slug": d, "newest_txn": _newest_mtime(projects_root / d, "*.jsonl"),
                     "newest_fact": _newest_mtime(projects_root / d / "memory", "*.md")} for d in dups]

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
        "index_names": index_names,
        "schema_drift": drift,
        "slug_orphans": slug_orphans,
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
    """The cycle-record SEED — before-values + scope + provisional rigor, for render_dashboard.py."""
    return {
        "project": ctx["project"],
        "session": "",  # fill with the session id when known
        "scope": {
            "git_range": ctx["git_range"],
            "git_commits": len(ctx["commits"]),
            "session_candidates": 0,  # fill in Phase 2
            "memories_reviewed": len(ctx["fact_files"]),
        },
        # Provisional rigor hint (Phase 0): tier from git_commits alone (candidates=0 yet);
        # the model recomputes with the CURATED session_candidates and sets phase="final" in
        # Phase 2. `magnitude` is DERIVED from `scope` at render — never stored (no parallel
        # count to drift). Computed by _provisional_rigor() so seed + Phase-0 report agree.
        "rigor": _provisional_rigor(ctx),
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
        "health": {"index_pointers_ok": True, "broken": [], "dangling_links": [],
                   "slug_orphans": [o["slug"] for o in ctx["slug_orphans"]],
                   "schema_drift": ctx["schema_drift"]},
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

    # Slug-orphan / near-duplicate store(s) — a rename moves the slug-scoped store to a
    # NEW slug, stranding the old one. ADVISORY: name each twin, flag which looks live
    # (newest mtime), and the reconciliation hint. Never acted on here (detect/offer only).
    if ctx["slug_orphans"]:
        print("\n--- ⚠ Slug-orphan / near-duplicate store(s) ---")
        cur_live = max(_newest_mtime(ctx["proj_root"], "*.jsonl"),
                       _newest_mtime(ctx["auto_mem"], "*.md"))
        print(f"  This slug ({ctx['slug']}) has near-duplicate sibling store(s) — likely a")
        print("  rename-orphan (a dir rename changes the slug and strands the old memory):")
        for o in ctx["slug_orphans"]:
            twin_live = max(o["newest_txn"], o["newest_fact"])
            which = "twin looks LIVE" if twin_live > cur_live else (
                "current store looks live" if cur_live > twin_live else "same recency")
            print(f"  • {_sane(o['slug'])}  ({which}; "
                  f"twin newest mtime {int(twin_live)} vs current {int(cur_live)})")
        print("  reconciliation: merge toward newest mtime, NOT most files; land under the")
        print("  slug whose disk path exists — ADVISORY, confirm before acting.")

    # Schema DRIFT — structural/malformed findings (always reported when present). The
    # advisory absence-counts are a SEPARATE, clearly-optional line that MAY print on an
    # otherwise-clean store (it is NOT a drift finding).
    d = ctx["schema_drift"]
    if drift_findings(d) > 0:
        print("\n--- ⚠ Schema DRIFT (documented-field / structural) ---")
        print(f"  missing node_type: {d['missing_node_type']} · malformed scope: {d['malformed_scope']} · "
              f"malformed originSessionId: {d['malformed_origin']} · index↔file mismatch: {d['index_mismatch']}")
        print("  offer backfill — ADVISORY, confirm before acting (Phase 0 never mutates a store).")
    if d["advisory_no_scope"] or d["advisory_no_origin"]:
        # OPTIONAL backfill advisory — NOT a drift finding; may print on an otherwise-clean
        # store. memory_status emits plain text (no TTY-gated color like the dashboard), so
        # 'optional/advisory' is carried by the words, not a raw ANSI dim that would garble
        # captured output.
        print("\n  backfill candidates (advisory, NOT drift — optional): "
              f"{d['advisory_no_scope']} lack scope, {d['advisory_no_origin']} lack originSessionId")

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

    # Provisional rigor hint for the operator (separate from the record, which stores NO
    # tier — the dashboard derives it from scope). prune-pressure shares _provisional_rigor.
    rg = _provisional_rigor(ctx)
    gc = len(ctx["commits"])
    tier = suggested_tier(gc, 0)  # candidates unknown in Phase 0 → 0
    print("\n--- Suggested rigor (PROVISIONAL — finalize in Phase 2 with curated candidates) ---")
    if ctx["last_commit"]:
        print(f"  provisional tier: {tier}   (magnitude = {gc} commits + 0 candidates so far)")
    else:
        print(f"  provisional tier: {tier}   (FIRST consolidation: no marker, so this reflects a "
              f"recent-≤20 commit lookback, NOT new-since-last-time work — advisory only)")
    if rg["prune_pressure"]:
        print(f"  ⚠ prune-pressure ({rg['prune_reason']}) — MUST prune-or-propose this pass, at ANY tier")
    print(f"  ladder: LIGHT ≤{TIER_LIGHT_MAX} inline · SUBSTANTIAL {TIER_LIGHT_MAX + 1}–{TIER_SUBSTANTIAL_MAX} "
          f"fan-out + 2-source for always-loaded · HEAVY ≥{TIER_SUBSTANTIAL_MAX + 1} + completeness critic + "
          "over-budget hard-stop  [HINT — you finalize in Phase 2]")

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
