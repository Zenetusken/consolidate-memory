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
from typing import Any, Mapping, TypedDict

import _ui  # sibling script: the shared visual vocabulary (color / rule / kv / bar / glyphs)

# ── The cycle-record CONTRACT (v0.1.6) ───────────────────────────────────────────────
# The cycle record is the contract between this script (seeds it), the workflow phases
# (fill it), and render_dashboard.py (renders it). It used to be an untyped dict whose
# shape was hand-maintained in THREE places (this seed ↔ the renderer ↔ SKILL.md's
# schema block) — the recurring source of drift/crash findings. These TypedDicts make
# that shape STATIC so mypy catches a drifted/renamed/wrong-typed key on the PRODUCER
# side (the dict LITERALS this file emits) and across modules, at dev time.
#
# Why TypedDict and not Pydantic/dataclasses: it is stdlib (3.8+), a ZERO runtime
# dependency, and runtime-INVISIBLE — a TypedDict *is* a plain dict, so there's no
# runtime cost and the model can still author the record as JSON mid-flight (which a
# dataclass would break). The static win is PRODUCER-asymmetric: total=False flags a
# mis-named key only via subscript / in a dict literal, NOT on a `.get()` read — so
# render's defensive reads rely on `validate_cycle_record` (below) + IDE hints, not
# mypy. All total=False because the record is filled incrementally across the phases:
# any key may legitimately be absent at a given moment (a partial record is normal).
#
# MIRRORS the SKILL.md "Cycle-record schema" block key-for-key (kept aligned by the
# smoke test that diffs CycleRecord.__annotations__ against that block). Nested shapes
# are their own TypedDicts so drift INSIDE them is also caught on the producer side.


class Scope(TypedDict, total=False):
    git_range: str
    git_commits: int
    session_candidates: int
    memories_reviewed: int


class Rigor(TypedDict, total=False):
    phase: str            # "provisional" | "final"
    prune_pressure: bool
    prune_reason: str
    applied: str          # the ceremony actually run: "LIGHT" | "SUBSTANTIAL" | "HEAVY"
    override_reason: str


class Verification(TypedDict, total=False):
    confirmed: int
    corrected: int
    unverifiable: int
    method: str           # "inline" | "subagents"


class Entry(TypedDict, total=False):
    action: str           # "added" | "corrected" | "deleted" | "reconciled" | "skipped"
    tier: str             # "always-loaded" | "recall" | "on-demand" | "-"
    store: str            # "auto-mem" | "repo" | "-"
    scope: str            # "project-local" | "stack-general" | "user-global"
    name: str
    reason: str
    citation: str


class ClaudeMdBudget(TypedDict, total=False):
    before: int
    after: int
    before_tokens: int
    after_tokens: int
    budget_tokens: int
    over: bool


class GlobalClaudeMd(TypedDict, total=False):
    present: bool
    lines: int
    tokens: int
    budget_tokens: int
    over: bool


class IndexBudget(TypedDict, total=False):
    before_lines: int
    after_lines: int
    before_bytes: int
    after_bytes: int
    before_tokens: int
    after_tokens: int
    budget_tokens: int
    over: bool


class RecallFacts(TypedDict, total=False):
    before: int
    after: int


class Budget(TypedDict, total=False):
    claude_md: ClaudeMdBudget
    global_claude_md: GlobalClaudeMd
    index: IndexBudget
    recall_facts: RecallFacts


class SchemaDrift(TypedDict, total=False):
    missing_node_type: int
    malformed_scope: int
    malformed_origin: int
    index_mismatch: int
    advisory_no_scope: int
    advisory_no_origin: int


class Health(TypedDict, total=False):
    index_pointers_ok: bool
    broken: list[str]
    dangling_links: list[str]
    slug_orphans: list[str]      # nests UNDER health (twin slug names)
    schema_drift: SchemaDrift    # nests UNDER health (the C2 drift dict)


class CrossProject(TypedDict, total=False):
    global_store_facts: int
    pulled: list[dict]       # [{"name": ..., "scope": ...}] — Phase 1: global → here
    promoted: list[dict]     # [{"name": ..., "scope": ...}] — Phase 4: here → global
    refreshed: int
    gc_removed: int


class NetworkNode(TypedDict, total=False):
    node: str
    trigger: bool
    always_loaded_tokens: int
    mirror_index_tokens: int
    recall_tokens: int
    facts: int
    shared: int


class NetworkTotals(TypedDict, total=False):
    nodes: int
    always_loaded_tokens: int
    mirror_index_tokens: int
    recall_tokens: int


class Network(TypedDict, total=False):
    basis: str
    node_def: str
    trigger: str
    nodes: list[NetworkNode]
    totals: NetworkTotals


class Marker(TypedDict, total=False):
    before_commit: str       # seed-only: the prior marker (for the dashboard delta)
    before_timestamp: str
    commit: str
    timestamp: str           # stamped in Phase 5 at write time


class CycleRecord(TypedDict, total=False):
    project: str
    session: str
    scope: Scope
    rigor: Rigor
    verification: Verification
    entries: list[Entry]
    budget: Budget
    health: Health
    cross_project: CrossProject
    network: Network
    marker: Marker
    outcome: str             # OPTIONAL explicit override of the derived outcome banner (render:_outcome)

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
# future calibration could refit against — and `--persist` now appends each record to
# `.consolidation-log.jsonl` (v0.1.4), so that data accrues; a real refit still needs enough
# records + longitudinal miss-detection (future work). The tier is a
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


def suggested_tier(git_commits: float, session_candidates: float) -> str:
    """EARLY pass-magnitude → rigor tier (LIGHT/SUBSTANTIAL/HEAVY). magnitude =
    git_commits + session_candidates, both FLOWS (work THIS cycle). Takes NO
    memories_reviewed argument by design: that cumulative STOCK belongs on the
    prune-pressure axis, not here (folding it in pegs every mature store to HEAVY — the
    bug this avoids). Pure + total so the smoke tests can sweep it. Args are FLOAT-typed
    (not int) because render coerces the model-authored magnitude through `_num` →
    float before calling; the magnitude sum + the two band comparisons are float-safe,
    and the int-arg smoke sweeps still pass (int ⊆ float)."""
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


def _provisional_rigor(ctx: dict) -> Rigor:
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
    """cwd → Claude's project slug: the absolute path with BOTH '/' AND '_' replaced by '-'.

    e.g. /home/you/project/Doc_Flo -> -home-you-project-Doc-Flo (case PRESERVED). Claude Code
    normalizes '/' and '_' to '-' — verified on disk (a session with cwd .../Doc_Flo was logged
    by CC under slug ...-Doc-Flo). A '/'-only slug (the pre-v0.1.17 bug) sent replicated
    cross-project facts to a slug an underscore-named project never recalls — the cross-project
    reachability blocker this fixes.

    HONEST LIMIT: the rule is verified ONLY for '/' and '_' (memex is the lone underscore example on
    disk; no '.'/space/other example exists). A dir with such a char COULD diverge further; that would
    NOT be caught by near_duplicate_slugs (it collapses only '_'/case), so it'd be a silent miss — an
    accepted, documented residual risk (see references/harness-map.md). Don't claim a complete rule.
    """
    return re.sub(r"[/_]", "-", str(project_dir.resolve()))


_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")
_LINK_RE = re.compile(r"\]\(([^)]+)\.md\)")        # MEMORY.md pointer link target (stem)
_SCOPES = ("project-local", "stack-general", "user-global")


def _valid_uuid(s: object) -> bool:
    """True iff `s` is a full 8-4-4-4-12 hex UUID (an originSessionId). Regex, no `uuid`
    import — mirrors `_valid_sha`. Used to flag a MALFORMED (present-but-wrong) originSessionId."""
    return bool(isinstance(s, str) and _UUID_RE.match(s.strip()))


def _is_mirror(text: str) -> bool:
    """True iff a fact is a MANAGED MIRROR — detected by the EXACT structured forms `_as_mirror`
    writes inside the frontmatter, NEVER a substring anywhere in the file:

      • a column-0 `# global_ref: <name>` comment stamp that is the FIRST frontmatter line (a
        `# global_ref:` comment *elsewhere* in a hand-authored note must not count), or
      • a `  global_ref: <name>` line that is a DIRECT (2-space) child of a top-level `metadata:` key.

    Parses frontmatter STRUCTURE, not the raw block (a raw regex would match `global_ref:` on a
    folded-scalar continuation line and misclassify a project-authored note — GC/promotion would then
    mishandle it). Lives here (the dependency root) so sync_global imports it — SINGLE definition shared
    by --pull / --gc / the promotion re-audit. Bias to False on ambiguity: a missed mirror merely isn't
    reclaimed (safe); a false positive destroys user memory (unsafe)."""
    if text.startswith("﻿"):
        text = text[1:]
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return False
    top = None
    first = True
    for ln in m.group(1).splitlines():
        if not ln.strip():
            continue
        if first and re.match(r"#\s*global_ref:\s*\S", ln):
            return True
        first = False
        if not ln[:1].isspace():
            mk = re.match(r"([^:#\s][^:]*):", ln)
            top = mk.group(1).strip() if mk else None
            continue
        if top == "metadata" and re.match(r" {2}global_ref:\s*\S", ln):
            return True
    return False


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


def schema_drift(fact_files: list, index_names: set) -> SchemaDrift:
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


def drift_findings(d: Mapping[str, Any]) -> int:
    """Count of DRIFT findings (NOT advisory) — the AC#1 'clean store' gate. Strict `int()` (its
    callers — the seed + smoke — always pass clean ints). Param is a read-only `Mapping[str, Any]`
    so the `SchemaDrift` that `schema_drift()` returns flows in (a TypedDict IS assignable to a
    read-only Mapping, but NOT to invariant `dict`). NOTE: render_dashboard does NOT call this; it
    sums the same four fields via its own `_num` at the model→presentation boundary (a
    model-authored non-numeric value must not crash render). Keep the two in sync if the drift
    fields change."""
    return (int(d.get("missing_node_type", 0)) + int(d.get("malformed_scope", 0))
            + int(d.get("malformed_origin", 0)) + int(d.get("index_mismatch", 0)))


def _newest_mtime(base: Path, pattern: str) -> float:
    """Newest mtime among base/pattern files; 0.0 if none/absent/UNREADABLE (slug-orphan
    liveness signal). Never raises: an unreadable sibling dir (PermissionError) or a file that
    vanishes between glob and stat (TOCTOU FileNotFoundError) degrades to 0.0 — Phase 0 must stay
    read-only AND crash-proof on a hostile/odd projects tree."""
    if not base.exists():
        return 0.0
    newest = 0.0
    try:
        for f in base.glob(pattern):
            try:
                newest = max(newest, f.stat().st_mtime)
            except OSError:
                continue  # file vanished between glob and stat (TOCTOU) — skip it
    except OSError:
        return 0.0  # unreadable dir — degrade, don't crash Phase 0
    return newest


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
    try:
        siblings = [p.name for p in projects_root.iterdir() if p.is_dir()] if projects_root.exists() else []
    except OSError:
        siblings = []  # unreadable projects root → skip the sibling scan (Phase 0 stays crash-proof)
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
        "promotion_candidates": _promotion_candidates(fact_files),
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


_PROMO_TYPES = {"feedback", "reference"}   # Auto-Dream memory types that lean cross-project (directives, pointers)
_PROMO_CAP = 8                              # cap the Phase-1 promotion seed — a re-audit list, not a rubber stamp


def _is_promotion_candidate(text: str) -> bool:
    """True if a fact's frontmatter passes the Phase-1 promotion SEED filter: NOT a mirror, no `scope`
    set yet, and a cross-project-leaning `type` (feedback/reference — directives, pointers). A WEAK
    pre-filter only; the model re-walks the scope cascade by CONTENT + re-verifies before promoting."""
    if _is_mirror(text):                           # already a global mirror → not a candidate
        return False
    fm = _frontmatter(text)
    return not fm.get("scope") and fm.get("type", "") in _PROMO_TYPES


def _promotion_candidates(fact_files: list) -> list[str]:
    """Names of project-authored facts that pass the promotion seed filter — the SEED for the Phase-1
    promotion re-audit. Capped (a re-audit list, not a rubber stamp)."""
    out: list[str] = []
    for f in fact_files:
        if len(out) >= _PROMO_CAP:
            break
        try:
            if _is_promotion_candidate(f.read_text(encoding="utf-8", errors="replace")):
                out.append(f.stem)
        except OSError:
            continue
    return out


def dream_timing_advisory(commits: int, marker_ts: str, has_marker: bool) -> str | None:
    """A NO-NAG dream-timing nudge for the Phase-0 report (and `cm status`): when work has
    accrued SINCE THE LAST DREAM, suggest consolidating at this arc boundary. Advisory only —
    it NEVER fires a dream (explicit-trigger-only is a kept design value). Returns None (silent)
    in the cases where a nudge would be wrong or noise:

    - **No prior dream** (`has_marker` False, from the caller's `bool(ctx["last_commit"])`): with
      no marker, `commits` is a recent-≤20 *lookback*, NOT since-a-dream, so "overdue since the
      last dream" is meaningless → None. (You're also mid-dream on a first consolidation.)
    - **Below the SUBSTANTIAL band** (tier LIGHT, commits ≤ TIER_LIGHT_MAX): too little accrued → None.

    Pure + never-crash: a tampered / tz-aware / garbage `marker_ts` only drops the age clause
    (never raises) — `datetime.now()` is tz-NAIVE but a marker may be tz-AWARE, so age is computed
    by subtracting `.timestamp()` FLOATS (the `_stale_since` pattern), not aware−naive datetimes."""
    if not has_marker:
        return None
    tier = suggested_tier(commits, 0)            # candidates unknown at Phase 0 → 0
    if tier == "LIGHT":                          # below the SUBSTANTIAL band → no-nag
        return None
    age = ""
    if isinstance(marker_ts, str) and marker_ts:
        try:
            hrs = (datetime.now().timestamp()
                   - datetime.fromisoformat(marker_ts.replace("Z", "+00:00")).timestamp()) / 3600
            age = (" (<1h ago)" if hrs < 1 else        # also clamps a future-dated marker
                   f" (~{round(hrs)}h ago)" if hrs < 48 else
                   f" (~{round(hrs / 24)}d ago)")
        except (ValueError, TypeError, OSError):
            age = ""
    return (f"💤 dream-timing: {commits} commits since the last dream{age} — a {tier} unconsolidated "
            "arc; a good boundary to consolidate before compaction. (Coarse hint: the count over-counts "
            "work already consolidated between dreams — judge whether there's genuinely new signal.)")


def seed_record(ctx: dict) -> CycleRecord:
    """The cycle-record SEED — before-values + scope + provisional rigor, for render_dashboard.py.
    Annotated as CycleRecord so mypy enforces this LITERAL against the contract: a drifted,
    renamed, extra, or wrong-typed key here (the main historical drift source — seed↔SKILL)
    is now a static error, not a runtime surprise downstream."""
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


def validate_cycle_record(record: object) -> list[str]:
    """Warn-only RUNTIME structural check on a cycle record — the complement to the
    static TypedDict (which is producer-asymmetric: it can't see render's `.get()` reads
    or a model-authored record loaded from JSON). Returns a list of human-readable
    warnings; PURE, stdlib-only, and NEVER raises (it guards every access, so junk input
    — a non-dict record, a non-dict `health`, a `health` that is a list — yields warnings
    or silence, never a crash).

    It flags only a PRESENT key whose CONTAINER type is wrong (the model-slip class behind
    the Gate-2 crashes), at the ACTUAL nesting — every top-level container key (`scope`,
    `health`, … — `health` included, so a non-dict `health` warns) plus `health.slug_orphans`
    / `health.schema_drift`, which nest UNDER `health`. It is deliberately QUIET on a missing
    key (a partial record is normal, the phases fill it incrementally) and on a correct
    type, and it does NOT check scalar value types — that's the `_num`/`_clean`/`_flag`
    coercion boundary in render, not this structural gate."""
    warnings: list[str] = []
    if not isinstance(record, dict):
        # Not even a dict — render's own json.loads guard handles the parse; here we just
        # report the shape and bail (nothing else is inspectable).
        return [f"cycle record is not a dict (got {type(record).__name__})"]

    # Top-level keys that MUST be a dict if present.
    for key in ("scope", "rigor", "verification", "budget", "cross_project", "network", "marker", "health"):
        if key in record and not isinstance(record[key], dict):
            warnings.append(f"{key} is not a dict")
    # entries must be a list if present.
    if "entries" in record and not isinstance(record["entries"], list):
        warnings.append("entries is not a list")

    # Nested under health — checked ONLY when health itself is a dict. A non-dict `health`
    # already warned via the top-level tuple above ("health is not a dict"); here we just
    # decline to descend into a malformed one (no double-warn, no crash on its sub-keys).
    health = record.get("health")
    if isinstance(health, dict):
        if "slug_orphans" in health and not isinstance(health["slug_orphans"], list):
            warnings.append("health.slug_orphans is not a list")
        if "schema_drift" in health and not isinstance(health["schema_drift"], dict):
            warnings.append("health.schema_drift is not a dict")
    return warnings


def print_report(ctx: dict) -> None:
    out: list = []
    add = out.append
    proj = ctx["project_dir"].name
    gc = len(ctx["commits"])
    tier = suggested_tier(gc, 0)  # candidates unknown in Phase 0 → 0
    rg = _provisional_rigor(ctx)
    has_marker = bool(ctx["last_commit"])
    tcol = {"LIGHT": "green", "SUBSTANTIAL": "yellow", "HEAVY": "red"}.get(tier, "bold")

    # ── banner (visually coherent with the final dashboard) ──
    title = "✦ PHASE 0 · consolidate-memory"
    tag = tier if (gc or rg["prune_pressure"]) else "NO-OP"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    add(_ui.rule())
    add("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, tcol if tag == tier else "dim"))
    sub = f"{proj} · {ctx['slug']}" + ("" if ctx["proj_root"].exists() else "   ⚠ proj_root MISSING")
    add("  " + _ui.c(sub, "dim"))
    add(_ui.rule())

    # ── SCOPE — the git range to harvest facts from (since the last consolidation) ──
    add("")
    if has_marker:
        add(_ui.kv("SCOPE", f"git {ctx['git_range']} · {gc} commit(s) since marker "
                            + _ui.c(f"{ctx['last_commit'][:12]} @ {ctx['last_ts']}", "dim")))
    else:
        add(_ui.kv("SCOPE", f"git {ctx['git_range']} · {gc} commit(s)  "
                            + _ui.c("· FIRST consolidation: a ≤20-commit lookback, NOT since-marker work", "dim")))
    for cmt in ctx["commits"]:
        add(_ui.li(_sane(cmt), bullet="·"))
    if not ctx["commits"]:
        add(_ui.li(_ui.c("(no new commits in range)", "dim"), bullet="·"))

    # ── RIGOR — provisional effort hint (DERIVED from magnitude; you finalize in Phase 2) ──
    add("")
    add(_ui.kv("RIGOR", f"{_ui.c(tier, tcol)} provisional · magnitude {gc} "
                        + _ui.c(f"(+ curated candidates in Phase 2) · ladder ≤{TIER_LIGHT_MAX} / {TIER_LIGHT_MAX + 1}–{TIER_SUBSTANTIAL_MAX} / ≥{TIER_SUBSTANTIAL_MAX + 1}", "dim")))
    if rg["prune_pressure"]:
        add(_ui.li(_ui.c(f"⚠ prune-pressure ({rg['prune_reason']}) — prune-or-propose this pass, at ANY tier", "yellow")))
    advisory = dream_timing_advisory(gc, ctx["last_ts"], has_marker)
    if advisory:
        add(_ui.li(advisory))

    # ── MEMORY LOAD — what the AI re-reads every session (smaller = cheaper, sharper) ──
    add("")
    add(_ui.kv("STORES", _ui.c("always-loaded tier paid every session · fact bodies read on-demand", "dim")))
    if ctx["auto_mem"].exists():
        il, ib, it = ctx["index_lb"]
        over = _ui.c("  ⚠ OVER", "red") if it > INDEX_TOKEN_BUDGET else ""
        add(f"    {_ui.lbl('index', 14)}{_ui.bar(it, INDEX_TOKEN_BUDGET)} {_ui.pct(it, INDEX_TOKEN_BUDGET):>4}  "
            + _ui.c(f"≈{it}/{INDEX_TOKEN_BUDGET} tok · {il} ln · {ib} by  [ALWAYS-LOADED]", "dim") + over)
    cl = ctx["repo"].get("CLAUDE.md")
    if cl and (cl[0] or cl[1]):
        cln, clb, ct = cl
        over = _ui.c("  ⚠ OVER", "red") if ct > CLAUDE_MD_TOKEN_BUDGET else ""
        add(f"    {_ui.lbl('CLAUDE.md', 14)}{_ui.bar(ct, CLAUDE_MD_TOKEN_BUDGET)} {_ui.pct(ct, CLAUDE_MD_TOKEN_BUDGET):>4}  "
            + _ui.c(f"≈{ct}/{CLAUDE_MD_TOKEN_BUDGET} tok · {cln} ln · {clb} by  [project, committed]", "dim") + over)
    gl, gb, gt = ctx["global_claude_md"]
    if gl or gb:
        heavy = _ui.c("  ⚠ heavy", "yellow") if gt > GLOBAL_CLAUDE_MD_TOKEN_BUDGET else ""
        add(f"    {_ui.lbl('~/.claude/CLAUDE.md', 14)}" + _ui.c(f"≈{gt} tok · {gl} ln · read-only, every project (never edited here)", "dim") + heavy)
    for nm in ("MEMORY.md", "AGENTS.md"):
        r = ctx["repo"].get(nm)
        if r and (r[0] or r[1]):
            add(f"    {_ui.lbl(nm, 14)}" + _ui.c(f"{r[0]} ln · {r[1]} by · ≈{r[2]} tok  [on-demand, committed]", "dim"))
    if ctx["auto_mem"].exists():
        facts = ctx["fact_files"]
        add("    " + _ui.c(f"recall facts ({len(facts)}) — bodies read on-demand in Phase 1:", "dim"))
        wn = min(max((len(f.stem) for f in facts), default=1), 42)
        for f in facts:
            fl, fby, ft = _measure(f)
            add("      " + _ui.c(f"{f.stem:<{wn}}  {fl:>3} ln · {fby:>5} by · ≈{ft:>4} tok", "dim"))

    # ── NEEDS A LOOK — suggestions only; nothing is changed automatically ──
    sig: list = []
    if ctx.get("promotion_candidates"):
        sig.append(_ui.li(f"promote? {len(ctx['promotion_candidates'])} unscoped feedback/reference fact(s) may apply "
                          "cross-project — re-scope by content + re-verify in Phase 1: "
                          + _ui.c(", ".join(ctx["promotion_candidates"]), "dim"), bullet="↑", bullet_color="cyan"))
    if ctx["stale_facts"]:
        sig.append(_ui.li(f"re-verify {len(ctx['stale_facts'])} stale fact(s) (mtime ≤ marker): "
                          + _ui.c(", ".join(ctx["stale_facts"]), "dim"), bullet="·"))
    if ctx["slug_orphans"]:
        cur_live = max(_newest_mtime(ctx["proj_root"], "*.jsonl"), _newest_mtime(ctx["auto_mem"], "*.md"))
        for o in ctx["slug_orphans"]:
            tl = max(o["newest_txn"], o["newest_fact"])
            which = "twin newer" if tl > cur_live else ("this store newer" if cur_live > tl else "same recency")
            sig.append(_ui.li(f"slug-orphan {_sane(o['slug'])} ({which}) — rename-orphan; merge toward newest mtime, confirm first",
                              bullet="⚠", bullet_color="yellow"))
    d = ctx["schema_drift"]
    if drift_findings(d) > 0:
        sig.append(_ui.li(f"schema drift: {d['missing_node_type']} missing node_type · {d['malformed_scope']} malformed scope · "
                          f"{d['malformed_origin']} malformed origin · {d['index_mismatch']} index↔file — offer backfill, confirm first",
                          bullet="⚠", bullet_color="yellow"))
    if d["advisory_no_scope"] or d["advisory_no_origin"]:
        sig.append(_ui.li(_ui.c(f"backfill (optional, NOT drift): {d['advisory_no_scope']} lack scope · {d['advisory_no_origin']} lack originSessionId", "dim"), bullet="·"))
    if sig:
        add("")
        add(_ui.kv("SIGNALS", _ui.c("detect-and-offer — Phase 0 never mutates a store", "dim")))
        out.extend(sig)

    # ── GLOBAL + SESSION ──
    add("")
    g = Path.home() / ".claude" / "memory"
    gn = len([f for f in g.glob("*.md") if f.name != "MEMORY.md"]) if g.exists() else 0
    add(_ui.kv("GLOBAL", f"{gn} cross-project fact(s) in ~/.claude/memory  " + _ui.c("(sync_global.py --list . for fit here)", "dim")))
    if ctx["transcripts"]:
        add(_ui.kv("SESSION", _ui.c("trajectory — the extractor streams it; never bulk-read", "dim")))
        for t in ctx["transcripts"][-5:]:
            add(_ui.li(f"{t.name}  {t.stat().st_size / 1_048_576:.1f} MB  " + _ui.c(f"(mtime {int(t.stat().st_mtime)})", "dim"), indent=6, bullet="·"))

    # ── NEXT ──
    add("")
    add(_ui.kv("NEXT", _ui.c(f"run with --json to start the record · render_dashboard.py draws the summary · saves a checkpoint at {ctx['head'][:12]}", "dim")))

    print(_ui.ascii_translate("\n".join(out)))


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    pos = [a for a in argv if not a.startswith("-")]   # positional = the project dir; flags (--json/--color/--ascii) excluded
    project_dir = Path(pos[0]) if pos else Path.cwd()
    ctx = build_context(project_dir)
    if as_json:
        print(json.dumps(seed_record(ctx), indent=2))
    else:
        _ui.set_modes(color=_ui.color_enabled(argv, sys.stdout), ascii="--ascii" in argv, width=_ui.resolve_width(argv, sys.stdout))
        print_report(ctx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
