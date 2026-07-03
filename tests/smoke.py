#!/usr/bin/env python3
"""Zero-dependency smoke tests for the consolidate-memory scripts.

Run:  python3 tests/smoke.py   (exit 0 = all passed). No pytest required.
Tests pure functions only — no filesystem mutation, no network, no real memory.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "consolidate-memory" / "scripts"))

import extract_signals as es  # noqa: E402
import memory_status as ms  # noqa: E402
import distill_scan as ds  # noqa: E402
import render_dashboard as rd  # noqa: E402
import render_html as rhtml  # noqa: E402
import render_log as rlog  # noqa: E402
import sync_global as sg  # noqa: E402
import _ui as ui  # noqa: E402  — shared visual vocabulary

# v0.1.15: capture the module-load DEFAULT widths BEFORE the wide override below — _ui.W must mirror
# render_dashboard.W (a direct render()/_ui library caller that never runs a script main() relies on
# this default; the override would otherwise make the drift-pin's W check tautological).
_UI_W0, _RD_W0 = ui.W, rd.W
# The content assertions below pin TEXT, not line-wrapping — render WIDE so a long value is never
# split by the new hanging-indent wrap (which would break an `"x" in render(...)` check that spans
# the wrap point). The wrap mechanism itself is exercised by dedicated tests at the end.
# Production non-TTY default stays W=60.
ui.set_modes(width=240)
rd.W = 240

passed = failed = 0


def check(name: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")


# --- slug rule ---
check("slug: / -> -", ms.slug_for(Path("/home/you/project/foo")) == "-home-you-project-foo")
# v0.1.17: CC normalizes BOTH '/' and '_' to '-' (verified on disk: cwd .../Doc_Flo → slug ...-Doc-Flo).
# The pre-fix '/'-only slug sent cross-project facts to a slug an underscore-named project never recalls.
check("v0.1.17: slug maps '_'→'-' too (underscore project reaches its real CC store), case PRESERVED",
      ms.slug_for(Path("/home/you/project/Doc_Flo")) == "-home-you-project-Doc-Flo")
check("v0.1.17: slug regression-free for a no-underscore path (≡ old replace('/','-'))",
      ms.slug_for(Path("/home/you/project/foo-bar")) == "-home-you-project-foo-bar")
# v0.1.20: the cycle-record temp path is PER-SLUG (fixes the shared-/tmp/cycle.json concurrent-dream collision).
check("v0.1.20: cycle_seed_path is per-slug + deterministic (no shared-path collision across projects)",
      ms.cycle_seed_path("-a-proj1") != ms.cycle_seed_path("-a-proj2")
      and ms.cycle_seed_path("-x") == ms.cycle_seed_path("-x")
      and ms.cycle_seed_path("-x").endswith("cm-cycle-x.json")
      and not ms.cycle_seed_path("-x").endswith("/cycle.json"))

# v0.1.21 (D4/D10): resolve_wikilink — EXACT/normalized/date-base only, NEVER substring; ambiguous → None.
_rw_stems = {"qwen_migration_research_2026_05_26", "keyfigures-example-hallucination",
             "form_table_research_2026_05_28", "form_table_research_2026_06_01"}
check("v0.1.21: resolve_wikilink resolves slug-drift (date-base, dash↔underscore) but never substring/ambiguous",
      ms.resolve_wikilink("qwen-migration-research", _rw_stems) == "qwen_migration_research_2026_05_26"
      and ms.resolve_wikilink("keyfigures-example-hallucination-2026-05-28", _rw_stems) == "keyfigures-example-hallucination"
      and ms.resolve_wikilink("nonexistent-thing-here", _rw_stems) is None
      and ms.resolve_wikilink("form_table_research_2026_05_28", _rw_stems) == "form_table_research_2026_05_28"  # exact wins
      and ms.resolve_wikilink("form-table-research", _rw_stems) is None)        # ambiguous date-base (two dated siblings) → None
# v0.1.21 (D7): _standing_baseline FAILS OPEN — only a dict with an int `facts` yields a baseline; else None (gate fires).
check("v0.1.21: _standing_baseline returns the int baseline only for a well-formed dict, else None (fail-open)",
      ms._standing_baseline({"facts": 42}) == 42
      and ms._standing_baseline("garbage") is None
      and ms._standing_baseline({}) is None
      and ms._standing_baseline({"facts": "12"}) is None
      and ms._standing_baseline(None) is None)

# v0.1.22: audit_snapshot_path is per-slug + deterministic (sibling of cycle_seed_path).
check("v0.1.22: audit_snapshot_path is per-slug + deterministic, distinct from the cycle path",
      ms.audit_snapshot_path("-a") == ms.audit_snapshot_path("-a")
      and ms.audit_snapshot_path("-a") != ms.audit_snapshot_path("-b")
      and ms.audit_snapshot_path("-a") != ms.cycle_seed_path("-a")
      and ms.audit_snapshot_path("-a").endswith("cm-audit-a.json"))
# v0.1.22: audit_diff classifies created/modified/deleted by content-hash; unchanged ≠ op.
_a_before = {"memory/keep.md": {"hash": "h1", "tokens": 5, "store": "memory"},
             "memory/edit.md": {"hash": "h2", "tokens": 5, "store": "memory"},
             "memory/gone.md": {"hash": "h3", "tokens": 4, "store": "memory"}}
_a_after = {"memory/keep.md": {"hash": "h1", "tokens": 5, "store": "memory"},      # unchanged
            "memory/edit.md": {"hash": "hX", "tokens": 9, "store": "memory"},      # modified
            "memory/new.md": {"hash": "h4", "tokens": 7, "store": "memory"}}       # created
_ad = ms.audit_diff(_a_before, _a_after)
_adops = {o["path"].rsplit("/", 1)[-1]: o["op"] for o in _ad["operations"]}
check("v0.1.22: audit_diff = created/modified/deleted by hash; unchanged is NOT an op",
      _adops == {"edit.md": "modified", "gone.md": "deleted", "new.md": "created"}
      and _ad["memory"]["created"] == 1 and _ad["memory"]["modified"] == 1 and _ad["memory"]["deleted"] == 1)
# v0.1.22 (Gate-2): the BEFORE snapshot is untrusted — a malformed/legacy entry must NOT crash audit_diff.
check("v0.1.22: audit_diff is robust to a malformed before-snapshot (missing tokens · bad store · non-dict)",
      ms.audit_diff({"memory/x.md": {"hash": "a"},                                  # missing tokens
                     "memory/y.md": {"hash": "h", "tokens": 5, "store": "weird"},   # unexpected store → clamped
                     "memory/z.md": "not-a-dict"},                                  # non-dict entry
                    {"memory/x.md": {"hash": "b", "tokens": 9, "store": "memory"}})["memory"]["modified"] == 1)

# v0.1.23 (D6): _standing_baseline_tokens fails OPEN exactly like _standing_baseline (only a well-formed int yields a baseline).
check("v0.1.23: _standing_baseline_tokens returns the int baseline only for a well-formed dict, else None (fail-open)",
      ms._standing_baseline_tokens({"index_tokens": 2000}) == 2000
      and ms._standing_baseline_tokens({"facts": 5}) is None          # facts present, index_tokens missing
      and ms._standing_baseline_tokens("garbage") is None
      and ms._standing_baseline_tokens({"index_tokens": "12"}) is None  # stringified → not int
      and ms._standing_baseline_tokens(None) is None)
# v0.1.23 (D10): resolve_wikilink finds an archive/index stem when it's in the valid-target set (the [[SHIPPED]] fix is set-membership).
check("v0.1.23: resolve_wikilink resolves an archive/index ref present in the valid-target set (D10)",
      ms.resolve_wikilink("SHIPPED", {"a", "b", "SHIPPED", "MEMORY"}) == "SHIPPED"
      and ms.resolve_wikilink("MEMORY", {"a", "b", "SHIPPED", "MEMORY"}) == "MEMORY"
      and ms.resolve_wikilink("SHIPPED", {"a", "b"}) is None)          # absent from the set → unresolved (correctly)

# v0.1.24 (SAFETY backstop): _has_normative_marker catches a binding directive in a relocate's moving chunk.
check("v0.1.24: _has_normative_marker flags RFC-2119/imperative directives (+ smart-quote/spacing), not plain prose",
      ms._has_normative_marker("you MUST keep src/ pyright-clean")
      and ms._has_normative_marker("never delete the canonical")
      and ms._has_normative_marker("Always run the gate")
      and ms._has_normative_marker("Don’t commit secrets")          # Gate-2 1a: smart-quote apostrophe
      and ms._has_normative_marker("DO  NOT  edit this")                 # Gate-2 1a: irregular DO NOT spacing
      and not ms._has_normative_marker("the rationale is batching improves throughput")
      and not ms._has_normative_marker("mustard and almonds"))            # word-boundary: 'must' in 'mustard' ≠ a marker
# v0.1.24 (SAFETY firewall): valid_relocate_target REJECTS outside-repo / private-store / .. -escape (these
# short-circuit before the git check, so they're testable without a git fixture; the gitignored case is Probe Q).
_fakerepo = Path("/home/nobody/some-repo")
check("v0.1.24: valid_relocate_target rejects outside-repo, private-store, and .. -escape targets",
      ms.valid_relocate_target("/tmp/elsewhere.md", _fakerepo) is False
      and ms.valid_relocate_target(str(Path.home() / ".claude" / "x.md"), _fakerepo) is False
      and ms.valid_relocate_target("../escape.md", _fakerepo) is False)

# --- hardening: SHA validation rejects argument-injection from a tampered state file ---
check("sha: accepts real hex sha", ms._valid_sha("b6d37b6") and ms._valid_sha("a" * 40))
check("sha: rejects git option injection", not ms._valid_sha("--output=/etc/passwd"))
check("sha: rejects empty / junk", not ms._valid_sha("") and not ms._valid_sha("HEAD; rm -rf"))

# --- dashboard outcome classification (data-driven banner) ---
def _oc(writes: int, cands: int, git: int, reviewed: int) -> str:
    entries = [{"action": "added"} for _ in range(writes)]
    return rd._outcome({"entries": entries,
                        "scope": {"session_candidates": cands, "git_commits": git,
                                  "memories_reviewed": reviewed}})


check("outcome: nothing", _oc(0, 0, 0, 0) == "NOTHING TO CONSOLIDATE")
check("outcome: no-op", _oc(0, 0, 0, 5).startswith("NO-OP"))
check("outcome: light", _oc(1, 1, 0, 1) == "LIGHT PASS")
check("outcome: substantial", _oc(4, 8, 12, 5) == "SUBSTANTIAL PASS")
check("dashboard renders banner", "DREAM · consolidate-memory" in
      rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))

# --- rigor tier (v0.1.3): FLOW magnitude → tier; provisional/final; NO memories_reviewed ---
import inspect as _inspect  # noqa: E402
check("rigor: LIGHT at magnitude <= 2",
      ms.suggested_tier(2, 0) == "LIGHT" and ms.suggested_tier(0, 2) == "LIGHT" and ms.suggested_tier(1, 1) == "LIGHT")
check("rigor: SUBSTANTIAL 3..7",
      ms.suggested_tier(3, 0) == "SUBSTANTIAL" and ms.suggested_tier(4, 3) == "SUBSTANTIAL" and ms.suggested_tier(7, 0) == "SUBSTANTIAL")
check("rigor: HEAVY at >= 8", ms.suggested_tier(8, 0) == "HEAVY" and ms.suggested_tier(5, 5) == "HEAVY")
_ord = ms.TIER_ORDER  # canonical tier rank (single source in memory_status)
check("rigor: monotonic non-decreasing in magnitude",
      all(_ord[ms.suggested_tier(0, m)] <= _ord[ms.suggested_tier(0, m + 1)] for m in range(0, 20)))
# F1 regression guard: the magnitude axis is FLOW-only; the cumulative stock
# (memories_reviewed) must NOT be a parameter, or a mature store pegs every pass to HEAVY.
check("rigor: suggested_tier excludes memories_reviewed (F1 axis-separation guard)",
      "memories_reviewed" not in _inspect.signature(ms.suggested_tier).parameters
      and "reviewed" not in _inspect.signature(ms.suggested_tier).parameters)
# prune-pressure: the SEPARATE axis the stock drives
check("rigor: prune_pressure on index-over-budget", ms.prune_pressure(True, 0) == (True, "index-over-budget"))
check("rigor: prune_pressure on many-facts at threshold", ms.prune_pressure(False, ms.PRUNE_PRESSURE_FACTS) == (True, "many-facts"))
check("rigor: prune_pressure clear when small + under budget", ms.prune_pressure(False, ms.PRUNE_PRESSURE_FACTS - 1) == (False, ""))
check("rigor: index-over takes reason precedence over many-facts", ms.prune_pressure(True, 999)[1] == "index-over-budget")
# A10: no-marker first pass — git_range defaults to a recent-≤20 lookback, so a mature repo's
# FIRST consolidation reads HEAVY provisional purely from history depth (documented, advisory;
# the model finalizes in Phase 2). The seed rigor block is phase:provisional regardless.
check("rigor: no-marker 20-commit lookback → HEAVY provisional (A10)", ms.suggested_tier(20, 0) == "HEAVY")
# v0.1.10: dream-timing advisory — a NO-NAG Phase-0 nudge; pure + never-crash; explicit-trigger-only.
_dt_a = ms.dream_timing_advisory(3, "2020-01-01T00:00:00+00:00", True)
check("dream-timing: SUBSTANTIAL accrued + marker → nudge string with age (v0.1.10)",
      isinstance(_dt_a, str) and "dream-timing" in _dt_a and "SUBSTANTIAL" in _dt_a and "ago" in _dt_a)
check("dream-timing: below the band (commits <= 2) → None / no-nag (v0.1.10)",
      ms.dream_timing_advisory(2, "2020-01-01T00:00:00+00:00", True) is None)
_dt_g = ms.dream_timing_advisory(8, "not-a-timestamp", True)
check("dream-timing: garbage marker_ts → string, age omitted, no crash (v0.1.10)",
      isinstance(_dt_g, str) and "HEAVY" in _dt_g and "ago" not in _dt_g)
check("dream-timing: NO marker (first consolidation) → None even at HEAVY commits (v0.1.10 Gate-1 guard)",
      ms.dream_timing_advisory(8, "2020-01-01T00:00:00+00:00", False) is None)
check("dream-timing: future-dated marker → age clamped to '<1h' (v0.1.10)",
      "<1h" in (ms.dream_timing_advisory(8, "2099-01-01T00:00:00+00:00", True) or ""))
check("rigor: provisional rigor block is phase:provisional, no stored tier (A10)",
      ms._provisional_rigor({"index_lb": (0, 0, 0), "fact_files": []})
      == {"phase": "provisional", "prune_pressure": False, "prune_reason": "",
          "applied": "", "override_reason": ""})
check("rigor: seed includes empty applied/override_reason, model fills in Phase 2/4 (v0.1.4)",
      ms._provisional_rigor({"index_lb": (0, 0, 0), "fact_files": []})["applied"] == ""
      and ms._provisional_rigor({"index_lb": (0, 0, 0), "fact_files": []})["override_reason"] == "")
# render: the RIGOR line shows a tier + magnitude BOTH DERIVED from scope (never stored)
# NOTE (v0.1.6): render() now takes ms.CycleRecord. The fixtures below are MODEL-AUTHORED-
# shaped — many deliberately carry malformed/wrong-typed values to prove render NEVER
# crashes (the _num/_clean/_flag boundary). That is consumer-side input where the TypedDict
# gives ~zero static value (spec F2), so we cast(ms.CycleRecord, …) at this trust boundary —
# the spec-endorsed escape hatch (it also casts json.loads → CycleRecord), NOT a disabled
# check. The producer-side contract (seed_record/_demo_record literals in scripts/) stays
# fully checked.
_rrec = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {"git_commits": 6, "session_candidates": 9},
         "entries": [], "rigor": {"phase": "final", "prune_pressure": True, "prune_reason": "many-facts"}})
check("render: rigor line shows derived tier (6+9=15 → HEAVY)", "RIGOR" in rd.render(_rrec) and "HEAVY" in rd.render(_rrec))
check("render: rigor magnitude DERIVED from scope (6+9=15)", "magnitude 15" in rd.render(_rrec))
check("render: prune-pressure surfaced on the rigor line", "prune-pressure" in rd.render(_rrec))
check("render: legacy record without rigor omits the line (no crash)",
      "RIGOR" not in rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))
# A1 regression: the displayed tier is DERIVED from the magnitude, NEVER a stored label —
# a stale/contradictory stored suggested_tier must not reach the RIGOR line.
_drift = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {"git_commits": 8, "session_candidates": 7},
          "entries": [], "rigor": {"suggested_tier": "LIGHT", "phase": "final"}})  # stored LIGHT is a lie: mag=15
_drift_line = next((ln for ln in rd.render(_drift).splitlines() if "RIGOR" in ln), "")
check("render: tier DERIVED from magnitude, ignores a contradictory stored suggested_tier (A1)",
      "HEAVY" in _drift_line and "LIGHT" not in _drift_line)
# A2: a present-but-empty rigor {} still renders the derived line (presence, not truthiness)
check("render: empty rigor {} still shows the derived RIGOR line (A2)",
      "RIGOR" in rd.render({"project": "p", "session": "s", "scope": {"git_commits": 3, "session_candidates": 0},
                            "entries": [], "rigor": {}}))
# v0.1.4: the realized-rigor `applied` decision renders "suggested → applied · why" ONLY when it
# DIFFERS from the magnitude-derived suggested tier; absent/empty/equal renders unchanged (back-compat).
_app = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {"git_commits": 10, "session_candidates": 3},
        "entries": [], "rigor": {"phase": "final", "applied": "LIGHT",
                                 "override_reason": "already-consolidated flow"}})
_app_line = next((ln for ln in rd.render(_app).splitlines() if "RIGOR" in ln), "")
check("render: applied≠suggested shows 'HEAVY → LIGHT' (v0.1.4)",
      "HEAVY" in _app_line and "→" in _app_line and "LIGHT" in _app_line)
check("render: override_reason shown when applied differs (v0.1.4)", "already-consolidated flow" in _app_line)
check("render: override note uses '· override:' label, not the old '· applied:' (v0.1.9)",
      "override:" in _app_line and "applied:" not in _app_line)
# v0.1.35 — remediation-resolution coherence (beta-test-confirmed bug): a rebuild-lean (pruned=0) that brought
# the index UNDER budget RESOLVED the gate — it is "acted on", NOT "gate fired but not acted on".
_rem_lean = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
        "budget": {"index": {"after_tokens": 900, "budget_tokens": 1200, "over": False}},
        "remediation": {"required": True, "lever": "prune", "candidates_surfaced": 1, "pruned": 0,
                        "achieved_index": 900, "projected_index": 480, "reaches_budget": True}})
_rem_lean_out = rd.render(_rem_lean)
check("v0.1.35: rebuild-lean-resolved gate (pruned=0, achieved≤budget) renders RESOLVED, not 'not acted on'",
      "resolved by rebuild-lean" in _rem_lean_out and "not acted on" not in _rem_lean_out)
check("v0.1.35: a gate STILL over budget (pruned=0, achieved>budget) DOES warn 'not acted on'",
      "not acted on" in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
          "budget": {"index": {"after_tokens": 1500, "budget_tokens": 1200, "over": True}},
          "remediation": {"required": True, "lever": "prune", "candidates_surfaced": 1, "pruned": 0,
                          "achieved_index": 1500, "projected_index": 480, "reaches_budget": False}})))
# v0.1.36 — the remediation block gates on `required`, NOT mere presence: a record carrying
# remediation={required:false} (the schema default) must render NO over-budget block.
check("v0.1.36: required=false renders NO over-budget block (gate on `required`, not presence)",
      "REMEDIATION" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
          "budget": {"index": {"after_tokens": 900, "budget_tokens": 1200, "over": False}},
          "remediation": {"required": False}})))
check("v0.1.36: required=true still renders the over-budget block (the safety gate is preserved)",
      "REMEDIATION" in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
          "budget": {"index": {"after_tokens": 1500, "budget_tokens": 1200, "over": True}},
          "remediation": {"required": True, "lever": "prune", "candidates_surfaced": 1, "pruned": 0,
                          "achieved_index": 1500, "projected_index": 480, "reaches_budget": False}})))
# v0.1.37 — the no-op self-heal pivot: a pivoted maintenance pass (pivoted=true, 0 writes) renders
# MAINTENANCE PASS, not the misleading NOTHING/NO-OP. The banner branch is gated on `pivoted`.
check("v0.1.37: a pivoted no-op (maintenance.pivoted, 0 writes) renders MAINTENANCE PASS",
      "MAINTENANCE PASS" in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s",
          "scope": {"memories_reviewed": 19}, "entries": [], "maintenance": {"pivoted": True, "work": True, "dangling": 6}})))
check("v0.1.37: a non-pivoted no-op does NOT render MAINTENANCE PASS (branch gated on pivoted)",
      "MAINTENANCE PASS" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s",
          "scope": {"memories_reviewed": 19}, "entries": []})))
# v0.1.37 — dangling_links() is the SINGLE-SOURCE helper (Phase-0 maintenance + Phase-5 health both call it):
# finds a dangling [[wikilink]], resolves a valid one, ignores an inline-code-span [[...]] (R3).
import tempfile as _tf37  # noqa: E402
with _tf37.TemporaryDirectory() as _td37:
    _s37 = Path(_td37)
    (_s37 / "alpha.md").write_text("---\nname: alpha\n---\nrefs [[beta]] (valid) · [[ghost-fact]] (dangling) · `[[code.span]]` (ignored)\n\n```toml\n[[fenced.ghost]]\n```\n")
    (_s37 / "beta.md").write_text("---\nname: beta\n---\nbody\n")
    check("v0.1.37: dangling_links finds [[ghost-fact]]; resolves [[beta]]; ignores inline + FENCED code spans",
          ms.dangling_links(_s37) == ["ghost-fact"])
# v0.1.52 — cross-store resolution: dangling_links(auto_mem, global_dir) resolves a pending-pull up-link to a
# global-only fact (Class B, the recurring false positive) while a sibling-project-local DOWN-link stays
# flagged (Class A, a true positive — unreachable here). global_dir=None/missing ⇒ byte-identical legacy.
import tempfile as _tf52  # noqa: E402
with _tf52.TemporaryDirectory() as _td52l, _tf52.TemporaryDirectory() as _td52g:
    _loc52, _glob52 = Path(_td52l), Path(_td52g)
    (_loc52 / "host.md").write_text("---\nname: host\n---\nup-link [[only-in-global]] (pending-pull) · down-link [[ghost-nowhere]] (unreachable)\n")
    (_glob52 / "only-in-global.md").write_text("---\nname: only-in-global\n---\nbody\n")
    check("v0.1.52: cross-store resolves a pending-pull up-link; a sibling-local down-link stays flagged (Class A)",
          ms.dangling_links(_loc52, global_dir=_glob52) == ["ghost-nowhere"])
    check("v0.1.52: global_dir=None is byte-identical legacy local-only (backward-compat; Class A still flagged)",
          ms.dangling_links(_loc52) == ["ghost-nowhere", "only-in-global"])
    check("v0.1.52: a MISSING global_dir collapses to legacy (the fresh-machine first-run path)",
          ms.dangling_links(_loc52, global_dir=_loc52 / "no-such-global") == ms.dangling_links(_loc52))
    # ISOLATION invariant: dangling_links globs ONLY auto_mem's *.md for links — the global store contributes
    # to the target SET but is never SCANNED. So a global-only dangling link must NOT leak into a local scan's
    # output (else a future union-the-scan refactor would surface OTHER projects' dangling links here).
    (_glob52 / "gphantom.md").write_text("---\nname: gphantom\n---\na global-only dangling [[global-ghost]]\n")
    check("v0.1.52: a global-only dangling link never leaks into a LOCAL scan (cross-store isolation)",
          "global-ghost" not in ms.dangling_links(_loc52, global_dir=_glob52))
# v0.1.38 (M1) — the projected net-grow guard (sync_global._would_net_grow), the SINGLE source for the
# pull-hold decision. The NEAR-budget overshoot (case 2) is the bug v0.1.37's cue-with-a-before-compare missed:
# `index > BUDGET` was False on a near-budget store, so it let the pull tip the index over.
_B38 = ms.INDEX_TOKEN_BUDGET
check("v0.1.38/M1: an over-budget store holds ANY new pull (case 1)", sg._would_net_grow(_B38 + 1561, 40, False) is True)
check("v0.1.38/M1: a NEAR-budget store holds a pull that would overshoot (case 2 — the v0.1.37 miss)",
      sg._would_net_grow(_B38 - 10, 40, False) is True)
check("v0.1.38/M1: an under-budget store with room PULLS (no false hold)", sg._would_net_grow(800, 40, False) is False)
check("v0.1.38/M1: a pull that fits EXACTLY to budget is allowed (boundary: ==budget, not >)",
      sg._would_net_grow(_B38 - 40, 40, False) is False)
check("v0.1.38/M1: --allow-net-grow overrides the guard", sg._would_net_grow(_B38 + 1561, 40, True) is False)
check("v0.1.38/M1: cross_project.held renders the LOUD lever (RENDER half only — the stdout→record capture is a SKILL Phase-1 instruction, model-driven, not script-testable here)",
      "held 2" in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {"git_commits": 1},
          "entries": [], "cross_project": {"held": 2}})))
# v0.1.39 (M2) — _bodies_match: frontmatter-stripped, whitespace-normalized BODY compare (the promote()
# reconcile data-loss guard). Identical body / differing frontmatter → True; a re-framed body → False.
check("v0.1.39/M2: _bodies_match True on identical body despite differing frontmatter",
      sg._bodies_match("---\na: 1\n---\nThe lesson.\n\n- pt\n", "---\nb: 2\nprojects: [p]\n---\nThe lesson.\n\n- pt\n") is True)
check("v0.1.39/M2: _bodies_match False on a re-framed body (the silent-data-loss case promote() now refuses)",
      sg._bodies_match("---\na: 1\n---\nThe lesson.\n", "---\na: 1\n---\nThe lesson, RE-FRAMED.\n") is False)
check("v0.1.39/M2: _body strips ONLY the leading frontmatter, preserving `---` rules in the body (not split('---'))",
      sg._body("---\nn: x\n---\nintro\n\n---\n\nmore") == "intro\n\n---\n\nmore")
check("v0.1.39/M2 (Gate-2): _bodies_match normalizes CRLF + strips BOM (no false refuse on editor artifacts)",
      sg._bodies_match("---\na: 1\r\n---\r\nThe lesson.\r\n", "﻿---\nb: 2\n---\nThe lesson.\n") is True)
# v0.1.39 (M4) — promote() Guard-2 validates stack-general stacks: ⊆ _DETECTABLE_STACKS (the closed vocab).
# Gate-2 (M24GuardFinder): pin _DETECTABLE_STACKS to detect_stacks's ACTUAL codomain via a fixture triggering
# every stack — so a future detect_stacks `.add(...)` marker not mirrored into the constant FAILS here (a
# hardcoded subset can't catch a too-small constant → the fleet-dead false-refuse would silently return).
with _tf37.TemporaryDirectory() as _td39:
    _p39 = Path(_td39)
    (_p39 / "pyproject.toml").write_text('[project]\ndependencies = ["sentence-transformers", "torch", "playwright", "pypdfium2", "mypy"]\n[tool.mypy]\nstrict = true\n')
    (_p39 / ".claude").mkdir()
    check("v0.1.39/M4: _DETECTABLE_STACKS == detect_stacks codomain (fixture triggers every stack; catches a new .add marker)",
          sg.detect_stacks(_p39) == sg._DETECTABLE_STACKS)
check("v0.1.39/M4: an undetectable stack is NOT in the vocab ([release]/[ci-cd] → fleet-dead, refused)",
      not ({"release", "ci-cd"} <= sg._DETECTABLE_STACKS))
# v0.1.40 (M3) — slug_for generalizes to ALL non-alphanumerics (CC's rule), fixing the '.'-segment split-brain;
# regression-IDENTICAL for the fleet; near_duplicate_slugs uses the same rule so a '.'-vs-'-' twin is detected.
check("v0.1.40/M3: slug_for maps '.' (a dotfile-dir path) → '-', matching CC (was split-brain)",
      ms.slug_for(Path("/home/u/.claude/app")) == "-home-u--claude-app")
check("v0.1.40/M3: slug_for is regression-IDENTICAL for the fleet (paths with only / _ -)",
      ms.slug_for(Path("/home/drei/project/Doc_Flo")) == "-home-drei-project-Doc-Flo")
check("v0.1.40/M3: near_duplicate_slugs catches a '.'-vs-'-' twin (the split-brain detector, was '_'/case-only)",
      ms.near_duplicate_slugs("-home-u-.claude-app", ["-home-u--claude-app", "-unrelated"]) == ["-home-u--claude-app"])
_eq_line = next((ln for ln in rd.render({"project": "p", "session": "s",
                 "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                 "rigor": {"phase": "final", "applied": "HEAVY"}}).splitlines() if "RIGOR" in ln), "")
check("render: applied==suggested shows no arrow (v0.1.4)", "→" not in _eq_line and "HEAVY" in _eq_line)
check("render: empty applied → derived tier only, no arrow (v0.1.4)",
      "→" not in next((ln for ln in rd.render({"project": "p", "session": "s",
                       "scope": {"git_commits": 1, "session_candidates": 0}, "entries": [],
                       "rigor": {"phase": "final", "applied": ""}}).splitlines() if "RIGOR" in ln), ""))
check("render: non-string applied doesn't crash, renders the line (v0.1.4)",
      "RIGOR" in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {"git_commits": 1, "session_candidates": 0},
                            "entries": [], "rigor": {"applied": 5}})))
check("render: whitespace ' HEAVY ' applied is normalized → NO spurious 'X → X' arrow (v0.1.4)",
      "→" not in next((ln for ln in rd.render({"project": "p", "session": "s",
                       "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                       "rigor": {"applied": " HEAVY "}}).splitlines() if "RIGOR" in ln), ""))
check("render: unrecognized applied value → no arrow, suggested tier only (v0.1.4)",
      "→" not in next((ln for ln in rd.render({"project": "p", "session": "s",
                       "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                       "rigor": {"applied": "banana"}}).splitlines() if "RIGOR" in ln), ""))
check("render: case-insensitive applied 'light' still shows the override arrow (v0.1.4)",
      "→" in next((ln for ln in rd.render({"project": "p", "session": "s",
                   "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                   "rigor": {"applied": "light"}}).splitlines() if "RIGOR" in ln), ""))
# A5: a JSON-stringified 'false' prune_pressure must NOT trip the warning (_flag coercion)
check("render: stringized 'false' prune_pressure shows no warning (A5/_flag)",
      "prune-pressure" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s",
          "scope": {"git_commits": 1, "session_candidates": 0}, "entries": [],
          "rigor": {"phase": "final", "prune_pressure": "false"}})))
check("render: _flag coerces stringized booleans",
      rd._flag("false") is False and rd._flag("true") is True and rd._flag(True) is True and rd._flag("") is False)
# model-authored gnarly rigor (string/None/wrong-type) must not crash; tier still derived
_grig = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {"git_commits": "7", "session_candidates": None},
         "entries": [], "rigor": {"suggested_tier": 123, "phase": None,
                                   "prune_pressure": "yes", "prune_reason": None}})
_grig_out = rd.render(_grig)
check("render: gnarly rigor never crashes + derives tier (ignores stored 123)",
      isinstance(_grig_out, str) and "RIGOR" in _grig_out and "123" not in _grig_out)
check("demo: rigor tier shown in --demo preview", "RIGOR" in rd.render(rd._demo_record()))

# --- cross-project relevance ---
check("relevance: user-global everywhere", sg.is_relevant({"scope": "user-global"}, set()) is True)
check("relevance: stack-general needs match",
      sg.is_relevant({"scope": "stack-general", "stacks": "[rag, gpu]"}, {"web"}) is False)
check("relevance: stack-general matches",
      sg.is_relevant({"scope": "stack-general", "stacks": "[rag, gpu]"}, {"rag"}) is True)
check("relevance: project-local never global", sg.is_relevant({"scope": "project-local"}, {"rag"}) is False)

# --- mirror stamping is robust + idempotent ---
fact = "---\nname: x\nmetadata:\n  node_type: memory\n---\nbody\n"
mirror = sg._as_mirror(fact, "x")
check("mirror: injects global_ref", "global_ref: x" in mirror)
check("mirror: idempotent", sg._as_mirror(mirror, "x").count("global_ref: x") == 1)
# v0.1.26 (provenance-churn root-fix): the canonical-only `projects:` provenance is NEVER carried into a
# mirror — eliminates cross-fleet staleness when a pull grows a canonical's holder list. Frontmatter-scoped:
# a prose body line starting "projects:" must SURVIVE; the round-trip + frontmatter validity must hold.
_canon_prov = "---\nname: y\nmetadata:\n  node_type: memory\n  scope: user-global\n  projects: [a, b, c]\n---\nbody\nprojects: prose survives\n"
_mir_prov = sg._as_mirror(_canon_prov, "y")
check("v0.1.26: _as_mirror strips frontmatter projects:, preserves body, keeps round-trip",
      "projects: [a, b, c]" not in _mir_prov            # frontmatter provenance gone
      and "projects: prose survives" in _mir_prov        # body line untouched (FM-scoped)
      and sg._is_mirror(_mir_prov) is True               # load-bearing round-trip
      and sg._frontmatter(_mir_prov).get("scope") == "user-global")  # frontmatter still parses

# --- retrieval safety: secret omission + noise filtering ---
check("retrieval: secret pattern hit (long token)", bool(es._looks_secret("AQ3D" + "x7Y2k9" * 9)))
# precision: long file paths / all-letter slugs must NOT be flagged (recall-preserving)
check("retrieval: long path NOT flagged",
      not es._looks_secret("/home/you/project/consolidate-memory/plugins/consolidate-memory/scripts/"))
check("retrieval: all-letter slug NOT flagged",
      not es._looks_secret("home-you-project-consolidate-memory-plugins-consolidate-memory"))
check("retrieval: OpenAI sk- key flagged", bool(es._looks_secret("sk-proj-" + "a1B2c3D4e5F6g7H8i9J0")))
check("retrieval: secret pattern hit (named)", bool(es._looks_secret("password = hunter2")))
check("retrieval: plain text not flagged", not es._looks_secret("fix the indeed scraper please"))
check("retrieval: noise drops command echo", bool(es._NOISE.match("<local-command-stdout>x</...>")))
check("retrieval: noise drops caveat", bool(es._NOISE.match("Caveat: messages below ...")))
check("retrieval: real turn not noise", not es._NOISE.match("Please fix this at the root with tests"))
_t, _scope, score = es._classify("Always validate at the root with tests")
check("retrieval: marker classified preference", _t == "preference" and score == 2)
check("retrieval: bare ack ranked lowest", es._classify("yes")[2] == 0)

# --- token estimation (Fix A / observability) ---
check("tokens: empty is 0", ms.est_tokens("") == 0)
check("tokens: ceil(chars/4)", ms.est_tokens("abcdefgh") == 2 and ms.est_tokens("abcde") == 2)
check("tokens: monotonic", ms.est_tokens("a" * 100) > ms.est_tokens("a" * 10))
# the sibling import must resolve to the SAME function (catches path breakage at the gate)
check("tokens: sync_global reuses memory_status.est_tokens", sg.est_tokens is ms.est_tokens)

# --- Fix C: index pointer is now an upsert (pure line builder) ---
check("pointer: builds line with scope tag",
      sg._pointer_line("foo", {"description": "a hook", "scope": "user-global"})
      == "- [foo](foo.md) — a hook [user-global]")
check("pointer: truncates long description to a recall hook",
      sg._pointer_line("foo", {"description": "x" * 200}).count("…") == 1)
check("pointer: strips control bytes/newlines from the hook (no index injection)",
      "\n" not in sg._pointer_line("foo", {"description": "a\nb\x1b[31mc"}) and
      "\x1b" not in sg._pointer_line("foo", {"description": "a\nb\x1b[31mc"}))
# frontmatter parses folded/block scalars (description: >-) instead of storing ">-"
check("frontmatter: folds block scalar value",
      sg._frontmatter("---\nname: x\ndescription: >-\n  hello\n  world\nmetadata:\n  scope: user-global\n---\nb")["description"] == "hello world")
check("frontmatter: single-line value unchanged",
      sg._frontmatter("---\nname: x\ndescription: plain hook\n---\nb")["description"] == "plain hook")

# --- v0.1.5: orphan + drift detection (PURE helpers — strings/sets/dicts only; FS-touching
#     cases live in simulate_accumulation.py since smoke must not mutate the filesystem) ---
# _frontmatter is now PROMOTED to memory_status (single definition); sync_global imports it.
check("v0.1.5: sync_global._frontmatter IS memory_status._frontmatter (single definition)",
      sg._frontmatter is ms._frontmatter)
# _frontmatter tolerates a malformed file ({}), a CRLF file, and a BOM-prefixed file — and
# all healthy variants must still extract node_type (else schema_drift miscounts them).
check("frontmatter: malformed (no fence) returns {} (never raises)",
      ms._frontmatter("not frontmatter at all\njust text\n") == {})
_normal_fm = ms._frontmatter("---\nname: x\nmetadata:\n  node_type: memory\n---\nbody\n")
check("frontmatter: parses a normal block (node_type captured)", _normal_fm.get("node_type") == "memory")
check("frontmatter: CRLF file still extracts node_type (M3)",
      ms._frontmatter("---\r\nname: x\r\nmetadata:\r\n  node_type: memory\r\n---\r\nbody\r\n").get("node_type") == "memory")
check("frontmatter: BOM-prefixed file still extracts node_type (M3)",
      ms._frontmatter("﻿---\nname: x\nmetadata:\n  node_type: memory\n---\nbody\n").get("node_type") == "memory")
# _valid_uuid: a real 8-4-4-4-12 hex UUID accepted; truncated / garbage rejected.
check("uuid: accepts a real 8-4-4-4-12 UUID",
      ms._valid_uuid("1920c541-0f32-4b9d-8b0b-1da262a307b0"))
check("uuid: rejects truncated / garbage / non-string",
      not ms._valid_uuid("1920c541-0f32-4b9d-8b0b") and not ms._valid_uuid("not-a-uuid")
      and not ms._valid_uuid("") and not ms._valid_uuid(None))
# near_duplicate_slugs: flags '-'/'_'/case twins, ignores unrelated, NEVER flags itself (B2).
_slug = "-home-drei-project-Doc-Flo"
_sibs = ["-home-drei-project-Doc-Flo", "-home-drei-project-Doc_Flo",
         "-home-drei-project-doc-flo", "-home-drei-project-other"]
check("near-dup: flags '_' and case variants, excludes self + unrelated",
      ms.near_duplicate_slugs(_slug, _sibs)
      == ["-home-drei-project-Doc_Flo", "-home-drei-project-doc-flo"])
check("near-dup: a slug is never its own duplicate (B2 self-exclusion)",
      ms.near_duplicate_slugs(_slug, [_slug]) == [])
check("near-dup: no twins → empty list", ms.near_duplicate_slugs(_slug, ["-x", "-y-z"]) == [])
# drift_findings: dict → int; counts the four DRIFT fields, NOT the advisory absence-counts.
check("drift_findings: sums the four drift fields, ignores advisory absence",
      ms.drift_findings({"missing_node_type": 1, "malformed_scope": 2, "malformed_origin": 0,
                         "index_mismatch": 3, "advisory_no_scope": 99, "advisory_no_origin": 99}) == 6)
check("drift_findings: all-zero drift → 0 (defines 'clean' for AC#1)",
      ms.drift_findings({"missing_node_type": 0, "malformed_scope": 0, "malformed_origin": 0,
                         "index_mismatch": 0, "advisory_no_scope": 5, "advisory_no_origin": 5}) == 0)
check("drift_findings: tolerant of missing keys (.get default 0)", ms.drift_findings({}) == 0)
# render: HEALTH surfaces slug-orphan + schema-drift findings (presence-checked) ...
_h_orphan = rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
                       "health": {"index_pointers_ok": True, "slug_orphans": ["-home-x-Doc_Flo"],
                                  "schema_drift": {"missing_node_type": 2, "malformed_scope": 0,
                                                   "malformed_origin": 0, "index_mismatch": 3}}})
check("render: HEALTH shows slug-orphan twin name", "slug-orphan" in _h_orphan and "Doc_Flo" in _h_orphan)
check("render: HEALTH shows schema-drift counts when drift_findings > 0",
      "schema drift" in _h_orphan and "missing node_type" in _h_orphan)
# ... and a CLEAN store (no drift, advisory-only) shows NO drift ⚠ in HEALTH (AC#3)
_h_clean = rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
                      "health": {"index_pointers_ok": True, "slug_orphans": [],
                                 "schema_drift": {"missing_node_type": 0, "malformed_scope": 0,
                                                  "malformed_origin": 0, "index_mismatch": 0,
                                                  "advisory_no_scope": 9, "advisory_no_origin": 9}}})
check("render: clean store shows no drift/orphan ⚠ in HEALTH (AC#3)",
      "schema drift" not in _h_clean and "slug-orphan" not in _h_clean and "✓ all pointers resolve" in _h_clean)
# LEGACY record (no slug_orphans/schema_drift keys) must render BYTE-IDENTICALLY (AC#5).
# Typed dict[str, Any] (not ms.CycleRecord): this fixture is then DEEP-COPIED and MUTATED
# with nested-key assignments; a plain dict keeps that simple, and render() accepts it via
# the cast at each call below.
_legacy: dict[str, Any] = {"project": "p", "session": "s", "scope": {}, "entries": [],
           "health": {"index_pointers_ok": True, "broken": [], "dangling_links": []}}
import copy as _copy  # noqa: E402
_legacy_plus = _copy.deepcopy(_legacy)   # same record WITH the v0.1.5 keys present-but-empty
_legacy_plus["health"]["slug_orphans"] = []
_legacy_plus["health"]["schema_drift"] = {}
_R = ms.CycleRecord  # local alias to keep the cast wraps below terse
check("render: empty v0.1.5 keys render identically to a legacy record (AC#5 back-compat)",
      rd.render(cast(_R, _legacy)) == rd.render(cast(_R, _legacy_plus)))
check("render: legacy render is deterministic + non-mutating",
      rd.render(cast(_R, _legacy)) == rd.render(cast(_R, _copy.deepcopy(_legacy))))
check("render: legacy health has no slug-orphan/schema-drift line (AC#5)",
      "slug-orphan" not in rd.render(cast(_R, _legacy)) and "schema drift" not in rd.render(cast(_R, _legacy)))
# model-authored health: a NON-numeric schema_drift value must NOT crash render (the
# _num/_clean/_flag never-crash invariant) — render coerces at the boundary, unlike the
# strict-int ms.drift_findings used by the seed/smoke with clean ints.
_gnarly_h = rd.render(cast(_R, {"project": "p", "session": "s", "scope": {}, "entries": [],
                       "health": {"index_pointers_ok": True, "slug_orphans": None,
                                  "schema_drift": {"missing_node_type": "two", "index_mismatch": None}}}))
check("render: non-numeric/None schema_drift never crashes render (model→presentation coercion)",
      isinstance(_gnarly_h, str) and "HEALTH" in _gnarly_h)
# Gate-2 F1: a TRUTHY non-dict schema_drift / non-list slug_orphans (model slip) must not crash —
# `or {}`/`or []` only catch FALSY values; the isinstance guards catch a truthy wrong-type.
# This shape is REUSED below by the validate_cycle_record contract test (v0.1.6).
_gnarly2_rec = {"project": "p", "session": "s", "scope": {}, "entries": [],
                "health": {"index_pointers_ok": True, "slug_orphans": "Doc_Flo",
                           "schema_drift": "2 missing node_type"}}
_gnarly2 = rd.render(cast(_R, _gnarly2_rec))
check("render: truthy non-dict schema_drift / non-list slug_orphans never crash render (Gate-2 F1)",
      isinstance(_gnarly2, str) and "HEALTH" in _gnarly2)

# --- v0.1.16: REAL-USAGE stack detection — the PURE pyproject parser + exact-token maps (FS-pure here;
#     end-to-end detect_stacks is exercised by simulate_accumulation.py Probe D) ---
_pp16 = ('[project]\nname = "x"\n'
         'dependencies = ["torch>=2.1", "uvicorn[standard]", "sentence-transformers>=5"]\n'
         '[project.optional-dependencies]\nserve = ["vllm", "lancedb"]   # faiss only in this comment\n'
         '[tool.poetry.dependencies]\nmypy = "^1"\n')
_dn16 = sg._dep_names_from_text(_pp16)
check("v0.1.16: parser extracts PEP621 + optional-deps + poetry-table dep NAMES",
      {"torch", "uvicorn", "sentence-transformers", "vllm", "lancedb", "mypy"} == _dn16)
check("v0.1.16: parser is EXTRAS-safe — a dep after `uvicorn[standard]` is not truncated",
      "sentence-transformers" in _dn16)
check("v0.1.16: a dep named only in a COMMENT is excluded (string-aware strip)", "faiss" not in _dn16)
_sc16 = sg._strip_toml_comments('dep = "a#b"  # real comment')
check("v0.1.16: comment strip is string-aware (# in a string kept, real comment dropped)",
      "a#b" in _sc16 and "real comment" not in _sc16)
check("v0.1.16: EXACT-token map — sentence-transformers is rag, NEVER gpu (no substring bug)",
      "sentence-transformers" in sg._STACK_DEPS["rag"] and "sentence-transformers" not in sg._STACK_DEPS["gpu"])
check("v0.1.16: is_relevant(stack-general:[rag]) binds a rag project, excludes a non-rag one",
      sg.is_relevant({"scope": "stack-general", "stacks": "rag"}, {"python", "rag"}) is True
      and sg.is_relevant({"scope": "stack-general", "stacks": "rag"}, {"python", "mypy"}) is False)
check("v0.1.16: a `dependencies = [...]` under a TOOL table (not [project]) is NOT leaked",
      "torch" not in sg._dep_names_from_text(
          '[project]\nname = "x"\ndependencies = ["requests"]\n[tool.hatch.envs.t]\ndependencies = ["torch"]\n'))
check("v0.1.16: imports are ast-based — an `import x` inside a docstring is NOT counted",
      sg._imports_in_source('import lancedb\n"""\n    import torch\n"""\n') == {"lancedb"})
# v0.1.17: the `pdf` stack — so PDF-lib gotchas (pdfium thread-unsafety) bind cross-project. Real-usage
# gated like every stack: a declared dep or a real import, NEVER a doc-mention; exact-token (no substring).
check("v0.1.17: pdf dep — a declared pypdfium2 maps to the pdf stack",
      "pypdfium2" in sg._STACK_DEPS["pdf"]
      and "pypdfium2" in sg._dep_names_from_text('[project]\ndependencies = ["pypdfium2>=4.0"]\n'))
check("v0.1.17: pdf import — pymupdf imports as `fitz` (module≠dist), and it's in the pdf import set",
      "fitz" in sg._STACK_IMPORTS["pdf"] and sg._imports_in_source("import fitz\n") == {"fitz"})
check("v0.1.17: pdf is EXACT-token — no pdf token collides with another stack's sets",
      all(sg._STACK_DEPS["pdf"].isdisjoint(sg._STACK_DEPS[s]) for s in ("rag", "gpu", "playwright", "mypy"))
      and all(sg._STACK_IMPORTS["pdf"].isdisjoint(sg._STACK_IMPORTS[s]) for s in ("rag", "gpu", "playwright")))
check("v0.1.17: is_relevant(stack-general:[pdf]) binds a pdf project, excludes a non-pdf one",
      sg.is_relevant({"scope": "stack-general", "stacks": "pdf"}, {"python", "pdf"}) is True
      and sg.is_relevant({"scope": "stack-general", "stacks": "pdf"}, {"python", "rag"}) is False)
check("v0.1.16: _is_mirror is single-source (promoted to memory_status; sync_global imports it)",
      sg._is_mirror is ms._is_mirror)
# promotion-candidate SEED filter (pure; the Phase-1 re-audit's pre-filter)
check("v0.1.16: promotion seed — an unscoped feedback fact IS a candidate",
      ms._is_promotion_candidate("---\nname: x\nmetadata:\n  type: feedback\n---\nb\n") is True)
check("v0.1.16: promotion seed — a type:project fact is NOT",
      ms._is_promotion_candidate("---\nname: y\nmetadata:\n  type: project\n---\nb\n") is False)
check("v0.1.16: promotion seed — an already-scoped fact is NOT",
      ms._is_promotion_candidate("---\nname: z\nmetadata:\n  type: feedback\n  scope: user-global\n---\nb\n") is False)
check("v0.1.16: promotion seed — a mirror is NOT (already global)",
      ms._is_promotion_candidate("---\nname: m\nmetadata:\n  global_ref: m\n  type: feedback\n---\nb\n") is False)
# promotion stacks-guard helper (pure): the set is_relevant intersects AND the dead-canonical guard
# refuses on. A stack-general fact with an empty set can match no project — promote() must reject it.
check("v0.1.16: _fact_stacks — tags parse to a set; empty/absent → empty set (the dead-canonical case)",
      sg._fact_stacks({"stacks": "[rag, gpu]"}) == {"rag", "gpu"} and sg._fact_stacks({}) == set())
# --promote writes the REAL global store, so it is exercised hermetically in simulate_accumulation.py
# (Probe K), NEVER here. Pin only that the op is exposed (a missing/renamed op would break the SKILL).
check("v0.1.16: promote() is exposed (the local→canonical hand-off op)", callable(sg.promote))

# --- node label: hyphenated project name not mislabeled (slug is not invertible) ---
check("node label: keeps hyphenated tail, not 'memory'",
      sg._label_from_slug("-home-you-project-consolidate-memory").endswith("consolidate-memory")
      and sg._label_from_slug("-home-you-project-consolidate-memory") != "memory")
check("node label: de-prefixes leading dash on short slug",
      sg._label_from_slug("-a-b") == "a-b")
check("node label: strips terminal control bytes (--tokens print safety)",
      "\x1b" not in sg._label_from_slug("-home-you-ev\x1b[31mil"))

# --- pentest fix (High/Med): mirror detection is frontmatter-anchored, not substring ---
_mirror_meta = "---\nname: x\nmetadata:\n  node_type: memory\n  global_ref: x\n---\nbody\n"
_mirror_hash = "---\n# global_ref: x\nname: x\n---\nbody\n"
_prose = "---\nname: notes\n---\nThis note explains how global_ref: markers work in sync.\n"
_nofm = "a plain note mentioning global_ref: somewhere with no frontmatter\n"
check("mirror: detects metadata global_ref", sg._is_mirror(_mirror_meta) is True)
check("mirror: detects frontmatter-comment global_ref", sg._is_mirror(_mirror_hash) is True)
check("mirror: prose mention in BODY is NOT a mirror (GC-safety)", sg._is_mirror(_prose) is False)
check("mirror: no-frontmatter mention is NOT a mirror", sg._is_mirror(_nofm) is False)
check("mirror: round-trips _as_mirror output", sg._is_mirror(sg._as_mirror(_prose, "notes")) is True)
# PROPERTY: _is_mirror(_as_mirror(t, n)) must hold for ANY frontmatter shape — producer
# and recognizer must agree, or a stamped mirror becomes unrecognized (never refreshed,
# GC-immune). Includes adversarial shapes (indented metadata:, metadata inside a folded
# scalar) that previously desynced the two.
for _i, _fm in enumerate([
    "---\nname: a\nmetadata:\n  node_type: memory\n---\nbody\n",          # normal metadata block
    "---\nname: b\ndescription: just text\n---\nbody\n",                  # no metadata block
    "---\nname: c\n  metadata:\n  scope: user-global\n---\nbody\n",       # INDENTED metadata (adversarial)
    "---\ndescription: >-\n  folded\n  metadata:\n---\nbody\n",           # 'metadata:' inside a folded scalar
    "﻿---\nname: e\nmetadata:\n  node_type: memory\n---\nbody\n",     # leading BOM (Gate-2 F3)
]):
    check(f"mirror: round-trip property holds (shape {_i})",
          sg._is_mirror(sg._as_mirror(_fm, "x")) is True)

# --- pentest fix (High): secrets firewall covers credential-shaped ERROR output ---
check("firewall: catches bearer token in error text",
      bool(es._looks_secret("HTTP 401 WWW-Authenticate: Bearer " + "a" * 50)))
check("firewall: catches password= leak in error text",
      bool(es._looks_secret("FATAL: password authentication failed; password=s3cr3t-value")))

# --- re-gate fixes: structural mirror detection (H-3, folded-YAML false positive) ---
_folded = "---\nname: design-notes\ndescription: >-\n  notes about the\n  global_ref: marker\n---\nbody\n"
_evil_meta = "---\nname: x\nmetadata:\n  description: >-\n    global_ref: x\n---\nb\n"
check("mirror: folded-scalar continuation is NOT a mirror (H-3 GC-safety)", sg._is_mirror(_folded) is False)
check("mirror: deep-indent under metadata child is NOT a mirror", sg._is_mirror(_evil_meta) is False)
check("mirror: real metadata-child + col-0 stamp still detected",
      sg._is_mirror(_mirror_meta) and sg._is_mirror(_mirror_hash))

# --- re-gate fixes: firewall catches named provider key shapes (H-4) ---
# NB: provider-token fixtures are assembled by concatenation from obviously-fake parts,
# so no contiguous real-looking token literal exists in this source file (GitHub
# secret-scanning push protection matches source text, not runtime values). Each still
# matches the firewall regex SHAPE, which is all these tests assert.
for _name, _val, _want in [
    ("AWS AKIA", "AKIA" + "EXAMPLE0EXAMPLE0", True),                 # AKIA + 16
    ("Slack xoxb", "xoxb-" + "000000000-000000-fakefakefake", True),
    ("Stripe sk_live", "sk_" + "live_" + "0000example0000fake", True),
    ("GitHub ghp_", "ghp_" + "A" * 36, True),
    ("JWT", "eyJ" + "fakehead." + "eyJfakebody." + "fakesig", True),
    ("URI user:pass@", "postgres://user:" + "fakepw" + "@db.example.com/app", True),
    ("ordinary phrase", "please fix the scraper and run the tests", False),
]:
    check(f"firewall: {_name} -> {'flagged' if _want else 'clean'}", bool(es._looks_secret(_val)) is _want)

# --- re-gate fix (High): firewall catches the keyword as a SEGMENT of a compound id ---
for _name, _val, _want in [
    ("AWS_SECRET_ACCESS_KEY=", "AWS_SECRET_ACCESS_KEY=wJalrFakeKeyValueHere", True),
    ("SECRET_KEY=", "SECRET_KEY=django-insecure-q8z", True),
    ("client_secret_key=", "client_secret_key=ZmFrZXZhbHVl", True),
    ("MY_API_KEY=", "MY_API_KEY=abc123", True),
    ("tokenizer_x= (NOT a secret — token is a substring, not a segment)", "tokenizer_config=5", False),
    ("secretary= (NOT a secret)", "secretary_name=alice", False),
    ("pwd=", "pwd=Hunter2!", True),
    ("pass:", "pass: MyS3cret", True),
    ("creds:", "credentials: admin/hunter2", True),
    ("private_key=", "private_key=shortval123", True),
    ("passenger_count= (NOT a secret — pass is a substring)", "passenger_count=5", False),
]:
    check(f"firewall(compound): {_name} -> {'flagged' if _want else 'clean'}",
          bool(es._looks_secret(_val)) is _want)

# --- re-gate(2) fixes: entropy-blob handles '/' + all-alpha; keyword arm handles quotes ---
for _name, _val, _want in [
    # bare slash-bearing base64 (AWS-secret shape), mixed case, <3 slashes, no keyword
    ("bare slash-base64", "Wj0Alr/UtnFEMI" + "K7MdENgbPxRfiCyExampleKey99", True),
    # all-alphabetic mixed-case 48-char token (no digit, no slash)
    ("all-alpha mixed 48", "AbCdEf" * 8, True),
    # quoted-JSON credential (keyword arm must see through the quotes)
    ('JSON {"password":"x"}', '{"password": "hunter2longvalue"}', True),
    ('JSON {"api_key":"x"}', '{"api_key": "abc123def456"}', True),
    ('JSON {"client_secret":"x"}', '{"client_secret": "ZmFrZXZhbHVl"}', True),
    # precision still holds: a deep file path is NOT a secret
    ("deep path (>=3 slashes)", "/home/you/project/foo/bar/baz/qux/some_module.py", False),
]:
    check(f"firewall(redesign): {_name} -> {'flagged' if _want else 'clean'}",
          bool(es._looks_secret(_val)) is _want)

# --- re-gate(2) fix (Low): a `# global_ref:` comment NOT on the first frontmatter line
#     is not a mirror (so plain --pull never clobbers a hand-authored note) ---
check("mirror: # global_ref comment below the first line is NOT a mirror",
      sg._is_mirror("---\nname: notes\n# global_ref: x\n---\nbody\n") is False)
check("mirror: # global_ref stamp on the FIRST frontmatter line IS a mirror",
      sg._is_mirror("---\n# global_ref: notes\nname: notes\n---\nbody\n") is True)

# --- re-gate(2) fix (Low): memory_status sanitizes control bytes before printing ---
check("sane: strips ESC/control bytes from printed git text",
      "\x1b" not in ms._sane("feat: x\x1b[2J\x07") and ms._sane("plain msg") == "plain msg")

# --- re-gate(3) fix (Low): zero-width/Cf chars are stripped before scan+store ---
check("norm: strips zero-width (Cf) chars", es._norm("a\u200bb\u200dc") == "abc")
check("firewall: zero-width-split secret is caught after _norm",
      bool(es._looks_secret(es._norm("AKIA\u200bEXAMPLE0EXAMPLE0"))))

# --- re-gate fix (Low): pointer matching uses the link target, hook strips markdown ---
check("pointer: hook strips markdown link chars (no []() injection)",
      all(c not in sg._pointer_line("foo", {"description": "evil](http://x) link"}).split("—", 1)[1]
          for c in "[]()"))
check("stale-since: non-string marker does not crash (returns [])",
      ms._stale_since([], cast(Any, 1234567890)) == [] and ms._stale_since([], cast(Any, None)) == [])

# --- run-3 fixes: name/token hardening into the shared store + tier-1 index ---
check("name: safe kebab stem accepted", sg._safe_stem("gh-pr-edit-broken_v2.1"))
check("name: markdown-link injection stem rejected", sg._safe_stem("evil](http://x)") is False)
check("name: whitespace stem rejected", sg._safe_stem("a b") is False and sg._safe_stem("") is False)
check("token: project name sanitized (neutralizes backref + brackets)",
      sg._sanitize_token(r"proj\1]evil") == "proj-1-evil")
check("token: clean project name unchanged", sg._sanitize_token("home-you-project-foo") == "home-you-project-foo")

# --- re-gate fix: dashboard strips terminal control bytes (Low) ---
check("render: _clean strips ESC/control bytes", "\x1b" not in rd._clean("a\x1b[31mX") and rd._clean("a\x1b[31mX").endswith("[31mX"))
check("render: _clean preserves plain text", rd._clean("b6d37b6 fix_thing.py") == "b6d37b6 fix_thing.py")

# --- Fix A render: budget overflow flag ---
check("render: over-budget flag shows ⚠", "OVER" in rd._over({"over": True, "budget_tokens": 1200}))
check("render: under budget is silent", rd._over({"over": False}) == "")

# --- global CLAUDE.md: measured read-only, rendered as a distinct every-project line ---
_gcm = lambda present, over=False: rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
    "budget": {"global_claude_md": {"present": present, "tokens": 900, "over": over}}})
check("render: global CLAUDE.md shows as its own read-only line", "global CLAUDE.md" in _gcm(True))
check("render: global CLAUDE.md line is framed read-only/every-project", "read-only" in _gcm(True))
check("render: global CLAUDE.md absent → no line (safe)", "global CLAUDE.md" not in _gcm(False))
check("render: global CLAUDE.md ⚠ is advisory ('heavy'), not the actionable 'OVER' flag",
      "heavy" in _gcm(True, over=True) and "OVER" not in _gcm(True, over=True))
# the project file keeps its DISTINCT actionable flag — the two are handled differently
check("render: project CLAUDE.md keeps the actionable OVER flag",
      "OVER" in rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
          "budget": {"claude_md": {"before": 0, "after": 0, "over": True, "budget_tokens": 4000}}}))

# --- color: opt-in + AUTO-gated (the safety property: off unless a real TTY) ---
class _TTY:    # noqa: E306
    def isatty(self): return True
class _NoTTY:  # noqa: E306
    def isatty(self): return False
check("color: --color=never wins even on a TTY", rd._color_enabled(["--color=never"], _TTY()) is False)
check("color: --color=always wins even when captured", rd._color_enabled(["--color=always"], _NoTTY()) is True)
check("color: AUTO is OFF when captured/piped (agent-relay + pipe safe)", rd._color_enabled([], _NoTTY()) is False)
check("color: _c is a no-op while disabled (default)", rd._c("x", "red") == "x" and rd._COLOR is False)

# --- budget bars: pure, ASCII-grid-safe, fill ∝ usage ---
check("bar: ~30% fills 3/10", rd._bar(30, 100, 10).count("█") == 3 and rd._bar(30, 100, 10).count("░") == 7)
check("bar: over-budget fills fully (capped)", rd._bar(150, 100, 10).count("█") == 10)
check("bar: no budget → empty (nothing to gauge)", rd._bar(5, 0) == "")
check("pct: rounds to whole percent", rd._pct(30, 120) == "25%" and rd._pct(1, 0) == "")

# --- --demo: paste-free preview record renders the full dashboard ---
_demo = rd.render(rd._demo_record())
check("demo: renders the banner", "DREAM · consolidate-memory" in _demo)
check("demo: skipped entry is self-labelled (action word shown)", "skipped" in _demo)
check("demo: no stray em-dash placeholder anywhere (the skipped-row fix)", "—" not in _demo)
check("demo: includes the network section", "NEURAL NETWORK" in _demo)

# --- robustness: a MODEL-authored record (string/None numerics, non-str tier) must not
# crash render(). The cycle record is model-authored, so numbers can arrive as "6183"/null
# and a field can be the wrong type; every model->presentation boundary coerces via _num/_clean. ---
_gnarly = cast(_R, {"project": "p", "session": "s", "scope": {},
           "entries": [{"action": "added", "tier": 1, "store": "repo", "scope": "user-global",
                        "name": "x", "reason": "", "citation": ""}],
           "budget": {"claude_md": {"before": "0", "after": "1", "over": False},
                      "global_claude_md": {"present": True, "tokens": "2240", "over": False}},
           "network": {"basis": "x", "trigger": "p",
                       "nodes": [{"node": "n", "trigger": True, "always_loaded_tokens": "6183",
                                  "recall_tokens": None, "facts": "12", "shared": 1}],
                       "totals": {"nodes": 1, "always_loaded_tokens": "6461",
                                  "mirror_index_tokens": "326", "recall_tokens": 0}}})
check("render: model-authored string/None numerics + non-str tier never crash render",
      isinstance(rd.render(_gnarly), str) and "NEURAL NETWORK" in rd.render(_gnarly))

# --- observability: network sub-section is guarded + rendered ---
_net = {"basis": "≈ chars/4", "node_def": "stores", "trigger": "p",
        "nodes": [{"node": "p", "trigger": True, "always_loaded_tokens": 10,
                   "recall_tokens": 20, "facts": 2, "shared": 1}],
        "totals": {"nodes": 1, "always_loaded_tokens": 10, "recall_tokens": 20}}
check("render: network section appears when present",
      "NEURAL NETWORK" in rd.render(cast(_R, {"project": "p", "session": "s", "scope": {},
                                      "entries": [], "network": _net})))
check("render: network section absent when no block (legacy/no-op safe)",
      "NEURAL NETWORK" not in rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))

# --- v0.1.6: the cycle-record CONTRACT (TypedDict + warn-only validator + SKILL sync) ---

# C5/F5: the SKILL.md schema block must stay key-for-key with the CycleRecord TypedDict, so
# the doc can't silently drift from the code. Parse the FIRST fenced ```json block out of
# SKILL.md, json.loads it, and assert its top-level key set == CycleRecord.__annotations__
# (and spot-check the nested health shape == Health.__annotations__). This makes the
# "single source for the CODE; SKILL.md kept aligned by this test" claim ENFORCEABLE.
import json as _json  # noqa: E402
_skill_md = (ROOT / "plugins" / "consolidate-memory" / "skills" / "consolidate-memory" / "SKILL.md")
_skill_text = _skill_md.read_text(encoding="utf-8")
_fence = "```json"
_j0 = _skill_text.index(_fence) + len(_fence)        # start of the FIRST ```json block
_j1 = _skill_text.index("```", _j0)                  # the next closing fence
_skill_schema = _json.loads(_skill_text[_j0:_j1])
check("SKILL↔TypedDict: schema-block top-level keys == CycleRecord (incl. outcome) (C5)",
      set(_skill_schema.keys()) == set(ms.CycleRecord.__annotations__))
check("SKILL↔TypedDict: schema-block health keys == Health TypedDict (nested spot-check)",
      set(_skill_schema.get("health", {}).keys()) == set(ms.Health.__annotations__))
check("SKILL↔TypedDict: schema-block marker keys == Marker TypedDict (incl. before_*; v0.1.6 drift fix)",
      set(_skill_schema.get("marker", {}).keys()) == set(ms.Marker.__annotations__))
# v0.1.12: extend the pin to ALL nested shapes (was only top-level + health + marker), so SKILL.md's
# nested schema can't silently drift from the code. Strip doc-annotation keys (leading "_", e.g.
# cross_project._pulled / network._) before comparing; list-wrapped shapes compare their [0] item.
# (SchemaDrift + the pulled/promoted item dicts aren't enumerated in the block — the former renders as
# an empty {} placeholder, the latter are untyped list[dict] — so they're out of scope for this pin.)
_sk_b = _skill_schema.get("budget", {})
_sk_n = _skill_schema.get("network", {})
for _nm, _obj, _td in [
    ("scope", _skill_schema.get("scope", {}), ms.Scope),
    ("rigor", _skill_schema.get("rigor", {}), ms.Rigor),
    ("verification", _skill_schema.get("verification", {}), ms.Verification),
    ("entries[0]", (_skill_schema.get("entries") or [{}])[0], ms.Entry),
    ("budget", _sk_b, ms.Budget),
    ("budget.claude_md", _sk_b.get("claude_md", {}), ms.ClaudeMdBudget),
    ("budget.global_claude_md", _sk_b.get("global_claude_md", {}), ms.GlobalClaudeMd),
    ("budget.index", _sk_b.get("index", {}), ms.IndexBudget),
    ("budget.recall_facts", _sk_b.get("recall_facts", {}), ms.RecallFacts),
    ("cross_project", _skill_schema.get("cross_project", {}), ms.CrossProject),
    ("network", _sk_n, ms.Network),
    ("network.nodes[0]", (_sk_n.get("nodes") or [{}])[0], ms.NetworkNode),
    ("network.totals", _sk_n.get("totals", {}), ms.NetworkTotals),
    ("remediation", _skill_schema.get("remediation", {}), ms.Remediation),   # v0.1.18
    ("maintenance", _skill_schema.get("maintenance", {}), ms.Maintenance),   # v0.1.37
    ("dream", _skill_schema.get("dream", {}), ms.DreamArc),                  # v0.1.54
    ("distill", _skill_schema.get("distill", {}), ms.Distill),               # v0.1.55
    # v0.1.22: whole-hierarchy measure + the deterministic audit block (+ their list-item shapes via [0]).
    ("budget.claude_md_hierarchy", _sk_b.get("claude_md_hierarchy", {}), ms.ClaudeMdHierarchy),
    ("budget.claude_md_hierarchy.files[0]", (_sk_b.get("claude_md_hierarchy", {}).get("files") or [{}])[0], ms.ClaudeMdHierarchyFile),
    ("audit", _skill_schema.get("audit", {}), ms.Audit),
    ("audit.memory", _skill_schema.get("audit", {}).get("memory", {}), ms.AuditStoreDelta),
    ("audit.operations[0]", (_skill_schema.get("audit", {}).get("operations") or [{}])[0], ms.AuditOp),
    ("audit.conservation", _skill_schema.get("audit", {}).get("conservation", {}), ms.Conservation),   # v0.1.24
]:
    check(f"SKILL↔TypedDict: schema-block {_nm} == {_td.__name__} (v0.1.12 full nested pin)",
          {k for k in _obj if not k.startswith("_")} == set(_td.__annotations__))

# v0.1.52: BLOCKER guard — Phase-5's health fill MUST call dangling_links with the SAME global_dir as Phase-0
# (memory_status.py), or health.dangling_links re-introduces the Class B false positive that maintenance.dangling
# drops (the count-drift the single-source helper exists to prevent). Pin the SKILL prose so a future edit can't
# silently drop the cross-store arg from either the count call or the fix-suggestion.
check("v0.1.52: SKILL Phase-5 dangling_links call passes global_dir (cross-store; closes Phase-0↔5 drift)",
      "dangling_links(auto_mem, global_dir=" in _skill_text)
check("v0.1.52: SKILL Phase-5 fix-suggestion resolves cross-store — valid_link_targets(global_dir)",
      "valid_link_targets(global_dir)" in _skill_text)

# v0.1.18: remediation triage — pure units (the full classifier is exercised hermetically in
# simulate_accumulation.py Probe L; these pin the short-circuit, the lever routing, and the regexes).
check("v0.1.18: triage is SILENT under budget (no false alarm on a healthy store)",
      ms.remediation_triage([], set(), 500, 0) == {})
check("v0.1.18: triage over-budget with no local candidates → lever 'justify' (no deadlock)",
      ms.remediation_triage([], set(), 6000, 0).get("lever") == "justify")
check("v0.1.18: triage routes a MIRROR-dominated overflow → 'gc' (not a futile local prune)",
      ms.remediation_triage([], set(), 6000, 4000).get("lever") == "gc"
      and ms.remediation_triage([], set(), 6000, 100).get("lever") == "justify")
check("v0.1.18: tracker/dated regexes match transient/dated, NOT a durable name",
      bool(ms._TRACKER_RE.search("build_status")) and bool(ms._TRACKER_RE.search("p3_tracker"))
      and bool(ms._DATED_RE.search("foo_2026_05_28")) and not ms._TRACKER_RE.search("use-placeholders")
      and not ms._DATED_RE.search("use-placeholders"))
# v0.1.18.x (beta patch): C1 archive-index docs are not facts; C2 referenced facts are not safe-evict orphans.
import tempfile as _tempfile  # noqa: E402
with _tempfile.TemporaryDirectory() as _bp_td:
    _bp_dir = Path(_bp_td)
    (_bp_dir / "archive.md").write_text("# Shipped\n- [a](a.md) — x\n- [b](b.md) — y\n- [c](c.md) — z\n", encoding="utf-8")
    (_bp_dir / "fact.md").write_text("---\nname: fact\nmetadata:\n  node_type: memory\n---\nbody\n", encoding="utf-8")
    check("v0.1.18.x: _is_archive_index — link-list YES, fact (frontmatter) NO (C1: never evict an archive)",
          ms._is_archive_index(_bp_dir / "archive.md") is True and ms._is_archive_index(_bp_dir / "fact.md") is False)
    (_bp_dir / "reffed.md").write_text("---\nname: reffed\nmetadata:\n  node_type: memory\n---\n" + "b\n" * 50, encoding="utf-8")
    (_bp_dir / "lonely.md").write_text("---\nname: lonely\nmetadata:\n  node_type: memory\n---\n" + "b\n" * 50, encoding="utf-8")
    _bp_tri = ms.remediation_triage([_bp_dir / "reffed.md", _bp_dir / "lonely.md"], set(), 6000, 0, reference_stems={"reffed"})
    _bp_orphans = [c["stem"] for c in _bp_tri["stages"]["A_orphans"]]
    _bp_refs = [c["stem"] for c in _bp_tri["stages"]["R_referenced"]]
    check("v0.1.18.x: C2 — referenced-unindexed → R (de-link first), unreferenced-unindexed → A (true orphan)",
          "reffed" in _bp_refs and "reffed" not in _bp_orphans and "lonely" in _bp_orphans and "lonely" not in _bp_refs)
    # v0.1.25: the --promote dangle guard — wikilinks to NON-global facts (would dangle in mirrors); excludes
    # an existing global fact, a self-reference, and a code-span dotted ref ([[tool.mypy.overrides]]).
    check("v0.1.25: _nonglobal_wikilinks flags project-local links, excludes global/self/code-span",
          sg._nonglobal_wikilinks("see [[fact]] and [[nonexistent-xyz]] and [[tool.mypy.overrides]]", _bp_dir) == ["nonexistent-xyz"]
          and sg._nonglobal_wikilinks("[[self-ref]] [[nonexistent-xyz]]", _bp_dir, exclude="self-ref") == ["nonexistent-xyz"]
          and sg._nonglobal_wikilinks("no links here", _bp_dir) == [])

# v0.1.14: _ui.py is the shared visual vocabulary the OTHER scripts import; render_dashboard keeps its
# OWN copies (the byte-pinned reference, untouched). This DRIFT-PIN asserts _ui stays byte-identical to
# render's primitives, so the unified look can never silently diverge from the reference.
check("ui↔rd drift-pin: rule / W / CODES / GLYPH_ASCII identical (v0.1.14)",
      ui.rule() == rd._rule() and ui.W == rd.W and ui.CODES == rd._CODES and ui.GLYPH_ASCII == rd._GLYPH_ASCII)
check("ui↔rd drift-pin: kv / bar / pct / num identical (color off)",
      ui.kv("X", "y") == rd._kv("X", "y") and ui.bar(3, 4) == rd._bar(3, 4)
      and ui.bar(9, 4) == rd._bar(9, 4) and ui.pct(3, 4) == rd._pct(3, 4) and ui.num("5") == rd._num("5"))
ui.set_modes(color=True)
rd._COLOR = True
check("ui↔rd drift-pin: c() color path identical", ui.c("x", "bold", "green") == rd._c("x", "bold", "green"))
ui.set_modes(color=False)
rd._COLOR = False

# C3/C8: validate_cycle_record — warn-only, pure, NEVER raises. WARNS on a present key of
# the wrong CONTAINER type, at the ACTUAL nesting (incl. health.slug_orphans/schema_drift).
# The CRITICAL contract (exact strings) for the _gnarly2 shape:
check("validate: _gnarly2 shape → exact two health warnings (C3 contract)",
      ms.validate_cycle_record({"health": {"slug_orphans": "x", "schema_drift": "y"}})
      == ["health.slug_orphans is not a list", "health.schema_drift is not a dict"])
# WARNS on the reused _gnarly2_rec shape (truthy non-list slug_orphans + non-dict schema_drift):
_w_gnarly = ms.validate_cycle_record(_gnarly2_rec)
check("validate: warns on _gnarly2_rec (non-list slug_orphans + non-dict schema_drift)",
      "health.slug_orphans is not a list" in _w_gnarly and "health.schema_drift is not a dict" in _w_gnarly)
# WARNS on a non-list top-level `entries` and a non-dict `scope`:
check("validate: warns on non-list entries", "entries is not a list" in
      ms.validate_cycle_record({"entries": "nope"}))
check("validate: warns on non-dict scope", "scope is not a dict" in
      ms.validate_cycle_record({"scope": "nope"}))
# SILENT on a clean record AND on a minimal partial record (partial is normal):
check("validate: SILENT on a clean record", ms.validate_cycle_record(
      {"project": "p", "scope": {}, "entries": [],
       "health": {"slug_orphans": [], "schema_drift": {}}}) == [])
check("validate: SILENT on a minimal partial record", ms.validate_cycle_record({"project": "p"}) == [])
# NEVER RAISES on junk: non-dict record, non-dict health, health-as-list. (No exception ⇒ pass.)
_validate_crashed = False
try:
    ms.validate_cycle_record(42)                       # non-dict record
    ms.validate_cycle_record(None)                     # non-dict record
    ms.validate_cycle_record({"health": "not-a-dict"})  # non-dict health → warns (FIX 2), no crash
    ms.validate_cycle_record({"health": ["x"]})        # health-as-list → warns (FIX 2), no descend, no crash
    ms.validate_cycle_record(cast(Any, [1, 2, 3]))     # a bare list record
except Exception:  # noqa: BLE001 — ANY raise fails the never-raise contract
    _validate_crashed = True
check("validate: NEVER raises on junk (non-dict record / non-dict health / health-as-list)",
      not _validate_crashed)
# A non-dict record returns a single descriptive warning, not a crash:
check("validate: non-dict record returns a descriptive warning (not a crash)",
      ms.validate_cycle_record(42) == ["cycle record is not a dict (got int)"])
# FIX 2: a present-but-non-dict `health` now WARNS (it was neither warned nor — before the
# render guard — survived). Added to the top-level container tuple alongside scope/budget/…
check("validate: warns on non-dict health (FIX 2)",
      "health is not a dict" in ms.validate_cycle_record({"health": "x"}))

# Gate-2 FIX 1: render() must DEGRADE (render what it can), NEVER crash, on a MODEL-authored
# malformed record — a non-dict record (a JSON list/scalar from stdin) or a truthy non-dict /
# wrong-container top-level value (`scope`/`rigor`/`health`/`budget`/`entries`). The contract
# is the codebase's never-crash invariant: render returns a `str` (and still emits its fixed
# skeleton, e.g. the always-rendered "CHANGES" header). NB: HEALTH is `if h:`-guarded, so a
# bare/malformed-health record renders NO HEALTH section — assert the unconditional skeleton,
# not HEALTH (only a record carrying a `health` dict, like _demo_record, shows HEALTH).
for _label, _bad in [
    ("non-dict record (list)", cast(_R, [1, 2, 3])),
    ("non-dict record (str)", cast(_R, "x")),
    ("non-dict record (None)", cast(_R, None)),
    ("non-dict scope", cast(_R, {"scope": "x", "entries": []})),
    ("non-dict rigor", cast(_R, {"rigor": "x", "scope": {}, "entries": []})),
    ("non-dict health", cast(_R, {"health": "x", "scope": {}, "entries": []})),
    ("non-dict budget", cast(_R, {"budget": "x", "scope": {}, "entries": []})),
    ("non-list entries", cast(_R, {"entries": "x"})),
]:
    _out = rd.render(_bad)
    check(f"render: degrades (never crashes) on {_label} — returns str with CHANGES skeleton",
          isinstance(_out, str) and "CHANGES" in _out)
# and a clean WELL-FORMED record still renders the banner (the degrade path is a no-op on
# correct types — coercions don't alter a valid record).
check("render: clean well-formed record still renders the banner (FIX 1 no-op on valid types)",
      "DREAM · consolidate-memory" in rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))

# --- v0.1.7 polish: no-op RIGOR suppression · noise-filter envelopes · --ascii fallback ---
# C1: a TRUE no-op (magnitude 0 + no entries) omits the RIGOR line; magnitude>0 OR entries keeps it.
check("render: true no-op (magnitude 0 + no entries) omits the RIGOR line (v0.1.7 C1)",
      "RIGOR" not in rd.render({"project": "p", "session": "s",
                                "scope": {"git_commits": 0, "session_candidates": 0},
                                "entries": [], "rigor": {"phase": "final"}}))
check("render: a pass with magnitude>0 keeps the RIGOR line (v0.1.7 C1)",
      "RIGOR" in rd.render({"project": "p", "session": "s",
                            "scope": {"git_commits": 1, "session_candidates": 0},
                            "entries": [], "rigor": {"phase": "final"}}))
check("render: a magnitude-0 pass WITH entries still keeps the RIGOR line (v0.1.7 C1)",
      "RIGOR" in rd.render({"project": "p", "session": "s",
                            "scope": {"git_commits": 0, "session_candidates": 0},
                            "entries": [{"action": "added", "name": "x"}], "rigor": {"phase": "final"}}))
# C2: the noise filter now drops the harness/agent envelopes the dream meta-test surfaced.
check("extract: _NOISE drops <task-notification> envelope (v0.1.7 C2)",
      bool(es._NOISE.match("<task-notification> done </task-notification>")))
check("extract: _NOISE drops <teammate-message> envelope (v0.1.7 C2)",
      bool(es._NOISE.match("<teammate-message> hi </teammate-message>")))
check("extract: _NOISE keeps a normal human turn (no over-match) (v0.1.7 C2)",
      not es._NOISE.match("Let's ship the polish patch now"))
# C3: --ascii (the _ASCII global) translates the 14 glyphs to ASCII, WIDTH-PRESERVING; the default
# (Unicode) render is unaffected.
_uni = rd.render(rd._demo_record())
rd._ASCII = True
try:
    _asc = rd.render(rd._demo_record())
finally:
    rd._ASCII = False
# The CONTRACT is "pure ASCII" — assert .isascii() (catches ANY unmapped/future glyph + the
# catch-all's coverage), NOT membership of a hand-listed glyph set (that was circular and missed
# ≈/−/↑/… in the first pass). Plus: the common glyphs map READABLY (not just catch-all '?').
check("render: --ascii output is pure ASCII (.isascii() — catches any unmapped glyph) (v0.1.7 C3)",
      _asc.isascii())
check("render: --ascii maps common glyphs READABLY (█→#, →→>), not just the catch-all (v0.1.7 C3)",
      "#" in _asc and ">" in _asc)
check("render: --ascii preserves line count + per-line width (single-char maps) (v0.1.7 C3)",
      _asc.count("\n") == _uni.count("\n")
      and all(len(a) == len(u) for a, u in zip(_asc.splitlines(), _uni.splitlines())))
check("render: default (Unicode) render is NOT pure ASCII — --ascii is opt-in (v0.1.7 C3)",
      not _uni.isascii())

# ── v0.1.15: the hanging-indent wrap (shared wrapping mechanism + adaptive width) ─────────────
# (_NoTTY is defined above — a deterministic non-TTY stream.)
_w = ui.wrap("alpha beta gamma delta epsilon zeta eta theta iota kappa", hang=4, width=20).split("\n")
check("wrap: every visible line fits the width, and it actually wrapped",
      all(ui.vis(line) <= 20 for line in _w) and len(_w) > 1)
check("wrap: first line is flush-left; continuations HANG at `hang` spaces",
      not _w[0].startswith(" ") and all(line.startswith("    ") for line in _w[1:]))
check("wrap: an over-long single word is kept whole, never chopped mid-token",
      "antidisestablishmentarianism" in ui.wrap("antidisestablishmentarianism x", hang=2, width=8))
ui.set_modes(color=True, width=240)
_cw = ui.wrap(ui.c("one two three four five six seven eight nine ten", "dim"), hang=4, width=22).split("\n")
check("wrap: ANSI-aware — colored value measured by VISIBLE width, every line fits",
      all(ui.vis(line) <= 22 for line in _cw) and len(_cw) > 1)
check("wrap: ANSI-aware — every wrapped line re-opens AND closes the color",
      all(("\x1b[2m" in line and line.rstrip().endswith(ui.CODES["reset"])) for line in _cw if line.strip()))
_stk = ui.wrap(ui.c("alpha beta gamma delta epsilon zeta eta", "bold", "green"), hang=2, width=18).split("\n")
check("wrap: ANSI-aware — a STACKED span (bold+green) re-opens BOTH codes on each line (v0.1.15)",
      len(_stk) > 1 and all(("\x1b[1m" in line and "\x1b[32m" in line) for line in _stk if line.strip()))
ui.set_modes(color=False, width=240)
ui.set_modes(width=40)
rd.W = 40
_long = " ".join(f"word{i}" for i in range(20))
check("kv: a long value hangs at the value column (12); a short value stays one line",
      all(line.startswith(" " * 12) for line in ui.kv("SCOPE", _long).split("\n")[1:]) and "\n" not in ui.kv("SCOPE", "x"))
check("ui↔rd: kv wraps IDENTICALLY for a long value (v0.1.15 wrap mirror — look can't diverge)",
      ui.kv("RIGOR", _long) == rd._kv("RIGOR", _long))
check("li: a bulleted item hangs past the bullet (indent + 2)",
      all(line.startswith(" " * 6) for line in ui.li(_long, indent=4, bullet="·").split("\n")[1:]))
ui.set_modes(width=240)
rd.W = 240
check("resolve_width: --width=N overrides; a non-TTY falls back to the fixed default (deterministic)",
      ui.resolve_width(["--width=88"], _NoTTY()) == 88 and ui.resolve_width([], _NoTTY()) == ui.W)
check("ui↔rd: module-default W mirrors (both 60, captured before the wide override) (v0.1.15)",
      _UI_W0 == _RD_W0 == 60)

# ── v0.1.28: HTML observability dashboard (render_html) — gated MECHANICAL guarantees (the visual is eye-judged) ──
import json as _json  # noqa: E402
import re as _re  # noqa: E402
_rec = {"project": "demo", "session": "s1", "budget": {"index": {"after_tokens": 900, "budget_tokens": 1200, "over": False},
        "recall_facts": {"after": 16}}, "verification": {"confirmed": 5}, "rigor": {"applied": "LIGHT"},
        "entries": [{"action": "added", "name": "x", "reason": "r"}], "marker": {"commit": "abc", "timestamp": "2026-06-21T00:00"}}
_html = rhtml.build_html(_rec, [_rec], "2026-06-21T00:00:00")
_m = _re.search(r'<script type="application/json" id="cm-data">(.*?)</script>', _html, _re.S)
_embed = _json.loads(_m.group(1).replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")) if _m else {}
_emc = (_embed.get("cycles") or [{}])[-1]   # v0.1.29: the archive embeds `cycles`; the current pass is the last
check("v0.1.28: render_html embeds the cycle record COHERENTLY (round-trip key numbers match the input)",
      _emc.get("budget", {}).get("index", {}).get("after_tokens") == 900
      and _emc.get("budget", {}).get("recall_facts", {}).get("after") == 16)
_evil = rhtml.build_html({"project": "x", "entries": [{"action": "added", "name": "</script><img src=x onerror=alert(1)>", "reason": "<b>&</b>"}]}, [], "t")
check("v0.1.28: render_html is </script>-break-out-safe (XSS hostile fixture escaped, not raw)",
      "</script><img" not in _evil and "\\u003c/script" in _evil)
# the attribute-context escaping happens client-side in esc(); verify the hardened esc() (quotes too) SHIPS in the template.
check("v0.1.28: client esc() is attribute-safe — escapes quotes too (the re-audit MED XSS fix is present)",
      'replace(/"/g,"&quot;")' in _html and "&#39;" in _html)
_ext = [u for u in _re.findall(r'https?://[a-z][a-z0-9.\-]*', _html) if "www.w3.org" not in u]
check("v0.1.28: render_html output has ZERO external deps (self-contained / offline)",
      _ext == [] and "<link" not in _html.lower() and "@import" not in _html and " src=" not in _html)
check("v0.1.28: dashboard.template.html is BUNDLED under the plugin (marketplace out-of-the-box)",
      (Path(rhtml.__file__).parent / "dashboard.template.html").exists())
check("v0.1.28: render_html renders a legacy/sparse record (no audit/hierarchy, empty history) without error",
      "<!DOCTYPE html>" in rhtml.build_html({"project": "old"}, [], "t"))
with _tempfile.TemporaryDirectory() as _hd:
    (Path(_hd) / ".consolidation-log.jsonl").write_text('{"a":1}\nNOT JSON\n{"b":2}\n', encoding="utf-8")
    check("v0.1.28: read_history skips malformed log lines (a corrupt log can't break the dashboard)",
          len(rhtml.read_history(Path(_hd))) == 2)
check("v0.1.28: render_html _store_for resolves --store / --project (slug) / neither (powers cm report)",
      str(rhtml._store_for("/tmp/s", None)) == "/tmp/s"
      and rhtml._store_for(None, None) is None
      and str(rhtml._store_for(None, "/home/x/proj")).endswith("/memory"))
# v0.1.29 — the per-repo dream ARCHIVE: assemble_cycles builds the series (dedup by marker; current appended iff newer)
_h2 = [{"marker": {"commit": "a", "timestamp": "t1"}, "project": "p"}, {"marker": {"commit": "b", "timestamp": "t2"}, "project": "p"}]
_cyA, _tA = rhtml.assemble_cycles({}, _h2)                                                   # no current → just the log
_cyB, _tB = rhtml.assemble_cycles({"marker": {"commit": "c", "timestamp": "t3"}, "project": "p"}, _h2)  # newer → appended
_cyC, _tC = rhtml.assemble_cycles(_h2[-1], _h2)                                              # current == last log → NOT doubled
check("v0.1.29: assemble_cycles builds the archive series (dedup by marker; current appended iff newer)",
      (_tA, len(_cyA)) == (2, 2) and (_tB, len(_cyB)) == (3, 3) and (_tC, len(_cyC)) == (2, 2))
_am = _re.search(r'id="cm-data">(.*?)</script>', rhtml.build_html({}, _h2, "t"), _re.S)
_ae = _json.loads(_am.group(1).replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")) if _am else {}
check("v0.1.29: build_html embeds the archive contract (cycles[] + project + total)",
      isinstance(_ae.get("cycles"), list) and len(_ae["cycles"]) == 2 and _ae.get("project") == "p" and _ae.get("total") == 2)
check("v0.1.29: render_html template carries the archive routing (sel parse + archive view + hashchange reload)",
      "_readSel" in _html and 'id="archive"' in _html and "showArchive" in _html and "hashchange" in _html)
check("v0.1.29: _marker + assemble_cycles tolerate a non-dict marker (a corrupt log entry can't crash --select/dedup)",
      rhtml._marker({"marker": "oops"}) == (None, None)
      and len(rhtml.assemble_cycles({}, [{"marker": "x"}, {"marker": {"commit": "a", "timestamp": "t"}}])[0]) == 2)
check("v0.1.31: template carries cycle-1 interactions (click-through + keyboard, archive filter/sort, collapse, density)",
      all(s in _html for s in ['location.hash="#sel="', '"keydown"', 'id="arch-tools"', 'f-sort', 'cm-collapsed', 'id="dens-tog"', 'cm-dense']))
# v0.1.32 — diff-modal capture: shared key + one-sided/capped diff + safe embed + template hooks
check("v0.1.32: diff_key sanitizes commit+timestamp to a safe filename + tolerates a non-dict marker (shared write/read key)",
      "/" not in ms.diff_key({"commit": "a/b", "timestamp": "t:1"}) and ":" not in ms.diff_key({"commit": "a", "timestamp": "2026:01"})
      and ms.diff_key("oops") == "nocommit__nots")
_cr = ms._diff_lines("", "a\nb\n"); _de = ms._diff_lines("a\nb\n", "")
check("v0.1.32: _diff_lines one-sided (create→adds, delete→removes) + per-file cap with +N more",
      all(l["t"] in ("+", "@") for l in _cr["lines"]) and all(l["t"] in ("-", "@") for l in _de["lines"])
      and ms._diff_lines("\n".join(map(str, range(300))), "\n".join("x" + str(i) for i in range(300)))["more"] > 0)
_hd = rhtml.build_html({"project": "p", "marker": {"commit": "c", "timestamp": "t"}}, [], "t",
                       {"c__t": {"memory/x.md": {"op": "modified", "lines": [{"t": "+", "s": "</script><img src=x onerror=alert(1)>"}], "more": 0}}})
check("v0.1.32: build_html embeds diffs INSIDE the data dict — a </script> in a diff line is escaped, not raw",
      '"diffs"' in _hd and "</script><img" not in _hd and "\\u003c/script" in _hd)
check("v0.1.32: template carries the diff-modal (diffKey mirror, dmodal overlay, openDiff, clickable ledger filename, esc'd lines)",
      all(s in _html for s in ["function diffKey", 'id="dmodal"', "function openDiff", "nm-diff", "DREAMDIFFS", "dl-plus"]))
# v0.1.34 — cm log: the lean log-audit renderer (3rd view; reuses the ONE read_history; legacy-safe; --json)
_lr = [{"marker": {"commit": "aaaa1111bb", "timestamp": "2026-06-21T01:00"}, "rigor": {"applied": "LIGHT"}, "project": "p",
        "budget": {"index": {"before_tokens": 100, "after_tokens": 120}, "recall_facts": {"before": 5, "after": 6}},
        "entries": [{"action": "added"}, {"action": "skipped"}], "audit": {"memory": {"created": 1, "modified": 0, "deleted": 0}}}]
_lt = rlog.render(_lr, 1, "p")
check("v0.1.34: render_log builds the dense per-dream table (marker · rigor · budget Δ · audit all present)",
      "DREAM LOG" in _lt and "aaaa1111bb" in _lt and "LIGHT" in _lt and "120 (+20)" in _lt and "+1 ~0 -0" in _lt)
check("v0.1.34: render_log is legacy/sparse-safe — a bare {} record renders (defaults, no KeyError)",
      "DREAM LOG" in rlog.render([{}], 1, "p"))
check("v0.1.34: render_log reuses render_html.read_history (ONE log reader, not a second)",
      rlog.read_history is rhtml.read_history)

# v0.1.4 (dream-beta-tester M5) — restore() must NOT destroy data. The audit found: restore unlinked any live
# store file absent from the snapshot, and capture SKIPPED unreadable files → a present-but-unreadable PRE-RUN
# file was deterministically deleted. Fix: capture RECORDS unreadable files (preserved on restore); restore
# QUARANTINES extras (moves to reports/.restore-trash-*), never unlinks. (chmod-0 needs non-root to bite; under
# root the file stays readable → case 1 exercises the normal-preserve path, still a valid assertion.)
sys.path.insert(0, str(ROOT / "plugins" / "dream-beta-tester" / "scripts"))
import snapshot as _snap  # noqa: E402
import tempfile as _tfm5  # noqa: E402
with _tfm5.TemporaryDirectory() as _tdm5:
    _r5 = Path(_tdm5); _s5 = _r5 / "store"; _s5.mkdir()
    _snap.REPORTS_DIR = _r5 / "reports"   # REPORTS_DIR binds at import; override the module attr so quarantine → temp
    (_s5 / "a.md").write_text("fact a\n")
    (_s5 / "b.md").write_text("fact b\n"); (_s5 / "b.md").chmod(0)        # b: UNREADABLE at capture
    _m5 = _snap.snapshot(_r5, _s5, _r5 / "snap")
    (_s5 / "c.md").write_text("dream-added\n")                            # an extra file appears post-snapshot
    _snap.restore(_m5, _r5, _s5)
    (_s5 / "b.md").chmod(0o644)
    check("v0.1.4/M5: restore PRESERVES an unreadable pre-run file (recorded, not deleted)", (_s5 / "b.md").exists())
    check("v0.1.4/M5: restore is byte-faithful on a normal pre-run file", (_s5 / "a.md").read_text() == "fact a\n")
    check("v0.1.4/M5: restore rolls a dream-added file OUT of the store (--test leaves no trace)", not (_s5 / "c.md").exists())
    check("v0.1.4/M5: the rolled-out file is QUARANTINED (recoverable), not destroyed",
          any((_r5 / "reports").glob(".restore-trash-*/c.md")))
# v0.1.40 (M3, altitude/recurrence guard) — the FIVE slug_for reimplementations MUST agree. make_fixture.py
# drifting (it kept [/_] after the other 4 generalized) was the M3 bug, caught only by eyeballing the prove
# step's slug — NOT a test. Pin them equal on a path with the chars that matter (. _ uppercase) so the NEXT
# drift FAILS deterministically here, instead of recurring as a silent split-brain store.
sys.path.insert(0, str(ROOT / "plugins" / "dream-beta-tester" / "fixtures"))
import beta_checks as _bc40, render_beta_report as _rbr40, make_fixture as _mf40  # noqa: E402
_p40 = Path("/home/u/.config/My_App.v2/repo")
_slugs40 = {ms.slug_for(_p40), _snap.slug_for(_p40), _bc40.slug_for(_p40), _rbr40.slug_for(_p40), _mf40.slug_for(_p40)}
check("v0.1.40/M3: all 5 slug_for reimplementations AGREE (skill + snapshot/beta_checks/render/make_fixture)",
      len(_slugs40) == 1)
# v0.1.41 (evict-to-receive) — the pure guards behind --evict (the release valve for M1's hold). extract_wikilinks
# (the single [[...]] extractor, factored from dangling_links); _evict_frees_enough (fit-check, no-partial-loss);
# _inbound_links (orphan-safety). The hermetic CLI E2E (happy + both refusals + surfacing) ran green out-of-band.
check("v0.1.41: extract_wikilinks strips fenced + inline code, finds [[real]] only (single [[...]] extractor)",
      ms.extract_wikilinks("a [[real]] b `[[inline]]` c\n```\n[[fenced]]\n```\n") == ["real"])
# explicit budget=1200 pins these to the eviction LOGIC, not the production INDEX_TOKEN_BUDGET
# (which moved 1200→1500) — a fixture sized to the live constant silently breaks on a re-ground.
check("v0.1.41: _evict_frees_enough True when the freed room fits the smallest held",
      sg._evict_frees_enough(1190, 80, [40, 60], budget=1200) is True)        # (1190-80)+40 = 1150 ≤ 1200
check("v0.1.41: _evict_frees_enough False when the evict frees too little (no-partial-loss refusal)",
      sg._evict_frees_enough(1190, 10, [40], budget=1200) is False)           # (1190-10)+40 = 1220 > 1200
check("v0.1.41: _evict_frees_enough False when nothing is held (nothing to receive)",
      sg._evict_frees_enough(1190, 80, [], budget=1200) is False)

# vNEXT: archive_candidates — completion-driven (dated-stem + KEEP-veto), INDEXED-only, high-precision.
import tempfile as _tf
from pathlib import Path as _ArcPath
with _tf.TemporaryDirectory() as _arc_td:
    _arc_dir = _ArcPath(_arc_td)
    (_arc_dir / "feat_shipped_2026_05_01.md").write_text("---\nname: a\n---\nThis arc SHIPPED.\n", encoding="utf-8")
    (_arc_dir / "lesson_2026_05_01.md").write_text("---\nname: b\ndescription: NEVER retry X — a standing rule\n---\nbody.\n", encoding="utf-8")
    (_arc_dir / "bodyonly_2026_05_01.md").write_text("---\nname: f\n---\nThe rule: NEVER retry.\n", encoding="utf-8")
    (_arc_dir / "active_design.md").write_text("---\nname: c\n---\nongoing active notes\n", encoding="utf-8")
    (_arc_dir / "orphan_2026_05_01.md").write_text("---\nname: d\n---\ndated but UNindexed\n", encoding="utf-8")
    (_arc_dir / "mirror_2026_05_01.md").write_text("---\nname: e\nmetadata:\n  global_ref: x\n---\ndated mirror\n", encoding="utf-8")
    _arc_idx = {"feat_shipped_2026_05_01", "lesson_2026_05_01", "bodyonly_2026_05_01", "active_design", "mirror_2026_05_01"}  # orphan NOT indexed
    _arc_got = {c["stem"] for c in ms.archive_candidates(list(_arc_dir.glob("*.md")), _arc_idx)}
    check("vNEXT: archive_candidates flags an indexed dated completed-arc", "feat_shipped_2026_05_01" in _arc_got)
    check("vNEXT: archive_candidates VETOes a dated fact whose DESCRIPTION signals a lesson (frontmatter KEEP → STAYS)", "lesson_2026_05_01" not in _arc_got)
    check("vNEXT: archive_candidates SURFACES a dated fact with a body-only directive (model's Phase-5 judgment is the net — measured: a whole-body veto collapses recall)", "bodyonly_2026_05_01" in _arc_got)
    check("vNEXT: archive_candidates spares an undated active fact", "active_design" not in _arc_got)
    check("vNEXT: archive_candidates spares an UNINDEXED dated fact (only indexed taxes budget)", "orphan_2026_05_01" not in _arc_got)
    check("vNEXT: archive_candidates spares a managed mirror (GC's domain)", "mirror_2026_05_01" not in _arc_got)
    check("vNEXT: archive_candidates surfaces EXACTLY {feat_shipped, bodyonly} on this fixture", _arc_got == {"feat_shipped_2026_05_01", "bodyonly_2026_05_01"})
check("vNEXT: archive_candidates never raises on a missing/odd file (OSError → skip)",
      ms.archive_candidates([_ArcPath("/nonexistent/zzz.md")], {"zzz"}) == [])

# vNEXT: defrag_candidates — bloated ACTIVE-file detector (body-size outlier vs self-consistent median; edge guards).
with _tf.TemporaryDirectory() as _dfg_td:
    _dfg_dir = _ArcPath(_dfg_td)
    for _dfn in "abcd":
        (_dfg_dir / f"{_dfn}.md").write_text("---\nname: " + _dfn + "\n---\n" + ("lean body " * 20), encoding="utf-8")
    (_dfg_dir / "roadmap.md").write_text("---\nname: roadmap\n---\n" + ("bloated body " * 400), encoding="utf-8")
    (_dfg_dir / "big_2026_05_01.md").write_text("---\nname: dated\n---\n" + ("bloated " * 400), encoding="utf-8")
    (_dfg_dir / "mir.md").write_text("---\nname: mir\nmetadata:\n  global_ref: x\n---\n" + ("bloated " * 400), encoding="utf-8")
    (_dfg_dir / "unindexed_big.md").write_text("---\nname: ux\n---\n" + ("bloated " * 400), encoding="utf-8")
    _dfg_idx = {"a", "b", "c", "d", "roadmap", "big_2026_05_01", "mir"}  # unindexed_big NOT indexed
    _dfg_got = {c["stem"] for c in ms.defrag_candidates(list(_dfg_dir.glob("*.md")), _dfg_idx)}
    check("vNEXT: defrag_candidates flags a bloated ACTIVE file (body ≫ median)", "roadmap" in _dfg_got)
    check("vNEXT: defrag_candidates spares a DATED bloated file (Cycle-1 pointer-archive's domain)", "big_2026_05_01" not in _dfg_got)
    check("vNEXT: defrag_candidates spares a bloated MIRROR", "mir" not in _dfg_got)
    check("vNEXT: defrag_candidates spares an UNINDEXED bloated file", "unindexed_big" not in _dfg_got)
    check("vNEXT: defrag_candidates spares the lean active facts", _dfg_got.isdisjoint({"a", "b", "c", "d"}))
    check("vNEXT: defrag_candidates flags EXACTLY {roadmap} on this fixture (high-precision)", _dfg_got == {"roadmap"})
with _tf.TemporaryDirectory() as _dfg_td2:
    _d2 = _ArcPath(_dfg_td2)
    (_d2 / "a.md").write_text("---\nname: a\n---\nx", encoding="utf-8"); (_d2 / "b.md").write_text("---\nname: b\n---\nx", encoding="utf-8")
    check("vNEXT: defrag_candidates edge — <3-fact population → [] (no outlier)", ms.defrag_candidates(list(_d2.glob("*.md")), {"a", "b"}) == [])
with _tf.TemporaryDirectory() as _dfg_td3:
    _d3 = _ArcPath(_dfg_td3)
    for _eqn in "abc":
        (_d3 / f"{_eqn}.md").write_text("---\nname: " + _eqn + "\n---\nidentical body size here\n", encoding="utf-8")
    check("vNEXT: defrag_candidates edge — all-equal median → [] (no degenerate outlier)", ms.defrag_candidates(list(_d3.glob("*.md")), set("abc")) == [])
check("vNEXT: defrag_candidates never raises on a missing/odd file", ms.defrag_candidates([_ArcPath("/nonexistent/q.md")], {"q"}) == [])
with _tf37.TemporaryDirectory() as _td41:
    _s41 = Path(_td41)
    (_s41 / "target.md").write_text("---\nname: target\n---\nbody\n")
    (_s41 / "linker.md").write_text("---\nname: linker\n---\nsee [[target]]\n")
    (_s41 / "lone.md").write_text("---\nname: lone\n---\nno links here\n")
    check("v0.1.41: _inbound_links finds the fact that [[links]] the evict target (orphan-safety)",
          sg._inbound_links(_s41, "target") == ["linker"])
    check("v0.1.41: _inbound_links empty when nothing links the target (safe to evict)",
          sg._inbound_links(_s41, "lone") == [])
# v0.1.43 (session-id, Option A) — the SECRETS FIREWALL across POOLED sessions is the advisor's ship-gate:
# reading N transcripts must NOT widen what reaches context before the scrub. One per-line scrub path, fed from
# all pooled files. Also pins: the multi-session pool surfaces a PRIOR session's intent (the killer-case fix),
# and each signal carries sessionId (the originSessionId source). + _window_transcripts mtime-prune direction.
import os as _os43, tempfile as _tf43, json as _json43, time as _time43
with _tf43.TemporaryDirectory() as _twd43:
    _wpr43 = Path(_twd43)
    (_wpr43 / "old.jsonl").write_text("{}\n"); (_wpr43 / "new.jsonl").write_text("{}\n")
    _os43.utime(_wpr43 / "old.jsonl", (1000, 1000))                                  # ancient → before any marker
    _os43.utime(_wpr43 / "new.jsonl", (_time43.time() + 10, _time43.time() + 10))    # future → after the marker
    check("v0.1.43/A: _window_transcripts keeps mtime>marker, prunes <=marker (current session never dropped)",
          [p.name for p in es._window_transcripts(_wpr43, "2026-06-22T00:00:00+00:00")] == ["new.jsonl"])
    check("v0.1.43/A: _window_transcripts no-marker → keeps ALL (first-pass safe)",
          len(es._window_transcripts(_wpr43, "")) == 2)
    check("v0.1.43/A: _window_transcripts Z-suffix marker prunes right (Gate-2: 3.10 no-op fix — Z normalized)",
          [p.name for p in es._window_transcripts(_wpr43, "2026-06-22T00:00:00Z")] == ["new.jsonl"])
    check("v0.1.43/A: _window_transcripts NAIVE marker treated as UTC not LOCAL (Gate-2: no wrong prior-session drop)",
          [p.name for p in es._window_transcripts(_wpr43, "2026-06-22T00:00:00")] == ["new.jsonl"])
with _tf43.TemporaryDirectory() as _td43:
    _home43 = Path(_td43); _proj43 = _home43 / "proj"; _proj43.mkdir()
    _pr43 = _home43 / ".claude" / "projects" / es.slug_for(_proj43); _pr43.mkdir(parents=True)
    def _tl43(sid, content):
        return _json43.dumps({"timestamp": "2026-06-22T10:00:00Z", "sessionId": sid,
                              "message": {"role": "user", "content": content}}) + "\n"
    (_pr43 / "sessA.jsonl").write_text(_tl43("sessA", "I strongly prefer typed stubs over a type-ignore comment here"))
    _SECRET43 = "export AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLEKEYabcdef0123456789"
    (_pr43 / "sessB.jsonl").write_text(_tl43("sessB", _SECRET43) + _tl43("sessB", "the deploy runs from the makefile release target"))
    _os43.utime(_pr43 / "sessB.jsonl", (_time43.time() + 10, _time43.time() + 10))  # B is the newer session
    _old43 = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_home43)
    try:
        _r43 = es.extract(_proj43, "", 20)
    finally:
        _os43.environ["HOME"] = _old43 if _old43 is not None else ""
    _txt43 = " ".join(s.get("text", "") for s in _r43.get("signals", []))
    check("v0.1.43/A: pooled BOTH window sessions (multi-session coverage, not just newest)",
          len(_r43.get("transcripts", [])) == 2)
    check("v0.1.43/A: FIREWALL holds across pooled files — secret SCRUBBED, value absent (ship-gate)",
          _r43["counts"]["secrets_omitted"] >= 1 and "AKIAIOSFODNN7EXAMPLE" not in _txt43)
    check("v0.1.43/A: a PRIOR session's clean intent surfaced w/ its sessionId (the fresh-session killer-case fix)",
          any(s.get("sessionId") == "sessA" for s in _r43.get("signals", [])))

# ── v0.1.48: uniform signal schema — EVERY emitted signal carries the canonical keyset ──
# The "?"/"s?" bug: error rows + the omitted-summary label grew free-form dict literals that dropped
# signal_type/score, so any consumer's `.get(k,'?')` rendered a literal `?`. The _signal constructor is the
# single funnel; this pins that --json output is UNIFORM over a fixture spanning ALL three classes that
# drifted or could (a scored human turn · an error tool_result · the redacted-secret omitted-summary label).
with _tf43.TemporaryDirectory() as _td48:
    _home48 = Path(_td48); _proj48 = _home48 / "proj"; _proj48.mkdir()
    _pr48 = _home48 / ".claude" / "projects" / es.slug_for(_proj48); _pr48.mkdir(parents=True)
    _SECRET48 = "export AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLEKEYabcdef0123456789"
    def _hl48(text: str) -> str:   # a human-turn transcript line
        return _json43.dumps({"timestamp": "2026-06-22T10:00:00Z", "sessionId": "s48",
                              "message": {"role": "user", "content": text}}) + "\n"
    def _el48(text: str) -> str:   # an error tool_result transcript line (the gotcha branch)
        return _json43.dumps({"timestamp": "2026-06-22T10:00:01Z", "sessionId": "s48",
                              "message": {"role": "user", "content": [
                                  {"type": "tool_result", "is_error": True,
                                   "content": [{"type": "text", "text": text}]}]}}) + "\n"
    (_pr48 / "s48.jsonl").write_text(
        _hl48("Always validate at the root with tests") +    # → a scored human signal (preference marker)
        _hl48(_SECRET48) +                                   # → secrets_omitted → the omitted-summary label
        _el48("Exit code 1 Traceback: connection refused"))  # → an error signal (was [error|?|s?])
    _old48 = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_home48)
    try:
        _r48 = es.extract(_proj48, "", 20)
    finally:
        _os43.environ["HOME"] = _old48 if _old48 is not None else ""
    _sigs48 = _r48.get("signals", [])
    _srcs48 = {s["source"] for s in _sigs48}; _types48 = {s.get("signal_type") for s in _sigs48}
    check("v0.1.48: fixture spans all 3 classes (human · error · omitted-summary label)",
          "human" in _srcs48 and "error" in _srcs48 and "omitted" in _types48 and _r48["counts"]["secrets_omitted"] >= 1)
    check("v0.1.48: EVERY signal carries the canonical keyset (no missing key → no '?' for any consumer)",
          bool(_sigs48) and all(set(s) >= es._CANONICAL_KEYS for s in _sigs48))
    check("v0.1.48: signal_type AND score present + non-None on every signal (the exact '?'/'s?' guard, pre-fix FAILS)",
          all(s.get("signal_type") is not None and s.get("score") is not None for s in _sigs48))
    check("v0.1.48: error signals carry signal_type+score (the reported bug — error rows were [error|?|s?])",
          any(s["source"] == "error" for s in _sigs48)
          and all({"signal_type", "score"} <= set(s) for s in _sigs48 if s["source"] == "error"))
    check("v0.1.48: _CANONICAL_KEYS is single-sourced FROM the constructor (cannot drift from emitted shape)",
          es._CANONICAL_KEYS == frozenset(es._signal("x", "y", signal_type="z", score=0)))

# ── v0.1.49: error-channel noise filter (<tool_use_error>) + cap ──────────────────
# Measured: ~73% of raw error tool-results are <tool_use_error> wrappers — Claude's OWN tool-protocol
# mistakes (file-not-read, string-not-found), NEVER an env gotcha. Drop them; KEEP genuine env signal
# (a ModuleNotFoundError inline-script error IS "X isn't installed here"); cap the UNRANKED survivors AFTER
# the filter. v0.1.53 REVERSAL: classifier-denials + the model-unavailable message — v0.1.49 kept the denial
# as "highest-signal" — are now DROPPED as harness artifacts (a transient classifier event, not a durable env
# gotcha; the real lesson is authored from session context, not the denial row). User-flagged as noise.
def _el49(text: str, sid: str = "s49") -> str:   # an error tool_result transcript line
    return _json43.dumps({"timestamp": "2026-06-22T10:00:00Z", "sessionId": sid,
                          "message": {"role": "user", "content": [
                              {"type": "tool_result", "is_error": True,
                               "content": [{"type": "text", "text": text}]}]}}) + "\n"
# Scenario A — drop/keep behaviour (under the cap)
with _tf43.TemporaryDirectory() as _td49a:
    _h49a = Path(_td49a); _p49a = _h49a / "proj"; _p49a.mkdir()
    _pr49a = _h49a / ".claude" / "projects" / es.slug_for(_p49a); _pr49a.mkdir(parents=True)
    (_pr49a / "s.jsonl").write_text(
        _el49("<tool_use_error>String to replace not found in file.</tool_use_error>") +   # DROP (tool-protocol)
        _el49("<tool_use_error>File has not been read yet.</tool_use_error>") +            # DROP (tool-protocol)
        _el49('Exit code 1 Traceback (most recent call last): File "<string>", line 1 ModuleNotFoundError: No module named \'foo\'') +  # KEEP (env gotcha)
        _el49("Permission for this action was denied by the Claude Code auto mode classifier. Reason: rm -rf of a real dir") +          # v0.1.53: now DROP (harness artifact; reverses v0.1.49)
        _el49("Exit code 127 somecli: command not found"))                                 # KEEP (env gotcha)
    _old49a = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_h49a)
    try:
        _r49a = es.extract(_p49a, "", 30)
    finally:
        _os43.environ["HOME"] = _old49a if _old49a is not None else ""
    _errs49a = [s for s in _r49a["signals"] if s["source"] == "error"]
    _etext49a = " ".join(s["text"] for s in _errs49a)
    check("v0.1.49: <tool_use_error> tool-protocol noise DROPPED from signals (the 73%-of-raw class)",
          "tool_use_error" not in _etext49a and "String to replace not found" not in _etext49a)
    check("v0.1.49: filtered tool-protocol errors counted as noise (≥2 dropped here)",
          _r49a["counts"]["noise"] >= 2)
    check("v0.1.49: a ModuleNotFoundError inline-script error is KEPT (NOT L2 — it's a durable env gotcha)",
          any("ModuleNotFoundError" in s["text"] for s in _errs49a))
    check("v0.1.53: a classifier-denial is now DROPPED as a harness artifact (REVERSES v0.1.49's keep — user-flagged noise, not a durable gotcha)",
          not any("auto mode classifier" in s["text"] for s in _errs49a))
    check("v0.1.49: surviving errors still carry the canonical keyset (filter didn't bypass _signal)",
          bool(_errs49a) and all(set(s) >= es._CANONICAL_KEYS for s in _errs49a))
# Scenario B — cap binds AFTER the filter (wrapped error FIRST → a naive cap-raw-then-filter would yield 7, not 8)
with _tf43.TemporaryDirectory() as _td49b:
    _h49b = Path(_td49b); _p49b = _h49b / "proj"; _p49b.mkdir()
    _pr49b = _h49b / ".claude" / "projects" / es.slug_for(_p49b); _pr49b.mkdir(parents=True)
    _lines49b = [_el49("<tool_use_error>File has not been read yet.</tool_use_error>")]  # FIRST → drops; tests order
    _lines49b += [_el49(f"Exit code 1 distinct env failure number {i}: connection refused") for i in range(es.MAX_ERRORS + 4)]
    (_pr49b / "s.jsonl").write_text("".join(_lines49b))
    _old49b = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_h49b)
    try:
        _r49b = es.extract(_p49b, "", 30)
    finally:
        _os43.environ["HOME"] = _old49b if _old49b is not None else ""
    _errs49b = [s for s in _r49b["signals"] if s["source"] == "error"]
    check("v0.1.49: error survivors capped at MAX_ERRORS AFTER the filter (cap-raw-then-filter would give MAX_ERRORS-1)",
          len(_errs49b) == es.MAX_ERRORS)
    check("v0.1.49: the leading <tool_use_error> is still absent under the cap (filter precedes cap)",
          all("tool_use_error" not in s["text"] for s in _errs49b))

# ── v0.1.50: foundation signal-extraction sharpeners (distill stage 1) ──────────────────
# Change 1: the "Another Claude session sent a message:" prose wrapper is agent-coordination noise that leaks
# through _NOISE (the bare <teammate-message tag arm doesn't fire — the prose precedes the tag). Change 2: dedup
# the error channel to a CLASS (byte-noise variants collapse; distinct errors stay separate — the recall guard).
# _error_key unit assertions (the recall guard with real teeth — GAP-1/GAP-2):
check("v0.1.50: _error_key MERGES same class+msg differing only in byte-noise (exit/line/path)",
      es._error_key('Exit code 1 Traceback ... File "/tmp/a/x.py", line 5 ModuleNotFoundError: No module named \'foo\'')
      == es._error_key('Exit code 2 Traceback ... File "/tmp/b/y.py", line 99 ModuleNotFoundError: No module named \'foo\''))
check("v0.1.50: _error_key SEPARATES same family / different identifier (foo vs bar — the STRONG recall guard)",
      es._error_key("ModuleNotFoundError: No module named 'foo'") != es._error_key("ModuleNotFoundError: No module named 'bar'"))
check("v0.1.50: _error_key SEPARATES different families (ModuleNotFoundError vs PermissionError)",
      es._error_key("ModuleNotFoundError: x") != es._error_key("PermissionError: x"))
check("v0.1.50: _error_key SEPARATES no-head command-not-found by binary name (foocli vs barcli — GAP-2, no path-strip)",
      es._error_key("Exit code 127 /usr/bin/foocli: command not found") != es._error_key("Exit code 127 /usr/bin/barcli: command not found"))
check("v0.1.50: _error_key PRESERVES signal-bearing hex/clock (HRESULT 0x… + slice [10:20] stay distinct — gate-2 symmetry fix)",
      es._error_key("RuntimeError: HRESULT 0x80004005") != es._error_key("RuntimeError: HRESULT 0xC0000005")
      and es._error_key("IndexError: bad slice arr[10:20]") != es._error_key("IndexError: bad slice arr[30:40]"))
# End-to-end through extract(): Change-1 drop + Change-2 collapse
with _tf43.TemporaryDirectory() as _td50:
    _h50 = Path(_td50); _p50 = _h50 / "proj"; _p50.mkdir()
    _pr50 = _h50 / ".claude" / "projects" / es.slug_for(_p50); _pr50.mkdir(parents=True)
    def _hl50(t: str) -> str:
        return _json43.dumps({"timestamp": "2026-06-22T10:00:00Z", "sessionId": "s50", "message": {"role": "user", "content": t}}) + "\n"
    def _el50(t: str) -> str:
        return _json43.dumps({"timestamp": "2026-06-22T10:00:00Z", "sessionId": "s50", "message": {"role": "user", "content": [
            {"type": "tool_result", "is_error": True, "content": [{"type": "text", "text": t}]}]}}) + "\n"
    (_pr50 / "s.jsonl").write_text(
        _hl50("Another Claude session sent a message: please run the tests") +     # Change-1 → DROP
        _hl50("Always pin the dependency versions in the lockfile") +              # real human turn → KEEP
        _el50('Exit code 1 File "/tmp/a/x.py", line 5 KeyError: \'gate\'') +       # error class A …
        _el50('Exit code 2 File "/tmp/b/y.py", line 88 KeyError: \'gate\'') +      # … collapses with A (byte-noise)
        _el50("PermissionError: [Errno 13] Permission denied"))                    # error class B → stays separate
    _old50 = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_h50)
    try:
        _r50 = es.extract(_p50, "", 30)
    finally:
        _os43.environ["HOME"] = _old50 if _old50 is not None else ""
    _sig50 = _r50["signals"]; _htext50 = " ".join(s["text"] for s in _sig50 if s["source"] == "human")
    _errs50 = [s for s in _sig50 if s["source"] == "error"]
    check("v0.1.50: Change-1 'Another Claude session...' wrapper DROPPED from human signal, real turn KEPT (end-to-end)",
          "Another Claude session" not in _htext50 and any("pin the dependency" in s["text"] for s in _sig50))
    check("v0.1.50: Change-2 same-class errors COLLAPSE, distinct family stays → exactly 2 error rows (KeyError + PermissionError)",
          len(_errs50) == 2 and any("KeyError" in s["text"] for s in _errs50) and any("PermissionError" in s["text"] for s in _errs50))

# ── v0.1.51 (extraction REBUILT v0.1.55): distill — workflow-recurrence scan (distill_scan.py) ──────────
# The v0.1.51 recall guards retarget to the v0.1.55 decomposition: pure per-segment `_seg_template`
# + command-level `_scan_cmd` (all-segment; the retired first-segment `_template` undercounted 4× on
# the measured corpus). REAL command forms (multi-line cd-first-line / heredoc / bare-cd), NOT the
# rare `cd && ` join.
check("v0.1.51/55: _scan_cmd multi-line cd-first-line → the real command (cd line stripped)",
      ds._scan_cmd("cd /home/drei/project/x\npython3 tests/smoke.py")[0] == ["python3 tests/smoke.py"])
check("v0.1.51/55: _scan_cmd bare cd → nothing (a 'cd' is NOT a workflow template)",
      ds._scan_cmd("cd /home/drei/project/x") == ([], []))
check("v0.1.55: heredoc → body dropped AND the 'python3 -' false class stoplisted (was a v0.1.51 row)",
      ds._scan_cmd("cd /x\npython3 - <<'PY'\nprint(1)\nPY") == ([], []))
_v55 = ds._scan_cmd("cd /x\nS=plugins/y\npython3 $S/foo.py")[0]
check("v0.1.51/55: _scan_cmd drops a leading VAR= assignment, templates the real command",
      len(_v55) == 1 and _v55[0].startswith("python3") and "S=" not in _v55[0])
check("v0.1.51/55: _seg_template GROUPS branch variants (checkout -b feat/X == feat/Y)",
      ds._seg_template("git checkout -b feat/X") == ds._seg_template("git checkout -b feat/Y") == "git checkout -b")
check("v0.1.51/55: _seg_template SEPARATES distinct subcommands (push != pull)",
      ds._seg_template("git push") != ds._seg_template("git pull"))
_cdp55 = ds._scan_cmd("cd /home/x\nmypy --config-file mypy.ini")[0]
check("v0.1.51/55: templates never carry a cd-prefix or an abs path (non-empty — no vacuous all())",
      len(_cdp55) == 1 and _cdp55[0].split()[0] != "cd" and "/home/" not in _cdp55[0])
# End-to-end scan() through a fixture transcript (recurrence + firewall + contract shape)
def _bl51(cmd: str) -> str:   # an assistant Bash tool_use transcript line
    return _json43.dumps({"timestamp": "2026-06-22T10:00:00Z", "sessionId": "s51",
                          "message": {"role": "assistant", "content": [
                              {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}) + "\n"
with _tf43.TemporaryDirectory() as _td51:
    _h51 = Path(_td51); _p51 = _h51 / "proj"; _p51.mkdir()
    _pr51 = _h51 / ".claude" / "projects" / es.slug_for(_p51); _pr51.mkdir(parents=True)
    _repo51 = str(_p51)
    _lines51 = []
    for _i in range(3):
        _lines51.append(_bl51(f"cd {_repo51}\npython3 tests/smoke.py"))          # → "python3 tests/smoke.py" ×3
        _lines51.append(_bl51(f"cd {_repo51}\ngit push -u origin feat/x{_i}"))    # → "git push -u origin" ×3 (branch varies)
    for _ in range(2):  # ≥2× so absence tests the MECHANISM (firewall drop / _template→None), NOT the count<2 filter
        _lines51.append(_bl51(f"cd {_repo51}\nexport AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLEKEYabcdef0123456789"))  # secret → firewall drops
        _lines51.append(_bl51(f"cd {_repo51}"))                                   # bare cd → _template returns None
    _lines51.append(_bl51(f"cd {_repo51}\nls -la"))                # stoplisted (ls) → never a row (v0.1.55)
    _lines51.append(_bl51(f"cd {_repo51}\noneoff-tool run"))       # NOT stoplisted, count 1 → the MIN_RECUR filter
    (_pr51 / "s.jsonl").write_text("".join(_lines51))
    _old51 = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_h51)
    try:
        _r51 = ds.scan(_p51, "")
    finally:
        _os43.environ["HOME"] = _old51 if _old51 is not None else ""
    _tpls51 = {r["template"]: r["count"] for r in _r51["recurring"]}
    check("v0.1.51: scan surfaces the repeated MULTI-LINE workflow (smoke ×3, push ×3 across branch variants)",
          _tpls51.get("python3 tests/smoke.py") == 3 and _tpls51.get("git push -u origin") == 3)
    check("v0.1.51: scan FIREWALL drops the secret command (absent from templates + samples)",
          not any("AWS_SECRET" in r["template"] or "AKIA" in r["sample"] for r in _r51["recurring"]))
    check("v0.1.51/55: scan — bare cd + ls do NOT surface (no cd template; ls stoplisted)",
          not any(r["template"].startswith("cd") for r in _r51["recurring"]) and "ls -la" not in _tpls51)
    check("v0.1.55: MIN_RECUR — a genuine (non-stoplisted) one-off stays below the count≥2 bar",
          "oneoff-tool run" not in _tpls51)
    check("v0.1.55: scan --json contract shape (+chains, +days — the exact-set pins updated with the keys)",
          set(_r51) == {"window", "scanned", "recurring", "chains"}
          and set(_r51["scanned"]) == {"sessions", "commands", "days"}
          and all(set(r) == {"template", "count", "days", "sample"} for r in _r51["recurring"]))
with _tf43.TemporaryDirectory() as _td51b:   # "create nothing" — distinct NON-stoplisted one-offs, so the
    # empty result exercises the MIN_RECUR count<2 filter itself (v0.1.55: the old `echo …` probes were
    # intercepted by the stoplist before ever reaching the tally — a vacuous pass).
    _h51b = Path(_td51b); _p51b = _h51b / "proj"; _p51b.mkdir()
    _pr51b = _h51b / ".claude" / "projects" / es.slug_for(_p51b); _pr51b.mkdir(parents=True)
    (_pr51b / "s.jsonl").write_text("".join(_bl51(f"cd {_p51b}\nprobe-tool-{_i} run") for _i in range(4)))
    _old51b = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_h51b)
    try:
        _r51b = ds.scan(_p51b, "")
    finally:
        _os43.environ["HOME"] = _old51b if _old51b is not None else ""
    check("v0.1.51/55: scan 'create nothing' — distinct one-offs surface NO recurring workflow (count<2)",
          _r51b["recurring"] == [] and _r51b["chains"] == [])

# ── v0.1.44: procedure-integrity detector — the lazy-skip safeguard ──────────────────
# The MEASURED 2026-06-22 failure: 3 dreams ran 0/0/0 verification while self-labeled
# SUBSTANTIAL/HEAVY. The predicate FIRES on that signature (magnitude>=SUBSTANTIAL AND tally==0),
# resting on script-derived git_commits (not the self-report). These pin the regression + the
# no-false-fire boundary (LIGHT/maintenance/bootstrap/seed) + the legacy no-op + the --persist gate.
def _pi(commits: int, cands: int, c: int = 0, cc: int = 0, u: int = 0, applied: "str | None" = None) -> Any:
    r: Any = {"scope": {"git_commits": commits, "session_candidates": cands},
              "verification": {"confirmed": c, "corrected": cc, "unverifiable": u}}
    if applied is not None:
        r["rigor"] = {"applied": applied}
    return r

# FIRES on the 3 real failures (by their logged field-values)
check("v0.1.44: FIRES on rushed HEAVY 11c/0cand/0-0-0 (the worst real failure — 0 candidates)",
      not ms.procedure_integrity(_pi(11, 0, applied="HEAVY"))[0])
check("v0.1.44: FIRES on rushed SUBSTANTIAL 3c+2cand/0-0-0",
      not ms.procedure_integrity(_pi(3, 2, applied="SUBSTANTIAL"))[0])
check("v0.1.44: FIRES on rushed SUBSTANTIAL 4c+2cand/0-0-0",
      not ms.procedure_integrity(_pi(4, 2, applied="SUBSTANTIAL"))[0])
# SPARES legit passes that recorded verification, and the legit low-magnitude cases the skill supports
check("v0.1.44: SPARES the corrected dream (4c+2cand, 19/2/2)",
      ms.procedure_integrity(_pi(4, 2, 19, 2, 2, applied="SUBSTANTIAL"))[0])
check("v0.1.44: SPARES a SUBSTANTIAL pass with tally>0 (verification recorded)",
      ms.procedure_integrity(_pi(2, 4, 10, 2, 0))[0])
check("v0.1.44: SPARES a LIGHT pass (magnitude<=2), even at 0/0/0",
      ms.procedure_integrity(_pi(2, 0))[0] and ms.procedure_integrity(_pi(0, 2))[0])
check("v0.1.44: SPARES maintenance/bootstrap (0 commits, 0 candidates, 0/0/0)",
      ms.procedure_integrity(_pi(0, 0))[0])
# the downgrade dodge: HEAVY magnitude relabeled LIGHT, 0 tally -> still FIRES + surfaces the dodge
_dd_ok, _dd_reason, _dd_sev = ms.procedure_integrity(_pi(11, 0, applied="LIGHT"))
check("v0.1.44: FIRES on the downgrade dodge (HEAVY magnitude labeled LIGHT, 0/0/0)", not _dd_ok)
check("v0.1.44: the downgrade dodge is SURFACED in the reason", "below magnitude" in _dd_reason)
# severity: self-admitted SUBSTANTIAL/HEAVY -> alert; unlabeled -> warn
check("v0.1.44: severity 'alert' when self-labeled SUBSTANTIAL/HEAVY (self-admission)",
      ms.procedure_integrity(_pi(11, 0, applied="HEAVY"))[2] == "alert")
check("v0.1.44: severity 'warn' when not self-labeled substantial",
      ms.procedure_integrity(_pi(11, 0))[2] == "warn")
# legacy / non-conformant -> NO-OP (never retroactively flag): missing verification/scope, non-dict
check("v0.1.44: NO-OP (ok) on a legacy record missing the verification block",
      ms.procedure_integrity({"scope": {"git_commits": 11, "session_candidates": 0}})[0])
check("v0.1.44: NO-OP (ok) on a record missing the scope block",
      ms.procedure_integrity({"verification": {"confirmed": 0, "corrected": 0, "unverifiable": 0}})[0])
check("v0.1.44: NO-OP (ok) on a non-dict record",
      ms.procedure_integrity(cast(Any, "junk"))[0] and ms.procedure_integrity(cast(Any, None))[0])
# coercion: model-slip string ints handled (never crashes, still fires)
check("v0.1.44: coerces model-slip string ints (still FIRES on '11'/'0' + '0'/'0'/'0')",
      not ms.procedure_integrity({"scope": {"git_commits": "11", "session_candidates": "0"},
                                  "verification": {"confirmed": "0", "corrected": "0", "unverifiable": "0"}})[0])
# NEVER raises on junk — incl. NON-FINITE floats (json.loads accepts NaN/Infinity; int(nan/inf) raises) [Gate-2 blocker fix]
_pi_crashed = False
try:
    ms.procedure_integrity(cast(Any, [1, 2, 3]))
    ms.procedure_integrity(cast(Any, {"scope": 5, "verification": "x"}))
    ms.procedure_integrity(cast(Any, {"scope": {"git_commits": None}, "verification": {"confirmed": [1]}}))
    ms.procedure_integrity(cast(Any, {"scope": {"git_commits": float("nan"), "session_candidates": float("inf")},
                                      "verification": {"confirmed": float("-inf"), "corrected": 0, "unverifiable": 0}}))
    ms.procedure_integrity(cast(Any, {"scope": {"git_commits": "inf", "session_candidates": "nan"},
                                      "verification": {"confirmed": "0", "corrected": "0", "unverifiable": "0"}}))
except Exception:  # noqa: BLE001 — ANY raise fails the never-raise contract
    _pi_crashed = True
check("v0.1.44: procedure_integrity NEVER raises on junk (incl. NaN/Infinity floats — Gate-2 blocker)", not _pi_crashed)
check("v0.1.44: non-finite floats (NaN/±inf) coerce to 0 — magnitude 0, SPARED (no crash at the render boundary)",
      ms.procedure_integrity({"scope": {"git_commits": float("nan"), "session_candidates": float("inf")},
                              "verification": {"confirmed": 0, "corrected": 0, "unverifiable": 0}})[0])
check("v0.1.44: a negative/junk tally does NOT dodge (tally<=0 fires on substantial magnitude — Gate-2 hardening)",
      not ms.procedure_integrity(_pi(11, 0, c=-100))[0])
# the FULL 13-record separation (the spec's empirical proof, PINNED): exactly the 3 rushed fire.
# tuples = (commits, cands, confirmed, corrected, unverifiable) from the live .consolidation-log.jsonl
_records_13 = [
    (11, 8, 7, 1, 0), (6, 10, 7, 1, 0), (11, 2, 11, 1, 0), (2, 4, 10, 2, 0), (2, 3, 12, 2, 0),
    (4, 2, 16, 1, 0), (11, 1, 15, 1, 0), (21, 5, 6, 1, 0), (2, 2, 16, 0, 0),
    (11, 0, 0, 0, 0), (3, 2, 0, 0, 0), (4, 2, 0, 0, 0),    # the 3 rushed failures
    (4, 2, 19, 2, 2),                                       # the corrected dream
]
_fires = sum(1 for (gc, cd, c, cc, u) in _records_13 if not ms.procedure_integrity(_pi(gc, cd, c, cc, u))[0])
check("v0.1.44: the 13 real records separate cleanly — EXACTLY 3 fire (the spec's empirical proof)",
      _fires == 3)
# render integration: the panel is GATED on `judged` (set by main() iff --persist). A seed/preview
# render (judged=False, the default) is the BEFORE state and must NOT show the panel — the re-gate F1 fix.
check("v0.1.44: render(judged=True) SHOWS the PROCEDURE INTEGRITY panel on a firing record",
      "PROCEDURE INTEGRITY" in rd.render(_pi(11, 0, applied="HEAVY"), judged=True))
check("v0.1.44: render(judged=False) does NOT show the panel (seed/preview — the --persist gate)",
      "PROCEDURE INTEGRITY" not in rd.render(_pi(11, 0, applied="HEAVY"), judged=False))
check("v0.1.44: render() default (no judged) does NOT show the panel (back-compat)",
      "PROCEDURE INTEGRITY" not in rd.render(_pi(11, 0, applied="HEAVY")))
check("v0.1.44: render(judged=True) shows NO panel on a clean record (no false-fire in the panel)",
      "PROCEDURE INTEGRITY" not in rd.render(_pi(2, 4, 10, 2, 0), judged=True))

# ── v0.1.53: signal-pipeline hardening (spec: docs/signal-pipeline-hardening.spec.md) ──
# Bug 1 — compound control acks demote to `ack` (score 0); _MARKERS WIN (reorder); signal turns stay surfaced.
for _t53 in ["Yes go ahead", "Ship it please", "Yes ship it", "Retry please", "Let's continue",
             "Implement it now", "Ship it and let's continue logically"]:
    check(f"v0.1.53 ack-demote (whole turn is ack-vocab → score 0): {_t53!r}", es._classify(_t53)[0] == "ack")
check("v0.1.53 ack: marker WINS over ack (reorder) — 'always' → preference, not ack",
      es._classify("Yes, but always validate at the root")[0] == "preference")
# the recall guard (cr2 CONFIRMED): a SHORT turn opening with a control verb but carrying a CONTENT noun is NOT
# an ack — the signal lives in the noun ("postgres migration", "parser.py", "50"), which the whole-turn vocab
# check keeps as `statement`/score-1 (a length-bound alone wrongly demoted these to score-0).
for _keep53 in ["proceed with the postgres migration", "yes the bug is in parser.py",
                "push to the staging remote only", "Sure let's allow up to 50",
                "Sure I'll live test it, give me a series of logical verification patterns",
                "Let's add a toggle in the search options modal as an option"]:
    check(f"v0.1.53 ack-KEEP (content noun → stays signal): {_keep53!r}", es._classify(_keep53)[0] != "ack")
# Bug 2 — strip leading [Image #N] markers; image-only turn → empty (noise).
check("v0.1.53 image: marker stripped, real text kept",
      es._strip_markers("[Image #1] [Image #2] the table is broken") == "the table is broken")
check("v0.1.53 image: image-only turn strips to empty (→ noise)", es._strip_markers("[Image #1] [Image #2]") == "")
check("v0.1.53 attach: leading quoted screenshot paths stripped, the prose that FOLLOWS revealed (real case)",
      es._strip_markers("'/home/d/Screenshot from 2026.png' '/home/d/b.png' Here are the impressions, revise")
      == "Here are the impressions, revise")
check("v0.1.53 attach: a BARE leading path is NOT stripped (it may be the subject)",
      es._strip_markers("/home/x/config.py needs fixing") == "/home/x/config.py needs fixing")
check("v0.1.53 attach: quoted path-ONLY strips to empty → noise via the empty-check (the real pipeline path, not _PATH_ONLY)",
      es._strip_markers("'/home/x/a.png' '/home/x/b.png'") == "")
# Bug 3 — path-only turns are noise; path + prose is kept.
check("v0.1.53 path-only: bare screenshot paths → noise", bool(es._PATH_ONLY.match("'/home/x/a.png' '/home/x/b.png'")))
check("v0.1.53 path-only: QUOTED path WITH SPACES → noise (the real screenshot case bare-\\S+ missed)",
      bool(es._PATH_ONLY.match("'/home/d/Pictures/Screenshot from 2026-06-22 19-48-49.png' '/home/d/Screenshot from 2.png'")))
check("v0.1.53 path-only: a single bare path → noise", bool(es._PATH_ONLY.match("/home/x/a.png")))
check("v0.1.53 path-only: path + prose is NOT path-only", not es._PATH_ONLY.match("see /home/x/a.png it is broken"))
# Bug 4 — error-channel noise arms (DROP harness/transient/own-bug) vs real env gotchas (KEEP).
for _e53, _drop53 in [
    ("Permission for this action was denied by the Claude Code auto mode classifier. Reason: x", True),
    ("claude-opus-4-8[1m] is temporarily unavailable, so auto mode cannot determine the safety of Bash", True),
    ("Exit code 1 === ruff check === E501 Line too long (102 > 100) --> a.py:1:101", True),
    ("Exit code 1 E501 Line too long (103 > 100) --> app.py:234", True),
    ("Exit code 1 All checks passed! Would reformat: app.py 1 file would be reformatted", True),
    ('Exit code 1 Traceback (most recent call last): File "<stdin>", line 20 KeyError: audit', True),
    ('Traceback File "<string>", line 5 ModuleNotFoundError: No module named requests', False),  # genuine env fact → KEEP
    ('Traceback File "<stdin>", line 3 OperationalError: could not connect: Connection refused', False),  # env fact via -c → KEEP (fix B)
    ("FileNotFoundError: /usr/bin/ruff check failed to find config", False),  # real error mentioning 'ruff check' → KEEP (fix G)
    ("ruff: command not found", False),                          # real env gotcha (no === / check) → KEEP
    ("HTTP 401 Unauthorized: bad token endpoint", False),        # real env error → KEEP
    ("PermissionError: [Errno 13] Permission denied: '/etc/x'", False),  # filesystem EPERM (not the classifier) → KEEP
]:
    check(f"v0.1.53 error-noise {'DROP' if _drop53 else 'KEEP'}: {_e53[:40]!r}", es._is_error_noise(_e53) is _drop53)
# Bug 5 — `--audit --into <cycle>` injects the audit block (no manual merge → no KeyError); the --into path is NOT
# mis-read as the positional project_dir. Hermetic: HOME → tmp (no real ~/.claude writes).
import subprocess as _sp53, os as _os53  # noqa: E402
with _tf43.TemporaryDirectory() as _td53:
    (Path(_td53) / "home").mkdir(); (Path(_td53) / "proj").mkdir()
    (Path(_td53) / "snap.json").write_text("{}")
    _cyc53 = Path(_td53) / "cycle.json"
    _cyc53.write_text('{"project":"p","marker":{"timestamp":"2026-01-01T00:00:00Z"}}')
    _scr53 = str(ROOT / "plugins" / "consolidate-memory" / "scripts" / "memory_status.py")
    _sp53.run([sys.executable, _scr53, "--audit", str(Path(_td53) / "snap.json"), "--into", str(_cyc53),
               str(Path(_td53) / "proj")], capture_output=True, text=True, timeout=60,
              env={**_os53.environ, "HOME": str(Path(_td53) / "home")})
    _after53 = _json43.loads(_cyc53.read_text())
    check("v0.1.53 bug5: --audit --into injects the audit block (no KeyError, no manual merge)",
          isinstance(_after53.get("audit"), dict))
    # the mutation-log lands under the PROJECT's slug → proves --into was NOT consumed as the positional
    # project_dir (else slug_for(cycle.json) and this path wouldn't exist) — the _argpaths regression guard.
    _mlog53 = Path(_td53) / "home" / ".claude" / "projects" / ms.slug_for(Path(_td53) / "proj") / "memory" / ".mutation-log.jsonl"
    check("v0.1.53 bug5: --audit wrote the mutation-log under the PROJECT slug (--into NOT mis-read as project_dir)",
          _mlog53.exists())

# --- v0.1.54: the dream-arc contract (write-time cues + record capture + surfaces) ---
# (1) validate_cycle_record: `dream` container checks (dict at top level, beats a list).
check("v0.1.54 validate: warns on non-dict dream", "dream is not a dict" in
      ms.validate_cycle_record({"dream": []}))
check("v0.1.54 validate: warns on non-list dream.beats", "dream.beats is not a list" in
      ms.validate_cycle_record({"dream": {"beats": "x"}}))
check("v0.1.54 validate: SILENT on a well-formed dream block",
      ms.validate_cycle_record({"dream": {"sleep": "> *💤 s*", "beats": ["> *🌙 b*"], "wake": "> *☀️ w*"}}) == [])

# (2) dashboard presence line — gated on the key: with `dream` → DREAM ARC line (beats counted,
# missing halves flagged ✗); without → not rendered (legacy byte-path untouched).
_dr54 = cast(ms.CycleRecord, {"project": "p", "session": "s",
                              "dream": {"sleep": "> *💤 s*", "beats": ["> *🌙 a*", "> *🌙 b*"], "wake": "> *☀️ w*"}})
_dr54_out = rd.render(_dr54)
check("v0.1.54 render: DREAM ARC line present when captured (sleep · N beats · wake)",
      "DREAM ARC" in _dr54_out and "2 beats" in _dr54_out and "sleep" in _dr54_out and "wake" in _dr54_out)
_dr54_partial = rd.render(cast(ms.CycleRecord, {"project": "p", "dream": {"beats": ["> *🌙 a*"]}}))
check("v0.1.54 render: partial arc shows its gaps (✗ sleep / ✗ wake, 1 beat)",
      "DREAM ARC" in _dr54_partial and "✗ sleep" in _dr54_partial and "✗ wake" in _dr54_partial and "1 beat" in _dr54_partial)
check("v0.1.54 render: NO DREAM ARC line without the key (legacy unchanged)",
      "DREAM ARC" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s"})))
# a JSON-null stanza must read ABSENT (✗), never a truthy str(None) — the null-arc honesty fix.
_dr54_null = rd.render(cast(ms.CycleRecord, {"project": "p", "dream": {"sleep": None, "beats": ["> *🌙 a*"], "wake": None}}))
check("v0.1.54 render: null sleep/wake → ✗ gaps (str(None) truthiness fixed)",
      "✗ sleep" in _dr54_null and "✗ wake" in _dr54_null and "1 beat" in _dr54_null)

# (3) the HTML surface: the template ships the gated panel (hidden by default; JS reveals) and
# build_html embeds the dream data through the XSS-safe embed (round-trip via the escaped JSON).
_tpl54 = (ROOT / "plugins" / "consolidate-memory" / "scripts" / "dashboard.template.html").read_text(encoding="utf-8")
check("v0.1.54 html: template ships the dream panel, hidden by default",
      'id="dream-blk" style="display:none"' in _tpl54 and 'id="dream-arc"' in _tpl54 and "The Dream" in _tpl54)
_html54 = rhtml.build_html(cast(dict, _dr54), [], "2026-07-01T00:00:00+00:00")
check("v0.1.54 html: build_html embeds the dream block (safe-embedded, round-trippable)",
      _json43.loads(_html54.split('id="cm-data">', 1)[1].split("</script>", 1)[0])["cycles"][-1]["dream"]["beats"][0] == "> *🌙 a*")

# (4) write-time cues — env-gated, stderr-only, stdout stays pure. Subprocess-driven (the gate is
# os.environ at runtime). Hermetic HOME (no real ~/.claude reads for the store-derived paths).
_scripts54 = ROOT / "plugins" / "consolidate-memory" / "scripts"
with _tf43.TemporaryDirectory() as _td54:
    _home54 = str(Path(_td54) / "home"); (Path(_td54) / "home").mkdir()
    _proj54 = str(Path(_td54) / "proj"); (Path(_td54) / "proj").mkdir()

    def _run54(script: str, *args: str, cue: bool) -> "tuple[str, str, int]":
        env = {**_os53.environ, "HOME": _home54}
        env.pop("CM_DREAM_ARC", None)
        if cue:
            env["CM_DREAM_ARC"] = "1"
        p = _sp53.run([sys.executable, str(_scripts54 / script), *args],
                      capture_output=True, text=True, timeout=60, env=env)
        return p.stdout, p.stderr, p.returncode

    for _script54, _args54 in [("memory_status.py", (_proj54,)), ("memory_status.py", (_proj54, "--json")),
                               ("extract_signals.py", (_proj54, "--json")), ("sync_global.py", ("--list", _proj54)),
                               ("sync_global.py", ("--tokens", _proj54, "--json")), ("distill_scan.py", (_proj54, "--json"))]:
        _lbl54 = f"{_script54} {' '.join(a for a in _args54 if a.startswith('--')) or '(plain)'}"
        _so54, _se54, _ = _run54(_script54, *_args54, cue=True)
        check(f"v0.1.54 cue ON → [dream-arc] on stderr only: {_lbl54}",
              "[dream-arc]" in _se54 and "[dream-arc]" not in _so54)
        _so54n, _se54n, _ = _run54(_script54, *_args54, cue=False)
        check(f"v0.1.54 cue OFF → silent: {_lbl54}",
              "[dream-arc]" not in _se54n and "[dream-arc]" not in _so54n)
        if "--json" in _args54:
            check(f"v0.1.54 stdout purity under cue: {_lbl54}", isinstance(_json43.loads(_so54), dict))
    # render_dashboard: cue ONLY with --persist, split by procedure integrity (WAKE ↔ NOT-over).
    _clean54 = Path(_td54) / "clean.json"
    _clean54.write_text(_json43.dumps({"project": "p", "scope": {"git_commits": 9, "session_candidates": 3},
                                       "verification": {"confirmed": 3, "corrected": 1, "unverifiable": 0},
                                       "marker": {"timestamp": "2026-07-01T00:00:00Z"}}))
    _lazy54 = Path(_td54) / "lazy.json"
    _lazy54.write_text(_json43.dumps({"project": "p", "scope": {"git_commits": 9, "session_candidates": 3},
                                      "verification": {"confirmed": 0, "corrected": 0, "unverifiable": 0},
                                      "marker": {"timestamp": "2026-07-01T00:00:01Z"}}))
    _pdir54 = str(Path(_td54) / "persist"); Path(_pdir54).mkdir()
    _so54, _se54, _rc54 = _run54("render_dashboard.py", str(_clean54), cue=True)
    check("v0.1.54 render cue: NO cue without --persist (preview render is mid-dream, not a boundary)",
          _rc54 == 0 and "[dream-arc]" not in _se54)
    # the clean persist does NOT wake — two mandatory SKILL steps remain (--diffs, render_html);
    # it cues "Phase 5 continues" and the WAKE cue fires at render_html (the archive open).
    _so54, _se54, _rc54 = _run54("render_dashboard.py", str(_clean54), "--persist", _pdir54, cue=True)
    check("v0.1.54 render cue: clean --persist (exit 0) → continue-Phase-5 hint, NOT a wake",
          _rc54 == 0 and "persist clean" in _se54 and "WAKE comes after that, not now" in _se54
          and "WAKE now" not in _se54)
    _so54, _se54, _rc54 = _run54("render_dashboard.py", str(_lazy54), "--persist", _pdir54, cue=True)
    check("v0.1.54 render cue: integrity exit-3 --persist → the NOT-over hint, never a wake",
          _rc54 == 3 and "NOT over" in _se54 and "WAKE now" not in _se54)
    _so54, _se54, _rc54 = _run54("render_dashboard.py", str(_lazy54), "--persist", _pdir54, cue=False)
    check("v0.1.54 render cue: env absent → exit-3 path silent too", _rc54 == 3 and "[dream-arc]" not in _se54)
    # render_html = the arc's true terminal boundary → the WAKE cue lives there (after the print).
    _out54 = str(Path(_td54) / "arc.html")
    _so54, _se54, _rc54 = _run54("render_html.py", str(_clean54), "--no-open", "--out", _out54, cue=True)
    check("v0.1.54 render_html cue: archive rendered → the WAKE hint (☀️ Awake, 📊 path last)",
          _rc54 == 0 and "WAKE now" in _se54 and "Awake." in _se54)
    _so54, _se54, _rc54 = _run54("render_html.py", str(_clean54), "--no-open", "--out", _out54, cue=False)
    check("v0.1.54 render_html cue: env absent → silent", _rc54 == 0 and "[dream-arc]" not in _se54)
    # cue-mode gating in sync_global: --network is outside dream flow → NO cue even with env set.
    _so54, _se54, _rc54 = _run54("sync_global.py", "--network", cue=True)
    check("v0.1.54 sync_global cue-mode gate: --network (non-dream mode) stays silent",
          "[dream-arc]" not in _se54)
    # env-value robustness: the conventional off-values do NOT fire the cue.
    _env054 = {**_os53.environ, "HOME": _home54, "CM_DREAM_ARC": "0"}
    _p054 = _sp53.run([sys.executable, str(_scripts54 / "extract_signals.py"), _proj54, "--json"],
                      capture_output=True, text=True, timeout=60, env=_env054)
    check("v0.1.54 cue env gate: CM_DREAM_ARC=0 counts as OFF", "[dream-arc]" not in _p054.stderr)
    # the plain/--json read cue is PHASE-NEUTRAL (it also serves Phase 5's final gauge re-read).
    _so54, _se54, _rc54 = _run54("memory_status.py", _proj54, cue=True)
    check("v0.1.54 memory_status read cue is phase-neutral (serves Phase 0 AND the Phase-5 re-read)",
          "this read's beat" in _se54 and "Phase-0" not in _se54)

# (5) SKILL pins: every scripts/ command line carries the CM_DREAM_ARC=1 prefix (uniform rule —
# zero unprefixed invocations), and the contract anchors exist (format schematic, beats, never-echo).
_sk54 = _skill_md.read_text(encoding="utf-8")
_cmd54 = [ln for ln in _sk54.splitlines() if "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/" in ln]
check(f"v0.1.54 SKILL pin: every scripts/ command line is CM_DREAM_ARC=1-prefixed ({len(_cmd54)} lines)",
      bool(_cmd54) and all("CM_DREAM_ARC=1 python3" in ln for ln in _cmd54))
check("v0.1.54 SKILL pin: the dream-arc contract anchors (schematic, beats, Awake, never-echo)",
      "> *🌙" in _sk54 and "SLEEP" in _sk54 and "SURFACING" in _sk54 and "WAKE" in _sk54
      and "☀️ **Awake.**" in _sk54 and "[dream-arc]" in _sk54)

# (6) the beta-harness family (same repo, sibling plugin): WARN on a dreamless latest record,
# PASS on a complete one, SKIP-by-empty on old skill / empty log.
sys.path.insert(0, str(ROOT / "plugins" / "dream-beta-tester" / "scripts"))
import beta_checks as _bc54  # noqa: E402


class _FakeCtx54:
    skill_version = "0.1.54"
    log_records: list = [{"marker": {"timestamp": "t1"}}]


_r54 = _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54()))
check("v0.1.54 beta family: dreamless latest record → LOW/WARN with the pre-feature caveat",
      len(_r54) == 1 and _r54[0].status == "WARN" and _r54[0].severity == "LOW" and "pre-v0.1.54" in _r54[0].actual)
_FakeCtx54.log_records = [{"dream": {"sleep": "s", "beats": ["b"], "wake": "w"}, "marker": {"timestamp": "t2"}}]
check("v0.1.54 beta family: complete arc → PASS", _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54()))[0].status == "PASS")
_FakeCtx54.log_records = [{"dream": {"sleep": None, "beats": ["b"], "wake": None}, "marker": {"timestamp": "t3"}}]
check("v0.1.54 beta family: JSON-null stanzas count as MISSING → WARN (str(None) truthiness fixed)",
      _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54()))[0].status == "WARN")
_FakeCtx54.skill_version = "0.1.53"
check("v0.1.54 beta family: pre-feature skill under test → SKIP-by-empty",
      _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54())) == [])
_FakeCtx54.skill_version = "unknown"
check("v0.1.54 beta family: UNPARSEABLE version fails CLOSED → SKIP-by-empty (no spurious WARN)",
      _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54())) == [])
_FakeCtx54.skill_version = "0.1.54"
_FakeCtx54.log_records = []
check("v0.1.54 beta family: empty log → SKIP-by-empty", _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54())) == [])

# --- v0.1.55: distill — clean signal (all-segment + stoplist + day-spread + chains) + captured verdict ---
# (1) extraction unit table (pure): the spec-review-proven regressions. The B1 pin is NON-VACUOUS by
# construction (round-2 finding: a bare `== ([],[])` also passed under the flipped-order defect): a
# command FOLLOWS the heredoc — the flipped order amputates it, the correct order keeps it.
check("v0.1.55 B1: quoted-tag heredoc body stripped AND the next command survives (order pin)",
      ds._scan_cmd("python3 - <<'PY'\nprint(1)\nPY\nmypy --strict") == (["mypy --strict"], []))
check("v0.1.55: dash-heredoc (<<-EOF) body stripped too",
      ds._scan_cmd("some-tool run <<-EOF\n\tbody line\n\tEOF") == (["some-tool run"], []))
check("v0.1.55 M2: loop body keeps its command (for/do/done → mypy counted, keywords absent)",
      ds._scan_cmd("for f in *.py; do mypy $f; done") == (["mypy $f"], []))
check("v0.1.55 D6b: 2>&1 leaves no dangling '2' token",
      ds._scan_cmd("./release.sh 2>&1 | tail -20")[0] == ["./release.sh"])
check("v0.1.55 m1: '>> file' truncates (split-keep-head — no leaked filename token)",
      ds._scan_cmd("some-tool run >> app.log")[0] == ["some-tool run"])
check("v0.1.55 D6c: backslash-continuation joins to ONE exact template (5-token cap)",
      ds._scan_cmd("gh pr create --base main \\\n  --title x \\\n  --body y")[0] == ["gh pr create --base main"])
check("v0.1.55 D1: echo-led chain counts the REAL segments; echo row absent",
      ds._scan_cmd('echo "=== gate ===" && python3 tests/smoke.py && mypy --strict')[0]
      == ["python3 tests/smoke.py", "mypy --strict"])
check("v0.1.55: once-per-command dedup (a retry isn't recurrence)",
      ds._scan_cmd("python3 tests/smoke.py && python3 tests/smoke.py")[0] == ["python3 tests/smoke.py"])
# (1b) round-2 code-review regressions — every mechanism verified live before AND after the fix.
check("v0.1.55 r2/H1: write-then-run — the command AFTER a heredoc keeps its own segment + chain",
      ds._scan_cmd("cat > conf.yml <<'EOF'\nkey: v\nEOF\npython3 run_pipeline.py && pytest tests/")
      == (["python3 run_pipeline.py", "pytest tests/"], [("python3 run_pipeline.py", "pytest tests/")]))
check("v0.1.55 r2/H2: quoted << (bit-shift / commit message) never amputates the command",
      ds._scan_cmd("python3 -c 'x = 1<<20; print(x)' && make build")[0] == ["make build"]
      and ds._scan_cmd('git commit -m "see << docs" && git push')[0] == ["git commit -m", "git push"])
check("v0.1.55 r2/H3: same-line tail after the heredoc tag survives (cmd <<TAG && next)",
      ds._scan_cmd("sqlite3 db <<SQL && pytest tests/\nselect 1;\nSQL") == (["sqlite3 db", "pytest tests/"],
                                                                            [("sqlite3 db", "pytest tests/")]))
check("v0.1.55 r2/K2: do-cd stays noise (the prefix strip re-applies the cd/assignment gate)",
      ds._scan_cmd("for d in */; do cd $d && git pull; done") == (["git pull"], []))
check("v0.1.55 r2/K3: env-prefixed invocation keeps the carried command (the SKILL's own CM_DREAM_ARC=1 idiom)",
      ds._scan_cmd("CM_DREAM_ARC=1 python3 tests/smoke.py") == (["python3 tests/smoke.py"], []))
check("v0.1.55 r2/else: the else arm carries its command (same M2 class as do/then)",
      ds._scan_cmd("if pytest tests/; then notify-ok; else diagnose-tool run; fi")[0]
      == ["notify-ok", "diagnose-tool run"])
check("v0.1.55 r2/&>: '&>' redirects truncate cleanly (no dangling '&' token)",
      ds._scan_cmd("python3 build_all.py &> build.log && pytest tests/")[0]
      == ["python3 build_all.py", "pytest tests/"])
check("v0.1.55 r2/case: a later case arm recovers its command (first arm = documented residual)",
      ds._scan_cmd("case $1 in start) run-server;; stop) kill-server;; esac")[0] == ["kill-server"])
check("v0.1.55 r2/here-string: '<<<' never treated as a heredoc; the backstop keeps the head clean",
      ds._scan_cmd('jq -r .x <<< "$json" && ./deploy.sh')[0] == ["jq -r .x", "./deploy.sh"])
check("v0.1.55 r2/hyphen-tag: <<'MY-TAG' body stripped (tag class is [\\w-]+)",
      ds._scan_cmd("some-tool run <<'MY-TAG'\ndanger-cmd --oops\nMY-TAG\nmypy --strict")[0]
      == ["some-tool run", "mypy --strict"])
check("v0.1.55 r2/bare-interp: `python3 <<PY` strips to a stoplisted bare interpreter (no junk row)",
      ds._scan_cmd("python3 <<'PY'\nprint(1)\nPY") == ([], []))
# (1c) round-3 code-review regressions — heredoc terminated-only (no amputation), $()-env, case/func.
check("v0.1.55 r3/multiline-commit: a quoted/multi-line `<<` NEVER amputates the following command",
      ds._scan_cmd('git commit -m "fix: a << b\n\nCo-Authored-By: X" && git push')[0]
      == ["git commit -m", "git push"])
check("v0.1.55 r3/empty-body-heredoc: `cat <<EOF\\nEOF\\nnext` keeps the following command",
      ds._scan_cmd("cat <<EOF\nEOF\nreal-cmd run && next")[0] == ["real-cmd run", "next"])
check("v0.1.55 r3/no-space-heredoc: `cat<<EOF` body IS stripped (tag starts non-digit, no ws-lookbehind)",
      ds._scan_cmd("cat<<EOF\nprint(1)\nEOF\nmypy --strict")[0] == ["mypy --strict"])
check("v0.1.55 r3/env-substitution: `TAG=$(git describe --tags) make` keeps the carried command (no leak)",
      ds._scan_cmd("TAG=$(git describe --tags) make release")[0] == ["make release"]
      and ds._scan_cmd("VERSION=$(cat VERSION) deploy-tool run")[0] == ["deploy-tool run"])
check("v0.1.55 r3/func-def: a function def is NOT mis-stripped into junk `{ cmd` (the case-arm '(' guard)",
      ds._scan_cmd("deploy() { kubectl apply -f .; }")[0][0].startswith("deploy()"))
check("v0.1.55 r3/multiline-case: a bare `pattern)` arm label leaks NO junk row (dropped)",
      not any(t.endswith(")") for t in
              ds._scan_cmd("case $1 in\n start)\n run-server\n ;;\n stop)\n kill-server\n ;;\nesac")[0]))
check("v0.1.55 r3/cmd-substitution: `VAR=$(cmd …)` on its own line leaks NO `… )` junk row (a $() is a value)",
      ds._scan_cmd("NET=$(some-tool --tokens . --json)\nreal-tool run")[0] == ["real-tool run"])
check("v0.1.55 r3/subshell-parens: `( a && b )` sheds the orphan grouping parens (no '(' / ')' rows)",
      not any(t.startswith("(") or t.endswith(")") for t in
              ds._scan_cmd("(alpha-tool run && beta-tool run)")[0]))
# (1d) day-spread is DETERMINISTIC across timezones (round-3): UTC bucketing, machine-independent.
_dayA = ds._day_of("2026-07-01T23:30:00Z")
_dayB = ds._day_of("2026-07-02T00:30:00Z")
check("v0.1.55 r3/day-utc: _day_of buckets by UTC date (deterministic, not runner-local)",
      _dayA == "2026-07-01" and _dayB == "2026-07-02")
# (2) chains — BRIDGE semantics (filter-then-adjacent): the stoplisted middle is decoration.
check("v0.1.55 chains: a && b && c → (a,b), (b,c)",
      ds._scan_cmd("alpha-tool run && beta-tool run && gamma-tool run")[1]
      == [("alpha-tool run", "beta-tool run"), ("beta-tool run", "gamma-tool run")])
check("v0.1.55 chains: a && echo x && b → (a,b) — the bridge",
      ds._scan_cmd("alpha-tool run && echo progress && beta-tool run")[1]
      == [("alpha-tool run", "beta-tool run")])
check("v0.1.55 chains: a && a → no self-chain",
      ds._scan_cmd("alpha-tool run && alpha-tool run")[1] == [])
# (3) day-spread — the episode dimension (a two-day recurrence outranks a one-day burst).
def _bl55(cmd: str, ts: str) -> str:
    return _json43.dumps({"timestamp": ts, "sessionId": "s55",
                          "message": {"role": "assistant", "content": [
                              {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}) + "\n"
with _tf43.TemporaryDirectory() as _td55:
    _h55 = Path(_td55); _p55 = _h55 / "proj"; _p55.mkdir()
    _pr55 = _h55 / ".claude" / "projects" / es.slug_for(_p55); _pr55.mkdir(parents=True)
    _l55 = []
    for _i in range(5):                                    # one-day burst ×5
        _l55.append(_bl55("burst-tool run", "2026-07-01T10:00:00Z"))
    _l55.append(_bl55("steady-tool run && echo ok && mypy --strict", "2026-07-01T09:00:00Z"))
    _l55.append(_bl55("steady-tool run && echo ok && mypy --strict", "2026-07-02T09:00:00Z"))  # two days ×2
    (_pr55 / "s.jsonl").write_text("".join(_l55))
    _old55 = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_h55)
    try:
        _r55 = ds.scan(_p55, "")
    finally:
        _os43.environ["HOME"] = _old55 if _old55 is not None else ""
    _rows55 = {r["template"]: r for r in _r55["recurring"]}
    check("v0.1.55 day-spread: per-row days counted (steady 2d, burst 1d) + scanned.days = 2",
          _rows55["steady-tool run"]["days"] == 2 and _rows55["burst-tool run"]["days"] == 1
          and _r55["scanned"]["days"] == 2)
    check("v0.1.55 ranking: 2-day ×2 outranks 1-day ×5 (episodes over volume)",
          _r55["recurring"][0]["template"] == "steady-tool run")
    check("v0.1.55 chains end-to-end: the bridged (steady → mypy) chain surfaces with day-spread",
          _r55["chains"] and _r55["chains"][0]["templates"] == ["steady-tool run", "mypy --strict"]
          and _r55["chains"][0]["count"] == 2 and _r55["chains"][0]["days"] == 2)
# (4) validator: the distill container checks.
check("v0.1.55 validate: warns on non-dict distill", "distill is not a dict" in
      ms.validate_cycle_record({"distill": []}))
check("v0.1.55 validate: warns on non-list distill.proposed / distill.created",
      "distill.proposed is not a list" in ms.validate_cycle_record({"distill": {"proposed": "x"}})
      and "distill.created is not a list" in ms.validate_cycle_record({"distill": {"created": {}}}))
check("v0.1.55 validate: SILENT on a well-formed distill block",
      ms.validate_cycle_record({"distill": {"sessions": 1, "commands": 9, "n_recurring": 3, "n_chains": 1,
                                            "proposed": [], "created": [], "verdict": "nothing: x fails covered"}}) == [])
# (5) dashboard: gated DISTILL line (verdict truncated at 60; missing verdict flagged; legacy absent).
_di55 = cast(ms.CycleRecord, {"project": "p", "distill": {"n_recurring": 14, "n_chains": 6,
                              "verdict": "nothing: the smoke→mypy→sim gate-chain — already covered by release.sh XXXX"}})
_di55_out = rd.render(_di55)
check("v0.1.55 render: DISTILL line present (counts + verdict, truncated ≤60)",
      "DISTILL" in _di55_out and "14 recurring" in _di55_out and "6 chains" in _di55_out
      and "already covered" in _di55_out and "XXXX" not in _di55_out)
check("v0.1.55 render: distill without a verdict flags the gap",
      "✗ no verdict" in rd.render(cast(ms.CycleRecord, {"project": "p", "distill": {"n_recurring": 2}})))
check("v0.1.55 render: NO DISTILL line without the key (legacy unchanged)",
      "DISTILL" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s"})))
# (6) HTML: the gated distill line ships in the verify panel JS (esc()-guarded, key-gated).
# (_tpl54 is read at RUNTIME above, so it already holds the current template — one arm, no dead dup.)
check("v0.1.55 html: template ships the gated distill line",
      "CUR.distill" in _tpl54 and "n_recurring" in _tpl54)
# (7) beta family: 6-case + the dream regression suite above still green post-refactor.
_FakeCtx54.skill_version = "0.1.55"
_FakeCtx54.log_records = [{"marker": {"timestamp": "d1"}}]
_rd55 = _bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54()))
check("v0.1.55 beta family: no distill block on latest → LOW/WARN with the pre-feature caveat",
      len(_rd55) == 1 and _rd55[0].status == "WARN" and _rd55[0].severity == "LOW" and "pre-v0.1.55" in _rd55[0].actual)
_FakeCtx54.log_records = [{"distill": {"n_recurring": 3}, "marker": {"timestamp": "d2"}}]
check("v0.1.55 beta family: counts-only block (empty verdict) → WARN (a skipped judgment)",
      _bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54()))[0].status == "WARN")
_FakeCtx54.log_records = [{"distill": {"verdict": "nothing: gate-chain — already covered"}, "marker": {"timestamp": "d3"}}]
check("v0.1.55 beta family: non-empty verdict → PASS",
      _bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54()))[0].status == "PASS")
_FakeCtx54.log_records = [{"maintenance": {"pivoted": True}, "marker": {"timestamp": "d4"}}]
check("v0.1.55 beta family: maintenance-pivot pass → SKIP-by-empty (distill legitimately skipped)",
      _bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54())) == [])
_FakeCtx54.log_records = [{"maintenance": {"pivoted": "false"}, "marker": {"timestamp": "d4b"}}]
check("v0.1.55 beta family: pivoted='false' (truthy STRING) does NOT skip — coerced, WARNs normally",
      len(_bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54()))) == 1
      and _bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54()))[0].status == "WARN")
_FakeCtx54.skill_version = "unknown"
_FakeCtx54.log_records = [{"marker": {"timestamp": "d5"}}]
check("v0.1.55 beta family: unknown version fails CLOSED → SKIP-by-empty",
      _bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54())) == [])
_FakeCtx54.skill_version = "0.1.55"
_FakeCtx54.log_records = []
check("v0.1.55 beta family: empty log → SKIP-by-empty", _bc54.distill_capture(cast(_bc54.Ctx, _FakeCtx54())) == [])
# (8) SKILL pins: the verdict contract anchors present; the deleted null-priming hedges ABSENT.
_sk55 = _skill_md.read_text(encoding="utf-8")
check("v0.1.55 SKILL pin: verdict contract anchors present",
      "THE VERDICT" in _sk55 and "fails" in _sk55 and "READ THE CHAINS FIRST" in _sk55
      and "n_recurring = len(recurring)" in _sk55)
check("v0.1.55 SKILL pin: the null-priming hedges are DELETED",
      "usually proposes nothing" not in _sk55 and "EXPECTED outcome" not in _sk55)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
