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

import difflib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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
    fat_hooks: int         # v0.1.63 (Phase A): pointer lines over HOOK_TOKEN_WARN (hook_stats)
    hook_max_tokens: int   # v0.1.63 (Phase A): the fattest pointer line (est tok)
    cliff_pct: int         # v0.1.63 (Phase A): % of the native 25KB/200-line truncation cliff (exact units)
    ceiling_tokens: int    # v0.1.66 (Phase B): INDEX_CEILING_TOKENS, stored for display (the budget_tokens precedent)


class RecallFacts(TypedDict, total=False):
    before: int
    after: int


class UsageFact(TypedDict, total=False):
    # v0.1.63 (Phase A): one organically-recalled fact this window (extract_signals --recalls).
    name: str
    reads: int
    last: str          # ISO of the newest organic read


class Usage(TypedDict, total=False):
    # v0.1.63 (Phase A): organic fact-body recall telemetry — script-injected by
    # `extract_signals.py --recalls --into <seed>` (Phase 5), never hand-authored. Dream-procedure
    # reads (Phase 1 reads every fact as procedure) are span-excluded. PINNED BIAS: retention +
    # span-exclusion UNDERCOUNT — 0 reads = absence of evidence, never evidence of no use.
    window: str
    transcripts: int
    dream_excluded: int
    reads: int
    facts_read: int
    per_fact: list[UsageFact]
    # v0.1.67 (Phase C): the MISS-DETECTOR — organic reads of ARCHIVED-tier facts (pointer in an
    # archive index, not MEMORY.md; tier judged against the Phase-0 snapshot state when --before is
    # given, so a same-pass archival is never misclassified). A miss = a transcript-visible demotion
    # error; it permanently vetoes the stem from future demotion candidacy (usage_history.miss_stems).
    # Computed from the UNCAPPED scan tally (never derived from the capped per_fact rows).
    archive_reads: int
    misses: list[str]


class Demotion(TypedDict, total=False):
    # v0.1.67 (Phase C): the rank-under-budget demotion triage — script-SEEDED by seed_record from
    # usage_history + demotion_candidates (docs/index-usage-and-budget-ladder.spec.md §Phase C).
    # DORMANT until per-fact evidence accrues (the instrument-before-policy pin, amended to runtime).
    # NO model-tallied disposition counts here: dispositions are entries[] rows (single source — the
    # distill hand-mirror lesson); `verdict` is the ONE model-authored sentence (the distill precedent:
    # "ran and proposed nothing" must be distinguishable from "never ran").
    windows_observed: int   # store-level PROBATIVE usage windows in the log (usage_history windows_full)
    eligible: int           # facts past the per-fact evidence gate (0 while dormant)
    surfaced: list[str]     # bottom-K stems, hook-cost ranked (≤ _DEMOTION_BOTTOM_K)
    struck: list[str]       # script-written by extract_signals.inject_usage: surfaced stems READ this window
    verdict: str            # the one model sentence, filled in Phase 5


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


class Conservation(TypedDict, total=False):
    # v0.1.24: a CLAUDE.md relocate should CONSERVE content — tokens leaving CLAUDE.md land in a relocate target.
    claude_md_drop: int       # net tokens that LEFT the CLAUDE.md hierarchy
    repo_doc_growth: int      # tokens that LANDED in relocate targets (sum of POSITIVE per-op deltas, not netted)
    possible_loss: bool       # a gross drop with little growth ⇒ a likely lost relocate (eviction, not move) — look


class Audit(TypedDict, total=False):
    # v0.1.22: the DETERMINISTIC, script-emitted mutation trail — what this pass ACTUALLY changed (a content-hash
    # snapshot diffed Phase0→Phase5), the counterpart to the model-narrated entries[]. HONEST GAP: the window
    # attributes ANY change in the Phase0→Phase5 span to the dream (an interrupted/concurrent edit mis-attributes).
    memory: AuditStoreDelta
    claude_md: AuditStoreDelta
    repo_doc: AuditStoreDelta      # v0.1.24: relocate-target docs (the conservation other-side of a CLAUDE.md relocate)
    operations: list[AuditOp]
    conservation: Conservation    # v0.1.24: the relocate conservation self-check (possible_loss flag)
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
    held: int                # v0.1.38 (M1): new-global pulls HELD (v0.1.66: would push the index past the HARD CEILING) — shrink to receive
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
    # v0.1.66 (Phase B): the hard ceiling — a SIBLING of `required`, never its replacement. Computed
    # independently (index tokens > INDEX_CEILING_TOKENS); standing-justify does NOT apply to it.
    over_ceiling: bool             # the index exceeds the HARD ceiling — M1 holds all new pulls until it shrinks


class Maintenance(TypedDict, total=False):
    # v0.1.37: the no-op SELF-HEAL pivot signal — surfaced on EVERY pass, load-bearing on magnitude-0. A
    # NON-EMPTY store with `work` true PIVOTS into Phase 1 (--pull) + Phase 5 (health) instead of the
    # Phase-0 no-op stop. Signal-driven: the pivot cue is DATA, not prose (missing prose is what failed).
    dangling: int                    # dangling [[wikilinks]] (len(dangling_links()) — the single-source helper)
    over_budget_not_justified: bool  # = remediation.required (the dual-axis suppression result; NOT a fresh budget compare)
    work: bool                       # any(dangling>0, over_budget_not_justified) — the magnitude-0 pivot trigger
    pivoted: bool                    # Phase 5: the model RAN a maintenance pass (drives the MAINTENANCE outcome banner)


class DreamArc(TypedDict, total=False):
    # v0.1.54: the dream-arc capture — the model MIRRORS its conversational dream blocks here
    # (conversation first, record second: filling this INSTEAD of narrating is a defect). Raw
    # markdown as emitted (`*…*` italic lines; 💤/☀️ only on sleep/wake); render_html strips the
    # wrappers at display time (and tolerates the legacy `> *…*` blockquote form).
    sleep: str               # the falling-asleep stanza (first output on invocation)
    beats: list[str]         # per-phase dream blocks in order (Phase-4 surfacing line included)
    wake: str                # the waking stanza (composed at final record-fill, performed after the render)


class Distill(TypedDict, total=False):
    # v0.1.55: the distill VERDICT capture — the model mirrors the Phase-5 distill outcome here so it
    # survives into the log/dashboard/archive ("ran and correctly proposed nothing" must be
    # distinguishable from "never ran"). The `verdict` is the terminal carrier and ENCODES disposition:
    # `created <X>` · `proposed <X> — awaiting confirmation` · `proposed <X> — declined` ·
    # `nothing: <top candidate> fails <gate leg>`. ONE sentence — both dashboards render it in full.
    # v0.1.58: the COUNTS are script-ONLY, injected by `distill_scan.py --into` (the first production
    # record hand-mirrored an impossible n_recurring=47 against a hard cap of 40); only the judgment
    # fields (proposed/created/verdict) are model-authored (by flag, preferred, or by hand).
    sessions: int            # scan scale, from the scan JSON's scanned.sessions (script-injected)
    commands: int            # scanned.commands (script-injected)
    n_recurring: int         # = len(scan.recurring) — n_ prefix: the scan JSON's `recurring` is a LIST
    n_chains: int            # = len(scan.chains)
    window: str              # v0.1.58: the scan window (`--since` ISO or "(all)") — a record can tell scopes apart
    secrets_omitted: int     # v0.1.58: firewall-flagged commands (samples suppressed) — capture parity with the scan
    proposed: list[str]      # artifacts proposed BY NAME (confirmation usually arrives post-persist)
    created: list[str]       # authored BEFORE --persist only (the rare interactive case)
    verdict: str             # the one-sentence disposition (see above) — REQUIRED for a compliant distill


# v0.1.58: the distill scanner's output caps, MIRRORED (importing distill_scan here would cycle —
# distill_scan imports FROM this module). A smoke pin asserts equality with distill_scan.MAX_RECUR_OUT /
# MAX_CHAIN_OUT, so the mirror cannot drift. Used by validate_cycle_record's impossible-count backstop.
_DISTILL_CAPS = (40, 20)

# v0.1.63 (Phase A): mirrors extract_signals._USAGE_FACT_CAP (the --recalls per_fact emission cap;
# smoke-pinned so the mirror cannot drift) — validate_cycle_record's impossible-count backstop for
# the usage block, same shape as _DISTILL_CAPS above.
# v0.1.67 (Phase C): 20 → 40. The fleet's heaviest-usage node measured 22 distinct facts read in one
# window — above the old cap, so its EVERY window would be cap-truncated and non-probative for
# zero-read evidence, keeping the demotion policy dormant exactly where usage data is richest (a
# spec-gate finding). 40 matches _DISTILL_CAPS[0]'s scale; an upper-bound LOOSENING is additive-safe
# (old ≤20-row records stay valid). Producer + this mirror + the smoke pins move together.
_USAGE_FACT_CAP = 40


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
    maintenance: Maintenance       # v0.1.37: no-op self-heal pivot signal (additive; legacy records render)
    audit: Audit                   # v0.1.22: deterministic script-emitted mutation trail (additive; legacy records render)
    dream: DreamArc                # v0.1.54: dream-arc capture (additive; legacy records render)
    distill: Distill               # v0.1.55: distill-verdict capture (additive; legacy records render)
    usage: Usage                   # v0.1.63 (Phase A): organic recall telemetry (additive; legacy records render)
    demotion: Demotion             # v0.1.67 (Phase C): demotion triage seed + verdict (additive; legacy records render)
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
INDEX_TOKEN_BUDGET = 1500       # auto-memory MEMORY.md index (pointers only). Sized to the ACTIVE
                                # /lesson-bearing set (measured ~1100-1200 tok across real stores) +
                                # ~25% growth headroom — NOT a fraction of native's 25KB (~6400 tok)
                                # HARD-truncation ceiling (that's the failure limit, not a target).
                                # Completion-driven archiving keeps the index = the active set; this
                                # budget is the headroom, and the over-budget gate is a backstop.
CLAUDE_MD_TOKEN_BUDGET = 4000   # repo CLAUDE.md (project conventions, committed)
# ~/.claude/CLAUDE.md — the USER-GLOBAL preamble, loaded in EVERY project, every session.
# Handled DIFFERENTLY from the repo file: measured READ-ONLY for honest always-loaded
# accounting (it taxes every project), but the skill NEVER writes it — it's personal,
# universal config, not a project store. Its own constant so it's tuned independently.
GLOBAL_CLAUDE_MD_TOKEN_BUDGET = 4000

# ── v0.1.63 (Phase A): the HARNESS-NATIVE index truncation cliff + hook telemetry ────────────────
# The REAL failure boundary for the auto-memory index, distinct from the curation target above:
# "The first 200 lines of MEMORY.md, or the first 25KB, whichever comes first, are loaded at the
# start of every conversation. Content beyond that threshold is not loaded."
# (code.claude.com/docs/en/memory, verified 2026-07-04.) Truncation is SILENT — facts past the cap
# simply stop loading — so the Phase-0 report + the dashboard surface proximity
# (`budget.index.cliff_pct`) and go loud at CLIFF_NEAR_FRACTION. Measured in the harness's OWN units
# (real st_size bytes, real lines) — the chars/4 estimator is deliberately not involved. 25KB is
# read as 25×1024; if the harness means 25,000 the shift is <2.5% (immaterial to an 80% alarm).
# Observe-only in Phase A; the budget-ladder semantics that ACT on these are Phase B.
# Full design: docs/index-usage-and-budget-ladder.spec.md.
NATIVE_INDEX_CAP_BYTES = 25 * 1024
NATIVE_INDEX_CAP_LINES = 200
CLIFF_NEAR_FRACTION = 0.8       # ≥ this share of either native cap → red (silent data loss imminent)
HOOK_TOKEN_WARN = 60            # est tok per index POINTER line above which the hook is flagged FAT.
                                # Measured (2026-07-04): fleet median ≈48-57 tok/line, the triage's
                                # lean model 30; the offenders (116/141 tok) were status-content-in-
                                # the-hook — 2 lines = 17% of the whole budget. Detected here (report
                                # + seed, v0.1.63); linted at write time in sync_global (v0.1.66).

# ── v0.1.66 (Phase B): the HARD CEILING — a SECOND, INDEPENDENT signal beside the target ─────────
# NOT a re-key of INDEX_TOKEN_BUDGET or of anything that reads it: the target gate (remediation
# `required`, the triage levers, standing-justify, prune-pressure, the maintenance pivot) is
# UNTOUCHED and still keys to INDEX_TOKEN_BUDGET above. This ceiling drives ONLY the new hard
# mechanisms: the M1 pull-hold + the evict fit-check (sync_global passes it at the call site) and
# the `remediation.over_ceiling` flag the renderers show. It is structurally standing-justify-
# INDEPENDENT — the comparison never reads `standing_justify` (same shape as _would_net_grow) — so
# there is no suppression to tune and no justify escape: over the ceiling, only shrinking satisfies.
# UNIT: one canonical est-token number derived from the BYTE axis of the native cliff (est_tokens ≈
# chars/4 ≈ bytes/4 on the ~ASCII index); the LINE axis (200-line cap) is deliberately NOT folded in
# — every mechanism this keys measures est-tokens, and line-axis proximity is already watched by
# cliff_pct (red at CLIFF_NEAR_FRACTION). A 3-lens spec-review gate (2026-07-04) produced this
# design after the original single-field re-key was found to break triage-at-amber, the maintenance
# pivot, and dream-beta-tester's CHK-REM-SEED-CONTRACT release oracle at once.
# Full design: docs/index-usage-and-budget-ladder.spec.md §Phase B.
INDEX_CEILING_FRACTION = 0.6
INDEX_CEILING_TOKENS = round(INDEX_CEILING_FRACTION * NATIVE_INDEX_CAP_BYTES / 4)   # = 3840 est tok

# The cross-project canonical store (the global tier). ONE named constant (cf. sync_global.GLOBAL)
# so the dangling cross-store resolver, the `global_store_facts` seed, and the network display can't
# drift on the path. READ-only here (it's the replication source); decoupled from this repo (v0.1.52).
GLOBAL_STORE = Path.home() / ".claude" / "memory"

# ── v0.1.67 (Phase C): the demotion rank's evidence-gate constants ────────────────────────────────
# ALL coarse, documented-tunable HINTS (the rigor-bands posture) — uncalibrated BY DESIGN: calibration
# is longitudinal, via the cycle log + the miss loop Phase C itself creates. Do not A/B-sweep them.
# Full design: docs/index-usage-and-budget-ladder.spec.md §Phase C.
_DEMOTION_MIN_WINDOWS = 3     # per-fact zero-read PROBATIVE windows before a fact is even eligible
_DEMOTION_BOTTOM_K = 5        # candidates surfaced per pass (also the validator's impossible-count cap)
_DEMOTION_JUSTIFY_REFIRE = 5  # a per-item counter-justify suppresses until windows_full grows by this
_DEMOTION_SIMILAR = 0.6       # SequenceMatcher ratio ≥ this → the nearest-description merge evidence
_LOG_TAIL_CAP = 500           # iter_cycle_log's Phase-0 tail bound (an append-only log; ~1 line/dream)

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
# is the BINDING primary lever — at real pointer cost (~45-60 tok/fact) the index trips 1500
# tokens at ~25-33 facts, well before this count — so PRUNE_PRESSURE_FACTS is a terse-pointer
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


_POINTER_LINE_RE = re.compile(r"^\s*-\s*\[([^\]]+)\]\(")   # an index pointer: "- [Title](file.md) — hook"


def hook_stats(index_text: str, warn: int = HOOK_TOKEN_WARN) -> tuple[int, int, list]:
    """v0.1.63 (Phase A): per-pointer hook cost over the always-loaded index TEXT →
    (fat_hooks, hook_max_tokens, offenders), offenders = [(est_tokens, title)] for pointer lines over
    `warn`, fattest first. PURE (text in, no I/O — smoke-pinned). Only `- [Title](file.md) — hook`
    pointer lines are measured: they are the per-session recall cues the budget pays for; headers and
    prose aren't cues. Detection only — nothing here trims (the write-time lint is Phase B)."""
    offenders: list = []
    hook_max = 0
    for ln in index_text.splitlines():
        m = _POINTER_LINE_RE.match(ln)
        if not m:
            continue
        t = est_tokens(ln)
        hook_max = max(hook_max, t)
        if t > warn:
            offenders.append((t, m.group(1)))
    offenders.sort(key=lambda o: -o[0])
    return len(offenders), hook_max, offenders


def cliff_pct(index_bytes: int, index_lines: int) -> int:
    """v0.1.63 (Phase A): proximity to the harness-native index truncation cliff as a percent — the
    BINDING axis wins: max(bytes/25KB, lines/200). PURE; exact units by design (see the constants
    block: the cliff is the harness's cap, so it's measured in the harness's units, never
    est_tokens)."""
    return round(100 * max(index_bytes / NATIVE_INDEX_CAP_BYTES, index_lines / NATIVE_INDEX_CAP_LINES))


# A `±HHMM` offset (no colon — what `date -u +%z` prints) → `±HH:MM`, which `fromisoformat` requires on
# Python 3.8–3.10 (3.11 relaxed it). Anchored to the END so it can't touch the date's own `-`/`:`.
_OFFSET_NOCOLON = re.compile(r"([+-]\d{2})(\d{2})$")


def _parse_ts(ts: str) -> "datetime | None":
    """A transcript/marker/`--since` timestamp string → an AWARE UTC datetime, or None if empty/unparseable.
    THE single timestamp parser for the pipeline. v0.1.67 (Phase C): RELOCATED here from extract_signals
    (unchanged — smoke pins identity across all three modules) because usage_history/demotion_candidates
    need it and extract_signals imports FROM this module — reusing it in place would be a circular import,
    and a second local parser is the documented already-bitten divergence class (a distill-local copy once
    diverged on a no-colon offset, so the file-prune no-op'd while the per-line filter worked).
    extract_signals re-imports it (distill_scan's `from extract_signals import _parse_ts` still resolves).
    Normalizes a bare `Z` (3.10 rejects it) and a `±HHMM` no-colon offset; a NAIVE stamp is assumed UTC
    (CC emits `…Z`); an offset stamp is converted to its true UTC INSTANT."""
    if not ts:
        return None
    s = _OFFSET_NOCOLON.sub(r"\1:\2", ts.replace("Z", "+00:00"))
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
    """cwd → Claude's project slug: the absolute path with EVERY non-alphanumeric char replaced by '-'
    (case PRESERVED, no dash-collapsing) — Claude Code's slug rule.

    e.g. /home/you/project/Doc_Flo -> -home-you-project-Doc-Flo · /home/you/.config/app -> -home-you--config-app.
    VERIFIED on disk for '/', '_', and '.' (a CC-created session under /home/you/.claude/… slugs to
    `-home-you--claude-…` — the '/' AND the '.' both map to '-', giving the '--'); GENERALIZED to all
    non-alphanumerics — strictly safer than a per-char list and regression-IDENTICAL for the fleet (paths
    with only '/ _ -'). v0.1.40 (audit M3): the prior `[/_]`-only rule left a '.'-segment project (a dotfile
    dir like ~/.claude) SPLIT-BRAIN — two stores, neither recalling the other. `near_duplicate_slugs` uses
    the SAME generalization so it can still detect such a twin."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(project_dir.resolve()))


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


def valid_link_targets(auto_mem: Path) -> set:
    """v0.1.23 (D10): every valid `[[wikilink]]` target stem in a store — ALL `*.md` (fact files, archive-index
    docs like SHIPPED.md, AND MEMORY.md → stem 'MEMORY'). A `[[SHIPPED]]` / `[[MEMORY]]` ref is a REAL target,
    not a dangling link; the Phase-5 dangling check must resolve against THIS set (not fact-stems alone) or it
    false-flags archive/index refs (the D10 false-positive class). READ-ONLY."""
    return {f.stem for f in auto_mem.glob("*.md")} if auto_mem.exists() else set()


def extract_wikilinks(text: str) -> list[str]:
    """Every `[[target]]` in `text`, code spans stripped FIRST — fenced (```...```) THEN inline (`...`) — so a
    `[[x]]` inside a code block (e.g. TOML `[[tool.mypy.overrides]]`) is NOT counted. The SINGLE `[[...]]`
    extractor: `dangling_links` AND sync_global's evict inbound-link scan both call THIS (a 4th wikilink regex
    is the reimplementation-drift the v0.1.40 slug-agreement guard exists to prevent). Targets are `.strip()`ed."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)   # fenced code blocks
    text = re.sub(r"`[^`]*`", "", text)                       # inline code spans
    return [m.strip() for m in re.findall(r"\[\[([^\]]+)\]\]", text)]


def dangling_links(auto_mem: Path, global_dir: Path | None = None) -> list[str]:
    """v0.1.37 (+v0.1.52 cross-store): the SINGLE-SOURCE dangling-[[wikilink]] list for a store — every
    `[[target]]` in a fact body resolving to NO valid target (resolve_wikilink against valid_link_targets),
    code spans stripped first — fenced (```...```) AND inline (`...`) — so a `[[x]]` inside a code block
    (e.g. TOML `[[tool.mypy.overrides]]`) is NOT a wikilink. (A 4-space-indented code block is a known minor
    gap → at worst a spurious-but-safe maintenance cue, never a wrong write.)
    v0.1.52: resolution spans local ∪ `global_dir` (the canonical store) when given — a `[[target]]` that is
    a real global fact pending mirror (a budget-HELD up-link) is PENDING-PULL, not dangling (the M1 `held`
    count already signals it); a target absent from BOTH stays flagged (a real typo, OR a sibling-project-
    local DOWN-link genuinely unreachable here — recall is slug-scoped, so the global canonical is the only
    OTHER store this node can pull from; NOT fleet-wide). `global_dir=None`/missing ⇒ legacy local-only.
    Phase-0 maintenance, the Phase-5 health fill, and the smoke test all call THIS, so the dangling count
    can't drift between them (the drift class the cycle-record contract exists to prevent). READ-ONLY."""
    if not auto_mem.exists():
        return []
    targets = valid_link_targets(auto_mem)
    if global_dir is not None:
        targets = targets | valid_link_targets(global_dir)   # cross-store: a pending-pull up-link ≠ dangling
    out: set[str] = set()
    for f in auto_mem.glob("*.md"):
        if f.name == "MEMORY.md":              # the index holds pointer links, not [[wikilinks]]
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in extract_wikilinks(body):
            if name in targets or resolve_wikilink(name, targets):
                continue
            out.add(name)
    return sorted(out)


# ── the secrets firewall (v0.1.70: RELOCATED here from extract_signals.py, the dependency
# root — mirrors the _is_mirror/_frontmatter precedent) ─────────────────────────────────
# extract_signals.py imports these three names from here; distill_scan.py and tests/smoke.py
# import/access them transitively through extract_signals' namespace — a smoke pin asserts
# single-sourcing (`es._looks_secret is ms._looks_secret`), matching the existing _is_mirror pin.
#
# Credential-shaped values. Detection is SPLIT in two because the generic high-entropy
# check needs CASE discrimination (mixed-case is the signal that separates a token from
# a file path / slug) and the keyword/vendor arms want case-INSENSITIVITY — and one
# regex can't be both. Use `_looks_secret()` (below) as the firewall, never `_SECRET`
# directly. Contract: drop-to-label, never surface the verbatim secret.
#
# _SECRET (case-insensitive): keyword=value in any serialization (incl. compound names
# AWS_SECRET_ACCESS_KEY= and quoted JSON "password": "..."), plus high-precision vendor /
# protocol shapes that carry no high-entropy blob.
_SECRET = re.compile(
    r"""(
        (?:[A-Za-z0-9]{1,40}[_.\-]){0,8}(?:li_at|cf_clearance|password|passwd|pwd|pass(?:phrase)?|cred(?:ential)?s?|api[_-]?key|access[_-]?key|private[_-]?key|secret|token|bearer|authorization)(?:[_.\-][A-Za-z0-9]{1,40}){0,8}["']?\s*[:=]\s*["']?(?=\S{8,}|(?=\S{4,})\S*\d)\S+
                                                                     # keyword as a full SEGMENT of a compound id, with
                                                                     # optional quotes/brackets around the delimiter so
                                                                     # JSON {"password": "..."} / dict / YAML all match.
                                                                     # v0.1.70 SECURITY: BOTH dimensions bounded now —
                                                                     # the repetition count ({0,8}, was an unbounded `*`)
                                                                     # AND each segment's own length ({1,40}, was an
                                                                     # unbounded `+`). Bounding only the repetition count
                                                                     # is NOT sufficient: on a payload with no separator
                                                                     # char anywhere (e.g. a long plain-letter run, or a
                                                                     # keyword immediately preceded by one), a single
                                                                     # `[A-Za-z0-9]+` repetition attempt greedily consumes
                                                                     # to the end of the alnum run, then backtracks
                                                                     # character-by-character looking for a separator —
                                                                     # an O(remaining-length) sweep repeated at EVERY
                                                                     # starting position, i.e. still O(n²) overall
                                                                     # (measured: 0.03s/0.11s/0.45s/1.79s/7.15s at
                                                                     # n=2000/4000/8000/16000/32000 with the count-only
                                                                     # bound — unchanged from the ORIGINAL unbounded
                                                                     # form). Capping the inner segment to 40 chars
                                                                     # (generous — AWS_SECRET_ACCESS_KEY's segments are
                                                                     # ≤19) bounds that sweep to a constant, restoring
                                                                     # true linear scaling (verified to ≥256000 chars
                                                                     # across dotted, separator-free, and mixed shapes).
                                                                     # v0.1.70 Gate-2a: the value clause is now gated
                                                                     # (a lookahead requiring EITHER 8+ non-whitespace
                                                                     # chars OR a 4+-char run containing a digit) — bare
                                                                     # `\S+` matched ANY value including ordinary short
                                                                     # words in "keyword: value" conventional-commit
                                                                     # prose ("token: bump TTL to 3600", "pass: 5 fail:
                                                                     # 0"), which this firewall now also gates commit
                                                                     # subjects against (v0.1.70's _scrub_commit_log).
      | --?(?:li_at|cf_clearance|password|passwd|pwd|pass(?:phrase)?|cred(?:ential)?s?|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)\b[= ](?=\S{8,}|(?=\S{4,})\S*\d)\S{4,}
                                                                     # v0.1.70: a CLI-FLAG-shaped keyword (a leading
                                                                     # `-`/`--` is the signal — ordinary prose essentially
                                                                     # never spells "-password") followed by `=` or a
                                                                     # single space then a value, so `--password hunter2`
                                                                     # / `--password=hunter2` are caught (whitespace-only
                                                                     # delimited, not just `[:=]`). Deliberately NOT a
                                                                     # generic concatenated short flag like `-p<value>`
                                                                     # (collides with common non-secret flags —
                                                                     # `docker run -p8080:80`, `tar -pxvf`) — considered
                                                                     # and rejected for false-positive risk. v0.1.70
                                                                     # Gate-2a: (a) the keyword list now matches the
                                                                     # main arm's — it omitted li_at/cf_clearance/
                                                                     # cred(?:ential)?s? entirely, so `--li_at <token>`
                                                                     # evaded the firewall even though `--li_at=<token>`
                                                                     # was caught by the main arm; (b) the SAME
                                                                     # length-or-digit value gate as the main arm — bare
                                                                     # `\S{4,}` matched ANY 4+-char word, so
                                                                     # "--secret flag to enable debug logging" flagged
                                                                     # the ordinary word "flag" as a credential.
      | (?:authorization|bearer)\b["']?\s{0,20}:?\s{0,20}(?:bearer\s+)?[A-Za-z0-9._~+/=-]{16,}  # auth header / bearer
                                                                     # token. v0.1.70 Gate-2a: a 4TH ReDoS instance in
                                                                     # this same regex, missed by the first pass — the
                                                                     # `\s*:?\s*` sandwich is two adjacent unbounded
                                                                     # same-charset quantifiers separated by an optional
                                                                     # token (the classic ambiguous-split shape); measured
                                                                     # 0.06s/0.23s/0.94s/3.76s at n=2000/4000/8000/16000
                                                                     # (clean O(n²)) on "authorization"+padding spaces.
                                                                     # Bounded to {0,20} each (generous past any real
                                                                     # header whitespace) restores linear scaling.
      | [a-z][a-z0-9+.\-]{0,20}://[^\s/:@]+:[^\s/@]+@                 # scheme://user:pass@host URI creds
                                                                     # v0.1.70 SECURITY: bounded (was an unbounded
                                                                     # `*`) — a SECOND, independently-discovered
                                                                     # instance of the same O(n²) ReDoS class the
                                                                     # pentest flagged on the keyword arm (measured
                                                                     # ~identical quadratic scaling in isolation);
                                                                     # 20 chars covers every real URI scheme name
                                                                     # with generous headroom (longest common ones,
                                                                     # e.g. "mongodb+srv", are under 12)
      | (?:AKIA|ASIA)[0-9A-Z]{16}                                    # AWS access key id
      | xox[baprs]-[0-9A-Za-z-]{10,}                                 # Slack token
      | sk-(?:proj-)?[A-Za-z0-9_-]{20,}                              # OpenAI key
      | (?:sk|rk|pk)_(?:live|test)_[0-9A-Za-z]{10,}                  # Stripe key
      | whsec_[0-9a-fA-F]{16,}                                       # Stripe webhook signing secret (v0.1.70)
      | gh[pousr]_[0-9A-Za-z]{20,}                                   # GitHub token
      | AIza[0-9A-Za-z_-]{35}                                        # Google API key
      | AC[0-9a-f]{32}                                               # Twilio account SID
      | eyJ[A-Za-z0-9_-]{8,2000}\.[A-Za-z0-9_-]{8,4000}\.[A-Za-z0-9_-]{6,200}  # JWT (header.payload.sig)
                                                                     # v0.1.70 SECURITY: each segment's unbounded `{n,}`
                                                                     # is now `{n,MAX}` — the charset a JWT segment
                                                                     # matches (`[A-Za-z0-9_-]`) includes the literal
                                                                     # anchor's OWN chars ('e','y','J'), so a repeated
                                                                     # `eyJeyJeyJ...` payload (no periods) makes each
                                                                     # occurrence's backtrack sweep run to the end of
                                                                     # the string — O(n²) over many repeats (measured
                                                                     # 0.001s/0.02s/0.33s at n=2000/8000/32000, ~16x per
                                                                     # 4x length). The caps are generous past any real
                                                                     # JWT (a payload of thousands of claims) and restore
                                                                     # linear scaling (verified to 128000 chars).
      | -----BEGIN[ A-Z]*PRIVATE[ ]KEY-----                          # PEM private key
    )""",
    re.I | re.X,
)

# A contiguous run of base64-ish chars (incl. '/' and '+' so slash-bearing AWS secret
# access keys are caught). Case-SENSITIVE on purpose (see _entropy_blob).
_BLOB = re.compile(r"[A-Za-z0-9+/=_-]{40,}")
_ENTROPY_SEG_FLOOR = 8   # v0.1.70: minimum PER-SEGMENT length before judging mixed-case/digit (below this,
                         # a real path component too often coincidentally looks token-like — e.g. "User1")
_COMMIT_SUBJECT_CAP = 4000   # v0.1.70 Gate-2a: bounds _scrub_commit_log's firewall call — git enforces no
                             # length limit on a commit subject; mirrors extract_signals.py's _PROBE_CAP.


def _entropy_blob(text: str) -> bool:
    """True if `text` holds a keyword-less high-entropy token (e.g. a bare AWS secret key
    or base64 blob). Distinguishes a token from a FILE PATH or SLUG without case folding:
    a token is mixed-case or carries digits; a path is slash-dense; a slug is all-lower
    with no digits. This is the half the case-insensitive `_SECRET` regex cannot express.

    Both signals — mixed-case and digit-bearing — are judged per '/','-','_','.' -delimited
    TOKEN (finer than a '/'-only split) at/past a length floor. Per-token scoping is what
    keeps a real path clean: a path component is overwhelmingly single-cased on its own
    (kebab/snake, or a single ALL-CAPS filename stem like "SKILL"/"README"), so requiring
    the mix *within one token* — not across the whole blob — excludes the ordinary case
    "plugins/.../SKILL" (one all-lower run next to one all-upper run, neither internally
    mixed) while still catching a genuinely random-looking token like "AbCdEf" or a
    lowercase hex/base64 run with digits. The floor also stops a natural kebab-case
    segment with a short version/date suffix ("v0-1-68", "module2024") from tripping the
    digit check — no sub-token there is both ≥8 chars and digit-bearing.

    v0.1.70 Gate-2a round 3 found the WHOLE-BLOB mixed-case variant of this check (added in
    round 2 to catch a synthetic two-segment case where each segment was internally
    single-cased but the two disagreed) is a worse trade than the FP it was chasing: it
    flags this repo's own everyday path shape (any '/'-path ending in an ALL-CAPS filename
    stem like SKILL.md/README.md/CLAUDE.md, once long enough to clear the blob floor) as a
    secret. Reverted to per-token scoping; the synthetic cross-segment case it caught is
    accepted as a known, narrow residual gap (not a realistic secret shape) rather than
    chased with more heuristics — see the accepted-gap test in tests/smoke.py.

    A short, no-digit, single-case value (a weak password like "qwerty" or "letmein") is
    ALSO a known, accepted gap on the keyword side (see the value-gating lookahead in
    `_SECRET`) — no length/digit threshold separates a weak password from an ordinary
    short English word ("flag", "usage") in the same position, so tightening one re-opens
    the other. This is a real tradeoff, not a bug to keep tuning; the firewall favors
    fewer false positives on ordinary commit prose over catching every possible weak,
    keyword-adjacent password. Widening it is a product decision, not a fix."""
    for m in _BLOB.finditer(text):
        s = m.group(0)
        for seg in re.split(r"[/\-_.]", s):
            if len(seg) < _ENTROPY_SEG_FLOOR:
                continue
            has_lower = any(c.islower() for c in seg)
            has_upper = any(c.isupper() for c in seg)
            if (has_lower and has_upper) or any(c.isdigit() for c in seg):
                return True
    return False


def _looks_secret(text: str) -> bool:
    """The firewall: True if `text` contains a credential-shaped value (keyword/vendor
    arms OR a high-entropy blob). Use THIS everywhere, not `_SECRET` directly."""
    return bool(_SECRET.search(text)) or _entropy_blob(text)


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
    def norm(s: str) -> str:                          # v0.1.40 (M3): match slug_for's generalization (ALL
        return re.sub(r"[^a-z0-9]", "-", s.lower())   # non-alnum → '-'), so a '.'/space twin is caught, not just '_'/case
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
_KEEP_RE = re.compile(r"(?i)\b(?:never|don['’]?t|do not|avoid|gotcha|footgun|always|must|shall|prefer|should|shouldn['’]?t|cannot|can['’]?t|won['’]?t|caveat)\b")  # lesson/negative/directive → VETO archive_candidates (a dated-but-live lesson STAYS); scanned over the WHOLE body, false-negative bias (over-veto is the safe direction)
_OVERSIZED_TOK = 2500          # a body this big is a dump/research-note → a (ranking) content-review candidate
_MIRROR_DOMINATED = 0.5        # mirror share of the index above which the lever is GC, not a futile local prune
_LEAN_HOOK_TOK = 30            # est tokens/pointer for a lean re-index of the keep core (the projected_index target)
_STANDING_JUSTIFY_DELTA = 10   # v0.1.21: a standing-justified over-budget gate re-FIRES once the store grows by this
                               # many facts past the justified baseline (the delta-detector) — keeps the v0.1.18 teeth
_STANDING_JUSTIFY_TOKEN_FACTOR = 1.25   # v0.1.23 (D6): ALSO re-fire when index tokens exceed the justified baseline
                                        # tokens × this — token bloat with flat fact-count was a blind spot; re-index
                                        # noise on a flat store is ~0%, real growth ~15-20%, so 1.25 is above noise


def _standing_baseline(sj: object) -> int | None:
    """v0.1.21 (D7): the justified fact-count baseline from a marker's `standing_justify`, or None. FAILS OPEN —
    a malformed/absent value (legacy marker, non-dict, non-int `facts`) returns None ⇒ the gate FIRES (never
    suppress on garbage; suppression is the dangerous direction). Pairs with _STANDING_JUSTIFY_DELTA."""
    if isinstance(sj, dict) and isinstance(sj.get("facts"), int):
        return sj["facts"]
    return None


def _standing_baseline_tokens(sj: object) -> int | None:
    """v0.1.23 (D6): the justified index-TOKEN baseline from a marker's `standing_justify`, or None. FAILS OPEN
    exactly like _standing_baseline — a malformed/absent `index_tokens` returns None ⇒ the token axis can't be
    proven safe ⇒ the gate FIRES (suppression is the dangerous direction). The v0.1.21 SKILL standing_justify
    write persists `index_tokens` (landed with the feature in c3e3ec7), so a real marker always carries it."""
    if isinstance(sj, dict) and isinstance(sj.get("index_tokens"), int):
        return sj["index_tokens"]
    return None


def _is_archive_index_text(text: str) -> bool:
    """v0.1.67 (Phase C): the archive-index rule on TEXT — split out of _is_archive_index so the
    miss-detector can classify tier from a Phase-0 --snapshot's stored CONTENT (the window-start state)
    with the SAME rule the path classifier uses (single source; the two cannot drift)."""
    if text.lstrip("﻿").lstrip().startswith("---"):   # fact frontmatter (BOM-tolerant, cf _frontmatter) → not an archive
        return False
    return len(_LINK_RE.findall(text)) >= 3          # link-list with no frontmatter → archive index


def _is_archive_index(path: Path) -> bool:
    """True if a store `*.md` is an ARCHIVE INDEX (a link-list like MEMORY.md / SHIPPED.md), NOT a fact.
    A fact begins with `---` frontmatter; an archive index does not and is mostly `](x.md)` links. v0.1.18.x
    (beta finding C1): the triage globs every `*.md` as a fact, so a relocated archive (`SHIPPED.md`, whose
    stem matches the tracker regex) lands in B → "evict" → nuking the archive. Excluding archive docs from
    fact_files prevents that, and lets their link-targets count as reference surfaces. Cheap: the 64-byte head
    short-circuits the common (fact-with-frontmatter) case before reading the whole file; the rule itself
    lives in _is_archive_index_text (v0.1.67 — shared with snapshot-content tiering)."""
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            head = fh.read(64)
            if head.lstrip("﻿").lstrip().startswith("---"):   # short-circuit before reading the whole file
                return False
            rest = head + fh.read()
    except OSError:
        return False
    return _is_archive_index_text(rest)


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


def archive_candidates(fact_files: list, index_names: set) -> list:
    """PURE, budget-INDEPENDENT: surface INDEXED, non-mirror facts that read as COMPLETED arcs — a
    dated stem (`_DATED_RE` — the Auto-Dream/CM `_YYYY_MM_DD` completed-arc convention) and carry NO
    keep-signal. These are candidates to relocate from the always-loaded index to the on-demand
    archive PROACTIVELY, every dream (the completion-driven decoupling), NOT only when over budget.

    CONSERVATIVE: a keep-signal (`_KEEP_RE`: lesson / negative / directive) VETOES the candidate — a
    dated-but-live lesson STAYS (the silent-failure guard). But the KEEP list is SUFFICIENT-NOT-
    NECESSARY (a marker-less live lesson can slip through), so this RANKS only — the model judges
    content + the user confirms (no relocate path here, like remediation_triage / schema_drift).
    Only INDEXED pointers cost always-loaded budget, so an unindexed completed fact is not a
    candidate. Never raises (OSError → skip)."""
    out: list = []
    for f in fact_files:
        if f.stem not in index_names:          # only an indexed pointer taxes the always-loaded tier
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _is_mirror(text):                   # a cross-project mirror is GC's domain, not an archive candidate
            continue
        if not _DATED_RE.search(f.stem):       # the completed-arc convention; a non-dated completed arc is
            continue                           # left to the model's Phase-5 judgment (helper stays high-precision)
        body = text[1:] if text.startswith("﻿") else text
        fm = re.search(r"^---\n(.*?)\n---", body, re.S)    # VETO on the CURATED frontmatter (description), NOT the
        if _KEEP_RE.search(fm.group(1) if fm else body):  # analysis BODY: a whole-body scan vetoes completed scope-docs
            continue                                       # (their analysis says "never"/"must" too → recall collapsed to
                                                           # ~0, MEASURED). A dated fact whose lesson-nature is ONLY in the
                                                           # body (not its description) relies on the model's Phase-5
                                                           # judgment (propose-then-apply) — the helper RANKS, the model decides.
        out.append({"stem": f.stem, "body_tokens": est_tokens(text), "reason": "dated (completed-arc convention)"})
    out.sort(key=lambda c: -c["body_tokens"])
    return out


def defrag_candidates(fact_files: list, index_names: set, *, factor: float = 2.5) -> list:
    """PURE, budget-INDEPENDENT: surface INDEXED, non-mirror, NON-dated (active) facts whose BODY is a
    SIZE outlier — `body_tokens` > `factor` × the MEDIAN body_tokens over that SAME population (indexed,
    non-mirror, non-dated — self-consistent/reproducible). These are bloated ACTIVE files (a roadmap/
    status doc accreting completed/stale items) → candidates for BODY-defragmentation (curate the body
    in place; the index pointer STAYS), DISTINCT from archive_candidates (whole DATED completed facts →
    pointer-archive; disjoint by the dated-stem gate). A body-SIZE outlier is a structural signal — the
    helper RANKS; the model curates by CONTENT + the user confirms (no write path here). Edge guards:
    returns [] when the population has <3 facts or a degenerate (all-equal / non-positive) median — no
    div-by-zero, no noise on a tiny/uniform store. Never raises (OSError → skip)."""
    pop: list = []                                  # (stem, body_tokens) over indexed, non-mirror, non-dated
    for f in fact_files:
        if f.stem not in index_names or _DATED_RE.search(f.stem):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _is_mirror(text):
            continue
        pop.append((f.stem, est_tokens(text)))
    if len(pop) < 3:                                # too few to define an outlier
        return []
    sizes = sorted(t for _, t in pop)
    n = len(sizes)
    med = sizes[n // 2] if n % 2 else (sizes[n // 2 - 1] + sizes[n // 2]) / 2
    if med <= 0 or sizes[0] == sizes[-1]:           # degenerate / all-equal → no meaningful outlier
        return []
    out = [{"stem": s, "body_tokens": t, "ratio": round(t / med, 1)} for s, t in pop if t > factor * med]
    out.sort(key=lambda c: -c["body_tokens"])
    return out


def iter_cycle_log(log: Path, tail: "int | None" = None) -> list:
    """v0.1.67 (Phase C): THE shared `.consolidation-log.jsonl` reader — parsed JSON values in file order,
    malformed/blank lines skipped, never raises (a corrupt log must not break a dream OR a dashboard).
    `tail=N` bounds the read to the last N lines (the Phase-0 path passes _LOG_TAIL_CAP; render surfaces
    pass None = all, so their output is unchanged). Exists so usage_history does NOT become the second
    independent log line-parser beside render_html.read_history — that reader now delegates here (the
    single-source rule; a smoke pin guards the delegation)."""
    if not log.exists():
        return []
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if tail is not None:
        lines = lines[-tail:]
    out: list = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def usage_history(auto_mem: Path) -> dict:
    """v0.1.67 (Phase C): aggregate the per-window script-truth `usage` blocks accrued in the cycle log →
    {"windows_full": int, "window_starts": list[float], "per_fact": {stem: {"reads", "last"}},
    "miss_stems": list[str]}. READ-ONLY; guarded everywhere (malformed blocks skipped).

    TWO deliberately different inclusion rules (a spec-gate finding — the draft used one and was
    anti-conservative): per-fact READS merge from EVERY usage block — full, cap-truncated, or empty —
    because positive read evidence must never be discarded (any recorded read vetoes demotion candidacy);
    but a window is PROBATIVE for zero-read evidence only iff transcripts ≥ 1 (an empty window observed
    nothing), facts_read == len(per_fact) (a cap-truncated window cannot prove any fact unread), AND its
    window since-side parses via _parse_ts (an unplaceable window — including every store's FIRST, whose
    literal since is "(no marker — all transcripts)" — is skipped for evidence, never fatal: the draft's
    global span anchor latched dead on it forever). `window_starts` carries the probative windows' epoch
    starts for demotion_candidates' per-fact counting. `miss_stems` unions every logged usage.misses —
    a caught miss persists here even after the transcript that revealed it rotates away. `last` merges by
    parsed-epoch max (lexicographic only as the unparseable fallback)."""
    windows_full = 0
    window_starts: list = []
    acc: dict = {}       # stem -> {"reads": int, "last": iso, "_ep": float|None}
    misses: set = set()
    for rec in iter_cycle_log(auto_mem / ".consolidation-log.jsonl", tail=_LOG_TAIL_CAP):
        u = rec.get("usage") if isinstance(rec, dict) else None
        if not isinstance(u, dict):
            continue
        pf = u.get("per_fact")
        pf = pf if isinstance(pf, list) else []
        for row in pf:                                   # reads merge from EVERY block (see docstring)
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "") or "")
            if not name:
                continue
            a = acc.setdefault(name, {"reads": 0, "last": "", "_ep": None})
            a["reads"] += max(0, _pi_int(row.get("reads")))
            ts = str(row.get("last", "") or "")
            dt = _parse_ts(ts)
            if dt is not None and (a["_ep"] is None or dt.timestamp() > a["_ep"]):
                a["_ep"], a["last"] = dt.timestamp(), ts
            elif dt is None and a["_ep"] is None and ts > a["last"]:
                a["last"] = ts                           # both unparseable → lexicographic fallback
        m = u.get("misses")
        for stem in (m if isinstance(m, list) else []):
            if isinstance(stem, str) and stem:
                misses.add(stem)
        if _pi_int(u.get("transcripts")) < 1 or _pi_int(u.get("facts_read")) != len(pf):
            continue                                     # non-probative: observed nothing / cap-truncated
        start = _parse_ts(str(u.get("window", "") or "").split("..", 1)[0])
        if start is None:
            continue                                     # unplaceable window — skip for evidence, not fatal
        windows_full += 1
        window_starts.append(start.timestamp())
    per_fact = {k: {"reads": v["reads"], "last": v["last"]} for k, v in acc.items()}
    return {"windows_full": windows_full, "window_starts": window_starts,
            "per_fact": per_fact, "miss_stems": sorted(misses)}


def _demotion_justify(dj: object) -> dict:
    """v0.1.67 (Phase C): the per-item counter-justify map from a marker's `demotion_justify` state →
    {stem: windows_at_justify}. WELL-FORMED entries only — a malformed entry (non-dict, non-int windows,
    bool) is DROPPED, i.e. does NOT suppress: the SAME fail direction as _standing_baseline (malformed ⇒
    the gate fires / the candidate surfaces — err toward the human seeing it; here the output is
    report-only, so surfacing is the safe direction)."""
    out: dict = {}
    if isinstance(dj, dict):
        for k, v in dj.items():
            if (isinstance(k, str) and isinstance(v, dict)
                    and isinstance(v.get("windows"), int) and not isinstance(v.get("windows"), bool)):
                out[k] = v["windows"]
    return out


def demotion_candidates(fact_files: list, index_names: set, hist: Mapping[str, Any],
                        index_text: str, justify: "Mapping[str, int] | None" = None) -> dict:
    """v0.1.67 (Phase C): the rank-under-budget demotion triage — the `*_candidates` family contract:
    PURE(ish — reads the given fact files), RANKS only, the model judges content + the user confirms;
    NO write path. docs/index-usage-and-budget-ladder.spec.md §Phase C2.

    Evidence is counted PER FACT: a fact's zero-read windows = the probative windows (hist.window_starts)
    whose epoch start ≥ the fact's st_mtime — the fact, in its current form, existed through the whole
    window; an edit resets mtime and restarts its clock (undercounts eligibility — the safe direction).
    ELIGIBLE iff: ≥ _DEMOTION_MIN_WINDOWS such windows · indexed (only an indexed pointer taxes the
    always-loaded tier) · not a mirror (GC's domain) · 0 merged reads EVER (truncated windows included —
    any recorded read vetoes) · no _KEEP_RE signal in the frontmatter description (a lesson STAYS; the
    rank finds dead reference/status weight — sufficient-not-necessary, the archive_candidates caveat) ·
    not in miss_stems (a fact once read from the archive proved live — scarred, never re-surfaced) · not
    suppressed by a live per-item counter-justify (re-fires at +_DEMOTION_JUSTIFY_REFIRE windows).

    Ranked by hook_tokens desc (the measurable always-loaded relief a demotion frees — the
    remediation_triage sort-by-cost shape), capped at _DEMOTION_BOTTOM_K. Deliberately NOT an ACT-R
    activation fit: eligibility is a binary evidence gate; fitted decay constants would be uncalibratable
    fake-empirics today (the rigor-bands posture). Veto TALLIES return so the report can show what the
    gate withheld — information for the human, without becoming policy. Surfaced candidates carry
    `indegree` (wikilink in-degree — safe for archive-demotion, load-bearing for a merge) and
    `similar`/`ratio` (nearest same-population description, SequenceMatcher autojunk=False over the
    canonically-sorted pair — deterministic; a spec-gate finding on the default autojunk)."""
    justify = justify or {}
    wf = _pi_int(hist.get("windows_full"))
    out: dict = {"windows_full": wf, "eligible": 0, "candidates": [],
                 "vetoed_read": 0, "vetoed_keep": 0, "vetoed_justified": 0, "vetoed_missed": 0}
    if wf < _DEMOTION_MIN_WINDOWS:
        return out                                       # DORMANT — no fact can out-count the store
    starts = [s for s in (hist.get("window_starts") or []) if isinstance(s, (int, float))]
    pf_raw = hist.get("per_fact")                        # assign-then-narrow (the module's mypy idiom)
    pf = pf_raw if isinstance(pf_raw, dict) else {}
    miss_stems = set(hist.get("miss_stems") or [])
    bodies: dict = {}
    mtimes: dict = {}
    for f in fact_files:
        try:
            bodies[f.stem] = f.read_text(encoding="utf-8", errors="replace")
            mtimes[f.stem] = f.stat().st_mtime
        except OSError:
            continue
    # The candidate POPULATION: indexed, non-mirror facts (the tier the budget pays for; mirrors are C4's).
    pop = {s for s in bodies if s in index_names and not _is_mirror(bodies[s])}
    descs = {s: _frontmatter(bodies[s]).get("description", "") for s in pop}
    eligible: list = []
    for stem in sorted(pop):
        row_raw = pf.get(stem)                           # assign-then-narrow (the module's mypy idiom)
        row = row_raw if isinstance(row_raw, dict) else {}
        if _pi_int(row.get("reads")) > 0:
            out["vetoed_read"] += 1                      # any recorded read, ever → never a candidate
            continue
        zrw = sum(1 for s in starts if s >= mtimes[stem])
        if zrw < _DEMOTION_MIN_WINDOWS:
            continue                                     # insufficient evidence YET — not a veto
        if stem in miss_stems:
            out["vetoed_missed"] += 1                    # proved live from the archive once — scarred
            continue
        jw = justify.get(stem)
        if isinstance(jw, int) and not isinstance(jw, bool) and jw + _DEMOTION_JUSTIFY_REFIRE > wf:
            out["vetoed_justified"] += 1                 # counter-justified; re-fires on +REFIRE windows
            continue
        if _KEEP_RE.search(descs[stem]):
            out["vetoed_keep"] += 1                      # lesson/negative/directive — stays, by design
            continue
        hook = next((est_tokens(ln) for ln in index_text.splitlines() if f"]({stem}.md)" in ln), 0)
        eligible.append({"stem": stem, "hook_tokens": hook, "zero_read_windows": zrw})
    out["eligible"] = len(eligible)
    eligible.sort(key=lambda c: (-c["hook_tokens"], c["stem"]))
    surfaced = eligible[:_DEMOTION_BOTTOM_K]
    if surfaced:
        indeg: dict = {s: 0 for s in pop}
        all_stems = set(bodies)
        for src, body in bodies.items():
            for link in extract_wikilinks(body):
                tgt = link if link in all_stems else resolve_wikilink(link, all_stems)
                if tgt and tgt != src and tgt in indeg:
                    indeg[tgt] += 1
        for c in surfaced:
            c["indegree"] = indeg.get(c["stem"], 0)
            best, best_r = "", 0.0
            for other in pop:
                if other == c["stem"] or not descs[other] or not descs[c["stem"]]:
                    continue
                a, b = sorted((c["stem"], other))        # canonical arg order → deterministic ratio
                r = difflib.SequenceMatcher(None, descs[a], descs[b], autojunk=False).ratio()
                if r > best_r:
                    best, best_r = other, r
            if best_r >= _DEMOTION_SIMILAR:
                c["similar"], c["ratio"] = best, round(best_r, 2)
    out["candidates"] = surfaced
    return out


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


_GIT_WARNED = False   # v0.1.69/A4: one label per process — _run fires many times per pass


def _run(cmd: list[str], cwd: Path) -> str:
    global _GIT_WARNED
    try:
        out = subprocess.run(  # noqa: S603 - fixed args
            cmd, cwd=cwd, capture_output=True, text=True, timeout=15, check=False
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        # v0.1.69/A4: LABEL the degraded path — a missing/broken/timed-out git must be distinguishable
        # from a clean repo with no new commits, or the dream silently under-scopes ("NOTHING TO
        # CONSOLIDATE" on a git failure would mask the failure). Degrade stays (""), now labeled.
        if not _GIT_WARNED:
            _GIT_WARNED = True
            print(f"memory_status: git unavailable ({type(e).__name__}) — scope degraded to empty",
                  file=sys.stderr)
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


# v0.1.24: binding-directive markers (RFC-2119 + imperatives). IGNORECASE → MUST≡must; the apostrophe class
# covers ASCII + smart quotes (Don't ≡ Don’t, Gate-2 1a); DO\s+NOT tolerates any spacing ("DO  NOT", "DO\tNOT").
_NORMATIVE_RE = re.compile(r"\b(?:MUST|SHALL|REQUIRED|NEVER|ALWAYS|DO\s+NOT|DON['‘’]T)\b", re.IGNORECASE)


def _has_normative_marker(text: str) -> bool:
    """v0.1.24 (SAFETY backstop for CLAUDE.md relocate): does this chunk carry an EXPLICIT binding-directive
    marker? Run it against the elaboration-that-MOVES — a hit means a directive is being relocated DOWN a tier
    (always-loaded → on-demand = enforcement erosion), which the byte-CONSERVATION check can't catch (the bytes
    still land). Mirrors the _looks_secret tripwire: asymmetric-safe (a false positive only costs a human look).
    SUFFICIENT, NOT NECESSARY (Gate-2 1c): a hit ⇒ definitely a directive, keep it — but a MISS does NOT mean
    safe-to-relocate. It catches only EXPLICIT RFC-2119/imperative markers; the DOMINANT directive form is the
    bare imperative ('Keep src/ clean', 'Run the gate') which carries NO marker — judgment still owns those, and
    the per-change human-approved proposal is the ultimate guard. Marker-absence must NEVER license a relocate."""
    return bool(_NORMATIVE_RE.search(text))


def _git_check_ignore(rel: str, root: Path) -> bool:
    """True if `rel` is git-ignored OR can't be confirmed safe — FAIL-CLOSED (a target we can't prove reaches
    teammates is unsafe). `git check-ignore -q`: exit 0 = ignored, 1 = not ignored, 128 = error → only 1 is safe."""
    try:
        r = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=root,  # noqa: S603 - fixed args
                           capture_output=True, timeout=15, check=False)
        return r.returncode != 1
    except (OSError, subprocess.SubprocessError):
        return True


def valid_relocate_target(path: str, project_dir: Path) -> bool:
    """v0.1.24 (SAFETY firewall): is `path` a SAFE relocate destination for committed CLAUDE.md content? True ONLY
    if it resolves INSIDE project_dir AND is NOT under ~/.claude (the private per-user store) AND is NOT git-ignored.
    Relocating team content into the private store OR a gitignored dir = silent team data loss (it never reaches
    teammates) — the exact failure this guards. Relative targets anchor to project_dir (cwd is not stable across
    calls); absolute paths resolve as-is. 3.8 idiom (relative_to/ValueError, not is_relative_to)."""
    root = project_dir.resolve()
    target = (root / path).resolve()                      # absolute `path` wins; relative anchors to root
    try:
        rel = target.relative_to(root)                    # must be inside the repo
    except ValueError:
        return False
    try:
        target.relative_to((Path.home() / ".claude").resolve())   # must NOT be under the private store
        return False
    except ValueError:
        pass
    return not _git_check_ignore(str(rel), root)          # must NOT be git-ignored (fail-closed)


def claude_md_sections(path: Path) -> list:
    """v0.1.24 (MECHANICAL only): split a CLAUDE.md into `##` sections with per-section token counts, so a heavy
    section can be EXAMINED for a directive/elaboration split. It does NOT rank-to-relocate (the biggest section is
    often the most load-bearing) and does NOT judge directive-vs-elaboration or staleness — that's the model's. The
    surfaced flag must say 'examine for a directive/elaboration split', NEVER 'relocate candidate'."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    sections: list = []
    title = "(preamble)"
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            body = "\n".join(buf)
            if body.strip():
                # has_directive (Gate-2): a mechanical signal that this section carries EXPLICIT binding markers —
                # split it carefully. SUFFICIENT not NECESSARY: a False does NOT mean 'all elaboration' (bare
                # imperatives carry no marker); it's a hint, the directive/elaboration judgment stays the model's.
                sections.append({"title": title, "tokens": est_tokens(body), "has_directive": _has_normative_marker(body)})
            title, buf = line[3:].strip(), [line]
        else:
            buf.append(line)
    body = "\n".join(buf)
    if body.strip():
        sections.append({"title": title, "tokens": est_tokens(body), "has_directive": _has_normative_marker(body)})
    return sections


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
        entry = {"hash": hashlib.sha1(data).hexdigest(),
                 "tokens": est_tokens(data.decode("utf-8", "replace")), "store": store}
        if store == "memory":   # v0.1.32: stash content (memory store ONLY) — the before-side for the diff-modal sidecar
            entry["content"] = data.decode("utf-8", "replace")
        snap[label] = entry

    if auto_mem.exists():
        for f in sorted(auto_mem.glob("*.md")):
            _add(f"memory/{f.name}", f, "memory")
    _cmd_set = {p.resolve() for p in _claude_md_files(project_dir)}
    for p in _claude_md_files(project_dir):
        try:
            label = f"claude_md/{p.relative_to(project_dir)}"
        except ValueError:
            label = f"claude_md/{p.name}"
        _add(label, p, "claude_md")
    # v0.1.24: the relocate-TARGET tree — non-gitignored repo *.md BEYOND the CLAUDE.md hierarchy — so a relocate
    # (CLAUDE.md shrink + target grow) is conservation-checked by the recorder itself, not just git diff. git
    # ls-files (tracked) + --others --exclude-standard (new-but-not-ignored) → committed targets AND a freshly
    # proposed-created one, while .gitignore'd noise (incl. vendored dirs) is excluded.
    _repo_md = set(_run(["git", "ls-files", "*.md"], project_dir).splitlines())
    _repo_md |= set(_run(["git", "ls-files", "--others", "--exclude-standard", "*.md"], project_dir).splitlines())
    for rel in sorted(_repo_md):
        p = project_dir / rel
        if p.resolve() in _cmd_set:                       # already 'claude_md' — no double-count
            continue
        _add(f"repo_doc/{rel}", p, "repo_doc")
    return snap


def audit_diff(before: dict, after: dict) -> dict:
    """v0.1.22: the DETERMINISTIC mutation set between two audit_snapshots — one op per file whose content-hash
    CHANGED (created / modified / deleted); an unchanged file (same hash) is NOT an op. Per-store rollups
    (memory / claude_md). This is the script-OBSERVED counterpart to the model-narrated entries[]."""
    ops: list = []
    roll = {"memory": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0},
            "claude_md": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0},
            "repo_doc": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0}}   # v0.1.24: relocate targets

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
    # v0.1.24 CONSERVATION: tokens that net-LEFT the CLAUDE.md hierarchy should land in relocate targets. Sum
    # repo_doc GROWTH from per-op POSITIVE deltas — NOT the netted rollup (a prune in doc B must not cancel a
    # relocate-grow in doc A; Gate-1 #4). A gross CLAUDE.md drop with little growth = a possible LOST relocate (an
    # eviction, not a move). Approximate (CLAUDE.md keeps directive+pointer) → flag only a GROSS shortfall.
    cmd_drop = max(0, -roll["claude_md"]["token_delta"])
    repo_growth = sum(o["token_delta"] for o in ops if o["store"] == "repo_doc" and o["token_delta"] > 0)
    conservation = {"claude_md_drop": cmd_drop, "repo_doc_growth": repo_growth,
                    "possible_loss": cmd_drop > 50 and repo_growth < cmd_drop * 0.5}
    return {"memory": roll["memory"], "claude_md": roll["claude_md"], "repo_doc": roll["repo_doc"],
            "operations": ops, "conservation": conservation}


# ── v0.1.32: per-dream diff capture for the diff-modal (memory store only; sidecar OUTSIDE the cycle record) ──
_DIFF_LINE_CAP = 80   # per-file diff line cap for the modal — a giant fact rewrite won't bloat the sidecar


def diff_key(marker: object) -> str:
    """The per-dream diff-sidecar key — the (commit, timestamp) `_marker` pair, sanitized to a filename. render_html
    reconstructs the SAME key from each embedded cycle's marker to find + embed its sidecar (belt-and-suspenders vs
    a timestamp-only collision when two dreams share a HEAD)."""
    m = marker if isinstance(marker, dict) else {}
    commit = re.sub(r"[^0-9A-Za-z]", "", str(m.get("commit", "") or ""))[:12] or "nocommit"
    ts = re.sub(r"[^0-9A-Za-z]", "-", str(m.get("timestamp", "") or "")) or "nots"
    return f"{commit}__{ts}"


def diffs_dir(project_dir: Path) -> Path:
    """The PRIVATE per-repo diff-sidecar dir: <store>/../dashboards/diffs (never the repo)."""
    auto_mem = Path.home() / ".claude" / "projects" / slug_for(project_dir.resolve()) / "memory"
    return auto_mem.parent / "dashboards" / "diffs"


def _write_private(path: Path, text: str) -> None:
    """v0.1.32: write owner-only (0o600) ATOMICALLY — these files hold memory fact BODIES. os.open WITH the mode
    avoids the write_text-then-chmod TOCTOU (content never lands in a world-readable 0o644 window); the trailing
    chmod also tightens a pre-existing file from before this fix."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def _diff_lines(before_text: str, after_text: str, cap: int = _DIFF_LINE_CAP) -> dict:
    """A capped unified diff (stdlib difflib) as structured lines for the modal: {lines:[{t,s}], more:N}. `t` is
    '+'/'-'/'@'/' ' (added/removed/hunk/context); the modal renders each `s` via esc() — the load-bearing XSS guard
    on the highest-volume untrusted-text-into-DOM path in the dashboard."""
    raw = [ln for ln in difflib.unified_diff(before_text.splitlines(), after_text.splitlines(), lineterm="", n=3)
           if not ln.startswith("--- ") and not ln.startswith("+++ ")]   # drop the file-header pair
    lines = []
    for ln in raw[:cap]:
        c = ln[:1]
        t = c if c in ("+", "-", "@") else " "
        lines.append({"t": t, "s": ln if t == "@" else ln[1:]})
    return {"lines": lines, "more": max(0, len(raw) - cap)}


def capture_diffs(before: object, project_dir: Path) -> dict:
    """Per-CHANGED-memory-file before/after diffs — the script-observed diff of THIS dream's memory mutations.
    `before` = the Phase-0 snapshot (with `content`); after = the current store. Scoped to store=='memory';
    one-sided create/delete handled (the empty side). Returns {path: {op, lines, more}}. Best-effort (caller guards)."""
    bsnap = before if isinstance(before, dict) else {}
    after = audit_snapshot(project_dir)
    diffs: dict = {}
    for op in audit_diff(bsnap, after).get("operations", []):
        label = str(op.get("path", ""))
        if op.get("store") != "memory" or label == "memory/MEMORY.md":   # exclude the index — pointer churn, not a fact
            continue
        b = bsnap.get(label) if isinstance(bsnap.get(label), dict) else {}
        a = after.get(label) if isinstance(after.get(label), dict) else {}
        d = _diff_lines(str((b or {}).get("content", "")), str((a or {}).get("content", "")))
        d["op"] = op.get("op", "modified")
        diffs[label] = d
    return diffs


def _scrub_commit_log(log: str) -> list:
    """v0.1.70 SECURITY: `git log --oneline` subject lines are attacker/mistake-influenceable text
    (a routine real-world slip — `git commit -m "debug: hardcoded STRIPE_KEY=sk_live_... to unblock
    CI"` — or a deliberate plant on a shared branch) that flowed straight into the Phase-0 report the
    model reads every dream, with SKILL.md itself framing git log as the "strongest, highest-precision
    source" for facts — yet this was the one Phase-2 source with NO secrets-firewall pass
    (extract_signals.py's session-signal source has one; this didn't). `_sane()` (used by
    print_report) only strips terminal control bytes, a DIFFERENT concern (injection-safety, not
    credential-shape) — this scrubs through the SAME firewall extract_signals uses, at construction,
    so every consumer (print_report, any future reader) sees only sanitized text. The short SHA is
    kept (harmless, and lets a human `git show` it directly); only a flagged subject is redacted.
    Pure (str -> list[str], no I/O) so it's directly unit-testable without a git repo.

    v0.1.70 Gate-2a: `_looks_secret` runs on the subject CAPPED at `_COMMIT_SUBJECT_CAP` first —
    unlike extract_signals.py's three call sites (which all cap at `_PROBE_CAP` before scanning),
    this one originally fed the RAW, unbounded subject straight to the regex. Git enforces no
    length limit on a commit message's first line, so a single ~900,000-char subject (a pasted
    blob committed as one line, deliberate or not) measured 6.4s against the real firewall — this
    read-only Phase-0 path runs on every `cm status`/dream invocation, so that's a real stall."""
    out: list = []
    for ln in log.splitlines():
        if not ln.strip():
            continue
        sha, sep, subject = ln.partition(" ")
        if sep and _looks_secret(subject[:_COMMIT_SUBJECT_CAP]):
            out.append(f"{sha} (omitted: commit subject contained a credential-shaped value)")
        else:
            out.append(ln)
    return out


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
    # v0.1.63 (Phase A): hook-cost + native-cliff telemetry for the always-loaded index (report + seed).
    try:
        _index_text = index_path.read_text(encoding="utf-8", errors="replace") if index_path.exists() else ""
    except OSError:
        _index_text = ""
    index_hooks = hook_stats(_index_text)
    index_cliff = cliff_pct(index_lb[1], index_lb[0])

    transcripts = sorted(proj_root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

    state_path = auto_mem / STATE_FILE
    last_commit = last_ts = ""
    standing_justify: object = None
    demotion_justify: object = None
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text())
            last_commit, last_ts = st.get("commit", ""), st.get("timestamp", "")
            standing_justify = st.get("standing_justify")   # v0.1.21 (D7): the justified-density baseline, if any
            demotion_justify = st.get("demotion_justify")   # v0.1.67 (Phase C): per-item counter-justify map, if any
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
    commits = _scrub_commit_log(log)

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
    _sj_baseline = _standing_baseline(standing_justify)          # v0.1.21 (D7): justified fact-count baseline, or None
    _sj_tokens = _standing_baseline_tokens(standing_justify)     # v0.1.23 (D6): justified index-token baseline, or None
    # STANDING-JUSTIFIED suppresses ONLY when BOTH axes are within bound: fact-count ≤ baseline+Δ AND index tokens
    # ≤ baseline_tokens × FACTOR. Either axis growing (or no valid baseline) re-FIRES the gate (fail-open) — so
    # token bloat with flat fact-count no longer hides (D6), while genuine earned density stays suppressed.
    if (index_lb[2] > INDEX_TOKEN_BUDGET
            and _sj_baseline is not None and len(fact_files) <= _sj_baseline + _STANDING_JUSTIFY_DELTA
            and _sj_tokens is not None and index_lb[2] <= int(_sj_tokens * _STANDING_JUSTIFY_TOKEN_FACTOR)):
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
    # v0.1.66 (Phase B): the hard-ceiling flag — a SIBLING assignment, deliberately OUTSIDE both branches
    # above so it never enters the `required`/standing-justify computation (the sibling-signal design the
    # 3-lens spec-review gate mandated; docs/index-usage-and-budget-ladder.spec.md §Phase B). Any store over
    # the ceiling is necessarily over the target (3840 > 1500 est tok), so `remediation` is always non-empty
    # when this could be True; a healthy (under-target) store carries no remediation block and no key.
    if remediation:
        remediation["over_ceiling"] = index_lb[2] > INDEX_CEILING_TOKENS

    # v0.1.37 (+v0.1.52): the no-op SELF-HEAL maintenance signal. Resolves dangling against local ∪ the
    # global canonical (a stem GLOB only — still cheap on the always-run Phase-0 path, NOT a dependency
    # scan) so a pending-pull up-link to a budget-HELD global isn't false-flagged (M1 `held` is the real
    # pull signal; a sibling-project-local DOWN-link stays flagged — unreachable here). `over_budget_not_justified`
    # REUSES the dual-axis suppression result (`remediation.required`), NOT a fresh budget compare — so a
    # standing-justified store reads False (no perpetual pivot). `remediation` is {} on the healthy path,
    # hence `.get`, not subscript (would KeyError). No `stale_since_marker` (it re-fires every run).
    _dangling = dangling_links(auto_mem, global_dir=GLOBAL_STORE)
    _obnj = bool((remediation or {}).get("required"))
    maintenance: dict = {"dangling": len(_dangling), "over_budget_not_justified": _obnj,
                         "work": bool(_dangling) or _obnj}

    # v0.1.67 (Phase C): the demotion-triage seed — longitudinal usage aggregation + the per-fact
    # evidence-gated rank. Cheap on the always-run Phase-0 path: one tail-capped log read + one store
    # scan (the archive/defrag candidate scans already set that cost precedent). DORMANT (eligible 0,
    # empty candidates) until probative windows accrue — see the §Phase C evidence gate.
    usage_hist = usage_history(auto_mem) if auto_mem.exists() else {
        "windows_full": 0, "window_starts": [], "per_fact": {}, "miss_stems": []}
    demotion = demotion_candidates(fact_files, index_names, usage_hist, _index_text,
                                   justify=_demotion_justify(demotion_justify))

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
        "index_hooks": index_hooks, "index_cliff": index_cliff,   # v0.1.63 (Phase A) telemetry
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
        "maintenance": maintenance,
        "usage_hist": usage_hist,   # v0.1.67 (Phase C)
        "demotion": demotion,       # v0.1.67 (Phase C)
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
                # v0.1.63 (Phase A): hook + cliff telemetry (observe-only; Phase B acts on them)
                "fat_hooks": ctx["index_hooks"][0], "hook_max_tokens": ctx["index_hooks"][1],
                "cliff_pct": ctx["index_cliff"],
                "ceiling_tokens": INDEX_CEILING_TOKENS,   # v0.1.66 (Phase B): the hard ceiling, for display
            },
            "recall_facts": {"before": len(ctx["fact_files"]), "after": len(ctx["fact_files"])},
            "claude_md_hierarchy": ctx["claude_md_hierarchy"],   # v0.1.22: whole-hierarchy measure (read-only)
        },
        "health": {"index_pointers_ok": True, "broken": [], "dangling_links": [],
                   "slug_orphans": [o["slug"] for o in ctx["slug_orphans"]],
                   "schema_drift": ctx["schema_drift"]},
        "maintenance": {"dangling": ctx["maintenance"]["dangling"],
                        "over_budget_not_justified": ctx["maintenance"]["over_budget_not_justified"],
                        "work": ctx["maintenance"]["work"]},
        "cross_project": {
            "global_store_facts": len(list(GLOBAL_STORE.glob("*.md")))
            - (1 if (GLOBAL_STORE / "MEMORY.md").exists() else 0),
            "pulled": [],     # fill in Phase 1 (sync_global --pull): global → here
            "promoted": [],   # fill in Phase 4: here → global (new cross-project facts)
            "refreshed": 0,   # stale mirrors refreshed on pull
            "held": 0,        # v0.1.38 (M1): new-global pulls held back (v0.1.66: past the HARD CEILING, was over-target)
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
        # v0.1.66 (Phase B): over_ceiling rides along UNCHANGED by the suppression — the ceiling is SJ-independent
        # by construction (the sibling-signal design), so a justified store past the ceiling still shows it.
        record["remediation"] = {"required": False, "standing_justified": True,
                                 "baseline_facts": rem.get("baseline_facts", 0),
                                 "over_ceiling": bool(rem.get("over_ceiling"))}
    elif rem:
        record["remediation"] = {
            "required": rem["required"], "lever": rem["lever"],
            "candidates_surfaced": rem["candidates"],
            "projected_index": rem.get("projected_index", 0),
            "projected_recall": rem.get("projected_recall", 0),
            "reaches_budget": rem.get("reaches_budget", True),   # D5: False ⇒ prune-then-standing-justify
            "over_ceiling": bool(rem.get("over_ceiling")),       # v0.1.66 (Phase B): sibling of required, never a re-key
        }
    # v0.1.67 (Phase C): seed the demotion-triage block whenever the store exists — a DORMANT pass
    # records windows_observed / eligible: 0 HONESTLY ("ran and proposed nothing" ≠ "never ran", the
    # distill precedent). `struck` is written later by extract_signals.inject_usage; `verdict` is the
    # model's Phase-5 sentence. Absent key on a store-less run — legacy records stay valid (total=False).
    if ctx["auto_mem"].exists():
        demo = ctx.get("demotion") or {}
        record["demotion"] = {"windows_observed": _pi_int(demo.get("windows_full")),
                              "eligible": _pi_int(demo.get("eligible")),
                              "surfaced": [c["stem"] for c in demo.get("candidates", []) if isinstance(c, dict)]}
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
    for key in ("scope", "rigor", "verification", "budget", "cross_project", "network", "marker", "health",
                "audit", "remediation", "maintenance", "dream", "distill", "usage", "demotion"):
        if key in record and not isinstance(record[key], dict):
            warnings.append(f"{key} is not a dict")
    # entries must be a list if present.
    if "entries" in record and not isinstance(record["entries"], list):
        warnings.append("entries is not a list")
    # dream.beats must be a list if present (mirrors the health.* nested checks: descend only
    # into a well-formed dream — a non-dict dream already warned above).
    dream = record.get("dream")
    if isinstance(dream, dict) and "beats" in dream and not isinstance(dream["beats"], list):
        warnings.append("dream.beats is not a list")
    # distill.proposed / distill.created must be lists if present (same descend-only-into-dict rule).
    distill = record.get("distill")
    if isinstance(distill, dict):
        for lk in ("proposed", "created"):
            if lk in distill and not isinstance(distill[lk], list):
                warnings.append(f"distill.{lk} is not a list")
        # v0.1.58 numeric backstop: counts above the scanner caps are IMPOSSIBLE from a capped scan —
        # the measured hand-mirror failure (a persisted n_recurring=47 vs MAX_RECUR_OUT=40). `--into`
        # is the cure; this warn catches a hand-fill that dodged it. Coercion-guarded (warn-only gate).
        for ck, cap in (("n_recurring", _DISTILL_CAPS[0]), ("n_chains", _DISTILL_CAPS[1])):
            try:
                if ck in distill and int(distill[ck]) > cap:
                    warnings.append(f"distill.{ck} exceeds the scanner cap ({cap}) — impossible from a capped scan")
            except (TypeError, ValueError):
                pass  # a non-numeric count is a shape problem the render coercion boundary absorbs

    # v0.1.63 (Phase A): usage.per_fact must be a list; a length above the producer cap is IMPOSSIBLE
    # from a capped --recalls scan (the distill hand-mirror lesson — same backstop shape). A non-dict
    # `usage` already warned via the top-level tuple; descend only into a well-formed one.
    usage = record.get("usage")
    if isinstance(usage, dict) and "per_fact" in usage:
        if not isinstance(usage["per_fact"], list):
            warnings.append("usage.per_fact is not a list")
        elif len(usage["per_fact"]) > _USAGE_FACT_CAP:
            warnings.append(f"usage.per_fact exceeds the scanner cap ({_USAGE_FACT_CAP}) — impossible from a capped scan")
    # v0.1.67 (Phase C): usage.misses — same producer, same cap, same backstop shape.
    if isinstance(usage, dict) and "misses" in usage:
        if not isinstance(usage["misses"], list):
            warnings.append("usage.misses is not a list")
        elif len(usage["misses"]) > _USAGE_FACT_CAP:
            warnings.append(f"usage.misses exceeds the scanner cap ({_USAGE_FACT_CAP}) — impossible from a capped scan")

    # v0.1.67 (Phase C): the demotion block — surfaced is script-seeded and capped at _DEMOTION_BOTTOM_K
    # (producer + validator share THIS module, so no cross-module mirror is needed, unlike _DISTILL_CAPS).
    demotion = record.get("demotion")
    if isinstance(demotion, dict):
        for lk in ("surfaced", "struck"):
            if lk in demotion and not isinstance(demotion[lk], list):
                warnings.append(f"demotion.{lk} is not a list")
        if isinstance(demotion.get("surfaced"), list) and len(demotion["surfaced"]) > _DEMOTION_BOTTOM_K:
            warnings.append(f"demotion.surfaced exceeds the rank cap ({_DEMOTION_BOTTOM_K}) — impossible from a capped rank")

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


# ── v0.1.44: procedure-integrity detector — the lazy-skip safeguard ──────────────────
# The MEASURED failure (2026-06-22): three consecutive dreams ran 0/0/0 verification while
# self-labeled SUBSTANTIAL/HEAVY — the orchestrator skipped the Phase-3 verification fan-out
# and graded its own (skipped) effort. `rigor.applied` is self-reported, so it can't catch this
# (it catches OVER-rigor, not UNDER-rigor). This is a DETECTOR at the one mandatory boundary a
# finishing dream always reaches (render_dashboard --persist, the SKILL's terminal step), NOT
# enforcement of phase invocation — nothing can make a stateless script force an LLM to run a
# phase. It fires on the lazy-skip SIGNATURE: substantial WORK existed (script-derived magnitude)
# yet ZERO verification was recorded. It does NOT catch a diligent liar who types fake tallies
# (the same limit as any self-reported scheme). Design + the empirical 13-record validation:
# docs/dream-procedure-integrity.spec.md.
#
# NON-CIRCULAR leg: magnitude derives from scope.git_commits (script-SEEDED by seed_record from
# `git log` — a lazy-skip never touches it) + session_candidates (model-curated, but LOWERING it
# only LOWERS magnitude, so the dodge can't manufacture a substantial pass). The trigger does NOT
# rest on rigor.applied (the audited self-report) NOR on mutation_ops (a skipped Phase 5 also
# skips --audit, so that data may not exist — measured: 11 mutation-log entries for 13 dreams,
# none of the 3 failures carrying an audit block). `applied` + any audit op-count are
# CORROBORATION / severity ONLY — never gating.


def _pi_int(x: object) -> int:
    """Coerce a model-authored numeric (a cycle record is model-emitted JSON) to int; 0 on
    anything odd. Local to this module (the dependency root render imports), mirroring render's
    `_num` at the model→logic boundary. Never raises."""
    if isinstance(x, bool):                 # bool ⊂ int — count True/False as 1/0 explicitly
        return int(x)
    if isinstance(x, (int, float)):
        return int(x) if math.isfinite(x) else 0   # NaN/±inf → 0: json.loads accepts NaN/Infinity, and int(nan/inf) raises
    if isinstance(x, str):
        try:
            f = float(x.strip() or 0)
        except ValueError:
            return 0
        return int(f) if math.isfinite(f) else 0    # "inf"/"nan" parse to a non-finite float → 0 (not a crash)
    return 0


def procedure_integrity(record: object) -> tuple[bool, str, str]:
    """DETECT the lazy-skip: a SUBSTANTIAL-or-larger-MAGNITUDE pass that recorded ZERO
    verification. Returns (ok, reason, severity); ok=True ⇒ no violation (or the record can't be
    evaluated). PURE; never raises. The renderer calls it, and `render_dashboard --persist` turns
    a violation into a loud panel + a nonzero exit (the teeth — see SKILL Phase 5).

    LEGACY / non-conformant GATE: returns (True, "", "") when `scope` or `verification` is absent
    or non-dict — an ancient or partial record predates this check and must NEVER be retroactively
    flagged. Every record this skill seeds carries both blocks, so real passes are always judged.

    FIRE (ok=False) iff `suggested_tier(git_commits, session_candidates) >= SUBSTANTIAL` AND the
    verification tally (confirmed+corrected+unverifiable) <= 0 (a negative/junk tally can't dodge it).
    `applied` + any audit op-count are CORROBORATION / severity ONLY (see the module note above) — never gating."""
    if not isinstance(record, dict):
        return (True, "", "")
    scope = record.get("scope")
    verif = record.get("verification")
    if not isinstance(scope, dict) or not isinstance(verif, dict):
        return (True, "", "")               # can't evaluate → no-op (legacy / partial record)
    commits = _pi_int(scope.get("git_commits"))
    cands = _pi_int(scope.get("session_candidates"))
    tally = _pi_int(verif.get("confirmed")) + _pi_int(verif.get("corrected")) + _pi_int(verif.get("unverifiable"))
    tier = suggested_tier(commits, cands)
    if TIER_ORDER.get(tier, 0) < TIER_ORDER["SUBSTANTIAL"] or tally > 0:
        return (True, "", "")               # honest LIGHT/maintenance/bootstrap, or POSITIVE verification recorded (tally>0)
    reason = (f"magnitude {tier} ({commits} commit(s) + {cands} candidate(s)) but 0 verification "
              f"recorded — the Phase-3 verification fan-out was likely skipped")
    severity = "warn"
    rg_raw = record.get("rigor")            # assign-then-narrow (a double .get() doesn't narrow for mypy)
    rg = rg_raw if isinstance(rg_raw, dict) else {}
    applied = str(rg.get("applied", "")).strip().upper()
    if applied in ("SUBSTANTIAL", "HEAVY"):
        severity = "alert"                  # self-graded substantial effort AND verified nothing — the measured failure
        reason += f"; self-labeled rigor.applied={applied} (effort graded, not done)"
    elif applied in TIER_ORDER and TIER_ORDER[applied] < TIER_ORDER[tier]:
        ov = str(rg.get("override_reason", "")).strip()    # the downgrade dodge — labeled below magnitude
        reason += f"; labeled rigor.applied={applied} below magnitude {tier}" + ("" if ov else " with no override_reason")
    audit = record.get("audit")
    if isinstance(audit, dict) and audit:
        ops = audit.get("operations")
        reason += f"; wrote {len(ops) if isinstance(ops, list) else 0} file op(s) this pass"
    else:
        reason += "; no audit trail (Phase-5 --audit also skipped)"
    return (False, reason, severity)


def _remediation_section(rem: dict) -> list:
    """The REMEDIATION report lines (v0.1.18) — shared by print_report + --triage. Empty when the index is
    under budget (rem is {}). Presentation only; the heuristics RANK, the model JUDGES + confirms."""
    if not rem:
        return []
    # v0.1.66 (Phase B): the hard-ceiling line renders in BOTH branches below — the ceiling is
    # standing-justify-INDEPENDENT (sibling signal), so suppression of the target gate never hides it.
    _ceil_line = (_ui.li(_ui.c(f"⚠ HARD CEILING exceeded (>{INDEX_CEILING_TOKENS} est tok) — M1 holds ALL new "
                               "pulls; standing-justify does not apply to the ceiling; shrink to receive",
                               "red"), indent=4, bullet="⚠", bullet_color="red")
                  if rem.get("over_ceiling") else None)
    # v0.1.21 (D6/D7): a STANDING-JUSTIFIED over-budget index is suppressed — show the standing state, no triage.
    if rem.get("standing_justified"):
        cur, base = rem.get("current_facts"), rem.get("baseline_facts", 0)
        grew = f"+{cur - base}" if isinstance(cur, int) else "?"
        return [_ui.kv("REMEDIATION", _ui.c(
            f"✓ over budget ({rem.get('index_tokens', '?')}/{rem.get('budget', INDEX_TOKEN_BUDGET)} tok) but "
            f"STANDING-JUSTIFIED · {cur} facts vs baseline {base} ({grew}; re-fires at +{_STANDING_JUSTIFY_DELTA} facts or on index-token bloat)", "green"))] \
            + ([_ceil_line] if _ceil_line else [])
    out = [_ui.kv("REMEDIATION", _ui.c(f"⚠ index OVER budget ({rem['index_tokens']}/{rem['budget']} tok) "
                                       f"— GATE active · lever {rem['lever'].upper()}", "red"))]
    if _ceil_line:
        out.append(_ceil_line)
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
        # v0.1.63 (Phase A): cliff proximity on the gauge line (red at CLIFF_NEAR_FRACTION — silent
        # truncation near); fat hooks on their own advisory line (a fat cue taxes every session).
        # v0.1.66 (Phase B): the hard-ceiling flag — independent of the target `over` and of
        # standing-justify (sibling signal; M1 holds all new pulls while it shows).
        _cp = ctx.get("index_cliff", 0)
        cliff = (_ui.c(f"  ⚠ cliff {_cp}% of native 25KB/200ln — SILENT truncation near", "red")
                 if _cp >= int(CLIFF_NEAR_FRACTION * 100) else _ui.c(f" · cliff {_cp}%", "dim"))
        ceil = _ui.c(f"  ⚠ HARD CEILING (>{INDEX_CEILING_TOKENS} tok — M1 holds all new pulls)", "red") \
            if it > INDEX_CEILING_TOKENS else ""
        add(f"    {_ui.lbl('index', 14)}{_ui.bar(it, INDEX_TOKEN_BUDGET)} {_ui.pct(it, INDEX_TOKEN_BUDGET):>4}  "
            + _ui.c(f"≈{it}/{INDEX_TOKEN_BUDGET} tok · {il} ln · {ib} by  [ALWAYS-LOADED]", "dim") + over + ceil + cliff)
        _fh, _hm, _off = ctx.get("index_hooks", (0, 0, []))
        if _fh:
            _tops = " · ".join(f"{n} ≈{t}t" for t, n in _off[:3])
            add("    " + " " * 14 + _ui.c(f"hooks: {_fh} pointer(s) > {HOOK_TOKEN_WARN} tok — {_tops}", "yellow"))
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

    # v0.1.37: the no-op SELF-HEAL pivot cue — prominent so a magnitude-0 pass on a NON-EMPTY store routes
    # into maintenance (Phase 1 --pull + Phase 5 health, report-then-apply) instead of exiting. The cue is
    # this line + the --json `maintenance` block (signal-driven; prose alone is what failed).
    _m = ctx.get("maintenance") or {}
    # The PROCEED cue fires on commits==0 + NON-EMPTY store (not just local `work`): cross-node enrichment
    # (a newly-promoted sibling global, found in Phase-1 --pull) is real + Phase-0-invisible, so a
    # local-only `work` gate would skip a pullable-only pass. Stop ONLY when the store is empty.
    _noop_nonempty = len(ctx["commits"]) == 0 and bool(ctx["fact_files"])
    if _m.get("work") or _noop_nonempty:
        _bits = []
        if _m.get("dangling"):
            _bits.append(f"{_m['dangling']} dangling [[link]](s)")
        if _m.get("over_budget_not_justified"):
            _bits.append("index over budget (not standing-justified)")
        _detail = "self-heal available — " + " · ".join(_bits) if _bits else "store-health + cross-node enrichment check"
        add("")
        add("  " + _ui.c("MAINTENANCE", "bold") + _ui.c("  " + _detail, "yellow"))
        add("    " + _ui.c("→ Phase 1 `sync_global --pull .` (cross-node enrichment) + Phase 5 health, report-then-apply", "dim"))
        # v0.1.38 (M1): the net-grow guard lives IN --pull (auto-holds a new pointer that would leave the index
        # over budget) — not a cue command to remember (a cue can't know the per-pull cost; only --pull can). So
        # this is ADVISORY: surface the lever, don't gate here.
        add("    " + _ui.c(f"--pull AUTO-HOLDS a new-global pull that would push the index past the HARD CEILING (>{INDEX_CEILING_TOKENS} tok; reports `held N` — shrink to receive)", "dim"))
        if _noop_nonempty:
            add("    " + _ui.c("0 new commits + NON-EMPTY store → PROCEED (a maintenance pass, NOT a no-op); stop ONLY if the store is empty", "dim"))

    # ── NEEDS A LOOK — suggestions only; nothing is changed automatically ──
    sig: list = []
    if ctx.get("promotion_candidates"):
        sig.append(_ui.li(f"promote? {len(ctx['promotion_candidates'])} unscoped feedback/reference fact(s) may apply "
                          "cross-project — re-scope by content + re-verify in Phase 1: "
                          + _ui.c(", ".join(ctx["promotion_candidates"]), "dim"), bullet="↑", bullet_color="cyan"))
    if ctx["stale_facts"]:
        sig.append(_ui.li(f"re-verify {len(ctx['stale_facts'])} stale fact(s) (mtime ≤ marker): "
                          + _ui.c(", ".join(ctx["stale_facts"]), "dim"), bullet="·"))
    _idxn = index_fact_names(ctx["auto_mem"] / "MEMORY.md")
    _arch = archive_candidates(ctx["fact_files"], _idxn)
    if _arch:
        sig.append(_ui.li(f"archive? {len(_arch)} indexed completed-arc pointer(s) (dated) → relocate to the on-demand "
                          "archive (e.g. SHIPPED.md) so the always-loaded index = the ACTIVE set "
                          "(completion-driven, NOT budget-gated; judge each, a dated-but-live lesson STAYS): "
                          + _ui.c(", ".join(c["stem"] for c in _arch[:8]) + ("…" if len(_arch) > 8 else ""), "dim"),
                          bullet="↓", bullet_color="cyan"))
    _defrag = defrag_candidates(ctx["fact_files"], _idxn)
    if _defrag:
        sig.append(_ui.li(f"defrag? {len(_defrag)} bloated ACTIVE file(s) (body ≫ store median) → curate the BODY "
                          "in place (collapse completed detail that's redundant with git/CHANGELOG, keep active "
                          "content + live lessons; propose-then-apply): "
                          + _ui.c(", ".join(f"{c['stem']}({c['ratio']}×)" for c in _defrag[:6]) + ("…" if len(_defrag) > 6 else ""), "dim"),
                          bullet="↓", bullet_color="cyan"))
    # v0.1.67 (Phase C): the demotion triage — `demote?` when eligible; the dim DORMANT accrual line while
    # the evidence gate hasn't opened (so the accrual is visible, not mysterious). Veto tallies show what
    # the gate withheld — information for the human, never policy.
    _demo = ctx.get("demotion") or {}
    if _demo.get("eligible"):
        _dtop = ", ".join(f"{c['stem']}(≈{c['hook_tokens']}t·{c['zero_read_windows']}w)"
                          for c in _demo.get("candidates", []))
        _vet = (f"vetoed: {_demo.get('vetoed_keep', 0)} keep-signal · {_demo.get('vetoed_read', 0)} read · "
                f"{_demo.get('vetoed_justified', 0)} justified"
                + (f" · {_demo['vetoed_missed']} missed" if _demo.get("vetoed_missed") else ""))
        sig.append(_ui.li(f"demote? {_demo['eligible']} eligible 0-read indexed fact(s) over ≥{_DEMOTION_MIN_WINDOWS} "
                          "probative window(s) → demote-to-archive / compress / merge / counter-justify "
                          "(report-then-apply — YOU judge content, keep-on-doubt): "
                          + _ui.c(_dtop, "dim") + "  " + _ui.c(_vet, "dim"),
                          bullet="↓", bullet_color="yellow"))
    elif ctx["auto_mem"].exists() and _demo.get("windows_full", 0) < _DEMOTION_MIN_WINDOWS:
        sig.append(_ui.li(_ui.c(f"usage evidence {_demo.get('windows_full', 0)}/{_DEMOTION_MIN_WINDOWS} probative "
                                "windows — demotion policy DORMANT (accrues per-dream via --recalls)", "dim"),
                          bullet="·"))
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
    g = GLOBAL_STORE
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


# v0.1.54: write-time dream-arc cues (stderr, CM_DREAM_ARC-gated — see _ui.dream_cue, which owns
# the authority prefix + never-echo suffix). _CUE_READ is PHASE-NEUTRAL: the plain/--json read runs
# in Phase 0 AND as Phase 5's final gauge re-read, and this script can't know which one it is
# serving — a phase-labeled cue there would issue a wrong-phase stage direction mid-Phase-5.
_CUE_READ = ("this read's beat is due — *1–3 plain-italic lines, no emoji* above the plain findings; "
             "if the arc hasn't opened yet, SLEEP (*💤 …*) comes first")
_CUE_PHASE0 = ("Phase-0 beat due — *1–3 plain-italic lines, no emoji* above the plain findings; "
               "SLEEP block (*💤 …*) first if you haven't slept yet")
_CUE_PHASE5 = ("Phase-5 beat due — narrate the audit/defrag dreamily (plain italics, no emoji); "
               "WAKE only after the archive opens (render_html)")


def main() -> int:
    argv = sys.argv[1:]
    audit_before = ""    # v0.1.22: --audit <before-snapshot-path> — capture its path arg so pos doesn't read it as project_dir
    if "--audit" in argv:
        _ai = argv.index("--audit")
        if _ai + 1 < len(argv) and not argv[_ai + 1].startswith("-"):
            audit_before = argv[_ai + 1]
    diffs_cycle = diffs_before = audit_into = ""   # v0.1.32: --diffs/--before sidecar; v0.1.53: --into <cycle> = inject the --audit block
    for _flag in ("--diffs", "--before", "--into"):
        if _flag in argv:
            _fi = argv.index(_flag)
            if _fi + 1 < len(argv) and not argv[_fi + 1].startswith("-"):
                if _flag == "--diffs":
                    diffs_cycle = argv[_fi + 1]
                elif _flag == "--before":
                    diffs_before = argv[_fi + 1]
                else:
                    audit_into = argv[_fi + 1]
    as_json = "--json" in argv
    _argpaths = {audit_before, diffs_cycle, diffs_before, audit_into} - {""}   # v0.1.53: --into value is NOT the positional project_dir
    pos = [a for a in argv if not a.startswith("-") and a not in _argpaths]   # positional = the project dir
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
        _ui.dream_cue(_CUE_PHASE0)
        return 0
    if "--sections" in argv:    # v0.1.24: mechanical ## breakdown of the heaviest CLAUDE.md — EXAMINE for a directive/elaboration split
        _wp = ctx["claude_md_hierarchy"].get("worst_path", ".")
        _cmd = project_dir / ("CLAUDE.md" if _wp in (".", "") else f"{_wp}/CLAUDE.md")
        try:
            _rel = str(_cmd.relative_to(project_dir))
        except ValueError:
            _rel = str(_cmd)
        print(json.dumps({"file": _rel, "_": "EXAMINE each heavy section for a directive(STAYS)/elaboration(relocates) split — "
                          "NEVER relocate a directive (it would drop from always-loaded to on-demand = enforcement erosion)",
                          "sections": claude_md_sections(_cmd)}, indent=2))
        return 0
    if "--snapshot" in argv:    # v0.1.22: Phase-0 BEFORE audit snapshot → per-slug temp path + print it
        path = audit_snapshot_path(ctx["slug"])
        _write_private(Path(path), json.dumps(audit_snapshot(project_dir), indent=2) + "\n")   # v0.1.32: holds fact bodies → 0o600 atomically
        print(path)
        _ui.dream_cue(_CUE_PHASE0)
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
        if audit_into:          # v0.1.53: deterministically inject the audit block INTO the cycle record (no model
            try:                # merge → no `d["audit"][k]` KeyError on a seed that lacks the key). Best-effort.
                _cyc = json.loads(Path(audit_into).read_text(encoding="utf-8"))
                if isinstance(_cyc, dict):
                    _cyc["audit"] = diff
                    _write_private(Path(audit_into), json.dumps(_cyc, indent=2, ensure_ascii=False) + "\n")  # holds fact bodies → 0o600
                    print(f"audit → injected into {audit_into}", file=sys.stderr)
                else:           # JSON but not an object → can't inject; tell the user (don't silently no-op)
                    print("--into: skipped (cycle record root is not a JSON object); paste the summary below into the `audit` block", file=sys.stderr)
            except (OSError, json.JSONDecodeError, ValueError) as e:   # never crash a dream — the printed summary below is the fallback
                print(f"--into: skipped ({e}); paste the summary below into the cycle record's `audit` block", file=sys.stderr)
        print(json.dumps(diff, indent=2))
        _ui.dream_cue(_CUE_PHASE5)
        return 0
    if "--diffs" in argv:       # v0.1.32: Phase-5 (post-persist) diff capture → per-dream sidecar for the diff-modal
        try:
            before = json.loads(Path(diffs_before).read_text(encoding="utf-8")) if diffs_before else {}
        except (OSError, json.JSONDecodeError):
            before = {}
        try:
            cyc = json.loads(Path(diffs_cycle).read_text(encoding="utf-8")) if diffs_cycle else {}
        except (OSError, json.JSONDecodeError):
            cyc = {}
        marker = cyc.get("marker") if isinstance(cyc, dict) else None
        if not isinstance(marker, dict):
            marker = {}
        if not str(marker.get("timestamp", "")).strip():   # mirror _persist's refusal — never key a sidecar on a blank ts
            print("--diffs: skipped (cycle has no marker.timestamp — unstamped)", file=sys.stderr)
            return 0
        try:                    # best-effort — a diff-capture failure must NEVER crash a dream (mirrors --audit)
            diffs = capture_diffs(before, project_dir)
            _d = diffs_dir(project_dir)
            _d.mkdir(parents=True, exist_ok=True)
            sp = _d / (diff_key(marker) + ".json")
            _write_private(sp, json.dumps(diffs) + "\n")   # holds memory fact BODIES → 0o600 atomically
            print(f"diffs → {sp}  ({len(diffs)} memory file(s) changed)")
        except Exception as e:   # noqa: BLE001 — never crash a dream over a sidecar
            print(f"--diffs: skipped ({e})", file=sys.stderr)
        _ui.dream_cue(_CUE_PHASE5)
        return 0
    if as_json:
        print(json.dumps(seed_record(ctx), indent=2))
    else:
        _ui.set_modes(color=_ui.color_enabled(argv, sys.stdout), ascii="--ascii" in argv, width=_ui.resolve_width(argv, sys.stdout))
        print_report(ctx)
    _ui.dream_cue(_CUE_READ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
