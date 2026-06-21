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

import hashlib
import json
import re
import subprocess
import sys
import tempfile
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


class ClaudeMdHierarchyFile(TypedDict, total=False):
    path: str          # repo-relative path of a CLAUDE.md
    tokens: int


class ClaudeMdHierarchy(TypedDict, total=False):
    # v0.1.22: the WHOLE CLAUDE.md hierarchy (root + nested), not just the root. CLAUDE.md loads hierarchically,
    # so worst_path = the heaviest root→leaf ancestor chain ("a session in <dir> pays worst_path_tokens").
    files: list[ClaudeMdHierarchyFile]
    worst_path: str            # the dir whose CLAUDE.md ancestor-chain sums highest (repo-relative)
    worst_path_tokens: int
    total_files: int


class Budget(TypedDict, total=False):
    claude_md: ClaudeMdBudget
    global_claude_md: GlobalClaudeMd
    index: IndexBudget
    recall_facts: RecallFacts
    claude_md_hierarchy: ClaudeMdHierarchy   # v0.1.22: whole-hierarchy measure (read-only)


class AuditOp(TypedDict, total=False):
    path: str          # store-/repo-relative path that changed
    op: str            # created | modified | deleted (v0.1.23 relocate = a delete+create pair)
    token_delta: int   # after − before tokens
    store: str         # memory | claude_md


class AuditStoreDelta(TypedDict, total=False):
    created: int
    modified: int
    deleted: int
    token_delta: int


class Audit(TypedDict, total=False):
    # v0.1.22: the DETERMINISTIC, script-emitted mutation trail — what this pass ACTUALLY changed (a content-hash
    # snapshot diffed Phase0→Phase5), the counterpart to the model-narrated entries[]. HONEST GAP: the window
    # attributes ANY change in the Phase0→Phase5 span to the dream (an interrupted/concurrent edit mis-attributes).
    memory: AuditStoreDelta
    claude_md: AuditStoreDelta
    operations: list[AuditOp]
    window: str


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


class Remediation(TypedDict, total=False):
    # v0.1.18: inherited-backlog remediation — the over-budget GATE + the staged triage outcome.
    required: bool                 # the gate is active (the always-loaded index is over budget)
    lever: str                     # ROUTED: "prune" (local-dominated) | "gc" (mirror-dominated) | "justify" (all-durable)
    candidates_surfaced: int       # ranked prune candidates triage offered (stages A+B+C); model judges + user confirms
    pruned: int                    # what the dream actually pruned this pass (Phase 5)
    projected_index: int           # est index tokens after evicting the candidates
    achieved_index: int            # actual index tokens after the pass
    projected_recall: int          # est recall-pool tokens freed if the candidates were evicted
    achieved_recall: int
    # v0.1.21 (beta defect cluster D3/D5/D6/D7/D11):
    standing_justified: bool       # the over-budget gate is SUPPRESSED — density already justified, store hasn't grown by Δ
    baseline_facts: int            # the fact-count baseline at which the density was last justified (delta-detector)
    reaches_budget: bool           # can a full prune of the candidates reach budget? False ⇒ prune-then-standing-justify


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
    remediation: Remediation       # v0.1.18: over-budget gate + staged-triage outcome (additive; legacy records render)
    audit: Audit                   # v0.1.22: deterministic script-emitted mutation trail (additive; legacy records render)
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


def cycle_seed_path(slug: str) -> str:
    """A DETERMINISTIC per-project temp path for a dream's cycle record — `<tmpdir>/cm-cycle<slug>.json`.
    Per-SLUG, NOT a shared `/tmp/cycle.json`: concurrent dreams of DIFFERENT projects each get their own
    file, so they can't clobber each other's record (a memex dream once overwrote consolidate-memory's via
    the shared path → a 'franken-record' with mismatched scope/remediation, v0.1.20 fix). Deterministic
    (slug-derived) so every phase + the render reconstruct the same path with no cross-shell state. The slug
    is already filesystem-safe (path with '/'+'_' → '-')."""
    return str(Path(tempfile.gettempdir()) / f"cm-cycle{slug}.json")


def resolve_wikilink(target: str, stems: set) -> str | None:
    """v0.1.21 (D4/D10): resolve a `[[target]]` to an EXISTING fact stem across slug-drift — EXACT match only,
    NEVER substring/prefix. Order: exact stem → normalized-exact (dash↔underscore, lowercased) → date-stripped
    EXACT-base equality (`[[foo]]`↔`foo_2026_05_28` and the reverse), only when the base is DISTINCTIVE (≥12
    chars). Ambiguous (>1 candidate) ⇒ None — DON'T resolve: a resolved target gets added to reference_stems,
    which SUPPRESSES an eviction, so the safe bias is to NOT match on doubt (the inverse of evict-safety).
    Powers wikilink in-degree (D4: a wikilinked fact is not a safe-evict orphan) + dangling-link fix hints (D10)."""
    if target in stems:
        return target

    def _norm(s: str) -> str:
        return re.sub(r"[-_]", "-", s).lower()

    nt = _norm(target)
    hits = [s for s in stems if _norm(s) == nt]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        return None                                   # ambiguous → don't resolve
    base = re.sub(r"[-_]20\d\d.*", "", target)
    if len(base) >= 12:                               # distinctive base only (mirrors the reference-scan guard)
        nb = _norm(base)
        dated = [s for s in stems if _norm(re.sub(r"[-_]20\d\d.*", "", s)) == nb]
        if len(dated) == 1:
            return dated[0]
    return None


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


# ── v0.1.18: inherited-backlog remediation ──────────────────────────────────────
# The app PREVENTS incremental bloat (budget ⚠ + prune_pressure) but couldn't REMEDIATE a backlog inherited
# from CC's Auto-Dream (unbounded append, no index discipline) — observed on memex (110 facts, index 5.5×
# budget, 30 unindexed orphans; the one dream that ran GREW the index 5.5× over). Empirics: a name/type/date
# heuristic MIS-classifies durability (false-pos durable techniques, false-neg dated refs), so triage
# RANKS/surfaces candidates in cost-ordered STAGES — it NEVER decides; the model judges content + the user
# confirms (no delete path here, like schema_drift / _promotion_candidates).
_TRACKER_RE = re.compile(r"(?i)(?:^|[_-])(?:tracker|status|shipped|backlog|roadmap|todo|progress|next[_-]?priorit\w*)(?:[_-]|$)|^p\d+[_-]|(?:^|[_-])bak(?:[_-]|$)")
_DATED_RE = re.compile(r"(?:^|[_-])20\d\d[_-]\d\d[_-]\d\d(?:[_-]|$)")   # an Auto-Dream _YYYY_MM_DD stamp
_OVERSIZED_TOK = 2500          # a body this big is a dump/research-note → a (ranking) content-review candidate
_MIRROR_DOMINATED = 0.5        # mirror share of the index above which the lever is GC, not a futile local prune
_LEAN_HOOK_TOK = 30            # est tokens/pointer for a lean re-index of the keep core (the projected_index target)
_STANDING_JUSTIFY_DELTA = 10   # v0.1.21: a standing-justified over-budget gate re-FIRES once the store grows by this
                               # many facts past the justified baseline (the delta-detector) — keeps the v0.1.18 teeth


def _standing_baseline(sj: object) -> int | None:
    """v0.1.21 (D7): the justified fact-count baseline from a marker's `standing_justify`, or None. FAILS OPEN —
    a malformed/absent value (legacy marker, non-dict, non-int `facts`) returns None ⇒ the gate FIRES (never
    suppress on garbage; suppression is the dangerous direction). Pairs with _STANDING_JUSTIFY_DELTA."""
    if isinstance(sj, dict) and isinstance(sj.get("facts"), int):
        return sj["facts"]
    return None


def _is_archive_index(path: Path) -> bool:
    """True if a store `*.md` is an ARCHIVE INDEX (a link-list like MEMORY.md / SHIPPED.md), NOT a fact.
    A fact begins with `---` frontmatter; an archive index does not and is mostly `](x.md)` links. v0.1.18.x
    (beta finding C1): the triage globs every `*.md` as a fact, so a relocated archive (`SHIPPED.md`, whose
    stem matches the tracker regex) lands in B → "evict" → nuking the archive. Excluding archive docs from
    fact_files prevents that, and lets their link-targets count as reference surfaces. Cheap: the 64-byte head
    short-circuits the common (fact-with-frontmatter) case before reading the whole file."""
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            head = fh.read(64)
            if head.lstrip("﻿").lstrip().startswith("---"):   # fact frontmatter (BOM-tolerant, cf _frontmatter) → not an archive
                return False
            rest = head + fh.read()
    except OSError:
        return False
    return len(_LINK_RE.findall(rest)) >= 3          # link-list with no frontmatter → archive index


def remediation_triage(fact_files: list, index_names: set, index_tokens: int,
                       mirror_index_tokens: int, budget: int = INDEX_TOKEN_BUDGET,
                       reference_stems: set | None = None) -> dict:
    """PURE: for an OVER-budget store, rank LOCAL prune candidates into cost-ordered STAGES + route the lever.
    Returns {} when the index is under budget (no false alarm on a healthy store). Heuristics RANK/surface;
    they NEVER decide durability (empirics: name/date mis-classifies) — the model judges content, the user
    confirms. NO unlink/write path here.

    Stages: A TRUE orphans (unindexed AND unreferenced — dead weight; evict OR re-index) · B tracker/status
    (transient) · C dated/oversized (UNRELIABLE class — content_review-flagged, may even be a PROMOTE candidate)
    · R referenced (unindexed BUT reachable via CLAUDE.md/archive `reference_stems` — NOT a safe evict; de-link
    the surface first; counts toward keep_core, re-indexed by the lean rebuild). Lever routing: MIRROR-dominated
    overflow (mirrors > 50% of index) → "gc" (local
    pruning is futile — --pull re-creates mirrors); local-dominated with candidates → "prune"; over budget but
    nothing locally prunable (all-durable) → "justify" (the gate is satisfiable by a recorded justification,
    never a deadlock)."""
    if index_tokens <= budget:
        return {}
    share = (mirror_index_tokens / index_tokens) if index_tokens else 0.0
    refs = reference_stems or set()
    A: list = []
    B: list = []
    C: list = []
    R: list = []
    keep = 0
    for f in fact_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _is_mirror(text):
            keep += 1                       # cross-project mirror — GC's domain, not a LOCAL prune candidate
            continue
        cand = {"stem": f.stem, "body_tokens": est_tokens(text)}
        if f.stem not in index_names:
            if f.stem in refs:
                cand["referenced"] = True   # C2: reachable via CLAUDE.md/archive prose → NOT a safe-evict orphan
                R.append(cand)
                keep += 1                   # counts toward keep_core: the lean rebuild re-indexes it (Gate-1 #3)
            else:
                A.append(cand)              # TRUE orphan — unindexed AND unreferenced = unreachable dead weight
        elif _TRACKER_RE.search(f.stem):
            B.append(cand)                  # tracker/status — transient by nature
        elif _DATED_RE.search(f.stem) or cand["body_tokens"] > _OVERSIZED_TOK:
            cand["content_review"] = True   # the unreliable class — ranked, JUDGED by content (never auto-pruned)
            C.append(cand)
        else:
            keep += 1                       # durable-keep core
    for stage in (A, B, C, R):
        stage.sort(key=lambda c: -c["body_tokens"])
    cands = A + B + C                        # R is NOT a safe-evict candidate (referenced elsewhere) — surfaced separately
    lever = "gc" if share > _MIRROR_DOMINATED else ("prune" if cands else "justify")
    return {
        "required": True, "lever": lever,
        "index_tokens": index_tokens, "budget": budget, "mirror_share": round(share, 2),
        "candidates": len(cands), "keep_core": keep, "referenced": len(R),
        "stages": {"A_orphans": A, "B_trackers": B, "C_dated_oversized": C, "R_referenced": R},
        "projected_recall": sum(c["body_tokens"] for c in cands),
        "projected_index": keep * _LEAN_HOOK_TOK,   # est lean re-index of the keep core (incl. R, re-indexed)
        # D5 (v0.1.21): can a full prune even reach budget? If not, the lever is prune-the-safe-THEN-standing-justify
        # the residual — not a clean achievable "prune" (mature stores: keep core alone often exceeds budget).
        "reaches_budget": keep * _LEAN_HOOK_TOK <= budget,
    }


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


def _claude_md_files(project_dir: Path) -> list[Path]:
    """Every CLAUDE.md in the repo tree (root + nested), excluding vendored/VCS dirs — the shared reference-scan
    predicate (mirrors the build_context glob). glob('**/') does NOT follow directory symlinks (no cycle risk)."""
    return [p for p in project_dir.glob("**/CLAUDE.md")
            if not any(part in {".venv", "node_modules", ".git"} for part in p.parts)]


def claude_md_hierarchy(project_dir: Path) -> dict:
    """v0.1.22 (READ-ONLY): measure the WHOLE CLAUDE.md hierarchy, not just the root. CLAUDE.md loads
    HIERARCHICALLY — a session in a leaf dir pays every ancestor's CLAUDE.md up to the repo root — so the
    load-bearing number is `worst_path`: the dir whose root→leaf CLAUDE.md ancestor-chain sums highest
    ('a session in <dir> pays worst_path_tokens of CLAUDE.md every turn'). Bounded at project_dir (the repo root
    via .resolve()), never the filesystem root. Pure read; never mutates."""
    root = project_dir.resolve()
    by_dir: dict = {}
    for p in _claude_md_files(root):                     # guard the read (Gate-2): a dir-named CLAUDE.md or an
        try:                                             # unreadable/raced file must NOT crash build_context — this
            by_dir[p.parent.resolve()] = est_tokens(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:                                  # is on the critical path (build_context calls it always)
            continue
    worst_dir, worst_tokens = root, 0
    for d in by_dir:                                    # 'leaf' = every dir that HAS a CLAUDE.md (Gate-1 #3)
        chain, cur = 0, d
        while True:                                     # sum this dir + all ancestors up to the repo root
            chain += by_dir.get(cur, 0)
            if cur == root or cur.parent == cur:        # stop at repo root (or filesystem root — belt-and-suspenders)
                break
            cur = cur.parent
        if chain > worst_tokens:
            worst_dir, worst_tokens = d, chain

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(root)) or "."
        except ValueError:
            return str(p)

    files = [{"path": _rel(d / "CLAUDE.md"), "tokens": t}
             for d, t in sorted(by_dir.items(), key=lambda kv: -kv[1])]
    return {"files": files, "worst_path": _rel(worst_dir),
            "worst_path_tokens": worst_tokens, "total_files": len(by_dir)}


def audit_snapshot_path(slug: str) -> str:
    """v0.1.22: deterministic per-slug temp path for a dream's BEFORE audit snapshot (sibling of cycle_seed_path)."""
    return str(Path(tempfile.gettempdir()) / f"cm-audit{slug}.json")


def audit_snapshot(project_dir: Path) -> dict:
    """v0.1.22: a deterministic content-hash snapshot of everything a dream may mutate — the private memory store
    (`*.md`: fact files + MEMORY.md + any archive index) and the CLAUDE.md hierarchy. The dream's own infra
    (`.consolidation-state.json` / `.consolidation-log.jsonl` / `.mutation-log.jsonl`) is NOT `*.md`, so the glob
    already excludes it — only legitimate facts/index/CLAUDE.md are tracked (MEMORY.md IS included: a re-index is
    a real, wanted write the audit SHOULD catch — the renderer labels an index-only diff as expected). READ-ONLY;
    a content hash the model can't fake. Pairs with audit_diff for the Phase0→Phase5 mutation trail."""
    project_dir = project_dir.resolve()
    auto_mem = Path.home() / ".claude" / "projects" / slug_for(project_dir) / "memory"
    snap: dict = {}

    def _add(label: str, p: Path, store: str) -> None:
        try:
            data = p.read_bytes()
        except OSError:
            return
        snap[label] = {"hash": hashlib.sha1(data).hexdigest(),
                       "tokens": est_tokens(data.decode("utf-8", "replace")), "store": store}

    if auto_mem.exists():
        for f in sorted(auto_mem.glob("*.md")):
            _add(f"memory/{f.name}", f, "memory")
    for p in _claude_md_files(project_dir):
        try:
            label = f"claude_md/{p.relative_to(project_dir)}"
        except ValueError:
            label = f"claude_md/{p.name}"
        _add(label, p, "claude_md")
    return snap


def audit_diff(before: dict, after: dict) -> dict:
    """v0.1.22: the DETERMINISTIC mutation set between two audit_snapshots — one op per file whose content-hash
    CHANGED (created / modified / deleted); an unchanged file (same hash) is NOT an op. Per-store rollups
    (memory / claude_md). This is the script-OBSERVED counterpart to the model-narrated entries[]."""
    ops: list = []
    roll = {"memory": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0},
            "claude_md": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0}}

    # The BEFORE snapshot is UNTRUSTED (a stale/cross-version/hand-edited file on disk) — guard every entry's
    # shape (Gate-2): non-dict entry → ignored; missing hash/tokens → coerced; an unexpected `store` → clamped to
    # 'memory'. (JSONDecodeError/OSError on the file are already handled at the --audit call site.)
    def _tok(d: object) -> int:
        try:
            return int((d or {}).get("tokens", 0) or 0) if isinstance(d, dict) else 0
        except (TypeError, ValueError):
            return 0

    for label in sorted(set(before) | set(after)):
        b = before.get(label) if isinstance(before.get(label), dict) else None
        a = after.get(label) if isinstance(after.get(label), dict) else None
        store = (a or b or {}).get("store", "memory")
        if store not in roll:
            store = "memory"
        bt, at = _tok(b), _tok(a)
        if b and a and b.get("hash") != a.get("hash"):
            op, delta = "modified", at - bt
        elif a and not b:
            op, delta = "created", at
        elif b and not a:
            op, delta = "deleted", -bt
        else:
            continue                                    # unchanged (same hash) or both absent → not an op
        ops.append({"path": label, "op": op, "token_delta": delta, "store": store})
        roll[store][op] += 1
        roll[store]["token_delta"] += delta
    return {"memory": roll["memory"], "claude_md": roll["claude_md"], "operations": ops}


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
    # C1 (v0.1.18.x): split store *.md into FACTS vs ARCHIVE-INDEX docs (link-lists like SHIPPED.md). Archive
    # indexes are NOT facts — exclude them so the triage never classifies/evicts a relocated archive (MEMORY.md
    # is already excluded by name; this generalizes). archive_docs double as a reference surface below.
    _store_md = sorted(f for f in auto_mem.glob("*.md") if f.name != "MEMORY.md") if auto_mem.exists() else []
    archive_docs = [f for f in _store_md if _is_archive_index(f)]
    fact_files = [f for f in _store_md if f not in archive_docs]
    # E (v0.1.18.x): a 0-token index read WHILE facts exist is anomalous (a write-truncate race) and would
    # wrongly clear the over-budget gate — re-read ONCE to settle it. A persistent 0 is a genuine all-unindexed
    # store (schema_drift flags the mismatch), not "under budget / all well".
    if index_lb[2] == 0 and fact_files and index_path.exists():
        index_lb = _measure(index_path)

    transcripts = sorted(proj_root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

    state_path = auto_mem / STATE_FILE
    last_commit = last_ts = ""
    standing_justify: object = None
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text())
            last_commit, last_ts = st.get("commit", ""), st.get("timestamp", "")
            standing_justify = st.get("standing_justify")   # v0.1.21 (D7): the justified-density baseline, if any
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
    # An indexed archive (MEMORY.md links to SHIPPED.md) is NOT a fact pointer — drop archive stems from
    # index_names so schema_drift's stems^index_names doesn't count it as a phantom mismatch (Gate-2 #2), and
    # so the triage never reads an archive as "indexed".
    index_names = index_fact_names(index_path) - {f.stem for f in archive_docs}
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

    # v0.1.18 remediation triage (only non-empty when the index is OVER budget). mirror_index_tokens —
    # the share of the always-loaded index driven by cross-project mirrors — ROUTES the lever: a
    # mirror-dominated overflow's fix is global GC, not a futile local prune (mirrors sync_global's
    # _node_tokens attribution).
    # Only relevant when the index is OVER budget — skip the mirror-attribution scan (which reads every
    # fact body) on the healthy path (remediation_triage would short-circuit to {} anyway). Gate-2 nit.
    remediation: dict = {}
    _sj_baseline = _standing_baseline(standing_justify)   # v0.1.21 (D7): justified-density baseline, or None (fail-open)
    if (index_lb[2] > INDEX_TOKEN_BUDGET and _sj_baseline is not None
            and len(fact_files) <= _sj_baseline + _STANDING_JUSTIFY_DELTA):
        # STANDING-JUSTIFIED (D6/D7): the density was judged EARNED at this baseline and the store hasn't grown by
        # Δ — SUPPRESS the gate (don't re-surface the same triage every pass). The delta-detector re-fires below
        # once fact-count exceeds baseline+Δ (new density to review). Keeps the v0.1.18 teeth without alarm fatigue.
        remediation = {"required": False, "standing_justified": True, "baseline_facts": _sj_baseline,
                       "index_tokens": index_lb[2], "budget": INDEX_TOKEN_BUDGET, "candidates": 0,
                       "current_facts": len(fact_files)}
    elif index_lb[2] > INDEX_TOKEN_BUDGET:
        mirror_stems: set = set()
        for _f in fact_files:
            try:
                if _is_mirror(_f.read_text(encoding="utf-8", errors="replace")):
                    mirror_stems.add(_f.stem)
            except OSError:
                continue
        _idx_text = index_path.read_text(encoding="utf-8", errors="replace") if index_path.exists() else ""
        _mirror_idx = [ln for ln in _idx_text.splitlines()
                       if (m := _LINK_RE.search(ln)) and m.group(1) in mirror_stems]
        # C2 (v0.1.18.x): gather reference_stems from the OTHER always-loaded surfaces so a fact reachable
        # there is NOT mis-flagged as a safe-evict orphan. Two match modes (Gate-1 #5): archive-index docs →
        # link-targets; CLAUDE.md prose → bare-stem substring.
        ref_stems: set = set()
        for _adoc in archive_docs:                       # store archive indexes (SHIPPED.md et al.) — link targets
            try:
                ref_stems.update(m.group(1) for m in _LINK_RE.finditer(_adoc.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
        _cmd_text = ""
        for _cmd in project_dir.glob("**/CLAUDE.md"):    # the repo CLAUDE.md hierarchy — bare-stem prose mentions
            if any(p in {".venv", "node_modules", ".git"} for p in _cmd.parts):
                continue
            try:
                _cmd_text += "\n" + _cmd.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        if _cmd_text:
            for _f in fact_files:
                _base = re.sub(r"_20\d\d.*", "", _f.stem)
                # full-stem match always; the date-stripped base only when distinctive (a date WAS stripped AND
                # base ≥12 chars) — a short base ("audit") substrings unrelated prose (Gate-2 #3). Safe either
                # way (a match → R/keep, never a blind evict), so this only trims noise.
                if _f.stem in _cmd_text or (_base != _f.stem and len(_base) >= 12 and _base in _cmd_text):
                    ref_stems.add(_f.stem)
        # D4 (v0.1.21): a fact [[wikilinked]] FROM another fact is reachable — fold its RESOLVED target into
        # reference_stems so the A-stage won't flag it a safe-evict orphan (evicting would dangle the link).
        # resolve_wikilink handles slug-drift; ambiguous → skipped, so we never over-suppress a real orphan.
        _stems = {f.stem for f in fact_files}
        for _f in fact_files:
            try:
                for _m in re.finditer(r"\[\[([^\]]+)\]\]", _f.read_text(encoding="utf-8", errors="replace")):
                    _tgt = resolve_wikilink(_m.group(1).strip(), _stems)
                    if _tgt:
                        ref_stems.add(_tgt)
            except OSError:
                continue
        remediation = remediation_triage(fact_files, index_names, index_lb[2],
                                         est_tokens("\n".join(_mirror_idx)), reference_stems=ref_stems)

    return {
        "project_dir": project_dir,
        "project": project_dir.name,
        "slug": slug,
        "proj_root": proj_root,
        "auto_mem": auto_mem,
        "repo": repo,
        "global_claude_md": global_claude_md,
        "claude_md_hierarchy": claude_md_hierarchy(project_dir),   # v0.1.22: whole-hierarchy measure (read-only)
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
        "remediation": remediation,
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
    record: CycleRecord = {
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
            "claude_md_hierarchy": ctx["claude_md_hierarchy"],   # v0.1.22: whole-hierarchy measure (read-only)
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
    # v0.1.18: seed the remediation block ONLY when the over-budget triage fired (else the key is
    # ABSENT — healthy/legacy records stay valid under total=False).
    # G (v0.1.18.x): seed the PRE-pass ANALYSIS only; OMIT pruned/achieved_* — the model fills them in Phase 5.
    # Seeding achieved_index=current read as "no progress"; ABSENT renders as "pending Phase 5" (total=False).
    rem = ctx.get("remediation") or {}
    if rem and rem.get("standing_justified"):
        # v0.1.21 (D7): the gate is SUPPRESSED (density already justified, store within Δ) — seed the lightweight
        # suppressed block (no lever/triage to surface). required=False so the dashboard reads "standing-justified".
        record["remediation"] = {"required": False, "standing_justified": True,
                                 "baseline_facts": rem.get("baseline_facts", 0)}
    elif rem:
        record["remediation"] = {
            "required": rem["required"], "lever": rem["lever"],
            "candidates_surfaced": rem["candidates"],
            "projected_index": rem.get("projected_index", 0),
            "projected_recall": rem.get("projected_recall", 0),
            "reaches_budget": rem.get("reaches_budget", True),   # D5: False ⇒ prune-then-standing-justify
        }
    return record


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
    for key in ("scope", "rigor", "verification", "budget", "cross_project", "network", "marker", "health", "audit"):
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


def _remediation_section(rem: dict) -> list:
    """The REMEDIATION report lines (v0.1.18) — shared by print_report + --triage. Empty when the index is
    under budget (rem is {}). Presentation only; the heuristics RANK, the model JUDGES + confirms."""
    if not rem:
        return []
    # v0.1.21 (D6/D7): a STANDING-JUSTIFIED over-budget index is suppressed — show the standing state, no triage.
    if rem.get("standing_justified"):
        cur, base = rem.get("current_facts"), rem.get("baseline_facts", 0)
        grew = f"+{cur - base}" if isinstance(cur, int) else "?"
        return [_ui.kv("REMEDIATION", _ui.c(
            f"✓ over budget ({rem.get('index_tokens', '?')}/{rem.get('budget', INDEX_TOKEN_BUDGET)} tok) but "
            f"STANDING-JUSTIFIED · {cur} facts vs baseline {base} ({grew}; re-fires at +{_STANDING_JUSTIFY_DELTA})", "green"))]
    out = [_ui.kv("REMEDIATION", _ui.c(f"⚠ index OVER budget ({rem['index_tokens']}/{rem['budget']} tok) "
                                       f"— GATE active · lever {rem['lever'].upper()}", "red"))]
    # D8 (v0.1.21): lead with the INDEX-RELIEF stages (B/C move the gated index); R = de-link-first; A = disk-only LAST.
    for key, label in (("B_trackers", "tracker/status (transient)"),
                       ("C_dated_oversized", "dated/oversized (content-review — heuristic ranks, you JUDGE)")):
        items = rem["stages"].get(key, [])
        if items:
            top = ", ".join(c["stem"] for c in items[:4]) + (f" +{len(items) - 4} more" if len(items) > 4 else "")
            out.append(_ui.li(f"{len(items):>2} {label}: " + _ui.c(top, "dim"), indent=4, bullet="↓", bullet_color="yellow"))
    referenced = rem["stages"].get("R_referenced", [])
    if referenced:
        rtop = ", ".join(c["stem"] for c in referenced[:4]) + (f" +{len(referenced) - 4} more" if len(referenced) > 4 else "")
        out.append(_ui.li(f"{len(referenced):>2} referenced in CLAUDE.md/archive/wikilinks — NOT safe to evict; de-link FIRST: "
                          + _ui.c(rtop, "dim"), indent=4, bullet="⚠", bullet_color="red"))
    orphans = rem["stages"].get("A_orphans", [])
    if orphans:
        otop = ", ".join(c["stem"] for c in orphans[:4]) + (f" +{len(orphans) - 4} more" if len(orphans) > 4 else "")
        out.append(_ui.li(f"{len(orphans):>2} TRUE orphans (disk hygiene — 0 index relief; evict / re-index): "
                          + _ui.c(otop, "dim"), indent=4, bullet="·"))
    # F (v0.1.18.x): the GATED quantity is INDEX-POINTER tokens; recall body-disk is a SEPARATE axis.
    out.append(_ui.li(f"keep core {rem['keep_core']} · projected index relief ≈{rem['projected_index']}/{rem['budget']} tok "
                      f"(pointers) · recall body-hygiene −≈{rem['projected_recall']} tok (SEPARATE disk axis)",
                      indent=4, bullet="→", bullet_color="cyan"))
    # D5 (v0.1.21): if a full prune can't reach budget, it's prune-the-safe-THEN-standing-justify the residual.
    if rem["lever"] == "prune" and not rem.get("reaches_budget", True):
        hint = "prune the safe candidates, THEN standing-justify the residual (full prune can't reach budget — earned density)"
    else:
        hint = {"gc": "mirror-dominated → the GLOBAL demote/GC lever (a local prune is futile)",
                "justify": "nothing safely prunable → justify-and-proceed (record an entries[] note)",
                "prune": "confirm the candidates, then prune / rebuild the index lean"}.get(rem["lever"], "")
    out.append(_ui.li(_ui.c(f"{hint} · detect-and-offer — confirm before any prune; NEVER auto-deleted", "dim"),
                      indent=6, bullet="·"))
    return out


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
    # D9 (v0.1.21): an active over-budget gate imposes HEAVY-equivalent hard-stop behavior — annotate the
    # provisional rigor so "LIGHT" doesn't undersell a gated pass (reuse the gate predicate; no third copy).
    _rem = ctx.get("remediation") or {}
    _gate = ((" · " + _ui.c("⚠ over-budget GATE active → HEAVY-equivalent hard-stop", "red")) if _rem.get("required")
             else (" · " + _ui.c("✓ over budget but STANDING-JUSTIFIED (gate suppressed)", "green")) if _rem.get("standing_justified")
             else "")
    add(_ui.kv("RIGOR", f"{_ui.c(tier, tcol)} provisional · magnitude {gc} "
                        + _ui.c(f"(+ curated candidates in Phase 2) · ladder ≤{TIER_LIGHT_MAX} / {TIER_LIGHT_MAX + 1}–{TIER_SUBSTANTIAL_MAX} / ≥{TIER_SUBSTANTIAL_MAX + 1}", "dim") + _gate))
    # F (v0.1.18.x): when the REMEDIATION gate will render (index over budget), suppress the redundant
    # `index-over-budget` prune-pressure line — the gate is its actionable form. A `many-facts` prune-pressure
    # is a genuinely separate signal → still print it. (Suppress the PRINT only; the seeded flag stays true.)
    if rg["prune_pressure"] and not (rg.get("prune_reason") == "index-over-budget" and ctx.get("remediation")):
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
    # v0.1.22 (read-only): the WHOLE CLAUDE.md hierarchy — CC loads it hierarchically, so a session in the
    # heaviest subtree pays every ancestor CLAUDE.md. Surface worst_path when nested files exist (the root row
    # above already covers a single-file repo). Detect-and-REPORT only — NOT wired into the remediation gate.
    _hier = ctx.get("claude_md_hierarchy") or {}
    if _hier.get("total_files", 0) > 1 or _hier.get("worst_path_tokens", 0) > CLAUDE_MD_TOKEN_BUDGET:
        _wt = _hier.get("worst_path_tokens", 0)
        _heavy = _ui.c("  ⚠ heavy", "yellow") if _wt > CLAUDE_MD_TOKEN_BUDGET else ""
        add(f"    {_ui.lbl('CLAUDE.md tree', 14)}"
            + _ui.c(f"≈{_wt} tok · {_hier.get('total_files', 0)} files · a session in {_hier.get('worst_path', '?')} pays this/turn", "dim") + _heavy)
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
        # D3/D11 (v0.1.21): when the index is OVER budget, the index↔file gap is INTENTIONAL (a mature store earns
        # density by NOT indexing everything) — do NOT offer "backfill" (it net-grows under the no-net-grow gate).
        # Under budget, backfill is legit. Only the index_mismatch clause is gate-sensitive; the rest always show.
        _mismatch = (f"{d['index_mismatch']} un-indexed (over budget → INTENTIONAL, do NOT backfill — net-grows)"
                     if ctx["index_lb"][2] > INDEX_TOKEN_BUDGET
                     else f"{d['index_mismatch']} index↔file — offer backfill, confirm first")
        sig.append(_ui.li(f"schema drift: {d['missing_node_type']} missing node_type · {d['malformed_scope']} malformed scope · "
                          f"{d['malformed_origin']} malformed origin · {_mismatch}",
                          bullet="⚠", bullet_color="yellow"))
    if d["advisory_no_scope"] or d["advisory_no_origin"]:
        sig.append(_ui.li(_ui.c(f"backfill (optional, NOT drift): {d['advisory_no_scope']} lack scope · {d['advisory_no_origin']} lack originSessionId", "dim"), bullet="·"))
    if sig:
        add("")
        add(_ui.kv("SIGNALS", _ui.c("detect-and-offer — Phase 0 never mutates a store", "dim")))
        out.extend(sig)

    # ── REMEDIATION (v0.1.18) — only present when the index is OVER budget (the gate) ──
    rem_lines = _remediation_section(ctx.get("remediation") or {})
    if rem_lines:
        add("")
        out.extend(rem_lines)

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
    add(_ui.kv("NEXT", _ui.c(f"run with --seed to start the record (per-pass file) · render_dashboard.py draws the summary · saves a checkpoint at {ctx['head'][:12]}", "dim")))

    print(_ui.ascii_translate("\n".join(out)))


def main() -> int:
    argv = sys.argv[1:]
    audit_before = ""    # v0.1.22: --audit <before-snapshot-path> — capture its path arg so pos doesn't read it as project_dir
    if "--audit" in argv:
        _ai = argv.index("--audit")
        if _ai + 1 < len(argv) and not argv[_ai + 1].startswith("-"):
            audit_before = argv[_ai + 1]
    as_json = "--json" in argv
    pos = [a for a in argv if not a.startswith("-") and a != audit_before]   # positional = the project dir
    project_dir = Path(pos[0]) if pos else Path.cwd()
    ctx = build_context(project_dir)
    if "--triage" in argv:    # v0.1.18: focused read-only remediation view (the SKILL Phase-5 gate reads this)
        _ui.set_modes(color=_ui.color_enabled(argv, sys.stdout), ascii="--ascii" in argv, width=_ui.resolve_width(argv, sys.stdout))
        rem = ctx.get("remediation") or {}
        body = _remediation_section(rem) if rem else [
            _ui.kv("REMEDIATION", _ui.c(f"✓ index under budget ({ctx['index_lb'][2]}/{INDEX_TOKEN_BUDGET} tok) — nothing to remediate", "green"))]
        print(_ui.ascii_translate(_ui.rule() + "\n  " + _ui.c("✦ REMEDIATION TRIAGE · " + ctx["project"], "cyan")
                                  + "\n" + _ui.rule() + "\n\n" + "\n".join(body)))
        return 0
    if "--seed" in argv:    # v0.1.20: write the seed to a per-slug temp path (NOT shared /tmp/cycle.json) + print it
        path = cycle_seed_path(ctx["slug"])
        Path(path).write_text(json.dumps(seed_record(ctx), indent=2) + "\n", encoding="utf-8")
        print(path)
        return 0
    if "--snapshot" in argv:    # v0.1.22: Phase-0 BEFORE audit snapshot → per-slug temp path + print it
        path = audit_snapshot_path(ctx["slug"])
        Path(path).write_text(json.dumps(audit_snapshot(project_dir), indent=2) + "\n", encoding="utf-8")
        print(path)
        return 0
    if "--audit" in argv:       # v0.1.22: Phase-5 diff vs the BEFORE snapshot → append the deterministic log + print summary
        try:
            before = json.loads(Path(audit_before).read_text(encoding="utf-8")) if audit_before else {}
        except (OSError, json.JSONDecodeError):
            before = {}
        diff = audit_diff(before if isinstance(before, dict) else {}, audit_snapshot(project_dir))
        try:                    # the ONLY write in the audit path — an append, mirroring the _persist log pattern
            ctx["auto_mem"].mkdir(parents=True, exist_ok=True)
            with open(ctx["auto_mem"] / ".mutation-log.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"window": "phase0..phase5", **diff}) + "\n")
        except OSError:
            pass
        print(json.dumps(diff, indent=2))
        return 0
    if as_json:
        print(json.dumps(seed_record(ctx), indent=2))
    else:
        _ui.set_modes(color=_ui.color_enabled(argv, sys.stdout), ascii="--ascii" in argv, width=_ui.resolve_width(argv, sys.stdout))
        print_report(ctx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
