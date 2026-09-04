#!/usr/bin/env python3
"""Zero-dependency smoke tests for the consolidate-memory scripts.

Run:  python3 tests/smoke.py   (exit 0 = all passed). No pytest required.
Hermetic by construction: TemporaryDirectory, temp `git init`, HOME overrides, and
subprocess script runs — never the real `~/.claude` stores, no network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, cast

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


def _v3_canon(stem: str, domain: str = "personal", body: str = "body\n",
              scope: str = "user-global", description: str = "d") -> str:
    """Valid active schema-v3 canonical body for production-shaped fixtures."""
    from fact_schema import stable_fact_id
    fid = stable_fact_id(domain, stem)
    now = "2026-09-01T00:00:00Z"
    if not str(body).endswith("\n"):
        body = str(body) + "\n"
    return (
        f"---\nschema_version: 3\nfact_id: {fid}\nname: {stem}\n"
        f"description: {description}\ndomain: {domain}\nsensitivity: internal\n"
        f"scope: {scope}\nstatus: active\n"
        f"applies_any: []\napplies_all: []\napplies_exclude: []\n"
        f"content_modified: {now}\nlast_observed_at: {now}\n---\n{body}"
    )


def _enroll_personal(project_dir: Path) -> None:
    """ADR 008: --pull/--promote require enrollment. Tests that exercise pull must enroll."""
    import store_context as _sc_e
    import control_plane as _cp_e
    ctx = _sc_e.resolve_store(Path(project_dir))
    conn = _cp_e.connect(_cp_e.db_path(ctx))
    try:
        _cp_e.enroll_project(conn, ctx, "personal")
        conn.commit()
    except Exception:
        pass
    conn.close()


def _seed_holders(project_dir: Path, stem: str, labels: list) -> None:
    """v0.4.0 (#142): seed SQLite holder rows — the sole holder authority — for a fixture fact.

    Raw project_id labels (no `projects` row): `_registry_holder_labels` resolves them via
    COALESCE(display_name, project_id) to the same token the old Markdown `projects:` used,
    so the classification/display paths see identical minds.
    """
    import store_context as _sc_seed
    import control_plane as _cp_seed
    ctx = _sc_seed.resolve_store(Path(project_dir))
    conn = _cp_seed.connect(_cp_seed.db_path(ctx))
    try:
        fid = _cp_seed.stable_fact_id(getattr(ctx, "domain_id", "") or "personal", stem)
        for lab in labels:
            conn.execute(
                "INSERT INTO holders(fact_id, project_id, base_revision, canonical_revision, "
                "semantic_hash) VALUES (?,?,?,?,?) ON CONFLICT(fact_id, project_id) DO UPDATE "
                "SET semantic_hash=excluded.semantic_hash",
                (fid, lab, "r1", "r1", "s1"))
        conn.commit()
    finally:
        conn.close()


# --- slug rule ---
# Synthetic absolute prefix: `/home` is a symlink/autofs/firmlink on macOS, so
# Path.resolve() rewrites `/home/you/...` (GH macos-latest) and a frozen
# `-home-you-…` expectation fails. CC still slugs the *resolved* path; a
# non-existent top-level dir is stable on Linux and Darwin. The on-disk CC
# example remains `/home/you/project/Doc_Flo` → `-home-you-project-Doc-Flo`.
_SLUG_ROOT = "/cm-slug-fixture"
check("slug: / -> -", ms.slug_for(Path(_SLUG_ROOT + "/project/foo")) == "-cm-slug-fixture-project-foo")
# v0.1.17: CC normalizes BOTH '/' and '_' to '-' (verified on disk: cwd .../Doc_Flo → slug ...-Doc-Flo).
# The pre-fix '/'-only slug sent cross-project facts to a slug an underscore-named project never recalls.
check("v0.1.17: slug maps '_'→'-' too (underscore project reaches its real CC store), case PRESERVED",
      ms.slug_for(Path(_SLUG_ROOT + "/project/Doc_Flo")) == "-cm-slug-fixture-project-Doc-Flo")
check("v0.1.17: slug regression-free for a no-underscore path (≡ old replace('/','-'))",
      ms.slug_for(Path(_SLUG_ROOT + "/project/foo-bar")) == "-cm-slug-fixture-project-foo-bar")
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
# v0.1.66: `budget` is a REQUIRED arg (no default) — every pin below passes it explicitly (the fix
# for a code-review-flagged unenforced-drift risk: a future call site that forgot `budget=` would
# have silently reverted to the pre-Phase-B semantics with no test or type error to catch it).
_B38 = ms.INDEX_TOKEN_BUDGET
check("v0.1.38/M1: an over-budget store holds ANY new pull (case 1)",
      sg._would_net_grow(_B38 + 1561, 40, False, budget=_B38) is True)
check("v0.1.38/M1: a NEAR-budget store holds a pull that would overshoot (case 2 — the v0.1.37 miss)",
      sg._would_net_grow(_B38 - 10, 40, False, budget=_B38) is True)
check("v0.1.38/M1: an under-budget store with room PULLS (no false hold)",
      sg._would_net_grow(800, 40, False, budget=_B38) is False)
check("v0.1.38/M1: a pull that fits EXACTLY to budget is allowed (boundary: ==budget, not >)",
      sg._would_net_grow(_B38 - 40, 40, False, budget=_B38) is False)
check("v0.1.38/M1: --allow-net-grow overrides the guard",
      sg._would_net_grow(_B38 + 1561, 40, True, budget=_B38) is False)
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
check("v0.1.39/M4: an undetectable stack is NOT in the vocab ([release]/[ci-cd] → fleet-dead, refused) — "
      "per-element isdisjoint, v0.1.77: the old negated-subset passed if EITHER element was missing, so "
      "adding 'release' alone (the exact regression this pins) would have stayed green",
      {"release", "ci-cd"}.isdisjoint(sg._DETECTABLE_STACKS))
# v0.1.40 (M3) — slug_for generalizes to ALL non-alphanumerics (CC's rule), fixing the '.'-segment split-brain;
# regression-IDENTICAL for the fleet; near_duplicate_slugs uses the same rule so a '.'-vs-'-' twin is detected.
check("v0.1.40/M3: slug_for maps '.' (a dotfile-dir path) → '-', matching CC (was split-brain)",
      ms.slug_for(Path(_SLUG_ROOT + "/u/.claude/app")) == "-cm-slug-fixture-u--claude-app")
check("v0.1.40/M3: slug_for is regression-IDENTICAL for the fleet (paths with only / _ -)",
      ms.slug_for(Path(_SLUG_ROOT + "/project/Doc_Flo")) == "-cm-slug-fixture-project-Doc-Flo")
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
_slug = "-home-you-project-Doc-Flo"
_sibs = ["-home-you-project-Doc-Flo", "-home-you-project-Doc_Flo",
         "-home-you-project-doc-flo", "-home-you-project-other"]
check("near-dup: flags '_' and case variants, excludes self + unrelated",
      ms.near_duplicate_slugs(_slug, _sibs)
      == ["-home-you-project-Doc_Flo", "-home-you-project-doc-flo"])
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
# Archived-by-design is not index↔file drift: SHIPPED.md holds the pointer, the body stays.
# Dogfood of v0.3.2 showed "3 not in the index" for facts the dream had correctly skipped
# as archive-index hits. schema_drift still xor's stems vs the placed set; the call site
# must pass placed_fact_names (MEMORY.md ∪ archive indexes), not MEMORY.md alone.
import tempfile as _tf_arch  # noqa: E402
_td_arch = _tf_arch.TemporaryDirectory()
try:
    _mem_arch = Path(_td_arch.name) / "memory"
    _mem_arch.mkdir()
    def _fact_arch(stem: str) -> None:
        (_mem_arch / f"{stem}.md").write_text(
            f"---\nname: {stem}\nmetadata:\n  node_type: memory\n  scope: project-local\n---\nbody\n",
            encoding="utf-8")
    _fact_arch("live")
    _fact_arch("old-one")
    _fact_arch("old-two")
    _fact_arch("old-three")
    (_mem_arch / "MEMORY.md").write_text(
        "# Memory Index\n\n- [live](live.md) — hook\n", encoding="utf-8")
    (_mem_arch / "SHIPPED.md").write_text(
        "# SHIPPED\n\n- [old-one](old-one.md) — done\n"
        "- [old-two](old-two.md) — done\n- [old-three](old-three.md) — done\n",
        encoding="utf-8")
    _arch_docs = [p for p in _mem_arch.glob("*.md")
                  if p.name != "MEMORY.md" and ms._is_archive_index(p)]
    _arch_facts = [p for p in _mem_arch.glob("*.md")
                   if p.name != "MEMORY.md" and p not in _arch_docs]
    _placed = ms.placed_fact_names(_mem_arch / "MEMORY.md", _arch_docs)
    _sd_arch = ms.schema_drift(_arch_facts, _placed)
    check("schema_drift: SHIPPED.md-indexed bodies are not index_mismatch",
          _sd_arch["index_mismatch"] == 0 and _sd_arch["missing_node_type"] == 0
          and ms.drift_findings(_sd_arch) == 0
          and _placed == {"live", "old-one", "old-two", "old-three"})
    _fact_arch("stray")
    _arch_facts2 = [p for p in _mem_arch.glob("*.md")
                    if p.name != "MEMORY.md" and not ms._is_archive_index(p)]
    _sd_stray = ms.schema_drift(_arch_facts2, ms.placed_fact_names(_mem_arch / "MEMORY.md", _arch_docs))
    check("schema_drift: a body in neither MEMORY.md nor SHIPPED.md is still mismatch",
          _sd_stray["index_mismatch"] == 1)
    check("schema_drift: MEMORY.md-only xor still flags an unarchived body (legacy call)",
          ms.schema_drift(_arch_facts, ms.index_fact_names(_mem_arch / "MEMORY.md"))["index_mismatch"] == 3)
finally:
    _td_arch.cleanup()
check("build_context schema_drift uses placed_fact_names (archive-indexed bodies are not drift)",
      "placed_fact_names(index_path, archive_docs)" in Path(__file__).resolve().parent.parent.joinpath(
          "plugins/consolidate-memory/scripts/memory_status.py").read_text(encoding="utf-8"))
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
    # v0.1.70 security: no metadata: key in frontmatter, but the BODY has a bare, unindented
    # 'metadata:' line — pre-fix this stole the anchor and stamped global_ref: into the body,
    # OUTSIDE the span _is_mirror parses, permanently desyncing producer/recognizer.
    "---\nscope: user-global\nnode_type: fact\n---\n# Heading\n\nprose.\n\nmetadata:\nmore prose.\n",
]):
    check(f"mirror: round-trip property holds (shape {_i})",
          sg._is_mirror(sg._as_mirror(_fm, "x")) is True)

# v0.1.70 Gate-2a: _as_mirror's global_ref: strip was unscoped (unlike the adjacent projects:/
# metadata: checks) — ANY body line starting with the literal text "global_ref:" was silently
# deleted, not just the function's own frontmatter-child stamp. A self-documenting fact whose
# prose explains the mirror mechanism itself is a realistic trigger, not just an adversarial one.
_body_gr_fixture = ("---\nname: x\nmetadata:\n  scope: user-global\n---\n# Notes\n\n"
                    "global_ref: this line is plain prose written by a human, not YAML\nmore text.\n")
_body_gr_out = sg._as_mirror(_body_gr_fixture, "crafted")
check("mirror: _as_mirror does NOT delete a body line merely starting with 'global_ref:' (Gate-2a)",
      "this line is plain prose written by a human" in _body_gr_out and "more text." in _body_gr_out)
check("mirror: _as_mirror still round-trips correctly on the same fixture",
      sg._is_mirror(_body_gr_out) is True)

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

# --- v0.1.70 security: firewall is single-sourced in memory_status.py (the dependency root —
# extract_signals.py imports it, mirroring the _is_mirror precedent), and its regex fixes hold ---
check("firewall: _looks_secret is single-source (promoted to memory_status; extract_signals imports it)",
      es._looks_secret is ms._looks_secret and es._SECRET is ms._SECRET and es._entropy_blob is ms._entropy_blob)

for _name, _val, _want in [
    # the CONFIRMED bypass: a keyword-less high-entropy value chunked into 3+ slash segments
    # used to be exempted WHOLESALE once any 3 '/' appeared anywhere in the match.
    ("AWS key + 1 more slash (was the exact bypass)",
     "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY/x", True),
    ("synthetic 4-segment slash-chunked secret (was secrets_omitted:0 end-to-end)",
     "aB3xY9kL2mQ7wErT1zXcVbNmQweRtYuIoPasDfGh/aB3xY9kL2mQ7wErT1zXc/VbNmQweRtYuIoPasDfGh/x", True),
    # Stripe webhook signing secret (whsec_ + hex) — no keyword, under the old 40-char floor
    ("Stripe whsec_", "whsec_1234567890abcdef1234567890abcdef", True),
    # CLI-flag-shaped keyword (whitespace/=, not just :/=) — the --password/-p gap
    ("--password value (space-delimited flag)", "--password hunter2longvalue", True),
    ("--password=value (CLI flag, = form)", "--password=hunter2longvalue", True),
    # deliberately-excluded gaps (documented false-positive-risk tradeoffs, not silently missed):
    ("mysqldump -p concatenated (deliberately NOT covered — collides with -p8080:80 etc.)",
     "mysqldump -uroot -pMyS3cretPassw0rd db > out.sql", False),
    ("curl -u user:pass without scheme (deliberately NOT covered — collides with -u UID:GID)",
     "curl -u admin:Sup3rSecretPass https://internal.example.com/api", False),
    # Gate-2a round 3 (accepted, documented gaps — see _entropy_blob's docstring): a whole-blob
    # mixed-case check briefly closed these two, but it FP'd on this repo's own everyday path
    # shape (a '/'-path ending in an ALL-CAPS filename stem, e.g. .../SKILL.md) once long enough
    # to clear the blob floor — a worse trade than the narrow gap it closed. Reverted to
    # per-token scoping; both stay accepted, narrow residual gaps rather than chased further.
    ("cross-segment mixed case (accepted gap: neither segment is internally mixed-case)",
     "thisisalowercasesegmentofconsiderablelength/THISISANUPPERCASESEGMENTALSOLONGENOUGH", False),
    ("short-segment-chunked secret (accepted gap: every segment is under the entropy floor)",
     "wJalrXU/tnFEMIK/7MDENGb/PxRfiCY/EXAMPLE/KEY1234/56", False),
    # Gate-2a [1]: the CLI-flag arm's keyword list was narrower than the main arm's — these three
    # evaded entirely even though the `=`-delimited form of the SAME keyword was already caught.
    ("--credentials value (Gate-2a: keyword was missing from the CLI-flag arm)",
     "--credentials mySecretValue123", True),
    ("--li_at value (Gate-2a: keyword was missing from the CLI-flag arm)",
     "--li_at ABCDEFGHIJ0123456789", True),
    ("--cf_clearance value (Gate-2a: keyword was missing from the CLI-flag arm)",
     "--cf_clearance ABCDEFGHIJ0123456789", True),
]:
    check(f"firewall(v0.1.70): {_name} -> {'flagged' if _want else 'clean'}",
          bool(es._looks_secret(_val)) is _want)

# --- v0.1.70 security: false-positive corpus — ordinary content that must NOT be omitted.
# Mandatory per the firewall's own asymmetric-safe design AND because v0.1.70 wires this same
# firewall onto git commit subjects (memory_status.py) — an over-greedy arm now silently drops
# legitimate commit messages, not just recall signal. ---
for _name, _val in [
    ("ordinary commit subject", "fix(cm): stop the masthead glow from tiling down the page"),
    ("commit subject mentioning 'token' as a noun", "refactor: extract the auth token validation into a helper"),
    ("commit subject mentioning 'password' as a noun", "docs: clarify the password reset flow in the README"),
    ("commit subject with a docker port mapping", "chore: docker run -p 8080:80 the staging container"),
    ("commit subject with a docker UID:GID flag", "fix: run the container as -u 1000:1000 not root"),
    ("commit subject with a real file path", "fix: correct the import path in scripts/memory_status.py"),
    ("prose mentioning 'secret' as a common noun", "the secret to a good API is a stable contract"),
    ("a git SHA-shaped hex string", "revert " + "a1b2c3d4e5f6" * 3),
    ("a UUID (dashless, 32 hex)", "session " + "0123456789abcdef" * 2),
    # Gate-2a [3]: a versioned/dated path segment — no individual '-_.'-delimited TOKEN within it
    # is both >=8 chars AND digit-bearing (every digit run there is short: "v0", "1", "68").
    ("versioned path with digits (Gate-2a: was flagged by the original per-'/'-segment design)",
     "docs: add docs/release-notes/v0-1-68-index-lifecycle-phase-c-summary.md"),
    # Gate-2a [2]: the CLI-flag arm's value clause was bare `\S{4,}` (any 4+-char word) — a
    # commit merely MENTIONING a flag name is not a leaked value.
    ("commit mentioning a --secret flag by name (Gate-2a: was flagged as a value)",
     "feat: add a --secret flag to enable debug logging"),
    ("commit mentioning a --api-key flag by name (Gate-2a: was flagged as a value)",
     "docs: document the --api-key flag usage"),
    # Gate-2a [6]: ordinary 'keyword: value' commit/prose clauses (not adversarial, not a CLI
    # flag) where the keyword-arm's old bare `\S+` accepted ANY short value after the delimiter.
    ("conventional-commit-style 'token: <value>' (Gate-2a: was flagged)", "token: bump TTL to 3600"),
    ("test-count-style 'pass: N fail: N' (Gate-2a: was flagged)", "pass: 5 fail: 0"),
    ("prose 'secret: <short value>' (Gate-2a: was flagged)", "secret: rotate the signing key"),
    # Gate-2a round 3: the whole-blob mixed-case check (briefly restored to close the
    # cross-segment gap above) flagged this repo's OWN routine path shape — a '/'-path ending
    # in an ALL-CAPS filename stem, long enough to clear the 40-char blob floor once nested a
    # couple of directories deep. Reverted to per-token scoping (see _entropy_blob's docstring).
    ("commit mentioning a deep path ending in an ALL-CAPS filename stem (Gate-2a round 3: was flagged)",
     "docs: update plugins/consolidate-memory/skills/consolidate-memory/SKILL.md wording"),
]:
    check(f"firewall FALSE-POSITIVE guard: {_name!r} -> stays clean",
          es._looks_secret(_val) is False)

# --- Gate-2a round 3 (accepted, documented gap — see _entropy_blob's docstring): a short,
# no-digit, single-case value (a weak password) is indistinguishable in SHAPE from an ordinary
# short English word ("flag", "usage") in the same 'keyword: value' position — no threshold
# separates them. The firewall favors fewer false positives on ordinary commit prose; this is
# a documented product tradeoff, not a bug this test expects to be tightened away. ---
for _name, _val in [
    ("weak no-digit password (accepted gap: same shape as 'keyword: <ordinary word>')",
     "fix: reset password=qwerty in the seed fixture"),
    ("weak no-digit password, short keyword form (accepted gap)",
     "chore: rotate pwd=letmein for the test account"),
]:
    check(f"firewall accepted-gap (documented, not chased): {_name!r} -> stays clean",
          es._looks_secret(_val) is False)

# --- v0.1.70 security: ReDoS — the firewall must stay LINEAR-time on adversarial input (a
# CONFIRMED bypass: the unbounded compound-keyword prefix AND a sibling unbounded URI-creds arm
# both gave real re.search O(n²) blowup; a THIRD instance was found in the JWT arm via a
# repeated-anchor attack; #4 the authorization|bearer arm, a Gate-2a-found 4th instance). Assert
# completion under a GENEROUS wall-clock bound (2.0s — deliberately loose vs. this machine's
# actual post-fix timings, ~0.005-0.19s below, to absorb slower/loaded-CI variance without going
# flaky) at a payload size chosen so the PRE-fix regex clearly exceeds it by a wide margin (3.4s
# to 21s measured, i.e. the bound isn't just barely tripped — a real regression fails it hard).
import time as _time70  # noqa: E402
for _redos_name, _redos_payload in [
    ("dotted/dashed run (original pentest PoC shape)", ("a1b2-c3d4." * 5000)),
    ("pure-alnum run + trailing keyword, no separator", ("x" * 49992) + "password" + ("y" * 12)),
    ("repeated JWT anchor, no periods", "eyJ" * 33333),
    ("authorization + padding spaces (Gate-2a's 4th instance)", "authorization" + " " * 20000),
]:
    _t0_70 = _time70.time()
    ms._SECRET.search(_redos_payload)
    _dt_70 = _time70.time() - _t0_70
    check(f"firewall ReDoS guard: {_redos_name} (len={len(_redos_payload)}) completes in <2s (was multi-second/unbounded)",
          _dt_70 < 2.0)

# --- v0.1.70 security: git-log commit subjects now pass through the SAME firewall (was: only
# _sane()'s control-byte strip — no credential-shape check at all, a stark asymmetry against
# extract_signals.py's session-signal source, which SKILL.md itself documents as firewalled) ---
# NB: the credential-shaped subject below is ASSEMBLED by concatenation from obviously-fake
# parts (matching this file's existing provider-token-fixture convention below) so no
# contiguous real-looking secret literal exists in this source file (GitHub push protection
# matches source text, not runtime values).
_scrub70_secret_line = ("d4e5f6a debug: hardcoded STRIPE_KEY=" + "sk_" + "live_" + "51H8" + "x" * 20
                        + " to unblock CI, revert before merge")
_scrub70_log = "\n".join([
    "a1b2c3d fix: normal commit message",
    _scrub70_secret_line,
    "",   # a blank line must not crash / must not become a bogus entry
    "789abcd docs: update the README",
])
_scrub70_out = ms._scrub_commit_log(_scrub70_log)
check("commit-log firewall: 3 real commits survive, blank line dropped", len(_scrub70_out) == 3)
check("commit-log firewall: the credential-shaped subject is redacted, SHA kept",
      _scrub70_out[1].startswith("d4e5f6a ") and "STRIPE_KEY" not in _scrub70_out[1]
      and ("sk_" + "live_" + "51H8") not in _scrub70_out[1] and "omitted" in _scrub70_out[1])
check("commit-log firewall: ordinary commit subjects pass through UNCHANGED",
      _scrub70_out[0] == "a1b2c3d fix: normal commit message"
      and _scrub70_out[2] == "789abcd docs: update the README")
check("commit-log firewall: a subject-less line (bare SHA, no space) is not mistaken for a secret hit",
      ms._scrub_commit_log("a1b2c3d") == ["a1b2c3d"])

# v0.1.70 Gate-2a [4]: _scrub_commit_log must cap the subject before firewall-scanning it — git
# enforces no length limit on a commit's first line, and the raw regex costs real time per char.
import time as _time_scrub70  # noqa: E402
_huge_subject_line = "abc1234 " + "eyJ" * 300000   # ~900,000-char subject, no keyword needed to be slow
_t0_scrub70 = _time_scrub70.time()
ms._scrub_commit_log(_huge_subject_line)
_dt_scrub70 = _time_scrub70.time() - _t0_scrub70
check(f"commit-log firewall: a ~900,000-char commit subject is capped before scanning (took {_dt_scrub70:.2f}s, must be <2s)",
      _dt_scrub70 < 2.0)

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
# v0.1.70 security: --evict='s path-traversal guard — a crafted evict name must never be able to
# walk outside the project's own store (confirmed exploitable pre-fix: reproduced deleting a file
# in the GLOBAL store via `--evict=../../../memory/<name>`; see simulate_accumulation.py Probe R
# for the full end-to-end proof against the live subprocess).
check("name: relative-traversal stem rejected", sg._safe_stem("../../../memory/victim") is False)
check("name: absolute-path stem rejected", sg._safe_stem("/etc/passwd") is False)
check("name: embedded-slash stem rejected", sg._safe_stem("a/b") is False)
# v0.1.70 Gate-2a (2nd pass): the reserved-stem guard (--evict=MEMORY, promote()'s local_fact/
# canon_name) must be CASE-insensitive — an exact-string match let 'memory'/'Memory' sail through
# on a case-insensitive filesystem (macOS/Windows, both supported), where it resolves to the SAME
# file as the real MEMORY.md index. Shared by both promote() and the evict guard (was two
# independent, already-drifted hand-written copies).
for _n in ("MEMORY", "memory", "Memory", "MeMoRy"):
    check(f"name: reserved stem {_n!r} rejected case-insensitively", sg._is_reserved_stem(_n) is True)
check("name: a non-reserved stem is NOT rejected", sg._is_reserved_stem("memoryx") is False
      and sg._is_reserved_stem("not-memory") is False)
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
# v0.1.69/A7: usage/usage.per_fact/demotion + explicit audit.claude_md/repo_doc rows close the last
# gaps — the two carve-outs above are now the ONLY un-pinned shapes.
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
    ("network.stack_edges[0]", (_sk_n.get("stack_edges") or [{}])[0], ms.StackEdge),
    ("network.totals", _sk_n.get("totals", {}), ms.NetworkTotals),
    ("remediation", _skill_schema.get("remediation", {}), ms.Remediation),   # v0.1.18
    ("maintenance", _skill_schema.get("maintenance", {}), ms.Maintenance),   # v0.1.37
    ("dream", _skill_schema.get("dream", {}), ms.DreamArc),                  # v0.1.54
    ("distill", _skill_schema.get("distill", {}), ms.Distill),               # v0.1.55
    ("usage", _skill_schema.get("usage", {}), ms.Usage),                     # v0.1.63 (Phase A)
    ("usage.per_fact[0]", (_skill_schema.get("usage", {}).get("per_fact") or [{}])[0], ms.UsageFact),
    ("demotion", _skill_schema.get("demotion", {}), ms.Demotion),            # v0.1.67 (Phase C)
    ("workflow_proposals", _skill_schema.get("workflow_proposals", {}), ms.WorkflowProposals),  # v0.1.87 (W-C)
    ("workflow_proposals.candidates[0]",
     (_skill_schema.get("workflow_proposals", {}).get("candidates") or [{}])[0], ms.WorkflowProposal),
    ("workflow_proposals.decline_anchors[0]",
     (_skill_schema.get("workflow_proposals", {}).get("decline_anchors") or [{}])[0], ms.DeclineAnchor),
    ("identity", _skill_schema.get("identity", {}), ms.Identity),  # v0.3.0 domain/enrollment snapshot
    # v0.1.69/A7: covered only TRANSITIVELY before (same AuditStoreDelta as audit.memory) — explicit
    # rows make the all-nested-shapes claim literally true.
    ("audit.claude_md", _skill_schema.get("audit", {}).get("claude_md", {}), ms.AuditStoreDelta),
    ("audit.repo_doc", _skill_schema.get("audit", {}).get("repo_doc", {}), ms.AuditStoreDelta),
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
      "dangling_links(auto_mem, global_dir=" in _skill_text
      and "canonical_domain_dir" in _skill_text
      and "global_store()" not in _skill_text[ _skill_text.find("dangling_links(auto_mem"):
                                               _skill_text.find("dangling_links(auto_mem")+220])
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
check("v0.1.72: template generalizes the diff-modal beyond the memory/ prefix (store-aware split + the size-capped message)",
      all(s in _html for s in ["function splitDiffPath", "function diffDisplayName", "size_capped", "too large to snapshot"]))
check("v0.1.72: an index-line-only entry (no diff for its OWN memory/<name>.md) falls back to the shared MEMORY.md diff",
      'store==="auto-mem"&&DREAMDIFFS["memory/MEMORY.md"]' in _html)
check("v0.1.72 Gate-2: the store='repo' fallback checks ambiguity JOINTLY across claude_md+repo_doc "
      "(repoKeys=cmKeys.concat(rdKeys); repoKeys.length===1) — NOT independently per store, which would auto-link "
      "an entry to the wrong file whenever exactly one claude_md AND one repo_doc file both changed in the same pass",
      "repoKeys.length===1" in _html and "cmKeys.length===1" not in _html and "rdKeys.length===1" not in _html)
check("v0.1.72: template gives model-declared entry.files[] priority over the name-match/store heuristics — "
      "deterministic linking (possibly MULTIPLE files per entry), not a guess",
      "Array.isArray(rawFiles)" in _html and "declared.length" in _html
      and _html.index("Array.isArray(rawFiles)") < _html.index('store==="auto-mem"&&DREAMDIFFS["memory/MEMORY.md"]'))
check("v0.1.72 Gate-2: declared entry.files are DEDUPED (seen{}) before rendering chips — a files[] array listing "
      "the same path twice must not render two redundant chips for one diff",
      "declared=[], seen={}" in _html and "seen[p]" in _html)
check("v0.1.72 Gate-2: an entry with declared-but-UNRESOLVED files (empty after the DREAMDIFFS filter — a model "
      "typo/omission) falls through to the legacy heuristic instead of trusting a possibly-wrong negative "
      "declaration and silently dropping a real, observed diff",
      _html.index("if(declared.length){") < _html.index('var p="memory/"+nm+".md";'))

# ── v0.3.0: HTML observability — identity / cross-project movement / budget extras ──────────────
# Presentation-only wiring of 0.1.91→0.3.0 surfaces the ASCII dashboard already showed (or the
# StoreContext snapshot the ASCII IDENTITY line now shows). Legacy records without `identity`
# must NOT invent a local-only banner (identOf.missing).
check("v0.3.0 html: template carries identity + movement + extra-meter hooks",
      all(s in _html for s in [
          "function identOf", "function outcomeOf", "function paintBanners", "function identLine",
          'id="h-ident"', 'id="a-ident"', 'id="h-banners"', 'id="a-banners"',
          'id="xp-strip"', 'id="m-global"', "This pass across the domain",
          "local-only", "/cm-domain", "schema drift", "slug orphans"]))
check("v0.3.0 html: outcomeOf matches ASCII write bands (≤2 light, else substantial) + maintenance pivot",
      "if(w<=2) return \"Light pass\"" in _html
      and "return \"Substantial pass\"" in _html
      and "Maintenance pass" in _html
      and "w>=4" not in _html)
check("v0.3.0 html: identOf does not invent local-only when identity is absent (legacy-safe)",
      "missing:true" in _html and "if(!id||id.missing)" in _html)
_id_html = rhtml.build_html(
    {"project": "p", "identity": {"domain_id": "personal", "enrolled": True,
                                  "registry_state": "healthy", "cross_project_allowed": True,
                                  "conflicts": 0},
     "cross_project": {"global_store_facts": 4,
                       "pulled": [{"name": "gh-pr-edit-broken-in-env", "scope": "user-global"}],
                       "promoted": [], "refreshed": 1, "held": 2, "gc_removed": 0},
     "budget": {"index": {"after_tokens": 900, "cliff_pct": 40, "fat_hooks": 1, "hook_max_tokens": 90},
                "global_claude_md": {"present": True, "tokens": 800, "budget_tokens": 4000, "over": False},
                "claude_md_hierarchy": {"total_files": 2, "worst_path": "src", "worst_path_tokens": 500}}},
    [], "t", identity={"domain_id": "personal", "enrolled": True, "registry_state": "healthy",
                       "cross_project_allowed": True, "conflicts": 1})
_id_m = _re.search(r'id="cm-data">(.*?)</script>', _id_html, _re.S)
_id_embed = _json.loads(_id_m.group(1).replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")) if _id_m else {}
check("v0.3.0 html: build_html embeds live identity + hook/cliff budgets (round-trip)",
      _id_embed.get("identity", {}).get("domain_id") == "personal"
      and _id_embed.get("identity", {}).get("conflicts") == 1
      and _id_embed.get("budgets", {}).get("hook_warn") == ms.HOOK_TOKEN_WARN
      and _id_embed.get("budgets", {}).get("cliff_near") == int(ms.CLIFF_NEAR_FRACTION * 100)
      and (_id_embed.get("cycles") or [{}])[-1].get("cross_project", {}).get("held") == 2)
_evil_id = rhtml.build_html({"project": "x", "identity": {"domain_id": "</script><img src=x>"}},
                            [], "t", identity={"domain_id": "</script>"})
check("v0.3.0 html: identity domain is </script>-break-out-safe (XSS)",
      "</script><img" not in _evil_id and "\\u003c/script" in _evil_id)
check("v0.3.0 ascii: IDENTITY line on a seeded enrolled record; absent on legacy",
      "IDENTITY" in rd.render(rd._demo_record()) and "domain personal" in rd.render(rd._demo_record())
      and "IDENTITY" not in rd.render(cast(_R, {"project": "p", "session": "s", "scope": {}, "entries": []})))
check("v0.3.0 ascii: LOCAL-ONLY when identity says unenrolled",
      "LOCAL-ONLY" in rd.render(cast(_R, {"project": "p", "session": "s", "scope": {}, "entries": [],
                                          "identity": {"domain_id": "unknown", "enrolled": False,
                                                       "registry_state": "absent",
                                                       "cross_project_allowed": False}})))
with _tempfile.TemporaryDirectory() as _tdI:
    _homeI = Path(_tdI) / "home"; _homeI.mkdir()
    _projI = Path(_tdI) / "proj"; _projI.mkdir()
    _oldI = __import__("os").environ.get("HOME")
    __import__("os").environ["HOME"] = str(_homeI)
    try:
        _seedI = ms.seed_record(ms.build_context(_projI))
        _identI = _seedI.get("identity") or {}
        check("v0.3.0 seed: identity snapshot is path-free and unenrolled-by-default",
              _identI.get("domain_id") == "unknown"
              and _identI.get("enrolled") is False
              and _identI.get("cross_project_allowed") is False
              and not any(isinstance(v, str) and ("/" in v or "\\" in v) for v in _identI.values()))
    finally:
        if _oldI is None:
            __import__("os").environ.pop("HOME", None)
        else:
            __import__("os").environ["HOME"] = _oldI
check("Entry.files is list[str] (not bare list) in the CycleRecord contract (TypedDict), and the SKILL.md "
      "schema-block pin (the top-level entries[0]==Entry.__annotations__ loop) catches key drift",
      "files" in ms.Entry.__annotations__)
# v0.1.72 — capture_diffs/audit_snapshot: the diff-modal now covers EVERY audit_snapshot store (memory facts +
# the MEMORY.md index + CLAUDE.md + repo docs), not memory-facts-only (the v0.1.32 scope) — a real screenshot
# showed a CLAUDE.md edit and 4 index-line-only fact compressions narrated in the ledger with NO way to ever
# link to a diff, because capture_diffs hard-excluded store!='memory' and label=='memory/MEMORY.md'. A real
# end-to-end fixture (git repo + HOME override, not hand-built dicts) so audit_snapshot's actual size-cap
# logic (_DIFF_CONTENT_CAP_TOKENS) runs, not just capture_diffs' handling of a pre-built input.
import os as _os72, subprocess as _sp72, tempfile as _tf72  # noqa: E402
with _tf72.TemporaryDirectory() as _td72:
    _home72 = Path(_td72) / "home"; _home72.mkdir()
    _proj72 = Path(_td72) / "proj"; _proj72.mkdir()
    _sp72.run(["git", "init", "-q"], cwd=_proj72, check=True)
    (_proj72 / "CLAUDE.md").write_text("small claude.md v1\n")
    (_proj72 / "docs.md").write_text("x" * 40)             # small repo doc (untracked-but-not-ignored)
    _big72 = "y " * 40000                                   # ~20000 est_tokens — well over the 8000 cap
    (_proj72 / "BIG.md").write_text(_big72)
    _pr72 = _home72 / ".claude" / "projects" / ms.slug_for(_proj72) / "memory"; _pr72.mkdir(parents=True)
    (_pr72 / "fact.md").write_text("---\nname: fact\n---\nv1\n")
    (_pr72 / "MEMORY.md").write_text("- [fact](fact.md) v1\n")
    _old72 = _os72.environ.get("HOME"); _os72.environ["HOME"] = str(_home72)
    try:
        _before72 = ms.audit_snapshot(_proj72)
        (_proj72 / "CLAUDE.md").write_text("small claude.md v2\n")
        (_proj72 / "docs.md").write_text("x" * 41)
        (_proj72 / "BIG.md").write_text(_big72 + "z")
        (_pr72 / "fact.md").write_text("---\nname: fact\n---\nv2\n")
        (_pr72 / "MEMORY.md").write_text("- [fact](fact.md) v2\n")
        _diffs72 = ms.capture_diffs(_before72, _proj72)
    finally:
        _os72.environ["HOME"] = _old72 if _old72 is not None else ""
check("v0.1.72: capture_diffs now covers a claude_md file (was memory-store-only)",
      "claude_md/CLAUDE.md" in _diffs72 and _diffs72["claude_md/CLAUDE.md"]["op"] == "modified"
      and not _diffs72["claude_md/CLAUDE.md"].get("size_capped")
      and any(l["s"] == "small claude.md v2" for l in _diffs72["claude_md/CLAUDE.md"]["lines"]))
check("v0.1.72: capture_diffs now covers the MEMORY.md index (was hard-excluded as 'pointer churn')",
      "memory/MEMORY.md" in _diffs72 and not _diffs72["memory/MEMORY.md"].get("size_capped"))
check("v0.1.72: capture_diffs now covers a small repo doc",
      "repo_doc/docs.md" in _diffs72 and not _diffs72["repo_doc/docs.md"].get("size_capped"))
check("v0.1.72: a giant repo doc (over _DIFF_CONTENT_CAP_TOKENS) is flagged size_capped, not diffed misleadingly one-sided",
      _diffs72.get("repo_doc/BIG.md", {}).get("size_capped") is True and _diffs72["repo_doc/BIG.md"]["lines"] == []
      and _diffs72["repo_doc/BIG.md"]["op"] == "modified")
check("v0.1.72: a plain memory-fact diff still works exactly as before (no regression on the original v0.1.32 path)",
      "memory/fact.md" in _diffs72 and not _diffs72["memory/fact.md"].get("size_capped")
      and any(l["s"] == "v2" for l in _diffs72["memory/fact.md"]["lines"]))

# v0.1.72 Gate-2 — the AGGREGATE cap (_DIFF_CONTENT_AGGREGATE_CAP_TOKENS): the per-file cap alone doesn't stop
# many medium-sized docs from adding up (the code-review-flagged gap — a per-file-only cap's own docstring
# claimed it prevents /tmp snapshot bloat, but 40 files each just under the per-file cap would still stash
# ~1.3MB). 6 repo docs at exactly 7000 est_tokens each (42000 total, over the 40000 aggregate cap, each
# individually under the 8000 per-file cap) — processed in sorted filename order, the first 5 (35000) fit,
# the 6th pushes over and must NOT be content-stashed.
with _tf72.TemporaryDirectory() as _td72b:
    _home72b = Path(_td72b) / "home"; _home72b.mkdir()
    _proj72b = Path(_td72b) / "proj"; _proj72b.mkdir()
    _sp72.run(["git", "init", "-q"], cwd=_proj72b, check=True)
    _doc72b = "d" * 28000   # (28000+3)//4 == 7000 est_tokens exactly
    for _n72b in "abcdef":
        (_proj72b / f"doc-{_n72b}.md").write_text(_doc72b)
    _pr72b = _home72b / ".claude" / "projects" / ms.slug_for(_proj72b) / "memory"; _pr72b.mkdir(parents=True)
    _old72b = _os72.environ.get("HOME"); _os72.environ["HOME"] = str(_home72b)
    try:
        _before72b = ms.audit_snapshot(_proj72b)
        for _n72b in "abcdef":
            (_proj72b / f"doc-{_n72b}.md").write_text(_doc72b + _n72b)   # mutate every file, same order preserved
        _diffs72b = ms.capture_diffs(_before72b, _proj72b)
    finally:
        _os72.environ["HOME"] = _old72b if _old72b is not None else ""
check("v0.1.72 Gate-2: the aggregate cap lets the first N docs (cumulative <= 40000 tokens) diff normally",
      all(not _diffs72b.get(f"repo_doc/doc-{_n}.md", {}).get("size_capped") for _n in "abcde"))
check("v0.1.72 Gate-2: the aggregate cap stops the doc that pushes the running total OVER 40000, even though "
      "it is individually well under the 8000 per-file cap — flagged size_capped, not silently unbounded growth",
      _diffs72b.get("repo_doc/doc-f.md", {}).get("size_capped") is True)

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
# (the single [[...]] extractor, factored from dangling_links); _inbound_links (orphan-safety). v0.1.73 replaced
# the static _evict_frees_enough fit-check with the _plan_pull A/B replay (docs/evict-accounting-truth.spec.md);
# its pins are below, and the once-out-of-band evict CLI E2E is now IN-REPO (the v0.1.73 block + sim Probe V).
check("v0.1.41: extract_wikilinks strips fenced + inline code, finds [[real]] only (single [[...]] extractor)",
      ms.extract_wikilinks("a [[real]] b `[[inline]]` c\n```\n[[fenced]]\n```\n") == ["real"])
# v0.1.73: _plan_pull — the ONE accounting replay both run()'s write loop and the --evict gain-gate consume.
# explicit budget=1200 pins these to the planning LOGIC, not the production ceiling constant (the v0.1.41 rule).
_pp73 = sg._plan_pull([("a", "MISSING", 30, 0), ("z", "MISSING", 30, 0)], 1150, False, budget=1200)
check("v0.1.73: _plan_pull ACCUMULATES in iteration order — the first pull's growth holds the second "
      "(a static per-fact pre-scan would pull both; F3's root)",
      _pp73["pull"] == ["a"] and _pp73["held"] == [("z", 30)] and _pp73["end_idx"] == 1180)
_pp73b = sg._plan_pull([("s", "STALE-mirror", 40, 10), ("m", "MISSING", 20, 0)], 1170, False, budget=1200)
check("v0.1.73: _plan_pull counts a STALE refresh's real pointer delta (F4) — the later MISSING holds at the ceiling",
      _pp73b["pull"] == [] and _pp73b["held"] == [("m", 20)] and _pp73b["end_idx"] == 1200)
check("v0.1.73: _plan_pull nets a MISSING fact against its EXISTING real line (index-drift state); ==budget boundary pulls",
      sg._plan_pull([("m", "MISSING", 30, 25)], 1195, False, budget=1200)["pull"] == ["m"])
check("v0.1.73: _plan_pull under --allow-net-grow holds nothing",
      sg._plan_pull([("a", "MISSING", 999, 0)], 1199, True, budget=1200)["held"] == [])
check("v0.1.73: _index_line_cost measures the REAL line via its ](stem.md) anchor; absent stem → 0 "
      "(F2: freed is measured, never derived)",
      sg._index_line_cost("# Memory Index\n- [x](x.md) — a real line here\n", "x") ==
      ms.est_tokens("- [x](x.md) — a real line here")
      and sg._index_line_cost("# Memory Index\n- [x](x.md) — y\n", "nope") == 0)

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
      ds._scan_cmd("cd /home/you/project/x\npython3 tests/smoke.py")[0] == ["python3 tests/smoke.py"])
check("v0.1.51/55: _scan_cmd bare cd → nothing (a 'cd' is NOT a workflow template)",
      ds._scan_cmd("cd /home/you/project/x") == ([], []))
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
    check("v0.1.55/58/82: scan --json contract shape (+chains, +days; +secrets_omitted v0.1.58; "
          "+used v0.1.82 — the Skill-adoption tally)",
          set(_r51) == {"window", "scanned", "recurring", "chains", "used"}
          and set(_r51["scanned"]) == {"sessions", "commands", "days", "secrets_omitted"}
          and all(set(r) == {"template", "count", "days", "sample"} for r in _r51["recurring"])
          and isinstance(_r51["used"], list))
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

# ── render-chain audit (the 4-reviewer presentation-layer swarm) — the renderers degrade, never lie ──
_RC_BASE = {"project": "p", "scope": {"git_commits": 1, "session_candidates": 1, "memories_reviewed": 1}}
_RC1 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, entries=["not-a-dict"], verification={"confirmed": 2})))
check("RC: a non-dict entries ITEM renders without crashing (the measured AttributeError blocker)",
      "DREAM" in _RC1)
_RC2 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, verification={"confirmed": None, "corrected": None, "unverifiable": None},
                                           marker={"commit": None, "timestamp": None})))
check("RC: stored JSON-nulls never print as 'None' (verification/marker coalesce)",
      "0 confirmed" in _RC2 and "None" not in _RC2)
_RC3 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, budget={"index": {"after_tokens": 2000, "budget_tokens": 1500, "over": "false"}})))
check("RC: a string-'false' over flag stays OFF (_flag coercion at the flag boundary)",
      "OVER" not in _RC3)
_RC4 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, entries=[{"action": "reconciled", "tier": "-", "store": "-", "scope": "-",
                                                                "name": "x", "reason": "r"}],
                                           cross_project={"pulled": [{"name": "f", "scope": "user-global"}]})))
check("RC: no angle-bracket placeholder tokens (<proj>/<global>/<->) reach the page",
      "<proj>" not in _RC4 and "<->" not in _RC4 and "<global>" not in _RC4)
_RC5 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, scope={"git_range": "-20", "git_commits": 3, "session_candidates": 1})))
check("RC: the markerless '-20' lookback sentinel renders as 'recent 20 (no marker)'",
      "recent 20 (no marker)" in _RC5)
_RC6 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, network={"totals": {"always_loaded_tokens": 100, "recall_tokens": 500}, "nodes": []})))
check("RC: totals-with-no-node-rows says 'node rows not captured', never 'no network yet'",
      "node rows not captured" in _RC6)
_RC7 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, distill={"verdict": "nothing: x fails"})))
check("RC: a distill-era record WITHOUT workflow_proposals renders 'registrar not consulted' (the visible decision)",
      "registrar not consulted" in _RC7)
_RC8 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, workflow_proposals={
      "candidates": [{"candidate": "python3 --pull .", "form": "command",
                      "evidence": {"nodes": ["a", "b"], "d": 2, "n": 4},
                      "mechanical": {"fleet_recurrence": True, "day_spread": True},
                      "name": "fleet-pull", "disposition": "awaiting-confirmation"}]})))
check("RC: the registrar block renders candidates with dispositions (its first render surface)",
      "REGISTRAR" in _RC8 and "fleet-pull" in _RC8 and "awaiting-confirmation" in _RC8)

# ── v0.1.89/v0.1.90 render-chain bugs: registrar overflow + repeated browser pop.
#    0.1.89 switched off the ledger .row grid but left cards as flex children of .dstl-verdict
#    (nowrap) with min-width:0 — 50 candidates shrank into unreadable columns. The panel is now
#    a COLUMN of .reg-card dockets; the verdict is a block sentence; missing disposition is
#    inferred from mechanical gates (never defaulted to awaiting-confirmation). ──
_TEMPLATE_SRC = (Path(__file__).resolve().parent.parent / "plugins" / "consolidate-memory" / "scripts"
                 / "dashboard.template.html").read_text(encoding="utf-8")
check("RC-90: registrar candidates are .reg-card dockets, never the ledger .row grid",
      ".reg-card" in _TEMPLATE_SRC and 'class="reg-card"' in _TEMPLATE_SRC
      and 'id="reg-board"' in _TEMPLATE_SRC
      and 'wbits+=\'<div class="row"' not in _TEMPLATE_SRC
      and 'class="reg-row"' not in _TEMPLATE_SRC)
check("RC-90: registrar board is a column (never a nowrap flex row of 50 cards)",
      ".reg-board{display:flex;flex-direction:column" in _TEMPLATE_SRC.replace(" ", ""))
check("RC-90: #reg-verdict is a sentence (flex-wrap tag+prose), never a nowrap card row",
      'class="reg-verdict" id="reg-verdict"' in _TEMPLATE_SRC
      and ".reg-verdict{display:flex;flex-wrap:wrap" in _TEMPLATE_SRC.replace(" ", "")
      and 'id="reg-board"' in _TEMPLATE_SRC
      and 'class="cmd-inline"' in _TEMPLATE_SRC)
check("RC-90: registrar does not default missing disposition to awaiting-confirmation",
      'disposition||"awaiting-confirmation"' not in _TEMPLATE_SRC
      and 'c.disposition||"awaiting-confirmation"' not in _TEMPLATE_SRC
      and "if(fleetG&&spreadG)" not in _TEMPLATE_SRC)
check("RC-91: HTML registrar cards MODEL decisions only — unnamed fleet co-occurrence is not a card",
      "BLOCKED_CAP" not in _TEMPLATE_SRC
      and "cm workflows" not in _TEMPLATE_SRC
      and "shared workflows" not in _TEMPLATE_SRC
      and "named.map(cardHtml)" in _TEMPLATE_SRC
      and "only showed up on one project or one day" not in _TEMPLATE_SRC
      and "single day each" in _TEMPLATE_SRC
      and 'stats.push(num(ev.d)+"d")' in _TEMPLATE_SRC
      and "across projects" in _TEMPLATE_SRC)
check("RC-90: registrar cards wrap long templates (a chain can never push the grid off-page)",
      "overflow-wrap:anywhere" in _TEMPLATE_SRC)
check("RC-90: carryFwd treats genuine 0 as data (p=v; a later null does not skip an emptied index)",
      "if(v==null)return p;v=num(v);p=v;return v" in _TEMPLATE_SRC)
check("RC-90: HTML traj uses the two-regime target (soft IDXB, then CEIL when over)",
      "var target=(cur>IDXB)?CEIL:IDXB" in _TEMPLATE_SRC)
check("RC-90: missing DATA.budgets falls back to 1500/3840, never the retired 1200 target",
      "num(BUD.index,1500)" in _TEMPLATE_SRC and "num(BUD.index,1200)" not in _TEMPLATE_SRC)
check("RC-90: hero axis labels the 1500 rung 'target' (not 'budget' — two-rung honesty)",
      'bl.textContent="target "' in _TEMPLATE_SRC)
check("RC-90: closeDiff is IIFE-scoped so Escape can close the diff modal",
      _TEMPLATE_SRC.count("function closeDiff") == 1
      and "Escape (keydown, outside paintDream)" in _TEMPLATE_SRC)
check("RC-90: over-target is cur>IDXB (parity with Python) and SJ is not the 'over budget' alarm",
      "over:cur>IDXB" in _TEMPLATE_SRC.replace(" ", "")
      and "just past the" in _TEMPLATE_SRC
      and "standing-justified" in _TEMPLATE_SRC
      and 'is <span class="hot">over budget</span>' not in _TEMPLATE_SRC)
check("RC-90: traj breach marker sits on t.target (ceiling when over-target), not the 1500 budget line",
      "var xCross=bx((n-1)+t.bf), ty=by(t.target)" in _TEMPLATE_SRC
      and "cx:xCross,cy:ty" in _TEMPLATE_SRC.replace(" ", "")
      and "cx:xCross,cy:ry" not in _TEMPLATE_SRC.replace(" ", "")
      and "if(t.bf<=ex)" in _TEMPLATE_SRC.replace(" ", ""))
check("RC-90: hashchange re-routes without location.reload()",
      "addEventListener(\"hashchange\", route)" in _TEMPLATE_SRC
      and "location.reload()" not in _TEMPLATE_SRC)
check("RC-90: hash-route resets scroll (reload used to land at top; in-page nav must too)",
      "window.scrollTo(0,0)" in _TEMPLATE_SRC.replace(" ", ""))
check("RC-90: light/dark --faint/--ghost are the WCAG-AA tokens (ghost passes on paper2/card too)",
      "--faint:#6a6356; --ghost:#6e675b" in _TEMPLATE_SRC
      and _TEMPLATE_SRC.count("--faint:#9a8d74; --ghost:#8e816a") == 2)
check("RC-90: audit head COUNTS are not uppercased (labels stay tracked small-caps)",
      ".audit-ln.head>.nums" in _TEMPLATE_SRC.replace(" ", "")
      and "text-transform:none" in _TEMPLATE_SRC)
# Dogfood 0.3.1: a 8-dangling health row wrapped "dangling wikilinks" onto two lines
# and silently dropped 5 names (slice(0,3) with no +N). Label column is now max-content
# + nowrap; names wrap in the result column; clipNames always emits +N when truncated.
check("0.3.1 html: health-row labels do not wrap when names are long",
      "grid-template-columns:max-content minmax(0,1fr)" in _TEMPLATE_SRC
      and "white-space:nowrap" in _TEMPLATE_SRC
      and ".audit-ln .nums" in _TEMPLATE_SRC
      and "overflow-wrap:anywhere" in _TEMPLATE_SRC
      and ".audit-ln{display:grid;grid-template-columns:1fr auto" not in _TEMPLATE_SRC)
check("0.3.1 html: dangling/orphan names clip with +N more, never a silent slice(0,3)",
      "function clipNames" in _TEMPLATE_SRC
      and "dangNames.slice(0,3)" not in _TEMPLATE_SRC
      and '" · +"+(names.length-cap)+" more"' in _TEMPLATE_SRC
      and "clipNames(dangNames, 8)" in _TEMPLATE_SRC)
check("0.3.1 html: usage is organic + dream-procedure excluded (not 0-reads vs N-confirmed)",
      "organic read" in _TEMPLATE_SRC
      and "dream-procedure excluded" in _TEMPLATE_SRC
      and "not in the index" in _TEMPLATE_SRC)
check("RC-90: longitudinal rigor is a categorical strip — no interpolating connectors, no LIGHT default",
      "x1:bx(i-1),y1:ty[pk],x2:bx(i),y2:ty[k]" not in _TEMPLATE_SRC.replace(" ", "")
      and 'if(!ty[k])k="LIGHT"' not in _TEMPLATE_SRC.replace(" ", "")
      and "chart-kicker" in _TEMPLATE_SRC
      and 'ht.textContent="writes"' not in _TEMPLATE_SRC
      and "function graphLabel" in _TEMPLATE_SRC
      and "this project</span>" in _TEMPLATE_SRC
      and "trigger node</span>" not in _TEMPLATE_SRC)
check("graph: Shared Consciousness caption + this-stack legend exist (split vs fallback)",
      'id="net-cap"' in _TEMPLATE_SRC
      and 'id="net-leg-stack"' in _TEMPLATE_SRC
      and "Numbers are this-stack facts; lines are what some share." in _TEMPLATE_SRC
      and "Older record — a line just means this project holds at least one shared fact." in _TEMPLATE_SRC)
check("graph: split records size by shared, number by stack; legacy keeps facts + shared/3 spokes",
      'sizeKey=split?"shared":"facts"' in _TEMPLATE_SRC.replace(" ", "")
      and "Math.max(.8,Math.min(3,n/3))" in _TEMPLATE_SRC.replace(" ", "")
      and "pn<=Math.max(spokeN[i],spokeN[j])" in _TEMPLATE_SRC.replace(" ", "")
      and 'split?"shared":"facts"' in _TEMPLATE_SRC)
check("graph: does not invent live topology at render (edges come from the cycle record)",
      "stack_edges" in _TEMPLATE_SRC
      and "global_facts" not in _TEMPLATE_SRC
      and "function edgeN" in _TEMPLATE_SRC)
check("graph: circle numbers don't steal hover (pointer-events none on the count text)",
      "font-size:11px;pointer-events:none" in _TEMPLATE_SRC)
check("graph: ring is seriated by this-stack affinity; baseline-only satellites trail + dim",
      "ringOrder" in _TEMPLATE_SRC
      and "function isBaseline" in _TEMPLATE_SRC
      and "function bowCtrl" in _TEMPLATE_SRC
      and 'S("path"' in _TEMPLATE_SRC
      and 'opacity:base?".5"' in _TEMPLATE_SRC)
check("graph: prettyNode keeps a trailing version tail (Qwen-3-6, not 3-6)",
      "/^[0-9]+$/.test(p[i])" in _TEMPLATE_SRC)
check("v0.1.90: registrar blocked persist cap is 8 (HTML no longer samples blocked cards)",
      ms._REGISTRAR_BLOCKED_CAP == 8)
_RC9_cands = [{"candidate": f"cmd{i}", "form": "command", "evidence": {"nodes": ["a"], "d": 2, "n": 2},
               "mechanical": {"fleet_recurrence": False, "day_spread": True}, "disposition": "declined"}
              for i in range(15)]
_RC9 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, workflow_proposals={"candidates": _RC9_cands})))
_check_rc9_rows = _RC9.count("◈")
check("RC-89: the ASCII registrar caps blocked rows at 8 + the '+N more' tail (parity with the HTML)",
      _check_rc9_rows == 8 and "+7 more blocked" in _RC9)
_RC10_cands = [{"candidate": f"cmd{i}", "form": "command",
                "evidence": {"nodes": ["a"], "d": 1, "n": 2},
                "mechanical": {"fleet_recurrence": True, "day_spread": False}}
               for i in range(3)]
_RC10 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, workflow_proposals={"candidates": _RC10_cands})))
check("RC-90: ASCII registrar infers blocked: day-spread when model disposition is missing (never awaiting)",
      "blocked: day-spread" in _RC10 and "awaiting-confirmation" not in _RC10)
_RC11 = rd.render(cast(ms.CycleRecord, dict(_RC_BASE, workflow_proposals={"candidates": [
      {"candidate": "python3 tests/foo.py", "form": "command",
       "evidence": {"nodes": ["a", "b"], "d": 2, "n": 4},
       "mechanical": {"fleet_recurrence": True, "day_spread": True, "distinctive": True}}]})))
check("RC-91: ASCII missing model disposition on a distinctive fleet row is fleet-candidate, never awaiting",
      "fleet-candidate" in _RC11 and "awaiting-confirmation" not in _RC11
      and "python3 tests/foo.py" in _RC11)
_TS = 1000.0
_tmpd = Path(_tempfile.mkdtemp())
check("RC-89: _open_recent is a PURE read (same-anchor within the window reports open; never writes)",
      rhtml._open_recent(Path("/tmp/x.html"), "#sel=3", _TS, _tmpd) is False
      and not (Path(_tmpd) / rhtml._OPEN_MARKER_NAME).exists())
rhtml._mark_open(Path("/tmp/x.html"), "#sel=3", _TS, _tmpd)
check("RC-89: _mark_open then _open_recent — one open per (archive, anchor) per window",
      rhtml._open_recent(Path("/tmp/x.html"), "#sel=3", _TS + 60, _tmpd) is True
      and rhtml._open_recent(Path("/tmp/x.html"), "#sel=4", _TS + 60, _tmpd) is False
      and rhtml._open_recent(Path("/tmp/x.html"), "#sel=3", _TS + 3000, _tmpd) is False)
with _tempfile.TemporaryDirectory() as _tdn4:
    _cyc_n4 = Path(_tdn4) / "c.json"
    _cyc_n4.write_text(_json43.dumps({"project": "p", "marker": {"commit": "c", "timestamp": "t"}}), encoding="utf-8")
    _store_n4 = Path(_tdn4) / "memory"; _store_n4.mkdir()
    (_store_n4 / ".consolidation-log.jsonl").write_text("", encoding="utf-8")
    _out_n4 = Path(_tdn4) / "index.html"
    _real_open_n4 = rhtml.webbrowser.open
    rhtml.webbrowser.open = cast(Any, lambda url: False)
    try:
        _rc_n4 = rhtml.main([str(_cyc_n4), "--store", str(_store_n4), "--out", str(_out_n4)])
    finally:
        rhtml.webbrowser.open = _real_open_n4
    check("RC-89/n4: a FAILED webbrowser.open writes no .last-open marker (the next attempt is never suppressed)",
          _rc_n4 == 0 and not (Path(_tdn4) / rhtml._OPEN_MARKER_NAME).exists())

# ── v0.4.1 archive-renderer repairs (C1/C2 embed-side + read_diffs aliasing) ──
_rhC1 = [{"marker": {"commit": "c", "timestamp": "t1"}, "session": "s", "project": "p"}]
_rrecC1: dict = {"marker": {"commit": "c", "timestamp": ""}, "session": "s", "project": "p"}
def _arc_first_ts(cy: Any) -> str:
    if isinstance(cy, list) and len(cy) and isinstance(cy[0], dict):
        m = cy[0].get("marker")
        if isinstance(m, dict):
            return str(m.get("timestamp"))
    return ""
_rcyC1, _rtC1 = cast(Any, rhtml.assemble_cycles(_rrecC1, _rhC1))
check("C1: assemble_cycles fills an empty marker.timestamp from a same-commit same-session history stamp (ONE row, stamped, source unmutated)",
      _rtC1 == 1 and _arc_first_ts(_rcyC1) == "t1" and _rrecC1["marker"]["timestamp"] == "")
_rcyC1b, _rtC1b = cast(Any, rhtml.assemble_cycles({"marker": {"commit": "c2", "timestamp": "", "before_timestamp": "t0"}}, []))
check("C1: no same-commit history → before_timestamp fills the empty stamp",
      _rtC1b == 1 and _arc_first_ts(_rcyC1b) == "t0")
_rcyC1c, _rtC1c = cast(Any, rhtml.assemble_cycles({"marker": {"commit": "c3", "timestamp": ""}}, []))
check("C1: no fill source → the stamp stays empty (the JS renders '—' and sorts the row last)",
      _rtC1c == 1 and _arc_first_ts(_rcyC1c) == "")
_rcw = cast(Any, rhtml.assemble_cycles({"marker": {"commit": "c2", "timestamp": ""}, "session": "x"},
                             [{"marker": {"commit": "c0", "timestamp": "tA"}, "session": "x"},
                              {"marker": {"commit": "c1", "timestamp": ""}, "session": "x"}]))
_rcw_row: object = _rcw[0][2] if isinstance(_rcw[0], list) and len(_rcw[0]) > 2 else {}
_rcw_ts = (_rcw_row or {}).get("marker", {}).get("timestamp") if isinstance(_rcw_row, dict) else ""
check("C1: the chain-walk fills adjacent empty rows from the nearest earlier stamp", _rcw_ts == "tA")
check("C2: a stale unstamped log tail vs a stamped current record dedup to ONE row (the stamped copy wins)",
      rhtml.assemble_cycles({"marker": {"commit": "c", "timestamp": "t9"}, "session": "s"},
                            [{"marker": {"commit": "c", "timestamp": ""}, "session": "s"}])
      == ([{"marker": {"commit": "c", "timestamp": "t9"}, "session": "s"}], 1))
check("C2: a same-marker log tail is REPLACED by the current record (a post-persist enrichment surfaces)",
      rhtml.assemble_cycles({"marker": {"commit": "c", "timestamp": "t9"}, "session": "s", "network": {"nodes": []}},
                            [{"marker": {"commit": "c", "timestamp": "t9"}, "session": "s"}])[0][-1].get("network") is not None)
check("C2: a stamped log tail vs an unstamped current record dedup to ONE row (the record is filled from history)",
      rhtml.assemble_cycles({"marker": {"commit": "c", "timestamp": ""}, "session": "s"},
                            [{"marker": {"commit": "c", "timestamp": "t9"}, "session": "s"}])
      == ([{"marker": {"commit": "c", "timestamp": "t9"}, "session": "s"}], 1))
check("C2 SESSION GUARD: same commit, different session, either empty → TWO rows (same-HEAD dreams never collapse)",
      rhtml.assemble_cycles({"marker": {"commit": "c", "timestamp": ""}, "session": "s2"},
                            [{"marker": {"commit": "c", "timestamp": "t1"}, "session": "s1"}])[1] == 2)
check("C2: same commit + DIFFERENT non-empty stamps still append (two dreams at one HEAD stay distinct)",
      rhtml.assemble_cycles({"marker": {"commit": "c", "timestamp": "t8"}},
                            [{"marker": {"commit": "c", "timestamp": "t9"}}])[1] == 2)
with _tempfile.TemporaryDirectory() as _td41r:
    _d41d = Path(_td41r) / "dashboards" / "diffs"; _d41d.mkdir(parents=True)
    (_d41d / "c41__nots__s41.json").write_text(_json43.dumps({"memory": {"modified": 1}}), encoding="utf-8")
    _rdf41 = rhtml.read_diffs(Path(_td41r) / "memory", [{"marker": {"commit": "c41", "timestamp": "t41"}, "session": "s41"}])
    check("C1 read_diffs alias: a legacy __nots sidecar resolves for a FILLED cycle under every probed key",
          _rdf41.get("c41__t41__s41") == {"memory": {"modified": 1}}
          and _rdf41.get("c41__nots__s41") == {"memory": {"modified": 1}})

# ── v0.4.1 template repairs — exact-fragment pins (the template must carry them verbatim) ──
check("C1: archive row + footer treat an empty timestamp as missing ('—', never a blank cell)",
      'String(g(c,"marker.timestamp","")||"—")' in _TEMPLATE_SRC
      and 'String(g(CUR,"marker.timestamp","")||"—")' in _TEMPLATE_SRC)
check("C1: empty-ts rows sort last under EITHER direction (unknown recency is never 'newest')",
      'var ea=a[st.key]==="", eb=b[st.key]==="";' in _TEMPLATE_SRC
      and "if(ea||eb)return ea&&eb?0:(ea?1:-1)" in _TEMPLATE_SRC)
check("M1: an ABSENT network block renders the honest not-captured fallback (never the false empty claim)",
      'g(CUR,"network",null)' in _TEMPLATE_SRC and "hasNet" in _TEMPLATE_SRC
      and _TEMPLATE_SRC.count("project list wasn’t captured this pass") >= 2
      and '"no other projects sharing memory yet"' in _TEMPLATE_SRC)
check("M2: files[] renders as a dim label even with no diff sidecar (capped +N more)",
      "function fileLabel" in _TEMPLATE_SRC and "return esc(nm)+fl;" in _TEMPLATE_SRC
      and "rawFiles.length>3" in _TEMPLATE_SRC)
check("M3: ledger middle column is minmax(0,1fr), reasons wrap, citations truncate + tooltip",
      "grid-template-columns:96px minmax(0,1fr) auto" in _TEMPLATE_SRC
      and "grid-template-columns:96px 1fr auto" not in _TEMPLATE_SRC
      and "String(cit).slice(0,10)" in _TEMPLATE_SRC and 'title="\'+esc(cit)+\'"' in _TEMPLATE_SRC)
check("m1: reg-counts appends the blocked tally (N blocked no longer hides under 'none this pass')",
      "num(WP.n_blocked" in _TEMPLATE_SRC and '" blocked"' in _TEMPLATE_SRC)
check("m2: audit per-file operations + usage archive_reads render",
      "a.operations" in _TEMPLATE_SRC and "per-file" in _TEMPLATE_SRC and "archive read" in _TEMPLATE_SRC)
check("m3: per_fact and demotion-surfaced truncation carry the +N more counter",
      "ufact.length>3" in _TEMPLATE_SRC and "surfStr.length>3" in _TEMPLATE_SRC)
check("m4: the demotion verdict strips a duplicated 'eligible N' lead and tags counter-justified",
      r"/^\s*eligible\s+\d+" in _TEMPLATE_SRC and "counter-justified" in _TEMPLATE_SRC)
check("n1: dream stanzas wrap instead of overflowing",
      ".dream-stanza div{font-family:var(--serif);font-style:italic;color:var(--ink2);font-size:14.5px;line-height:1.6;overflow-wrap:anywhere}" in _TEMPLATE_SRC)
check("n2: flag/dl tints are theme tokens in all three theme blocks (no hardcoded rgba rules)",
      "--tint-ok:rgba(95,169,150,.13)" in _TEMPLATE_SRC
      and _TEMPLATE_SRC.count("--tint-ok:rgba(95,169,150,.16)") == 2
      and "background:var(--tint-ok)" in _TEMPLATE_SRC and "background:var(--tint-crit)" in _TEMPLATE_SRC
      and "background:var(--tint-accent)" in _TEMPLATE_SRC and "background:var(--tint-warn)" in _TEMPLATE_SRC
      and ".dl-plus{background:rgba" not in _TEMPLATE_SRC and ".flag{background:rgba" not in _TEMPLATE_SRC)
check("n3: verification is glyph-free colored counts (no ✓ KPI, no +/~/− audit cells)",
      "'<small> ✓</small>'" not in _TEMPLATE_SRC
      and "'+'+num(d.created)" not in _TEMPLATE_SRC
      and "'~'+num(d.modified)" not in _TEMPLATE_SRC
      and "'−'+num(d.deleted)" not in _TEMPLATE_SRC
      and "class=\"a-added\">'+num(d.created)" in _TEMPLATE_SRC)
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
    # the mutation-log lands under plugin-data ops for the PROJECT slug → proves --into was NOT
    # consumed as the positional project_dir (else slug_for(cycle.json) and this path wouldn't
    # exist) — the _argpaths regression guard. Native plane stays facts-only.
    import retention as _ret53
    _native53 = Path(_td53) / "home" / ".claude" / "projects" / ms.slug_for(Path(_td53) / "proj") / "memory"
    _mlog53 = _ret53.mutation_log_write_path(_native53, environ={"HOME": str(Path(_td53) / "home")})
    _wrong53 = _ret53.mutation_log_write_path(
        Path(_td53) / "home" / ".claude" / "projects" / ms.slug_for(_cyc53) / "memory",
        environ={"HOME": str(Path(_td53) / "home")})
    check("v0.1.53 bug5: --audit wrote the mutation-log under plugin-data ops for the PROJECT slug (--into NOT mis-read as project_dir)",
          _mlog53.exists() and not _wrong53.exists())
    check("v0.1.53 bug5: --audit did not write .mutation-log.jsonl into the native plane",
          not (_native53 / ".mutation-log.jsonl").exists())

# --- v0.1.54: the dream-arc contract (write-time cues + record capture + surfaces) ---
# (1) validate_cycle_record: `dream` container checks (dict at top level, beats a list).
check("v0.1.54 validate: warns on non-dict dream", "dream is not a dict" in
      ms.validate_cycle_record({"dream": []}))
check("v0.1.54 validate: warns on non-list dream.beats", "dream.beats is not a list" in
      ms.validate_cycle_record({"dream": {"beats": "x"}}))
check("v0.1.54 validate: SILENT on a well-formed dream block",
      ms.validate_cycle_record({"dream": {"sleep": "> *💤 s*", "beats": ["> *🌙 b*"] * 6, "wake": "> *☀️ w*"}}) == [])
# v0.4.1 (D1): a PRESENT-but-short arc warns too (the same single predicate the persist gate uses).
check("v0.4.1 validate: warns on a present-but-short arc",
      "dream arc incomplete: 4/6 beats" in ms.validate_cycle_record(
          {"dream": {"sleep": "s", "beats": ["a"] * 4, "wake": "w"}}))
check("v0.4.1 validate: warns on a missing sleep with 6 beats",
      "dream arc incomplete: sleep missing" in ms.validate_cycle_record(
          {"dream": {"beats": ["a"] * 6, "wake": "w"}}))

# (2) dashboard presence line — gated on the key: with `dream` → DREAM ARC line (beats counted,
# missing halves flagged ✗); without → not rendered (legacy byte-path untouched).
_dr54 = cast(ms.CycleRecord, {"project": "p", "session": "s",
                              "dream": {"sleep": "> *💤 s*", "beats": ["> *🌙 a*", "> *🌙 b*"], "wake": "> *☀️ w*"}})
_dr54_out = rd.render(_dr54)
check("v0.1.54 render: DREAM ARC line present when captured (sleep · N/6 beats · wake)",
      "DREAM ARC" in _dr54_out and "2/6 beats" in _dr54_out and "sleep" in _dr54_out and "wake" in _dr54_out)
# render-chain audit: the beats ✓ now GATES on completeness (6 = 5 phase beats + surfacing), and an
# emoji inside a non-bookend beat is flagged (the arc contract bans it outside the bookends).
check("v0.1.54 render: incomplete arc shows ✗ N/6 + the emoji-in-beats flag (render-chain audit)",
      "✗ 2/6 beats" in _dr54_out and "emoji in beat(s)" in _dr54_out)
_dr54_full = rd.render(cast(ms.CycleRecord, {"project": "p",
      "dream": {"sleep": "*💤 s*", "beats": ["*a*", "*b*", "*c*", "*d*", "*e*", "*f*"], "wake": "*☀️ w*"}}))
check("v0.1.54 render: a COMPLETE 6-beat arc green-checks (✓ 6/6 beats)",
      "✓ 6/6 beats" in _dr54_full)
_dr54_partial = rd.render(cast(ms.CycleRecord, {"project": "p", "dream": {"beats": ["> *🌙 a*"]}}))
check("v0.1.54 render: partial arc shows its gaps (✗ sleep / ✗ wake, 1/6 beat)",
      "DREAM ARC" in _dr54_partial and "✗ sleep" in _dr54_partial and "✗ wake" in _dr54_partial and "1/6 beat" in _dr54_partial)
check("v0.1.54 render: NO DREAM ARC line without the key (legacy unchanged)",
      "DREAM ARC" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s"})))
# a JSON-null stanza must read ABSENT (✗), never a truthy str(None) — the null-arc honesty fix.
_dr54_null = rd.render(cast(ms.CycleRecord, {"project": "p", "dream": {"sleep": None, "beats": ["> *🌙 a*"], "wake": None}}))
check("v0.1.54 render: null sleep/wake → ✗ gaps (str(None) truthiness fixed)",
      "✗ sleep" in _dr54_null and "✗ wake" in _dr54_null and "1/6 beat" in _dr54_null)

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
    check("v0.1.54/64 render_html cue: archive rendered → the WAKE hint (full stop, no trailing Awake, 📊 path last)",
          _rc54 == 0 and "WAKE now" in _se54 and "no trailing" in _se54
          and "then '☀️ **Awake.**'" not in _se54)
    _so54, _se54, _rc54 = _run54("render_html.py", str(_clean54), "--no-open", "--out", _out54, cue=False)
    check("v0.1.54 render_html cue: env absent → silent", _rc54 == 0 and "[dream-arc]" not in _se54)

    # --- v0.4.1: dream-arc gate (exit 4), unstamped teeth (exit 5), marker auto-mirror, D3 ---
    import retention as _ret41  # local: the module-level `ret` alias lands later in this file
    # --- v0.4.1: dream-arc gate (exit 4), unstamped teeth (exit 5), marker auto-mirror, D3 ---
    # arc_completeness — the SINGLE completeness predicate (the panel ✓/✗, the gate, and the
    # WAKE cue all consume it — one definition, no reimplementation drift).
    check("v0.4.1 arc: dreamless record is complete (legacy/preview carve-out)",
          ms.arc_completeness({}) == (True, ""))
    check("v0.4.1 arc: a complete 6-beat arc", ms.arc_completeness(
          {"dream": {"sleep": "s", "beats": ["a"] * 6, "wake": "w"}}) == (True, ""))
    check("v0.4.1 arc: a 4-beat arc is incomplete", ms.arc_completeness(
          {"dream": {"sleep": "s", "beats": ["a"] * 4, "wake": "w"}}) == (False, "4/6 beats"))
    check("v0.4.1 arc: missing sleep with 6 beats is incomplete", ms.arc_completeness(
          {"dream": {"beats": ["a"] * 6, "wake": "w"}})[0] is False)
    check("v0.4.1 arc: non-dict dream / junk record never raise",
          ms.arc_completeness({"dream": "x"}) == (False, "dream block malformed (not a dict)")
          and ms.arc_completeness("junk") == (True, ""))
    # reconcile_marker — fills empty fields from the stamped state file (single source), a
    # non-empty value stands, junk/missing input never raises.
    _st41 = Path(_td54) / "v041-store"; _st41.mkdir(parents=True, exist_ok=True)
    (_st41 / ".consolidation-state.json").write_text(
        _json43.dumps({"commit": "abc1234", "timestamp": "2026-07-02T00:00:00Z"}))
    check("v0.4.1 reconcile: fills empty commit+timestamp from the state file",
          ms.reconcile_marker({"commit": "", "timestamp": ""}, _st41)
          == {"commit": "abc1234", "timestamp": "2026-07-02T00:00:00Z"})
    check("v0.4.1 reconcile: a non-empty value stands; junk degrades + fills; missing file never raises",
          ms.reconcile_marker({"commit": "mine", "timestamp": ""}, _st41)
          == {"commit": "mine", "timestamp": "2026-07-02T00:00:00Z"}
          and ms.reconcile_marker("junk", _st41)
          == {"commit": "abc1234", "timestamp": "2026-07-02T00:00:00Z"}
          and ms.reconcile_marker(None, Path(_td54) / "nope") == {})
    # D3: a managed mirror is EXEMPT from the drift field checks (its stamp block has no
    # node_type) while its stem stays in the index-symmetric diff.
    _f41 = Path(_td54) / "v041-facts"; _f41.mkdir(parents=True, exist_ok=True)
    (_f41 / "local-x.md").write_text("body\n", encoding="utf-8")   # node_type-less authored → drift
    (_f41 / "mirror-y.md").write_text(
        "---\nmetadata:\n  mirrored_at: 2026-07-02T00:00:00Z\n  global_ref: mirror-y\n"
        "  canonical_fact_id: f_abababababababababababab\n  canonical_domain: personal\n"
        "  global_ref_since: 2026-07-02T00:00:00Z\n  global_ref_body: ab12cd34ef56\n"
        "name: mirror-y\nscope: user-global\n---\nbody\n", encoding="utf-8")
    _sd41 = ms.schema_drift([_f41 / "local-x.md", _f41 / "mirror-y.md"], {"local-x", "mirror-y"})
    check("v0.4.1 D3: a managed mirror is exempt from drift checks, its stem still counted",
          _sd41["missing_node_type"] == 1 and _sd41["index_mismatch"] == 0)
    _sd41b = ms.schema_drift([_f41 / "mirror-y.md"], {"mirror-y"})
    check("v0.4.1 D3: a mirror-only store has zero drift findings",
          _sd41b["missing_node_type"] == 0)
    # terminal gate subprocess pins — fresh records, shared persist dir.
    _p41 = Path(_td54) / "v041-persist"; _p41.mkdir(parents=True, exist_ok=True)
    _base41 = {"project": "p", "scope": {"git_commits": 9, "session_candidates": 3},
               "verification": {"confirmed": 3, "corrected": 0, "unverifiable": 0}}
    def _wr41(name: str, extra: dict) -> str:
        p = Path(_td54) / name
        p.write_text(_json43.dumps({**_base41, **extra}))
        return str(p)
    _short41p = _wr41("v041-short.json", {"marker": {"timestamp": "2026-07-02T00:00:01Z"},
                                          "dream": {"sleep": "s", "beats": ["a"] * 4, "wake": "w"}})
    _so41, _se41, _rc41 = _run54("render_dashboard.py", _short41p, "--persist", str(_p41), cue=True)
    check("v0.4.1 gate: a 4/6 arc at --persist exits 4 with the loud panel + the NOT-over cue",
          _rc41 == 4 and "DREAM ARC INCOMPLETE" in _so41 and "4/6 beats" in _so41
          and "arc incomplete" in _se41)
    _log41 = _ret41.cycle_log_write_path(_p41, environ={**_os53.environ, "HOME": _home54})
    _last41 = _json43.loads(_log41.read_text(encoding="utf-8").strip().splitlines()[-1])
    check("v0.4.1 gate: the firing 4/6 record accrued to the log (persist-then-exit)",
          _log41.is_file() and len((_last41.get("dream") or {}).get("beats") or []) == 4)
    _smp41 = _wr41("v041-sleepmissing.json", {"marker": {"timestamp": "2026-07-02T00:00:02Z"},
                                              "dream": {"beats": ["a"] * 6, "wake": "w"}})
    _so41, _se41, _rc41 = _run54("render_dashboard.py", _smp41, "--persist", str(_p41), cue=True)
    check("v0.4.1 gate: missing sleep with 6 beats exits 4 too", _rc41 == 4 and "sleep missing" in _so41)
    _full41p = _wr41("v041-full.json", {"marker": {"timestamp": "2026-07-02T00:00:03Z"},
                                        "dream": {"sleep": "s", "beats": ["a"] * 6, "wake": "w"}})
    _so41, _se41, _rc41 = _run54("render_dashboard.py", _full41p, "--persist", str(_p41), cue=True)
    check("v0.4.1 gate: a complete 6/6 arc exits 0, prints the appended path, cues persist clean",
          _rc41 == 0 and "persist clean" in _se41 and "persist →" in _so41)
    _dr41 = _wr41("v041-dreamless.json", {"marker": {"timestamp": "2026-07-02T00:00:04Z"}})
    _so41, _se41, _rc41 = _run54("render_dashboard.py", _dr41, "--persist", str(_p41), cue=True)
    check("v0.4.1 gate: a dreamless record keeps exit 0 (the legacy carve-out)",
          _rc41 == 0 and "persist clean" in _se41)
    # auto-mirror: an empty record stamp reconciles from the stamped state file — BOTH the
    # log line and the cycle file carry it (the split-brain heal).
    (_p41 / ".consolidation-state.json").write_text(
        _json43.dumps({"commit": "stamp41", "timestamp": "2026-07-02T00:10:00Z"}))
    _am41p = _wr41("v041-automirror.json", {"marker": {"commit": "", "timestamp": ""}})
    _so41, _se41, _rc41 = _run54("render_dashboard.py", _am41p, "--persist", str(_p41), cue=True)
    _last41 = _json43.loads(_log41.read_text(encoding="utf-8").strip().splitlines()[-1])
    _cycle41 = _json43.loads(Path(_am41p).read_text(encoding="utf-8"))
    check("v0.4.1 auto-mirror: the empty stamp reconciles — log line AND cycle file carry it",
          _rc41 == 0 and "persist →" in _so41
          and _last41.get("marker", {}).get("timestamp") == "2026-07-02T00:10:00Z"
          and _cycle41.get("marker", {}).get("timestamp") == "2026-07-02T00:10:00Z")
    # duplicate: the idempotent re-render (the exit-4 loop-back) appends nothing and never
    # fakes a "persist clean" cue.
    _n41 = len(_log41.read_text(encoding="utf-8").strip().splitlines())
    _so41, _se41, _rc41 = _run54("render_dashboard.py", _am41p, "--persist", str(_p41), cue=True)
    check("v0.4.1 duplicate: the idempotent re-render adds no line and no 'persist clean' cue",
          _rc41 == 0 and "persist clean" not in _se41
          and len(_log41.read_text(encoding="utf-8").strip().splitlines()) == _n41)
    # still-unstamped: no state file → exit 5, loud stderr, nothing appended.
    _p41b = Path(_td54) / "v041-persist-b"; _p41b.mkdir(parents=True, exist_ok=True)
    _us41p = _wr41("v041-unstamped.json", {"marker": {"commit": "", "timestamp": ""}})
    _so41, _se41, _rc41 = _run54("render_dashboard.py", _us41p, "--persist", str(_p41b), cue=True)
    _log41b = _ret41.cycle_log_write_path(_p41b, environ={**_os53.environ, "HOME": _home54})
    check("v0.4.1 unstamped: exit 5, loud UNSTAMPED panel, no append, no 'persist clean'",
          _rc41 == 5 and "UNSTAMPED" in _se41 and "persist clean" not in _se41
          and not _log41b.is_file())
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
check("v0.1.54/57 SKILL pin: the dream-arc contract anchors (schematic, beats, never-echo)",
      "*💤" in _sk54 and "SLEEP" in _sk54 and "SURFACING" in _sk54 and "WAKE" in _sk54
      and "[dream-arc]" in _sk54)
check("v0.1.57 SKILL pin: the quiet-dream format — no blockquote schematic, bookend-only emojis",
      "> *💤" not in _sk54 and "> *🌙" not in _sk54 and "no blockquote" in _sk54
      and "every other dream line carries none" in _sk54)

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
_FakeCtx54.log_records = [{"dream": {"sleep": "s", "beats": ["b"] * 6, "wake": "w"}, "marker": {"timestamp": "t2"}}]
check("v0.1.54 beta family: complete arc → PASS", _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54()))[0].status == "PASS")
_FakeCtx54.log_records = [{"dream": {"sleep": "s", "beats": ["b"] * 4, "wake": "w"}, "marker": {"timestamp": "t2b"}}]
_r541 = _bc54.dream_arc_capture(cast(_bc54.Ctx, _FakeCtx54()))
check("v0.4.1 beta family: a 4-beat arc → WARN (the == 6 count, v0.4.1 boundary named)",
      _r541[0].status == "WARN" and "beats=4" in _r541[0].actual and "v0.4.1" in _r541[0].actual)
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
# (5) dashboard: gated DISTILL line (verdict rendered IN FULL on a wrapped continuation line —
# v0.1.57, was a mid-word 60-char truncation; missing verdict flagged; legacy absent).
_di55 = cast(ms.CycleRecord, {"project": "p", "distill": {"n_recurring": 14, "n_chains": 6,
                              "verdict": "nothing: the smoke→mypy→sim gate-chain — already covered by release.sh ENDTOKEN"}})
_di55_out = rd.render(_di55)
check("v0.1.55/57 render: DISTILL counts + the FULL verdict (no truncation — the tail survives)",
      "DISTILL" in _di55_out and "14 recurring" in _di55_out and "6 chains" in _di55_out
      and "already covered" in _di55_out and "ENDTOKEN" in _di55_out)
# …but a runaway model-authored verdict is still BOUNDED (220-char guard — "one sentence" is
# guidance, not validation; an unbounded slip would inflate the fixed-rhythm dashboard).
_di57_long = rd.render(cast(ms.CycleRecord, {"project": "p", "distill": {"n_recurring": 1, "n_chains": 0,
                       "verdict": "nothing: " + "x" * 400 + " TAILTOKEN"}}))
check("v0.1.57 render: a runaway verdict is capped at ~220 chars (ellipsis, no TAILTOKEN)",
      "TAILTOKEN" not in _di57_long and "…" in _di57_long)
check("v0.1.55 render: distill without a verdict flags the gap",
      "✗ no verdict" in rd.render(cast(ms.CycleRecord, {"project": "p", "distill": {"n_recurring": 2}})))
check("v0.1.55 render: NO DISTILL line without the key (legacy unchanged)",
      "DISTILL" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s"})))
# v0.1.58 [9]: the secrets_omitted transparency count REACHES the ASCII line (gated on > 0 — the
# schema-cascade contract; the fix was unpinned until here, the exact "key never reaches the view" gap).
check("v0.1.58 [9] render: secrets_omitted > 0 shows 'N secret-shaped' on the DISTILL line",
      "7 secret-shaped" in rd.render(cast(ms.CycleRecord, {"project": "p", "distill":
          {"n_recurring": 3, "n_chains": 1, "secrets_omitted": 7, "verdict": "nothing: x fails leg"}})))
check("v0.1.58 [9] render: secrets_omitted == 0 adds NO clause (gated)",
      "secret-shaped" not in rd.render(cast(ms.CycleRecord, {"project": "p", "distill":
          {"n_recurring": 3, "n_chains": 1, "secrets_omitted": 0, "verdict": "nothing: x fails leg"}})))
# (6) HTML: the gated distill line ships in the verify panel JS (esc()-guarded, key-gated).
# (_tpl54 is read at RUNTIME above, so it already holds the current template — one arm, no dead dup.)
check("v0.1.55/58 html: template ships the gated distill line + the secrets_omitted clause",
      "CUR.distill" in _tpl54 and "n_recurring" in _tpl54 and "secret-shaped" in _tpl54)
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
      "THE VERDICT" in _sk55 and "fails" in _sk55 and "READ THE CHAINS FIRST" in _sk55)
check("v0.1.55 SKILL pin: the null-priming hedges are DELETED",
      "usually proposes nothing" not in _sk55 and "EXPECTED outcome" not in _sk55)
check("v0.1.58 SKILL pin: the hand-mirror count language is DELETED (counts are script-only via --into)",
      "n_recurring = len(" not in _sk55 and "--into <the --seed path>" in _sk55)
check("v0.1.58 SKILL pin: gate leg 6 (previously DECLINED) present",
      "previously DECLINED" in _sk55 and ".consolidation-log.jsonl" in _sk55)
# Empty-set rule: judgment gated on scripted-empty, scans still mandatory; no store-wide
# fact-body preload (the index is the inventory; content reads stay targeted).
check("empty-set rule lives in SKILL (judgment, not scans)",
      "Empty-set rule (judgment, not scans)" in _sk55
      and "Never skip the scan" in _sk55
      and "nothing: 0 recurring · 0 chains" in _sk55)
check("Phase 1 no longer preloads every auto-memory fact body",
      "Read fully:" not in _sk55
      and "the auto-memory fact files" not in _sk55
      and "Fact bodies — targeted, not a store-wide preload" in _sk55)

# ── v0.1.58: distill hardening — closed POSIX noise classes, structural interpreter rule,
# firewall-at-emission, --into deterministic capture, per-line window, CLI honesty ───────────────
# (1) F1 — each junk class measured LIVE in the 2026-07-03 audit's top-40, one pin per class.
check("v0.1.58 F1: test-guard segment drops; the real command survives",
      ds._scan_cmd('[ -d "$X" ] && real-tool run') == (["real-tool run"], []))
check("v0.1.58 F1: 3-seg bridge ACROSS the dropped guard (non-vacuous adjacency — the 2-seg case is trivial)",
      ds._scan_cmd("[ -f x ] && alpha-tool run && beta-tool run")
      == (["alpha-tool run", "beta-tool run"], [("alpha-tool run", "beta-tool run")]))
check("v0.1.58 F1: brace-group opener carries, closer drops (no '{ cmd' fusion, no '}' row)",
      ds._scan_cmd("{ real-tool run; } 2>&1 | tee log") == (["real-tool run"], []))
check("v0.1.58 F1: control heads drop WITH args (exit 1 / continue / break / return 0)",
      ds._scan_cmd("x-tool run && exit 1")[0] == ["x-tool run"]
      and ds._scan_cmd("y-tool run && continue")[0] == ["y-tool run"]
      and ds._scan_cmd("z-tool run && break")[0] == ["z-tool run"]
      and ds._scan_cmd("w-tool run && return 0")[0] == ["w-tool run"])
check("v0.1.58 F1: a bare '}' line drops (the ×16 live row)",
      ds._scan_cmd("if x; then\n  real-tool run\nfi\n}") == (["real-tool run"], []))
check("v0.1.58 F1: '!' negation carries the command (then the stoplist applies)",
      ds._scan_cmd("! grep -q pat f && add-thing run") == (["add-thing run"], [])
      and ds._scan_cmd("! deploy-check run")[0] == ["deploy-check run"])
check("v0.1.58 F1: assignment keywords drop whole (no value retention, no bare-name rows)",
      ds._scan_cmd("export CM_FLAG=on") == ([], []) and ds._scan_cmd("export PATH") == ([], [])
      and ds._scan_cmd("readonly FOO") == ([], []) and ds._scan_cmd("declare -A m") == ([], []))
check("v0.1.58 F1: 'export … && cmd' keeps only the carried command",
      ds._scan_cmd("export PATH=$PATH:/x && real-tool run") == (["real-tool run"], []))
check("v0.1.58 F1: env-manipulation heads drop (set -euo pipefail)",
      ds._scan_cmd("set -euo pipefail\nreal-tool run") == (["real-tool run"], []))
check("v0.1.58 F1: eval-of-substitution strips to nothing; exec carries a real command",
      ds._scan_cmd('eval "$(ssh-agent -s)"') == ([], [])
      and ds._scan_cmd("exec gunicorn-run app")[0] == ["gunicorn-run app"])
check("v0.1.58 F1: exec fd-plumbing drops (2>&1 / 3< file — guard + numeric screen)",
      ds._scan_cmd("exec 2>&1") == ([], []) and ds._scan_cmd("exec 3< file") == ([], []))
# (2) F2 — the structural interpreter rule (the v0.1.55 literal stoplist regenerated the false class:
# `.venv/bin/python -` ×204 measured live). Segment-token placement: the abs-path head case is the proof.
check("v0.1.58 F2: any-path/any-runner inline-body interpreters drop",
      ds._scan_cmd(".venv/bin/python - <<'PY'\nprint(1)\nPY") == ([], [])
      and ds._scan_cmd('.venv/bin/python -c "import x"') == ([], [])
      and ds._scan_cmd('python3.12 -c "import x"') == ([], [])
      and ds._scan_cmd("uv run python - <<'PY'\nprint(1)\nPY") == ([], [])
      and ds._scan_cmd("/usr/bin/python3 -c 'x'") == ([], [])
      and ds._scan_cmd("/usr/bin/env python3 -") == ([], []))
check("v0.1.58 F2: survivors keep their class (real invocations, and the -F - false-positive guard)",
      ds._scan_cmd("python3 tests/smoke.py")[0] == ["python3 tests/smoke.py"]
      and ds._scan_cmd(".venv/bin/python -m pytest -m unit")[0] == [".venv/bin/python -m pytest -m unit"]
      and ds._scan_cmd("git commit -q -F -")[0] == ["git commit -q -F -"])
check("v0.1.58 [3]: the eval/exec fd-guard fires on a REDIRECT, not a digit-NAMED tool (7z/2to3 survive)",
      ds._scan_cmd("exec 7z x archive.zip")[0] == ["7z x archive.zip"]
      and ds._scan_cmd("eval 2to3 -w src")[0] == ["2to3 -w src"]
      and ds._scan_cmd("exec 2>&1") == ([], []) and ds._scan_cmd("exec 3< file") == ([], []))
# (3) F3 — firewall-at-emission, end-to-end: flagged commands COUNT; a flagged-FIRST template UPGRADES to
# a clean sample once a clean occurrence exists (code-review [8]) but an ALWAYS-flagged one keeps the
# label; the transparency counter includes ALL-NOISE flagged commands (increment BEFORE the all-noise skip).
with _tf43.TemporaryDirectory() as _td58a:
    _h58 = Path(_td58a); _p58 = _h58 / "proj"; _p58.mkdir()
    _pr58 = _h58 / ".claude" / "projects" / es.slug_for(_p58); _pr58.mkdir(parents=True)
    _l58 = [
        _bl55("deploy-tool run --opt=AKIAIOSFODNN7EXAMPLE", "2026-07-01T10:00:00Z"),         # flagged FIRST
        _bl55("deploy-tool run --opt=redacted", "2026-07-01T11:00:00Z"),                     # clean → upgrades sample
        _bl55("vault-tool run --opt=AKIAIOSFODNN7EXAMPLE", "2026-07-01T12:00:00Z"),          # flagged (never clean)
        _bl55("vault-tool run --opt=AKIAJJJJODNN7EXAMPLE", "2026-07-01T13:00:00Z"),          # flagged again → stays label
        _bl55("export AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE", "2026-07-01T14:00:00Z"),  # flagged + ALL-NOISE
    ]
    (_pr58 / "s.jsonl").write_text("".join(_l58))
    _old58 = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_td58a)
    try:
        _r58 = ds.scan(_p58, "")
    finally:
        _os43.environ["HOME"] = _old58 if _old58 is not None else ""
    _rows58 = {r["template"]: r for r in _r58["recurring"]}
    check("v0.1.58 F3: flagged commands COUNT into their class (deploy ×2, vault ×2)",
          _rows58.get("deploy-tool run --opt", {}).get("count") == 2
          and _rows58.get("vault-tool run --opt", {}).get("count") == 2)
    check("v0.1.58 F3 [8]: a flagged-FIRST template UPGRADES to a clean sample once a clean one exists",
          _rows58["deploy-tool run --opt"]["sample"] == "deploy-tool run --opt=redacted")
    check("v0.1.58 F3: an ALWAYS-flagged template keeps the omission label (no clean occurrence to upgrade to)",
          _rows58["vault-tool run --opt"]["sample"] == ds._OMIT_SAMPLE)
    check("v0.1.58 F3: secrets_omitted counts ALL flagged incl. the all-noise export; commands includes them",
          _r58["scanned"]["secrets_omitted"] == 4 and _r58["scanned"]["commands"] == 5)
    check("v0.1.58 F3: no raw vendor secret anywhere in the JSON",
          "AKIA" not in _json43.dumps(_r58))
# choke-point NON-VACUOUS: a zero-width-SPLIT, letters-only blob survives tokenization (no digit, position 2)
# and is INVISIBLE to a raw _looks_secret probe — only _norm(tpl) fuses it. Proves the screen uses _norm ([1]).
_zwl58 = "aB" * 20                            # 40 mixed-case letters, no digit → survives the template transform
_zwlsplit58 = _zwl58[:20] + "​" + _zwl58[20:]
check("v0.1.58 F3/[1]: raw _looks_secret MISSES the zw-split blob (the divergence the screen must cover)",
      not es._looks_secret(f"deploy-tool {_zwlsplit58}"))
check("v0.1.58 F3/[1]: the choke-point screens it via _norm (rows AND chain endpoints)",
      ds._seg_template(f"deploy-tool {_zwlsplit58}") is None)
# (4) F4 — --into deterministic capture: sub-key merge, script-truth counts, judgment preserved/replaced.
_scan58 = {"window": "W58", "scanned": {"sessions": 2, "commands": 9, "days": 3, "secrets_omitted": 1},
           "recurring": [{"template": "t", "count": 2, "days": 1, "sample": ""}], "chains": []}
with _tf43.TemporaryDirectory() as _td58b:
    _seed58 = Path(_td58b) / "cycle.json"
    _seed58.write_text(_json43.dumps({"project": "p", "session": "s",
                                      "distill": {"verdict": "nothing: x fails leg", "n_recurring": 47}}))
    check("v0.1.58 --into: returns True on a well-formed seed", ds.inject_into(str(_seed58), _scan58, "", [], []))
    _aft58 = _json43.loads(_seed58.read_text())
    check("v0.1.58 --into: counts are script-truth (the impossible 47 → 1), verdict PRESERVED, other keys untouched",
          _aft58["distill"]["n_recurring"] == 1 and _aft58["distill"]["verdict"] == "nothing: x fails leg"
          and _aft58["distill"]["window"] == "W58" and _aft58["distill"]["secrets_omitted"] == 1
          and _aft58["project"] == "p" and _aft58["session"] == "s")
    ds.inject_into(str(_seed58), _scan58, "proposed X — declined", ["X"], [])
    ds.inject_into(str(_seed58), _scan58, "proposed X — declined", ["X"], [])   # idempotence: run twice
    _aft58b = _json43.loads(_seed58.read_text())
    check("v0.1.58 --into: provided flags REPLACE their keys (list = whole list); re-run is idempotent",
          _aft58b["distill"]["verdict"] == "proposed X — declined" and _aft58b["distill"]["proposed"] == ["X"])
    check("v0.1.58 --into: missing seed → False (stderr, never a crash)",
          ds.inject_into(str(Path(_td58b) / "nope.json"), _scan58, "", [], []) is False)
    (Path(_td58b) / "arr.json").write_text("[]")
    check("v0.1.58 --into: non-object seed root → False",
          ds.inject_into(str(Path(_td58b) / "arr.json"), _scan58, "", [], []) is False)
    # [0/1/2]: a PARTIAL scan dict (stale/pre-v0.1.58 — no secrets_omitted, no window) must NOT KeyError-crash;
    # the defensive .get() defaults keep the capture working (0 / "(all)").
    _seed58p = Path(_td58b) / "partial.json"; _seed58p.write_text(_json43.dumps({"project": "p"}))
    _partial58 = {"scanned": {"sessions": 1, "commands": 3}, "recurring": [], "chains": []}  # missing keys
    check("v0.1.58 [0/1/2]: inject_into tolerates a partial --from scan (no crash; defaults fill the gaps)",
          ds.inject_into(str(_seed58p), _partial58, "nothing: n/a", [], []) is True
          and _json43.loads(_seed58p.read_text())["distill"]["secrets_omitted"] == 0
          and _json43.loads(_seed58p.read_text())["distill"]["window"] == "(all)")
# (5) validator backstop + the caps cross-module pin (no runtime import cycle; smoke pins the mirror).
check("v0.1.58 validate: warns on an impossible count (the ×47 production mis-fill class)",
      any("exceeds the scanner cap" in w for w in ms.validate_cycle_record({"distill": {"n_recurring": 47}}))
      and any("exceeds the scanner cap" in w for w in ms.validate_cycle_record({"distill": {"n_chains": 21}})))
check("v0.1.58 validate: silent AT the caps and on non-numeric junk",
      not any("exceeds" in w for w in ms.validate_cycle_record({"distill": {"n_recurring": 40, "n_chains": 20}}))
      and not any("exceeds" in w for w in ms.validate_cycle_record({"distill": {"n_recurring": "junk"}})))
check("v0.1.58 caps cross-module pin (the mirror cannot drift)",
      ms._DISTILL_CAPS == (ds.MAX_RECUR_OUT, ds.MAX_CHAIN_OUT))
# (6) F7 — the per-line window: a fresh-mtime file's OLD-timestamp line is excluded from counts AND days.
with _tf43.TemporaryDirectory() as _td58c:
    _h58c = Path(_td58c); _p58c = _h58c / "proj"; _p58c.mkdir()
    _pr58c = _h58c / ".claude" / "projects" / es.slug_for(_p58c); _pr58c.mkdir(parents=True)
    (_pr58c / "s.jsonl").write_text(
        _bl55("ancient-tool run", "2026-01-01T10:00:00Z") + _bl55("fresh-tool run", "2026-07-01T10:00:00Z")
        + _bl55("fresh-tool run", "2026-07-02T10:00:00Z"))
    _old58c = _os43.environ.get("HOME"); _os43.environ["HOME"] = str(_td58c)
    try:
        _r58c = ds.scan(_p58c, "2026-06-01T00:00:00+00:00")
    finally:
        _os43.environ["HOME"] = _old58c if _old58c is not None else ""
    check("v0.1.58 F7: out-of-window lines excluded from commands, days, and the tally",
          _r58c["scanned"]["commands"] == 2 and _r58c["scanned"]["days"] == 2
          and [r["template"] for r in _r58c["recurring"]] == ["fresh-tool run"])
# (7) F8 — CLI honesty (subprocess, hermetic HOME): --since validation, dir warning, usage-error exits on
# bad/unknown/valueless flags (code-review [4]/[7]), judgment-without-into warning ([5]), inject-fail exit
# ([6]), --from single-scan ([10]), and --json --into stdout purity (injection summary on stderr).
with _tf43.TemporaryDirectory() as _td58d:
    _home58 = str(Path(_td58d) / "home"); Path(_home58).mkdir()
    _proj58 = str(Path(_td58d) / "proj"); Path(_proj58).mkdir()

    def _run58(*args: str) -> "tuple[str, str, int]":
        env = {**_os53.environ, "HOME": _home58}
        env.pop("CM_DREAM_ARC", None)
        p = _sp53.run([sys.executable, str(_scripts54 / "distill_scan.py"), *args],
                      capture_output=True, text=True, timeout=60, env=env)
        return p.stdout, p.stderr, p.returncode

    _so58, _se58, _rc58 = _run58(_proj58, "--since", "banana")
    check("v0.1.58 F8: garbage --since → exit 2 + stderr (never a silent drop-everything compare)",
          _rc58 == 2 and "--since expects an ISO timestamp" in _se58)
    _so58, _se58, _rc58 = _run58(_proj58, "--since", "2026-06-01T00:00:00+0000", "--json")
    check("v0.1.58 F8/[3]: a no-colon offset (date -u +%z form) is accepted, not version-skew-aborted",
          _rc58 == 0 and isinstance(_json43.loads(_so58), dict))
    _so58, _se58, _rc58 = _run58(str(Path(_td58d) / "no-such-dir"), "--json")
    check("v0.1.58 F8: nonexistent project dir → stderr warning, exit 0, zero counts (visible, recall-safe)",
          _rc58 == 0 and "does not exist" in _se58 and _json43.loads(_so58)["scanned"]["sessions"] == 0)
    _so58, _se58, _rc58 = _run58(_proj58, "--sicne", "2026-06-01", "--json")
    check("v0.1.58 F8/[7]: an unknown flag is a USAGE ERROR (exit 2), not a swallowed value → wrong scan",
          _rc58 == 2 and "unknown flag: --sicne" in _se58)
    _so58, _se58, _rc58 = _run58(_proj58, "--json", "--into")
    check("v0.1.58 F8/[4]: a trailing value-flag missing its value → exit 2 (not a mislabeled 'unknown flag')",
          _rc58 == 2 and "--into requires a value" in _se58)
    _so58, _se58, _rc58 = _run58(_proj58, "--json", "--verdict", "nothing: x")
    check("v0.1.58 F8/[5]: judgment flags WITHOUT --into → loud warning (the verdict would go nowhere)",
          _rc58 == 0 and "require --into" in _se58)
    _so58, _se58, _rc58 = _run58(_proj58, "--ascii", "--json")
    check("v0.1.58 F8: the visual flags do NOT misfire the unknown-flag error",
          _rc58 == 0 and "unknown flag" not in _se58)
    _seed58d = Path(_td58d) / "seed.json"
    _seed58d.write_text(_json43.dumps({"project": "p"}))
    _so58, _se58, _rc58 = _run58(_proj58, "--json", "--into", str(_seed58d), "--verdict", "nothing: n/a — empty corpus")
    check("v0.1.58 F8: --json --into keeps stdout pure (scan JSON) with the injection summary on stderr",
          _rc58 == 0 and isinstance(_json43.loads(_so58), dict) and "distill → injected" in _se58
          and _json43.loads(_seed58d.read_text())["distill"]["verdict"] == "nothing: n/a — empty corpus")
    _so58, _se58, _rc58 = _run58(_proj58, "--into", str(Path(_td58d) / "nope" / "seed.json"), "--verdict", "x")
    check("v0.1.58 F8/[6]: a failed injection (unwritable seed) → non-zero exit (capture loss is detectable)",
          _rc58 != 0)
    # [10] --from: inject a SAVED scan JSON without re-scanning (counts identical to the judged evidence)
    _fromjson58 = Path(_td58d) / "scan.json"
    _fromjson58.write_text(_json43.dumps(_scan58))            # the fixture scan dict from block (4)
    _seed58e = Path(_td58d) / "seed2.json"; _seed58e.write_text(_json43.dumps({"project": "p"}))
    _so58, _se58, _rc58 = _run58("--from", str(_fromjson58), "--into", str(_seed58e), "--verdict", "nothing: via --from")
    _blk58 = _json43.loads(_seed58e.read_text()).get("distill", {})
    check("v0.1.58 F8/[10]: --from injects the SAVED scan's counts (no re-scan) + the verdict",
          _rc58 == 0 and _blk58.get("n_recurring") == 1 and _blk58.get("window") == "W58"
          and _blk58.get("verdict") == "nothing: via --from")
    _so58, _se58, _rc58 = _run58("--from", str(Path(_td58d) / "missing.json"), "--into", str(_seed58e))
    check("v0.1.58 F8/[10]: --from on a missing/invalid scan file → exit 2",
          _rc58 == 2 and "--from" in _se58)
# (8) docs pins — the stale docstring claims are gone; the harness-map distill section exists.
check("v0.1.58 docstring pins: residuals re-stated honestly (no 'low-frequency' ||; nested-only $(); glue wording)",
      "low-frequency" not in (ds.__doc__ or "") and "inside a NESTED" in (ds.__doc__ or "")
      and "`&&`/newline/`;`-glued" in (ds.__doc__ or ""))
_hmap58 = (ROOT / "plugins" / "consolidate-memory" / "skills" / "consolidate-memory" / "references"
           / "harness-map.md").read_text(encoding="utf-8")
check("v0.1.58 harness-map pin: the distill section exists (was ZERO mentions)",
      "## Distill (the second vertical" in _hmap58 and "script-only" in _hmap58)

# ── v0.1.62: the debrief is ONE sign-off (WAKE) + the card — no second emoji'd lead line ─────────
# MEASURED 2026-07-04: WAKE's `☀️ … / ☀️ **Awake.**` was followed by a debrief lead line ALSO
# carrying "outcome + one functional emoji" (🌙) — read as a redundant third landing (☀️/☀️/🌙 in
# three lines). Both occurrences of the old instruction (the dream-arc rule + the Phase-5 step-7
# echo) are fixed; pin their absence + the new no-emoji-lead-line rule's presence.
check("v0.1.62 SKILL pin: the old 'outcome + one functional emoji' lead-line instruction is GONE",
      "outcome + one functional emoji" not in _sk55)
check("v0.1.62 SKILL pin: the no-emoji lead-line rule + the retired generic 🌙 marker are documented",
      "no emoji on the lead line" in _sk55 and "Retired: a bare" in _sk55)
check("v0.1.62 SKILL pin: both debrief-instruction sites (dream-arc + Phase-5 step 7) name the fix",
      "no emoji — WAKE already closed the dream" in _sk55 and "A measured defect" in _sk55)

# ── v0.1.63 (Phase A): usage instrumentation + hook/cliff telemetry (observe-only) ───────────────
# docs/index-usage-and-budget-ladder.spec.md. Pure-function + render + contract pins; NO behavior
# change is the phase's own invariant (no new gates — the ladder semantics are Phase B).
import json as _jsonA  # noqa: E402
import tempfile as _tfA  # noqa: E402

# (1) cross-module cap pin — the validator's backstop mirrors the producer (the _DISTILL_CAPS shape).
check("v0.1.63 caps cross-module pin: ms._USAGE_FACT_CAP == es._USAGE_FACT_CAP",
      ms._USAGE_FACT_CAP == es._USAGE_FACT_CAP)

# (2) split_dream_span — the PURE classifier: outside-span reads are ORGANIC, in-span are dream-
# procedure; no arc ⇒ all organic (a non-dream session); inter-arc gap over-excluded by design.
_spanA = [{"i": 1, "kind": "read", "stem": "a", "ts": "t1"},
          {"i": 5, "kind": "arc", "stem": "", "ts": "t2"},
          {"i": 7, "kind": "read", "stem": "b", "ts": "t3"},
          {"i": 9, "kind": "arc", "stem": "", "ts": "t4"},
          {"i": 12, "kind": "read", "stem": "c", "ts": "t5"}]
_orgA, _exclA = es.split_dream_span(_spanA)
check("v0.1.63 split_dream_span: before/after-span organic, in-span excluded (first..last arc)",
      [r["stem"] for r in _orgA] == ["a", "c"] and _exclA == 1)
_noarcA = [{"i": 3, "kind": "read", "stem": "x", "ts": ""}]
check("v0.1.63 split_dream_span: no arc ⇒ all reads organic, 0 excluded",
      es.split_dream_span(list(_noarcA)) == (_noarcA, 0))

# (3) _recall_items — stream fixture: fact Reads collected; MEMORY.md / archive stems / foreign paths
# / nested paths never counted; only a Bash-tool_use CM_DREAM_ARC command is an arc (prose mentions
# must not widen the span — the strict spec rule).
with _tfA.TemporaryDirectory() as _tdA:
    _trA = Path(_tdA) / "s.jsonl"
    _storeA = "/home/u/.claude/projects/x/memory/"

    def _evA(name: str, inp: dict) -> str:
        return _jsonA.dumps({"timestamp": "2026-07-04T00:00:00Z",
                             "message": {"role": "assistant",
                                         "content": [{"type": "tool_use", "name": name, "input": inp}]}})

    _trA.write_text("\n".join([
        _evA("Read", {"file_path": _storeA + "alpha.md"}),                      # organic (before arc)
        _jsonA.dumps({"timestamp": "2026-07-04T00:00:00Z",                       # PROSE mention — not an arc
                      "message": {"role": "user", "content": [{"type": "text", "text": "CM_DREAM_ARC docs"}]}}),
        _evA("Bash", {"command": "CM_DREAM_ARC=1 python3 x.py"}),               # arc start
        _evA("Read", {"file_path": _storeA + "beta.md"}),                       # dream-procedure
        _evA("Bash", {"command": "CM_DREAM_ARC=1 python3 y.py"}),               # arc end
        _evA("Read", {"file_path": _storeA + "gamma.md"}),                      # organic (after arc)
        _evA("Read", {"file_path": _storeA + "MEMORY.md"}),                     # index — never a fact recall
        _evA("Read", {"file_path": _storeA + "SHIPPED.md"}),                    # archive stem — excluded
        _evA("Read", {"file_path": _storeA + "sub/dir.md"}),                    # nested — not a store fact
        _evA("Read", {"file_path": "/elsewhere/notes.md"}),                     # foreign path
    ]) + "\n")
    _itemsA = es._recall_items(_trA, _storeA, "", frozenset({"SHIPPED"}))
    _orgA2, _exclA2 = es.split_dream_span(_itemsA)
    check("v0.1.63 _recall_items+span: organic={alpha,gamma}, 1 in-span excluded; index/archive/nested/foreign never counted",
          sorted(r["stem"] for r in _orgA2) == ["alpha", "gamma"] and _exclA2 == 1)
    # per-line since filter: everything stamped ≤ since drops (transcripts straddle the marker).
    check("v0.1.63 _recall_items: per-line since filter drops in-marker lines",
          es._recall_items(_trA, _storeA, "2026-07-05T00:00:00Z", frozenset()) == [])
    # cross-project audit: a dream's scripted Bash line that LOST the env prefix must still
    # open the arc span — the raw-line pre-filter now admits the plugin-scripts signature, so
    # the dream-procedure Read after it is excluded, not counted as organic evidence.
    _trW = Path(_tdA) / "widened.jsonl"
    _trW.write_text("\n".join([
        _evA("Read", {"file_path": _storeA + "alpha.md"}),                     # organic
        _evA("Bash", {"command": "python3 /home/u/plugins/consolidate-memory/scripts/memory_status.py --json"}),  # arc (no env prefix)
        _evA("Read", {"file_path": _storeA + "beta.md"}),                      # dream-procedure
        _evA("Bash", {"command": "CM_DREAM_ARC=1 python3 y.py"}),              # arc end
        _evA("Read", {"file_path": _storeA + "gamma.md"}),                     # organic (after arc)
    ]) + "\n")
    _orgW, _exclW = es.split_dream_span(es._recall_items(_trW, _storeA, "", frozenset({"SHIPPED"})))
    check("cross-project audit: a prefix-less dream Bash call still opens the arc span "
          "(organic={alpha,gamma}, beta excluded)",
          sorted(r["stem"] for r in _orgW) == ["alpha", "gamma"] and _exclW == 1)
    # (3b) inject_usage — wholesale script-truth assignment; a bad seed FAILS LOUD (False), never silent.
    _seedA = Path(_tdA) / "seed.json"
    _seedA.write_text(_jsonA.dumps({"project": "p"}))
    _blockA = {"window": "w", "transcripts": 1, "dream_excluded": 1, "reads": 2, "facts_read": 2,
               "per_fact": [{"name": "alpha", "reads": 1, "last": "t"}]}
    check("v0.1.63 inject_usage: injects the usage block wholesale into the seed",
          es.inject_usage(str(_seedA), _blockA) is True
          and _jsonA.loads(_seedA.read_text())["usage"]["reads"] == 2)
    check("v0.1.63 inject_usage: missing seed → False (fails loud, never a silent drop)",
          es.inject_usage(str(Path(_tdA) / "nope.json"), _blockA) is False)

# (4) hook_stats — only POINTER lines are measured; expected values derived from est_tokens (no magic).
_leanA = "- [lean](lean.md) — ok"
_fatA = "- [fat](fat.md) — " + "x" * 300
_fhA, _hmA, _offA = ms.hook_stats("# Memory Index\n" + _leanA + "\n" + _fatA + "\nprose, not a pointer\n")
check("v0.1.63 hook_stats: fat POINTER lines counted, header/prose ignored, offenders fattest-first",
      _fhA == 1 and _hmA == ms.est_tokens(_fatA) and _offA[0][1] == "fat")
check("v0.1.63 hook_stats: empty/pointer-free text → (0, 0, [])", ms.hook_stats("") == (0, 0, []))

# (5) cliff_pct — the BINDING native axis wins; exact units (the 2026-07-04 live store = 24%).
check("v0.1.63 cliff_pct: bytes-bound (6138 B / 27 ln → 24%)", ms.cliff_pct(6138, 27) == 24)
check("v0.1.63 cliff_pct: lines-bound (1000 B / 150 ln → 75%)", ms.cliff_pct(1000, 150) == 75)
check("v0.1.63 cliff_pct: at the red rung (20480 B → 80%)", ms.cliff_pct(20480, 100) == 80)

# (6) validator backstop — impossible per_fact length warns; capped list + junk shapes stay sane.
check("v0.1.63 validate: usage.per_fact over the cap warns (impossible from a capped scan)",
      any("usage.per_fact exceeds" in w for w in ms.validate_cycle_record(
          {"usage": {"per_fact": [{"name": str(i)} for i in range(ms._USAGE_FACT_CAP + 1)]}})))
check("v0.1.63 validate: non-dict usage warns; a capped per_fact is quiet; non-list per_fact warns",
      any("usage is not a dict" in w for w in ms.validate_cycle_record({"usage": []}))
      and not ms.validate_cycle_record({"usage": {"per_fact": [{"name": "a"}]}})
      and any("usage.per_fact is not a list" in w for w in ms.validate_cycle_record({"usage": {"per_fact": 3}})))

# (7) render — USAGE section on a usage-bearing record; ABSENT on a legacy record (additive-only);
# gauge tail carries cliff/hooks only when the keys exist.
_urecA = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
                               "usage": {"window": "w", "transcripts": 2, "dream_excluded": 4,
                                         "reads": 7, "facts_read": 3,
                                         "per_fact": [{"name": "gh-pr-edit", "reads": 4, "last": "t"}]}})
_uoutA = rd.render(_urecA)
check("v0.1.63 render: USAGE section renders counts + top fact", "USAGE" in _uoutA and "gh-pr-edit" in _uoutA
      and "7 read(s) over 3 fact(s)" in _uoutA)
check("v0.1.63 render: USAGE absent on a legacy record (no usage key)",
      "USAGE" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": []})))
_gidxA = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
                               "budget": {"index": {"after_tokens": 100, "budget_tokens": 1500,
                                                    "cliff_pct": 24, "fat_hooks": 8, "hook_max_tokens": 141}}})
_goutA = rd.render(_gidxA)
check("v0.1.63 render: index gauge tail carries cliff % + fat-hook count (max ≈ tok)",
      "cliff 24%" in _goutA and "hooks 8>" in _goutA and "max ≈141" in _goutA)
check("v0.1.63 render: legacy index gauge has no cliff/hooks tail (keys absent)",
      "cliff" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
                                                     "budget": {"index": {"after_tokens": 100, "budget_tokens": 1500}}})))

# (8) cm log — READS column: usage.reads renders; legacy rows show an em-dash (0 ≠ absent).
check("v0.1.63 cm log: READS column from usage.reads; em-dash on a legacy record",
      rlog._row({"usage": {"reads": 7}})[5] == "7" and rlog._row({})[5] == "—"
      and rlog._HEAD[5] == "READS")

# ── v0.1.64: WAKE is ONE line, full stop — no trailing bolded "Awake." (a SECOND, adjacent
# defect to v0.1.62's, caught live from the RENDERED HTML archive: WAKE's own two lines
# duplicated each other, one layer under the fix v0.1.62 shipped). ─────────────────────────
_sk64 = _skill_md.read_text(encoding="utf-8")
check("v0.1.64 SKILL pin: the WAKE beat-table row retires the trailing 'Awake.' line as a live instruction",
      "no trailing bolded" in _sk64 and 'then `☀️ **Awake.**` on its own line, then the plain debrief' not in _sk64)
check("v0.1.64 SKILL pin: the debrief section documents the second defect + the fix",
      "A second, adjacent defect" in _sk64 and "no trailing bolded line, ever" in _sk64)
check("v0.1.64 SKILL pin: the Phase-5 step-7 WAKE instruction echoes the fix (no drift between the two sites)",
      "no trailing bolded \"Awake.\"" in _sk64.split("Then WAKE — and only then debrief")[1][:300])
_rh64_src = (ROOT / "plugins" / "consolidate-memory" / "scripts" / "render_html.py").read_text(encoding="utf-8")
check("v0.1.64 render_html cue source: the dream_cue text itself no longer instructs a trailing Awake line",
      "full stop (v0.1.64: no" in _rh64_src
      and "trailing 'Awake.' line), then the plain debrief" in _rh64_src
      and "then '☀️ **Awake.**'" not in _rh64_src)

# ── v0.1.66 (Phase B): the HARD CEILING — a second, independent signal beside the target ─────────
# docs/index-usage-and-budget-ladder.spec.md §Phase B (the post-3-lens-gate design). Invariants pinned
# here: (a) the ceiling is ONE canonical est-token constant; (b) the M1/evict re-key is CALL-SITE-
# passed — the v0.1.38 target-default pins above stay byte-identical; (c) over_ceiling is a SIBLING of
# required, NEVER entering the standing-justify computation (SJ-independence — the invariant whose
# violation the spec gate caught in the original design); (d) renders are additive + legacy-safe.
import contextlib as _ctxB  # noqa: E402
import io as _ioB  # noqa: E402
import json as _jsonB  # noqa: E402
import os as _osB  # noqa: E402
import tempfile as _tfB  # noqa: E402

# (1) constant derivation + the render_html mirror
check("v0.1.66 ceiling: ONE canonical est-token threshold from the native byte cap (0.6 × 25KB/4 = 3840, > target)",
      ms.INDEX_CEILING_TOKENS == round(ms.INDEX_CEILING_FRACTION * ms.NATIVE_INDEX_CAP_BYTES / 4) == 3840
      and ms.INDEX_CEILING_TOKENS > ms.INDEX_TOKEN_BUDGET)
check("v0.1.66 ceiling: render_html references ms.INDEX_CEILING_TOKENS directly (a live reference, not a hardcoded copy)",
      rhtml.INDEX_CEILING_TOKENS == ms.INDEX_CEILING_TOKENS)

# (2) _would_net_grow at the ceiling — the NEW call-site behavior (the v0.1.38 target-default pins above
# are UNCHANGED calls at the UNCHANGED default; these pass the ceiling explicitly, as run() now does).
check("v0.1.66 M1: an over-TARGET (amber) store RECEIVES a pull under the ceiling threshold",
      sg._would_net_grow(1600, 50, False, budget=ms.INDEX_CEILING_TOKENS) is False)
check("v0.1.66 M1: a pull that would cross the ceiling HOLDS",
      sg._would_net_grow(ms.INDEX_CEILING_TOKENS - 40, 50, False, budget=ms.INDEX_CEILING_TOKENS) is True)
check("v0.1.66 M1: exactly-to-ceiling is allowed (boundary: ==, not >)",
      sg._would_net_grow(ms.INDEX_CEILING_TOKENS - 50, 50, False, budget=ms.INDEX_CEILING_TOKENS) is False)
check("v0.1.66 M1: --allow-net-grow still overrides at the ceiling",
      sg._would_net_grow(ms.INDEX_CEILING_TOKENS + 500, 50, True, budget=ms.INDEX_CEILING_TOKENS) is False)

# (3) the write-time fat-hook lint (pure)
check("v0.1.66 hook lint: a fat pointer warns naming the CANONICAL's description; a lean one is silent",
      "tighten the CANONICAL" in (sg._fat_hook_warning("- [fat](fat.md) — " + "x" * 300, "fat") or "")
      and sg._fat_hook_warning("- [ok](ok.md) — lean", "ok") is None)
check("R128-8: local fat-hook names the native fact, not ~/.claude/memory/",
      "LOCAL" in (sg._fat_hook_warning("- [fat](fat.md) — " + "x" * 300, "fat",
                                       source_kind="local",
                                       source_path="native/fat.md") or "")
      and "~/.claude/memory/" not in (sg._fat_hook_warning("- [fat](fat.md) — " + "x" * 300, "fat",
                                                           source_kind="local") or ""))

# (4) seeding — over_ceiling is a SIBLING of required; standing-justify NEVER hides it
with _tfB.TemporaryDirectory() as _tdB:
    _homeB = Path(_tdB)
    _projB = (_homeB / "projects-src" / "ceil").resolve(); _projB.mkdir(parents=True)
    _stB = _homeB / ".claude" / "projects" / ms.slug_for(_projB) / "memory"; _stB.mkdir(parents=True)
    (_stB / "f.md").write_text("---\nname: f\nmetadata:\n  node_type: memory\n  type: project\n---\nbody\n",
                               encoding="utf-8")
    _oldHomeB = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_homeB)
    try:
        def _ctxAt(tokens: int) -> dict:
            (_stB / "MEMORY.md").write_text("# Memory Index\n- [f](f.md) — " + "h" * (tokens * 4),
                                            encoding="utf-8")
            return ms.build_context(_projB)
        _amberB = _ctxAt(1600)["remediation"]
        check("v0.1.66 seed: over-TARGET-under-ceiling → required True (target gate UNTOUCHED) · over_ceiling False",
              _amberB.get("required") is True and _amberB.get("over_ceiling") is False)
        _ceilB = _ctxAt(4000)
        check("v0.1.66 seed: past-the-ceiling → over_ceiling True BESIDE the unchanged target gate",
              _ceilB["remediation"].get("over_ceiling") is True and _ceilB["remediation"].get("required") is True)
        _idxTokB = _ceilB["index_lb"][2]
        (_stB / ".consolidation-state.json").write_text(_jsonB.dumps(
            {"commit": "x", "timestamp": "2026-07-01T00:00:00Z",
             "standing_justify": {"facts": 1, "index_tokens": _idxTokB}}), encoding="utf-8")
        _sjB = ms.build_context(_projB)
        check("v0.1.66 seed: standing-justify suppresses `required` but NEVER over_ceiling (the sibling-signal invariant)",
              _sjB["remediation"].get("standing_justified") is True
              and _sjB["remediation"].get("required") is False
              and _sjB["remediation"].get("over_ceiling") is True)
        _seedB = ms.seed_record(_sjB)
        check("v0.1.66 seed_record: over_ceiling relayed through the SJ branch + ceiling_tokens on budget.index",
              _seedB["remediation"]["over_ceiling"] is True
              and _seedB["budget"]["index"]["ceiling_tokens"] == ms.INDEX_CEILING_TOKENS)
        check("v0.1.66 seed: an under-target store carries NO remediation block (healthy stays keyless)",
              _ctxAt(300)["remediation"] == {})
    finally:
        if _oldHomeB is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldHomeB

# (5) renderers — additive red flag; suppression never hides it; False/legacy → byte-safe absence
_ceilRecB = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
    "budget": {"index": {"after_tokens": 3900, "budget_tokens": 1500, "over": True, "ceiling_tokens": 3840}},
    "remediation": {"required": True, "lever": "justify", "candidates_surfaced": 0,
                    "projected_index": 3900, "over_ceiling": True}})
_ceilOutB = rd.render(_ceilRecB)
check("v0.1.66 render: gauge AND panel carry the HARD CEILING flag on an over-ceiling record",
      _ceilOutB.count("HARD CEILING") >= 2 and "M1 holds" in _ceilOutB)
_sjOutB = rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
    "remediation": {"required": False, "standing_justified": True, "baseline_facts": 9, "over_ceiling": True}}))
check("v0.1.66 render: standing-justify does NOT hide the ceiling line (suppressed branch renders it too)",
      "HARD CEILING" in _sjOutB and "STANDING-JUSTIFIED" in _sjOutB)
check("v0.1.66 render: over_ceiling False and legacy (no key) both render NO ceiling flag",
      "CEILING" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
          "remediation": {"required": True, "lever": "prune", "candidates_surfaced": 1,
                          "projected_index": 100, "over_ceiling": False}}))
      and "CEILING" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {},
          "entries": [], "budget": {"index": {"after_tokens": 1504, "budget_tokens": 1500, "over": True}}})))

# (6) the run() call-site re-key — the actual behavior change, end to end (fixtured GLOBAL + HOME)
with _tfB.TemporaryDirectory() as _tdB2:
    _homeB2 = Path(_tdB2)
    _projB2 = (_homeB2 / "src" / "amberproj").resolve(); _projB2.mkdir(parents=True)
    _stB2 = _homeB2 / ".claude" / "projects" / ms.slug_for(_projB2) / "memory"; _stB2.mkdir(parents=True)
    _glB2 = _homeB2 / "global-mem"; _glB2.mkdir(parents=True)
    (_glB2 / "gfact.md").write_text(
        "---\nname: gfact\ndescription: \"a global lesson\"\nmetadata:\n  node_type: memory\n"
        "  scope: user-global\n  type: feedback\n---\nbody\n", encoding="utf-8")
    _oldHomeB2 = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_homeB2)
    _oldGlobalB2 = sg.GLOBAL
    sg.GLOBAL = _glB2
    try:
        (_stB2 / "MEMORY.md").write_text("# Memory Index\n- [f](f.md) — " + "h" * 6400, encoding="utf-8")
        _enroll_personal(_projB2)
        _buf1B = _ioB.StringIO()
        with _ctxB.redirect_stdout(_buf1B):
            sg.run(_projB2, pull=True)
        check("v0.1.66 run(): an over-TARGET (amber ≈1600t) store RECEIVES the pull — THE Phase-B behavior change",
              "pulled 1 new" in _buf1B.getvalue() and (_stB2 / "gfact.md").exists())
        (_stB2 / "gfact.md").unlink(missing_ok=True)
        (_stB2 / "MEMORY.md").write_text("# Memory Index\n- [f](f.md) — " + "h" * 15600, encoding="utf-8")
        _buf2B = _ioB.StringIO()
        with _ctxB.redirect_stdout(_buf2B):
            sg.run(_projB2, pull=True)
        check("v0.1.66 run(): a past-the-CEILING (≈3900t) store HOLDS the pull",
              "held 1" in _buf2B.getvalue() and not (_stB2 / "gfact.md").exists())
    finally:
        sg.GLOBAL = _oldGlobalB2
        if _oldHomeB2 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldHomeB2

# (7) fat-hook RESULT-line accounting on a STALE-mirror refresh — a max-effort code-review workflow
# finding (2026-07-04): the outer loop discarded _ensure_index_pointer's return value and unconditionally
# recounted `fat`, so a body-only canonical edit (description/scope unchanged → the derived pointer line
# is byte-identical → _ensure_index_pointer correctly NO-OPS, printing no stderr lint) still incremented
# `fat` on the SECOND pull, making the RESULT line claim a fat hook was "written" a second time with no
# accompanying stderr line to explain why. Fixed: `fat` counts only when the pointer was ACTUALLY written.
with _tfB.TemporaryDirectory() as _tdB3:
    _homeB3 = Path(_tdB3)
    _projB3 = (_homeB3 / "src" / "fatproj").resolve(); _projB3.mkdir(parents=True)
    _stB3 = _homeB3 / ".claude" / "projects" / ms.slug_for(_projB3) / "memory"; _stB3.mkdir(parents=True)
    _glB3 = _homeB3 / "global-mem"; _glB3.mkdir(parents=True)
    # _pointer_line truncates the DESCRIPTION hook to 88 chars — a realistic description alone can't cross
    # HOOK_TOKEN_WARN (60 est tok; the name occurs TWICE in `[name](name.md)`, so an unusually long NAME is
    # what actually crosses it here — confirmed empirically before picking this length).
    _fatName = "g" * 70
    _fatDesc = "x" * 100
    (_glB3 / f"{_fatName}.md").write_text(
        f'---\nname: {_fatName}\ndescription: "{_fatDesc}"\nmetadata:\n  node_type: memory\n'
        "  scope: user-global\n  type: feedback\n---\nbody v1\n", encoding="utf-8")
    _oldHomeB3 = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_homeB3)
    _oldGlobalB3 = sg.GLOBAL
    sg.GLOBAL = _glB3
    try:
        (_stB3 / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
        _enroll_personal(_projB3)
        _buf3aB = _ioB.StringIO()
        with _ctxB.redirect_stdout(_buf3aB), _ctxB.redirect_stderr(_ioB.StringIO()) as _err3aB:
            sg.run(_projB3, pull=True)
        check("v0.1.66 fat-hook accounting: a genuinely NEW fat pointer counts + lints on the pull that writes it",
              "fat hook(s)" in _buf3aB.getvalue() and f"fat hook: '{_fatName}'" in _err3aB.getvalue())
        # Edit the CANONICAL's BODY only (frontmatter/description unchanged) → the mirror goes STALE, but
        # the derived pointer line is byte-identical, so _ensure_index_pointer must no-op on refresh.
        (_glB3 / f"{_fatName}.md").write_text(
            f'---\nname: {_fatName}\ndescription: "{_fatDesc}"\nmetadata:\n  node_type: memory\n'
            "  scope: user-global\n  type: feedback\n---\nbody v2, changed\n", encoding="utf-8")
        _buf3bB = _ioB.StringIO()
        with _ctxB.redirect_stdout(_buf3bB), _ctxB.redirect_stderr(_ioB.StringIO()) as _err3bB:
            sg.run(_projB3, pull=True)
        check("v0.1.66 fat-hook accounting: a STALE-mirror body-only refresh (pointer unchanged) does NOT recount `fat`",
              "refreshed 1" in _buf3bB.getvalue() and "fat hook(s)" not in _buf3bB.getvalue()
              and "fat hook:" not in _err3bB.getvalue())
    finally:
        sg.GLOBAL = _oldGlobalB3
        if _oldHomeB3 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldHomeB3

# ── v0.1.67 (Phase C): the utility policy — demotion triage · miss loop · fleet utility ──────────
# docs/index-usage-and-budget-ladder.spec.md §Phase C (the post-code-review-skill-gate design).
# Invariants pinned: (a) _parse_ts relocated UNCHANGED — one function object across all three modules;
# (b) the 20→40 cap bump landed on BOTH sides; (c) reads merge from EVERY usage block while only
# full-fidelity parseable windows are PROBATIVE (the anti-conservative-draft fix); (d) per-FACT window
# counting (no span latch — a new fact accrues eligibility as new windows accrue); (e) every evidence-
# gate leg vetoes independently; (f) misses derive from the UNCAPPED tally and tier is judged at
# WINDOW START via --before; (g) inject_usage strikes just-read stems deterministically; (h) renders
# are additive + legacy-safe; (i) --utility attributes only through mirrors and never writes.
import hashlib as _hlC  # noqa: E402

# (1) relocation + cap pins
check("v0.1.67 _parse_ts relocation: ONE function object across ms/es/ds (the single-parser rule survives)",
      es._parse_ts is ms._parse_ts and ds._parse_ts is ms._parse_ts)
check("v0.1.67 _parse_ts behavior unchanged: bare Z + no-colon offset both parse to UTC instants",
      ms._parse_ts("2026-01-01T00:00:00Z") is not None
      and ms._parse_ts("2026-01-01T01:00:00+0100") == ms._parse_ts("2026-01-01T00:00:00Z")
      and ms._parse_ts("(no marker — all transcripts)") is None and ms._parse_ts("") is None)
check("v0.1.67 cap bump: _USAGE_FACT_CAP is 40 on BOTH sides (producer + validator mirror move together)",
      ms._USAGE_FACT_CAP == es._USAGE_FACT_CAP == 40)
check("v0.1.67 sg: --utility is a cued Phase-5 mode (joins --gc/--tokens)", "--utility" in sg._CUED_MODES)
check("v0.1.67 fleet-tax advisory: a positive documented constant above today's measured Σ (3283)",
      isinstance(sg.GLOBAL_FLEET_TAX_ADVISORY, int) and sg.GLOBAL_FLEET_TAX_ADVISORY > 3283)

# (2) iter_cycle_log + the read_history delegation (the shared-reader single-source rule)
with _tfB.TemporaryDirectory() as _tdC:
    _logC = Path(_tdC) / ".consolidation-log.jsonl"
    _logC.write_text('{"a": 1}\nnot json\n\n42\n{"b": 2}\n', encoding="utf-8")
    check("v0.1.67 iter_cycle_log: malformed/blank skipped, order + non-dict values kept, tail bounds",
          ms.iter_cycle_log(_logC) == [{"a": 1}, 42, {"b": 2}]
          and ms.iter_cycle_log(_logC, tail=1) == [{"b": 2}]
          and ms.iter_cycle_log(Path(_tdC) / "missing.jsonl") == [])
    check("v0.1.67 read_history delegates to iter_cycle_log (same output, non-dict lines included)",
          rhtml.read_history(Path(_tdC)) == ms.iter_cycle_log(_logC))

# (3) usage_history — G-C1: reads merge from EVERY block; only full+parseable windows are probative
def _uwC(window: str, tx: int, facts_read: int, per_fact: list, misses: "list | None" = None) -> str:
    u: dict = {"window": window, "transcripts": tx, "dream_excluded": 0,
               "reads": sum(f.get("reads", 0) for f in per_fact), "facts_read": facts_read,
               "per_fact": per_fact}
    if misses is not None:
        u["misses"] = misses
    return _jsonB.dumps({"usage": u})

with _tfB.TemporaryDirectory() as _tdC1:
    _amC1 = Path(_tdC1)
    (_amC1 / ".consolidation-log.jsonl").write_text("\n".join([
        _uwC("2026-01-01T00:00:00Z..2026-01-02T00:00:00Z", 2, 1,
             [{"name": "a", "reads": 2, "last": "2026-01-01T12:00:00Z"}], misses=["m1"]),
        _uwC("2026-01-02T00:00:00Z..2026-01-03T00:00:00Z", 0, 0, []),                       # empty window
        _uwC("2026-01-03T00:00:00Z..2026-01-04T00:00:00Z", 1, 3,
             [{"name": "b", "reads": 5, "last": "2026-01-03T05:00:00Z"}]),                  # cap-TRUNCATED
        _uwC("(no marker — all transcripts)..2026-01-05T00:00:00Z", 1, 1,
             [{"name": "a", "reads": 1, "last": "2026-01-04T00:00:00+01:00"}], misses=["m2"]),  # unplaceable
        "junk line",
    ]) + "\n", encoding="utf-8")
    _hC1 = ms.usage_history(_amC1)
    _dtC1 = ms._parse_ts("2026-01-01T00:00:00Z")
    check("v0.1.67 usage_history: only the full+parseable window is PROBATIVE (windows_full == 1)",
          _hC1["windows_full"] == 1 and len(_hC1["window_starts"]) == 1
          and _dtC1 is not None and _hC1["window_starts"][0] == _dtC1.timestamp())
    check("v0.1.67 usage_history: reads MERGE from every block — truncated + unplaceable included (a=3, b=5)",
          _hC1["per_fact"]["a"]["reads"] == 3 and _hC1["per_fact"]["b"]["reads"] == 5)
    check("v0.1.67 usage_history: `last` merges by parsed-EPOCH max (the +01:00 stamp is the later instant)",
          _hC1["per_fact"]["a"]["last"] == "2026-01-04T00:00:00+01:00")
    check("v0.1.67 usage_history: miss_stems unions across ALL blocks (a caught miss never rotates away)",
          _hC1["miss_stems"] == ["m1", "m2"])
    check("v0.1.67 usage_history: missing store/log → clean zero-state",
          ms.usage_history(Path(_tdC1) / "nope") == {"windows_full": 0, "window_starts": [],
                                                     "per_fact": {}, "miss_stems": [], "mention_stems": []})

# (4) _demotion_justify — the guarded reader (malformed does NOT suppress; the _standing_baseline direction)
check("v0.1.67 _demotion_justify: well-formed kept; non-dict/bool/str-windows entries DROPPED (fail open to surface)",
      ms._demotion_justify({"good": {"windows": 3}, "b1": "junk", "b2": {"windows": True},
                            "b3": {"windows": "3"}, "b4": None})
      == {"good": {"windows": 3, "at": None}}
      and ms._demotion_justify("garbage") == {} and ms._demotion_justify(None) == {})
check("O1: _demotion_justify keeps parseable at (dual-read input)",
      ms._demotion_justify({"g": {"windows": 11, "at": "2026-09-01T21:23:45.446Z"}})
      == {"g": {"windows": 11, "at": "2026-09-01T21:23:45.446Z"}})

# (5) demotion_candidates — every evidence-gate leg, the rank, the cap
_epC = [ms._parse_ts(t) for t in ("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "2026-03-01T00:00:00Z")]
assert all(d is not None for d in _epC)
_e1C, _e2C, _e3C = (d.timestamp() for d in _epC if d is not None)
with _tfB.TemporaryDirectory() as _tdC2:
    _stC2 = Path(_tdC2)

    def _factC(stem: str, desc: str, mtime: float, mirror: bool = False, body: str = "body") -> Path:
        p = _stC2 / f"{stem}.md"
        gref = f"  global_ref: {stem}\n" if mirror else ""
        p.write_text(f'---\nname: {stem}\ndescription: "{desc}"\nmetadata:\n{gref}'
                     f"  node_type: memory\n  type: reference\n---\n{body}\n", encoding="utf-8")
        _osB.utime(p, (mtime, mtime))
        return p

    _ffC = [
        _factC("dead-ref", "an old pointer to a dashboard nobody opens", 1000.0),
        _factC("fresh-fact", "a recently edited reference note", _e2C + 60),        # zrw = 1 → not yet
        _factC("read-fact", "a reference that was actually recalled", 1000.0),
        _factC("lesson-fact", "never retry the flaky endpoint without backoff", 1000.0),   # KEEP veto
        _factC("missed-fact", "a reference once mis-demoted", 1000.0),
        _factC("justified-fact", "a reference the human vouched for", 1000.0),
        _factC("mirror-fact", "a replicated global reference", 1000.0, mirror=True),
        _factC("linker", "a fact whose body links to the dead one for depth", 1000.0,
               body="see [[dead-ref]] for the old dashboard"),
        _factC("dead-ref-twin", "an old pointer to a dashboard nobody opens at all", 1000.0),
    ]
    _idxC = {"dead-ref", "fresh-fact", "read-fact", "lesson-fact", "missed-fact",
             "justified-fact", "mirror-fact", "linker", "dead-ref-twin"}
    _itxC = "# Memory Index\n" + "\n".join(
        f"- [{s}]({s}.md) — " + "h" * n for s, n in
        [("dead-ref", 200), ("fresh-fact", 40), ("read-fact", 40), ("lesson-fact", 40),
         ("missed-fact", 40), ("justified-fact", 40), ("mirror-fact", 40), ("linker", 300),
         ("dead-ref-twin", 100)]) + "\n"
    _histC = {"windows_full": 3, "window_starts": [_e1C, _e2C, _e3C],
              "per_fact": {"read-fact": {"reads": 4, "last": "2026-01-15T00:00:00Z"}},
              "miss_stems": ["missed-fact"]}
    _dcC = ms.demotion_candidates(_ffC, _idxC, _histC, _itxC, justify={"justified-fact": 1})
    _stemsC = [c["stem"] for c in _dcC["candidates"]]
    check("v0.1.67 gate: eligible = 0-read, ≥3-window, indexed, non-mirror, non-KEEP, un-missed, un-justified",
          _dcC["eligible"] == 3 and set(_stemsC) == {"dead-ref", "linker", "dead-ref-twin"})
    check("v0.1.67 gate vetoes tally independently (read · keep · justified · missed)",
          _dcC["vetoed_read"] == 1 and _dcC["vetoed_keep"] == 1
          and _dcC["vetoed_justified"] == 1 and _dcC["vetoed_missed"] == 1)
    check("v0.1.67 gate: a fact edited mid-span counts only the windows it predates (fresh ⇒ not yet, not vetoed)",
          "fresh-fact" not in _stemsC and _dcC["eligible"] + sum(
              _dcC[k] for k in ("vetoed_read", "vetoed_keep", "vetoed_justified", "vetoed_missed")) == 7)
    check("v0.1.67 rank: hook-cost desc (linker 300h > dead-ref 200h > twin 100h)",
          _stemsC == ["linker", "dead-ref", "dead-ref-twin"])
    _c0C = _dcC["candidates"][1]                                   # dead-ref — wikilinked from linker
    check("v0.1.67 evidence: indegree counts the [[wikilink]] from another fact",
          _c0C["indegree"] == 1 and _dcC["candidates"][0]["indegree"] == 0)
    check("v0.1.67 evidence: nearest-description similarity ≥ 0.6 surfaces as merge evidence (deterministic pair)",
          _c0C.get("similar") == "dead-ref-twin" and _c0C.get("ratio", 0) >= 0.6)
    check("v0.1.67 evidence: zero_read_windows counts per-fact probative windows (3 for a pre-span fact)",
          _c0C["zero_read_windows"] == 3)
    check("v0.1.67 dormant short-circuit: < 3 probative windows ⇒ eligible 0, no candidates, no vetoes",
          ms.demotion_candidates(_ffC, _idxC, {**_histC, "windows_full": 2}, _itxC)
          == {"windows_full": 2, "eligible": 0, "candidates": [],
              "vetoed_read": 0, "vetoed_keep": 0, "vetoed_justified": 0, "vetoed_missed": 0,
              "justified_live": []})
    _h8C = {**_histC, "windows_full": 8, "window_starts": [_e1C] * 8, "miss_stems": []}
    check("v0.1.67 justify re-fire boundary: suppressed while jw+REFIRE > wf, re-surfaces at exactly +REFIRE",
          "justified-fact" in [c["stem"] for c in
                               ms.demotion_candidates(_ffC, _idxC, _h8C, _itxC,
                                                      justify={"justified-fact": 3})["candidates"]]
          and "justified-fact" not in [c["stem"] for c in
                                       ms.demotion_candidates(_ffC, _idxC, {**_h8C, "windows_full": 7,
                                                                            "window_starts": [_e1C] * 7},
                                                              _itxC, justify={"justified-fact": 3})["candidates"]])
    _manyC = [_factC(f"bulk-{i}", f"an unread reference row number {i}", 1000.0) for i in range(7)]
    _midxC = {f"bulk-{i}" for i in range(7)}
    # 20-char steps = 5-token steps — a 1-char step would tie inside one ceil(chars/4) bucket and
    # the (-hook, stem) tiebreak would sort alphabetically instead of by cost.
    _mitxC = "# Memory Index\n" + "\n".join(f"- [bulk-{i}](bulk-{i}.md) — " + "h" * (10 + 20 * i) for i in range(7)) + "\n"
    _mrkC = ms.demotion_candidates(_manyC, _midxC, {**_histC, "per_fact": {}, "miss_stems": []}, _mitxC)
    check("v0.1.67 cap: 7 eligible → 5 surfaced (bottom-K), eligible reports the true count",
          _mrkC["eligible"] == 7 and len(_mrkC["candidates"]) == ms._DEMOTION_BOTTOM_K
          and _mrkC["candidates"][0]["stem"] == "bulk-6")

    # O1 — script-truth stamp + dual-read zrw trap (dogfood 11-vs-16)
    _app16 = ms.apply_demotion_justify(
        {"commit": "abc", "stacks": ["python"], "beacon_snooze_until": "x",
         "standing_justify": {"facts": 9}},
        ["justified-fact"], wf=16, window_starts=[_e1C] * 16,
        now_iso="2026-09-01T21:23:45.446Z")
    check("O1: writer stamps sequence (and mirrors it as windows) not a caller/zrw integer",
          _app16["stamped"][0]["windows"] == 16
          and _app16["stamped"][0]["sequence"] == 16
          and _app16["stamped"][0]["until"] == 21
          and _app16["state"]["stacks"] == ["python"]
          and _app16["state"]["beacon_snooze_until"] == "x"
          and _app16["state"]["standing_justify"] == {"facts": 9}
          and _app16["state"]["commit"] == "abc"
          and _app16["state"]["demotion_justify"]["justified-fact"]["sequence"] == 16)
    _noop = ms.apply_demotion_justify(
        _app16["state"], ["justified-fact"], wf=16, window_starts=[_e1C] * 16,
        now_iso="2026-09-01T22:00:00.000Z")
    check("O1: re-stamp of a still-suppressed stem is a no-op (clock not reset)",
          _noop["stamped"] == []
          and _noop["skipped"] == [{"stem": "justified-fact", "reason": "already-justified"}]
          and _noop["state"]["demotion_justify"]["justified-fact"]["at"]
          == "2026-09-01T21:23:45.446Z"
          and _noop["state"]["demotion_justify"]["justified-fact"]["windows"] == 16)
    _expired_state = {"demotion_justify": {
        "justified-fact": {"windows": 3, "at": "2026-01-01T00:00:00Z"}}}
    _starts_after = []
    for _mo in range(2, 7):  # Feb..Jun = 5 windows after Jan 1
        _dtm = ms._parse_ts(f"2026-0{_mo}-01T00:00:00Z")
        assert _dtm is not None
        _starts_after.append(_dtm.timestamp())
    _re2 = ms.apply_demotion_justify(
        _expired_state, ["justified-fact"], wf=16, window_starts=_starts_after,
        now_iso="2026-09-01T21:23:45.446Z")
    check("O1: re-stamp after expiry writes a new sequence / at",
          _re2["stamped"][0]["windows"] == 16
          and _re2["stamped"][0]["sequence"] == 16
          and _re2["stamped"][0]["at"] == "2026-09-01T21:23:45.446Z"
          and _re2["state"]["demotion_justify"]["justified-fact"]["sequence"] == 16)

    _at_now = "2026-09-01T21:23:45.446Z"
    _at_ep = ms._parse_ts(_at_now)
    assert _at_ep is not None
    _starts_before = [_e1C] * 16  # all 2026-01-01, before at
    _zrw_just = {"justified-fact": {"windows": 11, "at": _at_now}}
    _h16 = {**_histC, "windows_full": 16, "window_starts": _starts_before, "miss_stems": []}
    _dc_zrw = ms.demotion_candidates(_ffC, _idxC, _h16, _itxC, justify=_zrw_just)
    check("O1: dual-read zrw trap (jw=11, wf=16, at=now) still suppresses",
          "justified-fact" not in [c["stem"] for c in _dc_zrw["candidates"]]
          and _dc_zrw["vetoed_justified"] >= 1
          and any(j["stem"] == "justified-fact" and j["remaining"] == 5
                  for j in _dc_zrw["justified_live"]))
    _starts_5_after = [(_at_ep.timestamp() + 86400 * (i + 1)) for i in range(5)]
    _h16b = {**_histC, "windows_full": 16, "window_starts": _starts_5_after, "miss_stems": []}
    _dc_exp = ms.demotion_candidates(_ffC, _idxC, _h16b, _itxC, justify=_zrw_just)
    check("O1: dual-read expires after 5 window_starts after at",
          "justified-fact" in [c["stem"] for c in _dc_exp["candidates"]])

    _dlines_el = ms.demotion_signal_lines({
        "windows_full": 16, "eligible": 1,
        "candidates": [{"stem": "cadence", "hook_tokens": 58, "zero_read_windows": 11}],
        "vetoed_keep": 2, "vetoed_read": 3, "vetoed_justified": 1, "vetoed_missed": 0,
        "justified_live": [{"stem": "governance-signal", "windows": 13, "refire_at": 18, "remaining": 2}],
    })
    check("O1: Phase 0 eligible stems are not on the same line as justified tally",
          any(ln.startswith("demote?") and "cadence" in ln and "justified" not in ln for ln in _dlines_el)
          and any(ln.startswith("vetoed:") and "keep-signal" in ln and "justified" not in ln for ln in _dlines_el)
          and any("justified: governance-signal (re-fires at 18w · 2 to go)" in ln for ln in _dlines_el))
    _dlines_j = ms.demotion_signal_lines({
        "windows_full": 16, "eligible": 0, "candidates": [],
        "justified_live": [{"stem": "cadence", "windows": 16, "refire_at": 21, "remaining": 5}],
    })
    check("O1: Phase 0 justified-until line even when eligible=0",
          any("justified: cadence (re-fires at 21w · 5 to go)" in ln for ln in _dlines_j)
          and not any(ln.startswith("demote?") for ln in _dlines_j))

    check("I3: _KEEP_RE pattern frozen (do not widen for standing-ops policy)",
          ms._KEEP_RE.pattern == (
              r"(?i)\b(?:never|don['’]?t|do not|avoid|gotcha|footgun|always|must|shall|"
              r"prefer|should|shouldn['’]?t|cannot|can['’]?t|won['’]?t|caveat)\b"))
    check("I3: cadence-like description is not KEEP (counter-justify is the path)",
          not ms._KEEP_RE.search(
              "Phase C ops: NO burst-seeding — dream cadence at real arc boundaries "
              "IS the seeding; first triage + misses = the calibration events."))

_now_stale = ms._parse_ts("2026-09-01T21:42:00Z")
assert _now_stale is not None
_stale_all = ms.stale_signal_text(
    ["a", "b", "c"], 3, "2026-09-01T21:23:00Z", now_ts=_now_stale.timestamp())
check("stale-all: all facts stale + last dream 19m ago collapses (no stem dump)",
      _stale_all is not None
      and "3 stale fact(s)" in _stale_all
      and "stems omitted" in _stale_all
      and "a, b, c" not in _stale_all)
_stale_mix = ms.stale_signal_text(
    ["a"], 3, "2026-09-01T21:23:00Z", now_ts=_now_stale.timestamp())
check("stale-all: mixed stale still lists stems",
      _stale_mix is not None and "a" in _stale_mix and "stems omitted" not in _stale_mix)
_old = ms._parse_ts("2026-09-04T21:23:00Z")
assert _old is not None
_stale_old = ms.stale_signal_text(
    ["a", "b", "c"], 3, "2026-09-01T21:23:00Z", now_ts=_old.timestamp())
check("stale-all: all stale but last dream ≥24h still lists stems",
      _stale_old is not None and "a, b, c" in _stale_old and "stems omitted" not in _stale_old)

# (6) validator backstops — additive; a clean/legacy record stays quiet
check("v0.1.67 validate: usage.misses non-list + over-cap both warn; capped list is quiet",
      any("usage.misses is not a list" in w for w in ms.validate_cycle_record({"usage": {"misses": 3}}))
      and any("usage.misses exceeds" in w for w in ms.validate_cycle_record(
          {"usage": {"misses": [str(i) for i in range(ms._USAGE_FACT_CAP + 1)]}}))
      and not ms.validate_cycle_record({"usage": {"misses": ["a"]}}))
check("v0.1.67 validate: demotion non-dict warns; surfaced over the rank cap warns; struck non-list warns",
      any("demotion is not a dict" in w for w in ms.validate_cycle_record({"demotion": []}))
      and any("demotion.surfaced exceeds" in w for w in ms.validate_cycle_record(
          {"demotion": {"surfaced": [str(i) for i in range(ms._DEMOTION_BOTTOM_K + 1)]}}))
      and any("demotion.struck is not a list" in w for w in ms.validate_cycle_record({"demotion": {"struck": 0}}))
      and not ms.validate_cycle_record({"demotion": {"windows_observed": 1, "eligible": 0, "surfaced": []}}))

# (7) inject_usage — the current-window STRIKE (script-truth; the model check is belt-and-suspenders)
with _tfB.TemporaryDirectory() as _tdC3:
    _seedC = Path(_tdC3) / "cycle.json"
    _seedC.write_text(_jsonB.dumps({"project": "p", "demotion": {
        "windows_observed": 4, "eligible": 2, "surfaced": ["keep-me", "just-read"]}}), encoding="utf-8")
    _blkC = {"window": "w", "transcripts": 1, "dream_excluded": 0, "reads": 1, "facts_read": 1,
             "per_fact": [{"name": "just-read", "reads": 1, "last": "t"}], "archive_reads": 0, "misses": []}
    with _ctxB.redirect_stderr(_ioB.StringIO()) as _errC3:
        _okC3 = es.inject_usage(str(_seedC), _blkC)
    _afterC3 = _jsonB.loads(_seedC.read_text(encoding="utf-8"))
    check("v0.1.67 inject_usage strike: a surfaced stem read THIS window moves surfaced → struck (stderr-logged)",
          _okC3 and _afterC3["demotion"]["surfaced"] == ["keep-me"]
          and _afterC3["demotion"]["struck"] == ["just-read"]
          and "struck 1 surfaced stem" in _errC3.getvalue()
          and _afterC3["usage"]["per_fact"][0]["name"] == "just-read")
    _seedC.write_text(_jsonB.dumps({"project": "p", "demotion": {"surfaced": ["keep-me"]}}), encoding="utf-8")
    with _ctxB.redirect_stderr(_ioB.StringIO()):
        es.inject_usage(str(_seedC), {**_blkC, "per_fact": []})
    check("v0.1.67 inject_usage: no reads this window → surfaced untouched, no struck key invented",
          _jsonB.loads(_seedC.read_text(encoding="utf-8"))["demotion"] == {"surfaced": ["keep-me"]})

# (8) the miss-detector — recall_scan tiering, window-start via --before, uncapped-tally misses
def _rlC(ts: str, kind: str, path_or_cmd: str) -> str:
    tu = ({"type": "tool_use", "name": "Bash", "input": {"command": path_or_cmd}} if kind == "arc"
          else {"type": "tool_use", "name": "Read", "input": {"file_path": path_or_cmd}})
    return _jsonB.dumps({"timestamp": ts, "message": {"content": [tu]}})

with _tfB.TemporaryDirectory() as _tdC4:
    _homeC4 = Path(_tdC4)
    _projC4 = (_homeC4 / "src" / "missproj").resolve(); _projC4.mkdir(parents=True)
    _prC4 = _homeC4 / ".claude" / "projects" / ms.slug_for(_projC4)
    _stC4 = _prC4 / "memory"; _stC4.mkdir(parents=True)
    (_stC4 / "MEMORY.md").write_text("# Memory Index\n- [ind](ind.md) — indexed fact\n", encoding="utf-8")
    (_stC4 / "SHIPPED.md").write_text("archive\n- [arch1](arch1.md) — done\n- [arch2](arch2.md) — done\n"
                                      "- [zz-arch](zz-arch.md) — done\n", encoding="utf-8")
    for _fnC4 in ("ind", "arch1", "arch2", "zz-arch"):
        (_stC4 / f"{_fnC4}.md").write_text(f"---\nname: {_fnC4}\n---\nbody\n", encoding="utf-8")
    _linesC4 = [_rlC("2026-01-01T01:00:00Z", "read", str(_stC4 / "arch1.md")),      # organic ARCHIVED read → MISS
                _rlC("2026-01-01T02:00:00Z", "read", str(_stC4 / "ind.md")),        # organic indexed read → not a miss
                _rlC("2026-01-01T03:00:00Z", "arc", "CM_DREAM_ARC=1 python3 x.py"),
                _rlC("2026-01-01T04:00:00Z", "read", str(_stC4 / "arch2.md")),      # inside the arc span → excluded
                _rlC("2026-01-01T05:00:00Z", "arc", "CM_DREAM_ARC=1 python3 y.py")]
    (_prC4 / "t1.jsonl").write_text("\n".join(_linesC4) + "\n", encoding="utf-8")
    _oldHomeC4 = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_homeC4)
    try:
        _u1C4 = es.recall_scan(_projC4, "")
        check("v0.1.67 miss-detector: an organic archived-tier read is a MISS; indexed isn't; arc-span is excluded",
              _u1C4["misses"] == ["arch1"] and _u1C4["archive_reads"] == 1
              and _u1C4["dream_excluded"] == 1 and _u1C4["reads"] == 2)
        _snapC4 = Path(_tdC4) / "before.json"
        _snapC4.write_text(_jsonB.dumps({
            "memory/MEMORY.md": {"store": "memory",
                                 "content": "# Memory Index\n- [ind](ind.md) — x\n- [arch1](arch1.md) — y\n"},
            "memory/SHIPPED.md": {"store": "memory",
                                  "content": "archive\n- [arch2](arch2.md) — a\n- [zz-arch](zz-arch.md) — b\n- [old](old.md) — c\n"},
        }), encoding="utf-8")
        _u2C4 = es.recall_scan(_projC4, "", before=str(_snapC4))
        check("v0.1.67 miss-detector --before: tier at WINDOW START — a fact archived THIS pass is NOT a miss",
              _u2C4["misses"] == [] and _u2C4["archive_reads"] == 0)
        # uncapped-tally leg: 41 organic reads push per_fact past the cap; the archived read (zz-arch,
        # sorts last alphabetically at equal reads) falls OFF per_fact yet still lands in misses.
        _bulkC4 = [_rlC(f"2026-01-01T06:{i:02d}:00Z", "read", str(_stC4 / f"f{i:02d}.md")) for i in range(41)]
        _bulkC4.append(_rlC("2026-01-01T07:00:00Z", "read", str(_stC4 / "zz-arch.md")))
        (_prC4 / "t2.jsonl").write_text("\n".join(_bulkC4) + "\n", encoding="utf-8")
        (_prC4 / "t1.jsonl").unlink()
        _u3C4 = es.recall_scan(_projC4, "")
        check("v0.1.67 miss-detector: misses derive from the UNCAPPED tally — a miss beyond the per_fact cap still lands",
              "zz-arch" in _u3C4["misses"]
              and "zz-arch" not in [f["name"] for f in _u3C4["per_fact"]]
              and len(_u3C4["per_fact"]) == es._USAGE_FACT_CAP and _u3C4["facts_read"] == 42)
    finally:
        if _oldHomeC4 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldHomeC4

# (9) seed integration — build_context + seed_record carry the demotion block (dormant AND eligible)
with _tfB.TemporaryDirectory() as _tdC5:
    _homeC5 = Path(_tdC5)
    _projC5 = (_homeC5 / "src" / "seedproj").resolve(); _projC5.mkdir(parents=True)
    _stC5 = _homeC5 / ".claude" / "projects" / ms.slug_for(_projC5) / "memory"; _stC5.mkdir(parents=True)
    (_stC5 / "MEMORY.md").write_text("# Memory Index\n- [old-ref](old-ref.md) — an aging pointer\n", encoding="utf-8")
    (_stC5 / "old-ref.md").write_text('---\nname: old-ref\ndescription: "an aging reference pointer"\n'
                                      "metadata:\n  node_type: memory\n  type: reference\n---\nbody\n",
                                      encoding="utf-8")
    _osB.utime(_stC5 / "old-ref.md", (1000.0, 1000.0))
    _oldHomeC5 = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_homeC5)
    try:
        _rec5a = ms.seed_record(ms.build_context(_projC5))
        check("v0.1.67 seed: a log-less store seeds an HONEST dormant block (0 windows, 0 eligible)",
              _rec5a.get("demotion") == {"windows_observed": 0, "eligible": 0, "surfaced": []})
        (_stC5 / ".consolidation-log.jsonl").write_text("\n".join(
            _uwC(f"2026-0{i}-01T00:00:00Z..2026-0{i}-02T00:00:00Z", 1, 0, []) for i in (1, 2, 3)) + "\n",
            encoding="utf-8")
        _rec5b = ms.seed_record(ms.build_context(_projC5))
        check("v0.1.67 seed: 3 probative windows + an old 0-read fact → eligible, surfaced by name",
              _rec5b.get("demotion") == {"windows_observed": 3, "eligible": 1, "surfaced": ["old-ref"]})
    finally:
        if _oldHomeC5 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldHomeC5

# (10) render — additive DEMOTION/MISS surfaces; legacy renders byte-identically (key-presence gates)
_drecC = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
                               "demotion": {"windows_observed": 1, "eligible": 0}})
check("v0.1.67 render: a dormant demotion block renders the DORMANT line",
      "DEMOTION" in rd.render(_drecC) and "dormant — 1 probative" in rd.render(_drecC))
_drec2C = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
                                "demotion": {"windows_observed": 4, "eligible": 2,
                                             "surfaced": ["a-fact"], "struck": ["b-fact"],
                                             "verdict": "demoted 1 · justified 1"}})
_dout2C = rd.render(_drec2C)
check("v0.1.67 render: eligible block shows surfaced + struck + the verdict sentence",
      "surfaced: a-fact" in _dout2C and "b-fact" in _dout2C and "verdict:" in _dout2C
      and "demoted 1 · justified 1" in _dout2C)
_mrecC = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
                               "usage": {"reads": 3, "facts_read": 2, "transcripts": 1, "dream_excluded": 0,
                                         "archive_reads": 2, "misses": ["mfact"],
                                         "per_fact": [{"name": "mfact", "reads": 2, "last": "t"}]}})
check("v0.1.67 render: a non-empty misses list renders the red demotion-MISS line naming the fact",
      "demotion MISS" in rd.render(_mrecC) and "mfact" in rd.render(_mrecC))
_legC = rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
                                        "usage": {"reads": 1, "facts_read": 1, "transcripts": 1,
                                                  "dream_excluded": 0, "per_fact": []}}))
check("v0.1.67 render: legacy records (no demotion / no misses keys) carry NEITHER new surface",
      "DEMOTION" not in _legC and "demotion MISS" not in _legC)

# (11) fleet_utility — mirror-attributed reads, shadow separation, unheld = 0 tax, read-only, JSON-safe
with _tfB.TemporaryDirectory() as _tdC6:
    _homeC6 = Path(_tdC6)
    _projC6 = (_homeC6 / "src" / "trigproj").resolve(); _projC6.mkdir(parents=True)
    _glC6 = _homeC6 / "global-mem"; _glC6.mkdir(parents=True)
    (_glC6 / "canon-x.md").write_text('---\nname: canon-x\ndescription: "a shared canonical"\nmetadata:\n'
                                      "  node_type: memory\n  scope: user-global\n  type: feedback\n"
                                      "  projects: [nodeA]\n---\nbody\n", encoding="utf-8")
    (_glC6 / "canon-unheld.md").write_text('---\nname: canon-unheld\ndescription: "held by nobody"\nmetadata:\n'
                                           "  node_type: memory\n  scope: user-global\n  type: feedback\n---\nbody\n",
                                           encoding="utf-8")
    _projRootC6 = _homeC6 / ".claude" / "projects"
    _nAC6 = _projRootC6 / "-src-nodeA" / "memory"; _nAC6.mkdir(parents=True)
    _nBC6 = _projRootC6 / "-src-nodeB" / "memory"; _nBC6.mkdir(parents=True)
    _canonTextC6 = (_glC6 / "canon-x.md").read_text(encoding="utf-8")
    (_nAC6 / "canon-x.md").write_text(sg._as_mirror(_canonTextC6, "canon-x"), encoding="utf-8")
    # the mirror must PREDATE the window for its windows to count (the mtime gate — see the review leg below)
    _dtPreC6 = ms._parse_ts("2025-12-01T00:00:00Z")
    assert _dtPreC6 is not None
    _osB.utime(_nAC6 / "canon-x.md", (_dtPreC6.timestamp(), _dtPreC6.timestamp()))
    (_nAC6 / ".consolidation-log.jsonl").write_text(
        _uwC("2026-01-01T00:00:00Z..2026-01-02T00:00:00Z", 1, 1,
             [{"name": "canon-x", "reads": 3, "last": "2026-01-01T12:00:00Z"}]) + "\n", encoding="utf-8")
    # node B: a mirror of the UNHELD canonical (so it counts as a network node) + a same-stem LOCAL
    # (never-pulled) fact shadowing canon-x, with reads that must NOT be attributed.
    (_nBC6 / "canon-unheld.md").write_text(
        sg._as_mirror((_glC6 / "canon-unheld.md").read_text(encoding="utf-8"), "canon-unheld"), encoding="utf-8")
    (_nBC6 / "canon-x.md").write_text("---\nname: canon-x\nmetadata:\n  node_type: memory\n---\nlocal twin\n",
                                      encoding="utf-8")
    (_nBC6 / ".consolidation-log.jsonl").write_text(
        _uwC("2026-01-03T00:00:00Z..2026-01-04T00:00:00Z", 1, 1,
             [{"name": "canon-x", "reads": 7, "last": "2026-01-03T12:00:00Z"}]) + "\n", encoding="utf-8")
    _hashesC6 = {p: _hlC.sha1(p.read_bytes()).hexdigest() for p in _projRootC6.rglob("*") if p.is_file()}
    _oldHomeC6 = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_homeC6)
    _oldGlobalC6 = sg.GLOBAL
    sg.GLOBAL = _glC6
    try:
        _enroll_personal(_projC6)
        _seed_holders(_projC6, "canon-x", ["nodeA"])
        _fuC6 = sg.fleet_utility(_projC6)
        _byC6 = {e["name"]: e for e in _fuC6["canonicals"]}
        check("v0.1.67 --utility: reads attribute ONLY through a mirror (nodeA 3); a same-stem local is shadow (7)",
              _byC6["canon-x"]["reads"] == 3 and _byC6["canon-x"].get("shadow_reads") == 7
              and _byC6["canon-x"]["windows"] == 1)
        check("v0.1.67 --utility: fleet_tax = pointer × holders; an unheld canonical is 0 tax and listed",
              _byC6["canon-x"]["fleet_tax"] == _byC6["canon-x"]["pointer_tok"] * 1
              and _byC6["canon-unheld"]["fleet_tax"] == 0 and _fuC6["unheld"] == ["canon-unheld"])
        check("v0.1.67 --utility: nodes_reporting counts probative-window stores; payload is JSON-safe",
              _fuC6["nodes_reporting"] == 2 and _fuC6["nodes"] == 2
              and isinstance(_jsonB.dumps(_fuC6), str))
        check("v0.1.67 --utility: READ-ONLY — no store file changed",
              _hashesC6 == {p: _hlC.sha1(p.read_bytes()).hexdigest()
                            for p in _projRootC6.rglob("*") if p.is_file()})
        # the inline adversarial review (2026-07-05): a FRESHLY-pulled mirror must not be credited the
        # node's whole window history — mtime-gate the per-canonical window count (0 reads/10w on a
        # one-day-old mirror overstates zero-read evidence; a refresh resets the clock — undercount, safe).
        _dtPostC6 = ms._parse_ts("2026-06-01T00:00:00Z")
        assert _dtPostC6 is not None
        _osB.utime(_nAC6 / "canon-x.md", (_dtPostC6.timestamp(), _dtPostC6.timestamp()))
        _fu2C6 = sg.fleet_utility(_projC6)
        _by2C6 = {e["name"]: e for e in _fu2C6["canonicals"]}
        check("v0.1.67 --utility review fix: a mirror pulled AFTER a window gets NO zero-read credit for it",
              _by2C6["canon-x"]["windows"] == 0 and _by2C6["canon-x"]["reads"] == 3)
    finally:
        sg.GLOBAL = _oldGlobalC6
        if _oldHomeC6 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldHomeC6

# ── v0.1.69 (audit hygiene — docs/audit-hygiene-remediation.spec.md): red-first gates ──────────────
# Each check below FAILED on the pre-fix tree (recorded in the PR); the fixes flip them green.
import contextlib as _cl69  # noqa: E402
import io as _io69  # noqa: E402
import json as _json69  # noqa: E402
import os as _os69  # noqa: E402
import re as _re69  # noqa: E402
import tempfile as _tf69  # noqa: E402

# A1: the per-line window compare must be PARSED-instant, not raw-string (distill's v0.1.58 twin fix,
# never ported to extract). Vector: since 18:00+02:00 == 16:00Z; a 16:30Z line is instant-AFTER (must
# be kept) but raw-string-compares BELOW "…18:00…+02:00" (pre-fix: wrongly dropped). 15:30Z drops both ways.
_SINCE69 = "2026-07-05T18:00:00+02:00"          # == 2026-07-05T16:00:00Z
def _hl69(ts: str, text: str) -> str:            # a human-turn transcript line at ts
    return _json69.dumps({"timestamp": ts, "sessionId": "s69",
                          "message": {"role": "user", "content": text}}) + "\n"
with _tf69.TemporaryDirectory() as _td69:
    _home69 = Path(_td69); _proj69 = _home69 / "proj"; _proj69.mkdir()
    _pr69 = _home69 / ".claude" / "projects" / es.slug_for(_proj69); _pr69.mkdir(parents=True)
    (_pr69 / "sess.jsonl").write_text(
        _hl69("2026-07-05T16:30:00Z", "prefer the frobnicator flag for exports")
        + _hl69("2026-07-05T15:30:00Z", "stale turn from before the marker")
        + _hl69("not-a-timestamp", "unparseable ts line kept fail-open"), encoding="utf-8")
    _old69 = _os69.environ.get("HOME"); _os69.environ["HOME"] = str(_home69)
    try:
        _r69 = es.extract(_proj69, _SINCE69, 20)
    finally:
        _os69.environ["HOME"] = _old69 if _old69 is not None else ""
    _texts69 = " ".join(s.get("text", "") for s in _r69.get("signals", []))
    check("v0.1.69/A1: an offset `since` keeps the instant-AFTER Z-stamped line (raw-string compare dropped it)",
          "frobnicator" in _texts69)
    check("v0.1.69/A1: …and still drops the instant-BEFORE line (window semantics unchanged)",
          "stale turn" not in _texts69)
    check("v0.1.69/A1: an unparseable line ts fails OPEN — kept, never raises (green both ends; semantics pin)",
          "unparseable ts line" in _texts69)

# A1 twin: _recall_items carries the same raw-string compare on the recall-usage scan.
with _tf69.TemporaryDirectory() as _td69b:
    _store69 = _td69b + "/memory/"
    _tr69 = Path(_td69b) / "t.jsonl"
    def _rl69(ts: str, stem: str) -> str:        # a Read-tool_use line on a store fact
        return _json69.dumps({"timestamp": ts, "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": _store69 + stem + ".md"}}]}}) + "\n"
    _tr69.write_text(_rl69("2026-07-05T16:30:00Z", "kept-fact") + _rl69("2026-07-05T15:30:00Z", "old-fact"),
                     encoding="utf-8")
    _items69 = es._recall_items(_tr69, _store69, _SINCE69, frozenset())
    _stems69 = {it.get("stem") for it in _items69}
    check("v0.1.69/A1: _recall_items keeps the instant-AFTER read under an offset since (twin site)",
          "kept-fact" in _stems69 and "old-fact" not in _stems69)

# A2: _report is a TTY presentation boundary — repo-controlled error text must be _sane()d there.
# ESC survives _norm (it strips Cf; ESC is Cc) → pre-fix the raw \x1b reaches stdout = escape injection.
_sig69 = {"counts": {"human_seen": 1, "noise": 0, "secrets_omitted": 0, "errors": 1, "surfaced": 1},
          "transcripts": ["t.jsonl"], "since": "2026-07-05T00:00:00Z",
          "signals": [{"source": "error", "signal_type": "gotcha", "scope_hint": "env",
                       "sessionId": "", "ts": "", "score": 0, "text": "\x1b[31mred\x1b[0m alert"}]}
_buf69 = _io69.StringIO()
with _cl69.redirect_stdout(_buf69):
    es._report(_sig69)
_out69 = _buf69.getvalue()
check("v0.1.69/A2: report output carries NO raw ESC byte, text content preserved (presentation _sane)",
      "\x1b" not in _out69 and "red" in _out69)
# v0.1.69/A2 Gate-2b follow-up: the spec's OWN acceptance criterion ("the same record through the
# --json path keeps signal_type/score intact") was never exercised — the --json path is a SEPARATE
# emitter (`print(json.dumps(d, ...))`, main():796) that never calls _report/_sane; prove sanitization
# stays presentation-only and doesn't leak into (or corrupt) the machine-readable path.
_json69_out = _json43.dumps(_sig69, indent=2)
_json69_rt = _json43.loads(_json69_out)
_json69_sig = _json69_rt["signals"][0]
check("v0.1.69/A2: --json path keeps signal_type/score intact AND the RAW (unsanitized) text — "
      "sanitize is presentation-only, never a stored/machine-readable mutation",
      _json69_sig.get("signal_type") == "gotcha" and _json69_sig.get("score") == 0
      and _json69_sig.get("text") == "\x1b[31mred\x1b[0m alert")

# A3: the store-scan convention (skip unreadable, never abort) applied to the two token/node scans.
_a3_tok_ok = _a3_net_ok = False
with _tf69.TemporaryDirectory() as _td69c:
    _st69 = Path(_td69c) / "memory"; _st69.mkdir()
    (_st69 / "real.md").write_text("---\nname: real\n---\nbody\n", encoding="utf-8")
    (_st69 / "ghost.md").symlink_to(_st69 / "nowhere")     # dangling: read_text raises OSError
    try:
        _a3_tok_ok = sg._node_tokens(_st69).get("facts") == 1   # ghost skipped, real counted
    except OSError:
        _a3_tok_ok = False
    check("v0.1.69/A3: _node_tokens skips a vanished/dangling fact instead of crashing", _a3_tok_ok)
with _tf69.TemporaryDirectory() as _td69d:
    _home69d = Path(_td69d)
    _stA69 = _home69d / ".claude" / "projects" / "-p-a" / "memory"; _stA69.mkdir(parents=True)
    (_stA69 / "ghost.md").symlink_to(_stA69 / "nowhere")   # ghost-ONLY store sorts FIRST (deterministic red)
    _stB69 = _home69d / ".claude" / "projects" / "-p-b" / "memory"; _stB69.mkdir(parents=True)
    (_stB69 / "m.md").write_text("---\nname: m\nmetadata:\n  global_ref: m\n---\nb\n", encoding="utf-8")
    _oldH69 = _os69.environ.get("HOME"); _os69.environ["HOME"] = str(_home69d)
    try:
        _nodes69 = sg._network_nodes()
        _a3_net_ok = _stB69 in _nodes69 and _stA69 not in _nodes69
    except OSError:
        _a3_net_ok = False
    finally:
        _os69.environ["HOME"] = _oldH69 if _oldH69 is not None else ""
    check("v0.1.69/A3: _network_nodes survives a dangling-only store and still finds the readable mirror",
          _a3_net_ok)
# v0.1.69/A3 Gate-2b follow-up: _orphans() (feeds `cm gc`) was the 4th unguarded site found AFTER this
# spec's original 3-site scope — it got the fix (via the shared _safe_read_text helper) but no
# dedicated regression test, unlike its _node_tokens/_network_nodes siblings just above. Close the gap.
_a3_orphan_ok = False
with _tf69.TemporaryDirectory() as _td69e:
    _st69e = Path(_td69e) / "memory"; _st69e.mkdir()
    (_st69e / "real.md").write_text("---\nname: real\nmetadata:\n  global_ref: real\n---\nbody\n",
                                     encoding="utf-8")   # a mirror whose canonical is gone → a real orphan
    (_st69e / "ghost.md").symlink_to(_st69e / "nowhere")  # dangling: read_text raises OSError
    _oldGlobal69e = sg.GLOBAL
    sg.GLOBAL = Path(_td69e) / "empty-global"   # no canonicals at all → "real" IS orphaned
    try:
        _a3_orphan_ok = sg._orphans(_st69e) == ["real"]   # ghost skipped (not a crash), real correctly flagged
    except OSError:
        _a3_orphan_ok = False
    finally:
        sg.GLOBAL = _oldGlobal69e
    check("v0.1.69/A3: _orphans() skips a dangling fact instead of crashing `cm gc` "
          "(the 4th unguarded site, found post-spec at Gate-2a)", _a3_orphan_ok)

# A4: a git failure must be LABELED (stderr, once per process) — silent "" made broken-git ≡ empty-repo.
def _boom69(*a: Any, **k: Any) -> Any:
    raise FileNotFoundError("git not found")
_real_run69 = ms.subprocess.run
setattr(ms, "_GIT_WARNED", False)                # reset (attr exists only post-fix; setattr is pre-fix-safe)
_err69 = _io69.StringIO(); _out69b = _io69.StringIO()
try:
    setattr(ms.subprocess, "run", _boom69)
    with _cl69.redirect_stderr(_err69), _cl69.redirect_stdout(_out69b):
        _rv69a = ms._run(["git", "log"], Path("."))
        _rv69b = ms._run(["git", "status"], Path("."))
finally:
    setattr(ms.subprocess, "run", _real_run69)
_errtxt69 = _err69.getvalue()
check("v0.1.69/A4: git failure returns '' AND labels the degradation on stderr (no-masking law)",
      _rv69a == "" and _rv69b == "" and "git unavailable" in _errtxt69)
check("v0.1.69/A4: the label fires ONCE per process (no spam across repeated _run calls)",
      _errtxt69.count("git unavailable") == 1)
check("v0.1.69/A4: stdout stays EMPTY on the degraded path (diagnostic is stderr-only; --json purity)",
      _out69b.getvalue() == "")
setattr(ms, "_GIT_WARNED", False)                # leave clean for any later check exercising _run

# A5: genericity PIN — no personal /home/<name> (slash) or -home-<name>- (slug) may enter the
# shipped/public tree. Allowed = the five generic placeholders in use; extending this set is a
# CONSCIOUS edit here (that friction is the guard). The name class is deliberately restrictive
# ([A-Za-z0-9_]) so the remediation spec's pin-inert `<user>` placeholder can never match.
# v0.1.69 Gate-2a follow-up: the original suffix filter (.py/.md/.sh/.html) missed the
# extensionless `cm` CLI and .json manifests — both real, tracked, shipped/public files a
# personal path could hide in undetected. .json now scans inside the 3 recursive roots; `cm`,
# the repo-root marketplace.json, AND CHANGELOG.md (Gate-2b follow-up: a shipped, public,
# repo-root file edited on every release — an easy place for a bad copy-paste from a bug
# repro to land) are checked as explicit extras rather than widening the recursive scan to
# bare-no-suffix (which risks sweeping in binaries).
_GENERIC69 = {"you", "u", "x", "d", "nobody"}
_SKIP69 = {"__pycache__", ".mypy_cache", ".ruff_cache"}
_bad69: list = []
_extra69 = [ROOT / "cm", ROOT / ".claude-plugin" / "marketplace.json", ROOT / "CHANGELOG.md"]
_files69 = [p for p in _extra69 if p.is_file()]
for _root69 in (ROOT / "plugins", ROOT / "tests", ROOT / "docs"):   # v0.1.69/B9: widened from
    # plugins/consolidate-memory to ALL of plugins/ (both plugins covered — Track B's own
    # genericity scrub (B4/B10) is what this widening enforces going forward)
    for _p69 in sorted(_root69.rglob("*")):
        if not _p69.is_file() or _p69.suffix not in {".py", ".md", ".sh", ".html", ".json"}:
            continue
        if any(part in _SKIP69 for part in _p69.parts):
            continue
        _files69.append(_p69)
for _p69 in _files69:
    _t69 = _p69.read_text(encoding="utf-8", errors="replace")
    for _nm69 in (_re69.findall(r"/home/([A-Za-z0-9_]+)", _t69)
                  + _re69.findall(r"-home-([A-Za-z0-9_]+)-", _t69)
                  + _re69.findall(r"(?:^|[^A-Za-z0-9_-])home-([A-Za-z0-9_]+)-", _t69)):
        if _nm69 not in _GENERIC69:
            _bad69.append(f"{_p69.relative_to(ROOT)}:{_nm69}")
check("v0.1.69/A5+B9: genericity pin — every /home/<name> + -home-<name>- under ALL of plugins/ "
      "(both plugins, widened at Track B), tests, docs (+ .json manifests, the `cm` CLI, "
      "CHANGELOG.md) is a generic placeholder (you/u/x/d/nobody)",
      not _bad69)
if _bad69:
    print(f"    offending: {sorted(set(_bad69))[:8]}", file=sys.stderr)

# A6 (Gate-2b follow-up): SKILL.md's ONLY previously had a MANUAL grep as its spec's acceptance
# criterion — no automated regression check, unlike every other A-item. Pin it: the --list command's
# inline comment must describe a read-only preview, NEVER "held" (held only exists under --pull).
_list69_line = next((ln for ln in _skill_text.splitlines() if "sync_global.py --list ." in ln), "")
check("v0.1.69/A6: SKILL.md's --list command comment never overclaims 'held' (regression guard — "
      "held only exists under --pull, per sync_global.py's own held_this predicate)",
      bool(_list69_line) and "held" not in _list69_line)

# ── Track B (v0.1.7 dbt truth restoration) — Gate-2a follow-up: close the test-coverage gap ──
# every capture family got dedicated tests EXCEPT usage_capture/demotion_capture; emit_result.py's
# B2 fixes and the safe_suggestion SKIP / cycle_identity basis relabel had ZERO smoke coverage.
import subprocess as _spB  # noqa: E402
sys.path.insert(0, str(ROOT / "plugins" / "dream-beta-tester" / "scripts"))
import emit_result as _erB  # noqa: E402


class _FakeCtxB:
    skill_version = "0.1.63"
    log_records: list = [{"marker": {"timestamp": "t1"}}]


# usage_capture — mirrors dream_arc_capture's v0.1.54 battery exactly (same scaffold, same shapes).
check("Track B: usage_capture — dormant/absent-window latest record → LOW/WARN with the pre-feature caveat",
      len(_bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB()))) == 1
      and _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB()))[0].status == "WARN"
      and "pre-v0.1.63" in _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB()))[0].actual)
_FakeCtxB.log_records = [{"usage": {"window": "2026-01-01..2026-01-02", "reads": 0}, "marker": {"timestamp": "t2"}}]
check("Track B: usage_capture — a stamped window (even zero-read/dormant) → PASS",
      _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB()))[0].status == "PASS")
_FakeCtxB.log_records = [{"usage": {"window": ""}, "marker": {"timestamp": "t3"}}]
check("Track B: usage_capture — usage block present but window EMPTY → WARN (injection ran, stamped nothing)",
      _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB()))[0].status == "WARN")
_FakeCtxB.skill_version = "0.1.62"
check("Track B: usage_capture — pre-feature skill (< 0.1.63) → SKIP-by-empty",
      _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB())) == [])
_FakeCtxB.skill_version = "unknown"
check("Track B: usage_capture — unparseable version fails CLOSED → SKIP-by-empty",
      _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB())) == [])
_FakeCtxB.skill_version = "0.1.63"
_FakeCtxB.log_records = []
check("Track B: usage_capture — empty log → SKIP-by-empty (invisible, not even a SKIP row)",
      _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB())) == [])
_FakeCtxB.log_records = [{"maintenance": {"pivoted": True}, "marker": {"timestamp": "t4"}}]
check("Track B: usage_capture — maintenance.pivoted=True → legitimately skipped (SKIP-by-empty, not WARN)",
      _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB())) == [])
_FakeCtxB.log_records = [{"maintenance": {"pivoted": "false"}, "marker": {"timestamp": "t5"}}]
check("Track B: usage_capture — pivoted='false' (truthy STRING) does NOT skip (str(None)-truthiness class bug guard)",
      _bc54.usage_capture(cast(_bc54.Ctx, _FakeCtxB())) != [])

# demotion_capture — same battery.
_FakeCtxB.skill_version = "0.1.67"
_FakeCtxB.log_records = [{"marker": {"timestamp": "t1"}}]
check("Track B: demotion_capture — no demotion block on a v0.1.67+ record → WARN",
      _bc54.demotion_capture(cast(_bc54.Ctx, _FakeCtxB()))[0].status == "WARN")
_FakeCtxB.log_records = [{"demotion": {"verdict": "dormant — 0 probative windows observed"}, "marker": {"timestamp": "t2"}}]
check("Track B: demotion_capture — a dormant (but stamped) verdict → PASS (dormant is honest, not a defect)",
      _bc54.demotion_capture(cast(_bc54.Ctx, _FakeCtxB()))[0].status == "PASS")
_FakeCtxB.log_records = [{"demotion": {"verdict": ""}, "marker": {"timestamp": "t3"}}]
check("Track B: demotion_capture — demotion block present but verdict EMPTY → WARN (skipped judgment)",
      _bc54.demotion_capture(cast(_bc54.Ctx, _FakeCtxB()))[0].status == "WARN")
_FakeCtxB.skill_version = "0.1.66"
check("Track B: demotion_capture — pre-feature skill (< 0.1.67) → SKIP-by-empty",
      _bc54.demotion_capture(cast(_bc54.Ctx, _FakeCtxB())) == [])
_FakeCtxB.skill_version = "0.1.67"
_FakeCtxB.log_records = []
check("Track B: demotion_capture — empty log → SKIP-by-empty",
      _bc54.demotion_capture(cast(_bc54.Ctx, _FakeCtxB())) == [])
_FakeCtxB.log_records = [{"maintenance": {"pivoted": True}, "marker": {"timestamp": "t4"}}]
check("Track B: demotion_capture — maintenance.pivoted=True → legitimately skipped (SKIP-by-empty, not WARN)",
      _bc54.demotion_capture(cast(_bc54.Ctx, _FakeCtxB())) == [])

# cycle_identity — basis="identity-by-construction" (was mislabeled "structural").
class _FakeCtxCI:
    repo = ROOT
    status = {"project": ROOT.resolve().name, "budget": {"index": {"after_tokens": 100}}}
    network: dict = {"nodes": []}


_ci_rows = _bc54.cycle_identity(cast(_bc54.Ctx, _FakeCtxCI()))
check("Track B: cycle_identity CHK-CYCLE-PROJECT carries basis='identity-by-construction' (was 'structural')",
      any(r.id == "CHK-CYCLE-PROJECT" and r.basis == "identity-by-construction" for r in _ci_rows))

# safe_suggestion's B7(a) SKIP branch — force _skill_triage(ctx) → None via ctx.ms=None (the simplest,
# real (non-mocked) path into _skill_triage's first guard), with ctx.status reporting over-budget.
class _FakeCtxSS:
    store = ROOT   # any real, existing dir — only .is_dir() is checked by safe_suggestion
    store_present = True
    ms = None
    status = {"remediation": {"required": True}}
    notes: list = []
    repo = ROOT
    fact_stems: set = set()          # leg (2)'s recompute basis — empty is a valid, harmless no-op
    index_targets: list = []
    wikilink_targets: dict = {}


with _cl69.redirect_stdout(_io69.StringIO()):   # store.glob("*.md") on ROOT is noisy but harmless; silence it
    _ss_rows = _bc54.safe_suggestion(cast(_bc54.Ctx, _FakeCtxSS()))
_ss_skip = next((r for r in _ss_rows if r.id == "CHK-EVICT-STAGE"), None)
check("Track B: safe_suggestion SKIP fires when ctx.ms is None over an over-budget store (was silent omission)",
      _ss_skip is not None and _ss_skip.status == "SKIP" and "module failed to import" in _ss_skip.actual)
_FakeCtxSS.status = {"remediation": {"required": False}}
check("Track B: safe_suggestion — ctx.ms None but store NOT over budget → no CHK-EVICT-STAGE row (real no-op, not defused)",
      not any(r.id == "CHK-EVICT-STAGE" for r in _bc54.safe_suggestion(cast(_bc54.Ctx, _FakeCtxSS()))))

# emit_result.py's B2 fixes — a stray leading '{' must not mis-land the parse (the exact class
# beta_checks.py's own _last_json_object docstring rejects), and --self-test-ok must require the
# EXACT literal "true" (a typo/garbage must fail toward distrust, not toward trust).
check("Track B/B2(b): _last_json_object skips a stray leading non-JSON '{' and lands the REAL trailing object",
      _erB._last_json_object('{not json') is None
      and _erB._last_json_object('log: {oops} then ' + _json69.dumps({"results": [], "summary": {"fail": 0}}))
      == {"results": [], "summary": {"fail": 0}})
check("Track B/B2(b): emit_result._last_json_object AGREES with beta_checks._last_json_object "
      "(the reimplementation-pin discipline this repo already applies to slug_for)",
      all(_erB._last_json_object(sample) == _bc54._last_json_object(sample) for sample in [
          '{"a": 1}', 'junk {"a": {"b": 1}} more junk {"c": 2}', '', 'not json at all',
          '{"nested": {"deep": {"x": [1, "a{b}c", 2]}}}',
      ]))
for _stok_flag, _stok_expect in [("TRUE", "selftest_broken"), ("", "selftest_broken"), ("junk", "selftest_broken"),
                                 ("true", "harness_error")]:   # "true" + empty stdin → harness_error (no results), not selftest_broken
    _p = _spB.run([sys.executable, str(ROOT / "plugins" / "dream-beta-tester" / "scripts" / "emit_result.py"),
                   "--version", "0.0.0", "--self-test-ok", _stok_flag, "--canary-fail", "0",
                   "--out", "/dev/null", "--generated-at", "t"],
                  input="", capture_output=True, text=True)
    _verdict = _p.stdout.strip()
    check(f"Track B/B2(c): --self-test-ok {_stok_flag!r} (empty stdin) → verdict={_stok_expect!r} (exact-'true' required)",
          _verdict == _stok_expect)

# Gate-2b: self_test.meaning must be conditioned on st_ok FIRST — a broken self-test (ok:false) must
# never assert "proved detection" (the round-1 fix only handled the no-canary/empty-expected-ids case;
# Gate-2b found the sibling selftest_broken branch — a REAL canary that FAILED — still lied).
with _tf69.TemporaryDirectory() as _tdMeaning:
    _outMeaning = str(Path(_tdMeaning) / "latest.json")
    _spB.run([sys.executable, str(ROOT / "plugins" / "dream-beta-tester" / "scripts" / "emit_result.py"),
              "--version", "0.0.0", "--self-test-ok", "false",
              "--expected-ids", "CHK-GATE-BACKFILL,CHK-EVICT-STAGE", "--detected-ids", "CHK-QTY-x-TRUTH",
              "--canary-fail", "4", "--out", _outMeaning, "--generated-at", "t"],
             input="", capture_output=True, text=True)
    _meaning = _json69.loads(Path(_outMeaning).read_text())["self_test"]["meaning"]
check("Track B Gate-2b: self_test.meaning on a BROKEN self-test (ok:false) says FAILED/BROKEN, "
      "never 'proved detection' (the exact contradiction Gate-2b found in the sibling branch)",
      "FAILED" in _meaning and "BROKEN" in _meaning and "proved" not in _meaning)

# v0.1.70 Gate-2a (3rd pass): global_facts() excluded the reserved index by an exact-case
# f.name == "MEMORY.md" check — a global fact literally named memory.md/Memory.md (reachable from
# data written before promote()'s OWN case-insensitive guard existed, or hand-placed) passed both
# that check and _safe_stem("memory"), so it was treated as an ordinary ingestible global and would
# later be pulled/written to a project's store / "memory.md" — colliding with the project's own
# MEMORY.md on a case-insensitive filesystem (macOS).
import tempfile as _tf70g  # noqa: E402
with _tf70g.TemporaryDirectory() as _td70g:
    _glob70g = Path(_td70g)
    (_glob70g / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    (_glob70g / "memory.md").write_text(
        "---\nname: memory\nmetadata:\n  scope: user-global\n---\nbody\n", encoding="utf-8")
    (_glob70g / "real-fact.md").write_text(
        "---\nname: real-fact\nmetadata:\n  scope: user-global\n---\nbody\n", encoding="utf-8")
    _oldGlobal70g = sg.GLOBAL
    sg.GLOBAL = _glob70g
    try:
        _stems70g = {n for n, _fm, _t, _p in sg._all_domain_records()}
    finally:
        sg.GLOBAL = _oldGlobal70g
check("enumerator excludes a case-variant 'memory.md' global fact (not just exact 'MEMORY.md')",
      "memory" not in _stems70g and "real-fact" in _stems70g)

# v0.1.70 Gate-2a (4th pass): _orphans() (which feeds gc(..., apply=True)'s destructive unlink())
# had the SAME exact-case gap as global_facts() — a genuine mirror file literally named memory.md
# would be scanned as an ordinary fact, and since its canonical never exists (GLOBAL has none),
# _orphans() would report it as reclaimable — `gc --apply` would then delete a file whose bare
# name collides with the store's own live MEMORY.md on a case-insensitive filesystem. Now routed
# through the same _is_reserved_stem() predicate as every other guard in this file.
with _tf70g.TemporaryDirectory() as _td70o:
    _store70o = Path(_td70o) / "store"
    _store70o.mkdir()
    (_store70o / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    (_store70o / "memory.md").write_text(          # a genuine MIRROR (global_ref: stamped) —
        "---\n# global_ref: memory\nname: memory\n---\nbody\n", encoding="utf-8")   # would be a real orphan pre-fix
    (_store70o / "real-orphan.md").write_text(
        "---\n# global_ref: real-orphan\nname: real-orphan\n---\nbody\n", encoding="utf-8")
    _emptyGlobal70o = Path(_td70o) / "empty-global"   # no canonicals at all -> everything's an orphan pre-fix
    _oldGlobal70o = sg.GLOBAL
    sg.GLOBAL = _emptyGlobal70o
    try:
        _orphans70o = sg._orphans(_store70o)
    finally:
        sg.GLOBAL = _oldGlobal70o
check("_orphans() excludes a case-variant 'memory.md' mirror (not reclaimable by gc --apply)",
      "memory" not in _orphans70o and "real-orphan" in _orphans70o)

# Track D3 — dashboard.template.html has no automated LAYOUT test (its CSS paint + inline JS execute
# only in a real browser; jsdom parses the DOM but computes no layout/paint, so it can't catch either
# bug class below — verified against jsdom's own docs before ruling it out). These are STRUCTURAL
# SOURCE-TEXT pins on the real shipped template, not render/paint proofs: pixel-level dashboard QA
# stays eye-judged. Each pin is a reversion tripwire for a specific, already-fixed (v0.1.68) defect —
# sabotage-verified (reverting either fix locally flips its check red) before landing.
# (reuses the module-wide `_re` import from line 1064 — no new alias needed)

check("v0.1.68 CSS pin: the masthead's radial-gradient is immediately followed by background-repeat:"
      "no-repeat (its absence is exactly what tiled the glow down the page — CSS's `background:` "
      "shorthand earlier in the same rule resets repeat to its 'repeat' initial value)",
      _re.search(r"background-image:radial-gradient\([^)]*var\(--glow\)[^)]*\);\s*"
                 r"background-repeat:no-repeat;", _tpl54) is not None)

check("v0.1.68 JS pin: the demotion-verdict classifier parses a leading dormant/demoted/"
      "justified/none/counter-justified disposition word into the badge tag — v0.4.1 strips a "
      "duplicated 'eligible N' lead first (the tag+prose split, mirroring the distill panel's grammar)",
      'dvd2=dvd.replace(/^\\s*eligible\\s+\\d+\\s*(?:→|—|-)?\\s*/i,"")' in _tpl54
      and 'dvd2.match(/^\\s*(dormant|demoted|justified|none|counter-justified)\\b[:\\s—-]*/i)' in _tpl54)

check("v0.1.68 JS pin: demoted/justified/counter-justified verdicts get the 'ok' (positive) badge class, "
      "not the neutral default (dormant/none stay neutral — only a resolved-favorably verdict reads as OK)",
      'dcls=(dtag==="demoted"||dtag==="justified"||dtag==="counter-justified")?" ok":""' in _tpl54)

# --- v0.1.71 Track D-1: _atomic_write_text — write-temp+os.replace, no torn write visible ---
import tempfile as _tf71  # noqa: E402
import stat as _stat71  # noqa: E402
import os as _os71  # noqa: E402

with _tf71.TemporaryDirectory() as _td71:
    _p71 = Path(_td71) / "canon.md"
    _p71.write_text("OLD CONTENT", encoding="utf-8")
    sg._atomic_write_text(_p71, "NEW CONTENT")
    check("v0.1.71 D-1: _atomic_write_text produces the expected final content",
          _p71.read_text(encoding="utf-8") == "NEW CONTENT")
    check("v0.1.71 D-1: _atomic_write_text leaves no .tmp<pid> sibling behind",
          list(Path(_td71).glob("*.tmp*")) == [])

    # Sabotage-style: interrupt AFTER the temp write but BEFORE os.replace (monkeypatch os.replace
    # to raise — this patches the SAME shared `os` module object sync_global.py itself imported,
    # so it's observed there too) — the destination must be untouched, never partial.
    _p71b = Path(_td71) / "canon2.md"
    _p71b.write_text("PRE-EXISTING", encoding="utf-8")
    _real_replace71 = _os71.replace
    def _boom_replace71(*a, **kw):  # noqa: E306
        raise OSError("simulated crash between temp-write and replace")
    _os71.replace = _boom_replace71
    try:
        try:
            sg._atomic_write_text(_p71b, "WOULD-BE NEW CONTENT")
            _raised71 = False
        except OSError:
            _raised71 = True
    finally:
        _os71.replace = _real_replace71
    check("v0.1.71 D-1: an interrupted os.replace propagates (doesn't swallow the error) "
          "AND leaves the destination's pre-write content untouched (no partial/torn write)",
          _raised71 and _p71b.read_text(encoding="utf-8") == "PRE-EXISTING")
    check("v0.1.71 D-1 Gate-2b: the interrupted write leaves NO .tmp<pid> sibling behind either "
          "(the same cleanup-on-failure guarantee Gate-2a gave _create_exclusive — the parity "
          "fix _atomic_write_text was missing)",
          list(Path(_td71).glob("*.tmp*")) == [])

# --- v0.1.71 Track D-2b: _create_exclusive — atomic create-or-detect-collision, no torn-read window ---
with _tf71.TemporaryDirectory() as _td71c:
    _new71 = Path(_td71c) / "new-canon.md"
    _won71 = sg._create_exclusive(_new71, "WINNER CONTENT")
    check("v0.1.71 D-2b: _create_exclusive returns True and writes the content when the path is absent",
          _won71 is True and _new71.read_text(encoding="utf-8") == "WINNER CONTENT")
    check("v0.1.71 D-2b: _create_exclusive leaves no .tmp<pid> sibling on the success path",
          list(Path(_td71c).glob("*.tmp*")) == [])

    # The race: the destination ALREADY exists (simulating another process's concurrent create) —
    # this call must lose cleanly: return False, leave the winner's content byte-identical, leak no temp.
    _lost71 = sg._create_exclusive(_new71, "LOSER CONTENT — must never land")
    check("v0.1.71 D-2b: _create_exclusive returns False when the path already exists (lost the race)",
          _lost71 is False)
    check("v0.1.71 D-2b: the pre-existing (winner's) content is COMPLETELY untouched by the loser's attempt "
          "(the exact silent-clobber this item exists to prevent)",
          _new71.read_text(encoding="utf-8") == "WINNER CONTENT")
    check("v0.1.71 D-2b: the loser's attempt leaves no .tmp<pid> sibling behind (cleaned up in `finally`)",
          list(Path(_td71c).glob("*.tmp*")) == [])

# --- v0.1.71 Track D-3: --seed's write is hardened the same way --snapshot's already is ---
check("v0.1.71 D-3: the --seed branch calls _write_private (owner-only 0o600), not a bare write_text "
      "(was the inconsistency vs. --snapshot, which already used it)",
      "_write_private(Path(path), json.dumps(seed_record(ctx), indent=2)" in
      Path(ms.__file__).read_text(encoding="utf-8"))

with _tf71.TemporaryDirectory() as _td71p:
    _priv71 = Path(_td71p) / "seed.json"
    ms._write_private(_priv71, '{"x": 1}')
    check("v0.1.71 D-3: _write_private produces an owner-only 0o600 file (no existing test pinned "
          "this before — verified 0 hits for '_write_private'/'0o600' in tests/ pre-fix)",
          _stat71.S_IMODE(_priv71.stat().st_mode) == 0o600)

# --- v0.1.73: evict accounting truth (docs/evict-accounting-truth.spec.md) — the five audit
# repro probes, ported IN-REPO after running RED against the pre-fix tree (5/5 defects present,
# measured 2026-07-10) and GREEN after. Fixtured GLOBAL + HOME, in-process (the Phase-B pattern);
# exact-token fixtures derived from the live constants, never hardcoded to them.
import contextlib as _ctx73, io as _io73, os as _os73, tempfile as _tf73  # noqa: E401,E402


def _fact73(name: str, desc: str) -> str:
    return (f"---\nname: {name}\ndescription: \"{desc}\"\nmetadata:\n  node_type: memory\n"
            f"  scope: user-global\n  type: feedback\n---\nbody of {name}\n")


def _pad_index73(target_tokens: int, lines: list) -> str:
    """Index text whose est_tokens == target_tokens exactly, containing `lines` + one pad line."""
    base = "# Memory Index\n" + "".join(ln + "\n" for ln in lines)
    prefix = "- [zzzpad](zzzpad.md) — "
    need = target_tokens * 4 - len(base) - len(prefix) - 1
    assert need > 0, f"pad target too small (need={need})"
    text = base + prefix + "p" * need + "\n"
    assert ms.est_tokens(text) == target_tokens
    return text


class _Env73:
    """Hermetic store+global fixture: HOME and sg.GLOBAL both redirected into a tempdir."""
    def __enter__(self):
        self._td = _tf73.TemporaryDirectory(prefix="smoke73-")
        home = Path(self._td.name)
        self.proj = (home / "src" / "proj73").resolve(); self.proj.mkdir(parents=True)
        self.store = home / ".claude" / "projects" / ms.slug_for(self.proj) / "memory"
        self.store.mkdir(parents=True)
        self._home, self._global = _os73.environ.get("HOME"), sg.GLOBAL
        _os73.environ["HOME"] = str(home)
        _enroll_personal(self.proj)
        import store_context as _sc73
        _ctx73e = _sc73.resolve_store(self.proj)
        _ctx73e.canonical_domain_dir.mkdir(parents=True, exist_ok=True)
        self.glob = _ctx73e.canonical_domain_dir
        sg.GLOBAL = self.glob
        return self

    def __exit__(self, *a):
        sg.GLOBAL = self._global
        if self._home is None:
            _os73.environ.pop("HOME", None)
        else:
            _os73.environ["HOME"] = self._home
        self._td.cleanup()


def _run73(proj, evict=None):
    out, err = _io73.StringIO(), _io73.StringIO()
    with _ctx73.redirect_stdout(out), _ctx73.redirect_stderr(err):
        rc = sg.run(proj, pull=True, evict=evict)
    return rc, out.getvalue(), err.getvalue()


_C73 = ms.INDEX_CEILING_TOKENS

# F1 — a managed MIRROR is refused as evictee (pre-fix: accepted, re-pulled itself the same pass,
# the held global never landed — a destructive op that gained nothing).
with _Env73() as _e:
    (_e.glob / "aaa-m.md").write_text(_fact73("aaa-m", "short a"), encoding="utf-8")
    (_e.glob / "zzz-h.md").write_text(_fact73("zzz-h", "short z"), encoding="utf-8")
    _mir = sg._as_mirror((_e.glob / "aaa-m.md").read_text(encoding="utf-8"), "aaa-m")
    (_e.store / "aaa-m.md").write_text(_mir, encoding="utf-8")
    _lineA = sg._pointer_line("aaa-m", sg._frontmatter(_mir))
    (_e.store / "MEMORY.md").write_text(_pad_index73(_C73 - 1, [_lineA]), encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj, evict="aaa-m")
    check("v0.1.73/F1: --evict of a managed MIRROR is refused (self-defeating swap), mirror untouched",
          _rc == 1 and "managed MIRROR" in _err and (_e.store / "aaa-m.md").read_text(encoding="utf-8") == _mir)

# F2a — an UNINDEXED evictee frees nothing real: refused BEFORE any delete; the ceiling is never
# breached by phantom credit (pre-fix: deleted the fact, under-counted, real index landed ≈3857 > C).
with _Env73() as _e:
    (_e.glob / "held-g.md").write_text(_fact73("held-g", "a held global fact"), encoding="utf-8")
    (_e.store / "evictme.md").write_text(
        "---\nname: evictme\ndescription: \"local authored\"\nmetadata:\n  type: reference\n---\nlocal body\n",
        encoding="utf-8")
    (_e.store / "MEMORY.md").write_text(_pad_index73(_C73 + 2, []), encoding="utf-8")  # over ceiling; evictme NOT indexed
    _rc, _out, _err = _run73(_e.proj, evict="evictme")
    check("v0.1.73/F2a: --evict of an UNINDEXED fact is refused (freed is MEASURED, phantom credit gone) "
          "and the fact survives",
          _rc == 1 and "frees NOTHING" in _err and (_e.store / "evictme.md").exists()
          and not (_e.store / "held-g.md").exists())

# F2b — a fat HAND-WRITTEN real line is credited at its real cost: the evict is ACCEPTED and the
# held global lands (pre-fix: judged by its lean derived pointer ≈7t and refused).
with _Env73() as _e:
    (_e.glob / "held-g.md").write_text(_fact73("held-g", "a held global fact"), encoding="utf-8")
    (_e.store / "fatline.md").write_text(
        "---\nname: fatline\ndescription: \"x\"\nmetadata:\n  type: reference\n---\nbody\n", encoding="utf-8")
    _fat_real = "- [fatline](fatline.md) — " + "hand-written enormous hook " * 10
    (_e.store / "MEMORY.md").write_text(_pad_index73(_C73 + 2, [_fat_real]), encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj, evict="fatline")
    check("v0.1.73/F2b: a fat REAL index line evicts at its MEASURED cost — accepted, held global lands",
          _rc == 0 and "measured" in _err and not (_e.store / "fatline.md").exists()
          and (_e.store / "held-g.md").exists() and "pulled 1 new" in _out)

# F3 — the gain-gate: an evict whose A/B plan replay lands NO additional held global is refused and
# the authored fact SURVIVES (pre-fix: static fit-check passed, the loop's accumulation re-held the
# target, the irreplaceable authored fact was deleted for zero gain). Constraints (seed = C - fill):
# held_pre ∋ mmm ⇔ held > fill; static fit passes ⇔ freed ≥ held - fill; loop re-holds ⇔ freed < held.
with _Env73() as _e:
    (_e.glob / "aab-fill.md").write_text(_fact73("aab-fill", "ff"), encoding="utf-8")
    (_e.glob / "mmm-held.md").write_text(
        _fact73("mmm-held", "a much longer description string here to size the pointer"), encoding="utf-8")
    _cf = ms.est_tokens(sg._pointer_line("aab-fill", sg._frontmatter((_e.glob / "aab-fill.md").read_text(encoding="utf-8"))))
    _ch = ms.est_tokens(sg._pointer_line("mmm-held", sg._frontmatter((_e.glob / "mmm-held.md").read_text(encoding="utf-8"))))
    (_e.store / "evictme.md").write_text(
        "---\nname: evictme\ndescription: \"" + "d" * 50 + "\"\nmetadata:\n  type: reference\n---\nirreplaceable\n",
        encoding="utf-8")
    _evl = sg._pointer_line("evictme", sg._frontmatter((_e.store / "evictme.md").read_text(encoding="utf-8")))
    _fr = ms.est_tokens(_evl)
    assert _ch > _cf and _ch - _cf <= _fr < _ch, (_cf, _ch, _fr)
    (_e.store / "MEMORY.md").write_text(_pad_index73(_C73 - _cf, [_evl]), encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj, evict="evictme")
    check("v0.1.73/F3: a GAINLESS evict is refused by the A/B plan replay — the authored fact survives "
          "(Guard-3 by construction; was: destroyed for zero gain)",
          _rc == 1 and "gains nothing" in _err and (_e.store / "evictme.md").exists())

# F4 — a STALE refresh's pointer delta is counted before later hold decisions: the subsequent
# MISSING fact HOLDS instead of breaching (pre-fix: pulled on the stale figure, real index ≈3862 > C).
with _Env73() as _e:
    _old_canon = _fact73("aaa-stale", "old")
    (_e.glob / "aaa-stale.md").write_text(
        _fact73("aaa-stale", "a new grown description that is much much longer than before, sized near the "
                             "eighty-eight char hook cap"), encoding="utf-8")
    (_e.glob / "nnn-new.md").write_text(_fact73("nnn-new", "n" * 20), encoding="utf-8")
    (_e.store / "aaa-stale.md").write_text(sg._as_mirror(_old_canon, "aaa-stale"), encoding="utf-8")
    _oldl = sg._pointer_line("aaa-stale", sg._frontmatter(_old_canon))
    _delta = (ms.est_tokens(sg._pointer_line("aaa-stale", sg._frontmatter((_e.glob / "aaa-stale.md").read_text(encoding="utf-8"))))
              - ms.est_tokens(_oldl))
    _cn = ms.est_tokens(sg._pointer_line("nnn-new", sg._frontmatter((_e.glob / "nnn-new.md").read_text(encoding="utf-8"))))
    assert _delta > 0 and _cn > 0
    (_e.store / "MEMORY.md").write_text(_pad_index73(_C73 - _cn, [_oldl]), encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    check("v0.1.73/F4: a STALE refresh's real pointer delta is tracked — the later MISSING pull HOLDS "
          "instead of breaching the ceiling on a stale figure",
          _rc == 0 and "held 1" in _out and "refreshed 1" in _out and not (_e.store / "nnn-new.md").exists())

# The offer table — mirrors are never offered as evict candidates; authored candidates carry the
# MEASURED real-line cost (the pre-fix table listed mirrors, labeled, feeding F1's trap).
with _Env73() as _e:
    (_e.glob / "aaa-m.md").write_text(_fact73("aaa-m", "short a"), encoding="utf-8")
    (_e.glob / "zzz-h.md").write_text(_fact73("zzz-h", "short z"), encoding="utf-8")
    _mir = sg._as_mirror((_e.glob / "aaa-m.md").read_text(encoding="utf-8"), "aaa-m")
    (_e.store / "aaa-m.md").write_text(_mir, encoding="utf-8")
    (_e.store / "local-a.md").write_text(
        "---\nname: local-a\ndescription: \"authored local\"\nmetadata:\n  type: reference\n---\nbody\n",
        encoding="utf-8")
    _lla = "- [local-a](local-a.md) — authored local"
    (_e.store / "MEMORY.md").write_text(
        _pad_index73(_C73 - 1, [sg._pointer_line("aaa-m", sg._frontmatter(_mir)), _lla]), encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    _offer = _out.split("EVICT-TO-RECEIVE", 1)[1] if "EVICT-TO-RECEIVE" in _out else ""
    check("v0.1.73: the EVICT-TO-RECEIVE offer lists AUTHORED candidates only (measured cost); mirrors "
          "are never offered",
          "held 1" in _out and bool(_offer) and "local-a" in _offer and "measured" in _offer
          and "aaa-m" not in _offer)

# --- v0.1.74: _as_mirror/_body fence-boundary PARITY with _frontmatter (audit finding #1, VERIFIED
# major) — ran RED pre-fix (5/5 defects present, measured 2026-07-10). The parser closes frontmatter
# on ANY line starting '---' (`^---\n(.*?)\n---`), while _as_mirror counted only bare stripped '---'
# lines (and counted INDENTED ones the parser ignores): a non-bare close ('----', '--- notes') made
# the frontmatter-scoped strips eat BODY lines to EOF — silent mirror corruption via --pull (every
# puller) and --promote (the origin's own copy) — and an indented '---' leaked canonical-only
# 'projects:' provenance into mirrors (the v0.1.26 churn class, reopened).
_t74 = ("---\nname: x\ndescription: \"d\"\nmetadata:\n  node_type: memory\n  scope: user-global\n"
        "----\nBody first line.\nglobal_ref: a body line about the mirror mechanism\n"
        "projects: a body line listing projects\nlast body line\n")
check("v0.1.74: the fixture's non-bare close ('----') IS a parser-valid frontmatter close (the fact "
      "parses relevant/replicable — the corruption was reachable, not contrived)",
      ms._frontmatter(_t74).get("scope") == "user-global")
_m74 = sg._as_mirror(_t74, "x")
check("v0.1.74: through a '----' close, body lines starting 'projects:'/'global_ref:' SURVIVE mirroring "
      "(were eaten to EOF pre-fix; fence parity with _frontmatter/_is_mirror)",
      "projects: a body line listing projects" in _m74
      and "global_ref: a body line about the mirror mechanism" in _m74
      and "Body first line." in _m74 and "last body line" in _m74)
check("v0.1.74: the '----'-fenced mirror still ROUND-TRIPS (_is_mirror recognizes the stamp) and "
      "_as_mirror stays idempotent on it",
      ms._is_mirror(_m74) and sg._as_mirror(_m74, "x") == _m74)
_t74b = ("---\nname: z\ndescription: \"d\"\nnotes: |\n  ---\nmetadata:\n  scope: user-global\n"
         "  projects: [alpha]\n---\nbody\n")
check("v0.1.74: an INDENTED '  ---' is NOT a close fence (parser parity) — canonical-only 'projects:' "
      "provenance is still STRIPPED from the mirror (v0.1.26 stays closed; was leaked by the early close)",
      "projects: [alpha]" not in sg._as_mirror(_t74b, "z") and ms._is_mirror(sg._as_mirror(_t74b, "z")))
check("v0.1.74: _body strips a frontmatter block closed at EOF (no trailing newline) AND consumes a "
      "non-bare close line whole",
      sg._body("---\nscope: x\n---") == "" and sg._body("---\nscope: x\n--- tail\nreal body\n") == "real body")
check("v0.1.74: _bodies_match TRUE for two body-less facts with differing frontmatter "
      "(was a spurious promote Guard-5 'body differs' refusal)",
      sg._bodies_match("---\nscope: user-global\n---", "---\nscope: stack-general\nstacks: [gpu]\n---") is True)

# --- v0.1.75: pull-side guards (audit F5/F6/F7) — ran RED pre-fix (3/3 defects present, 2026-07-10):
# a fleet-dead canonical was invisible, a typo'd PROJECT_DIR minted a phantom store + polluted shared
# provenance, and a relevance-flipped mirror froze forever with no surfacing and no reclaim lever.
with _Env73() as _e:
    (_e.glob / "dead-tag.md").write_text(
        "---\nname: dead-tag\ndescription: \"d\"\nmetadata:\n  scope: stack-general\n  stacks: [release]\n"
        "  type: feedback\n---\nbody\n", encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    check("v0.1.75/F7: the read path warns on a FLEET-DEAD stack-general canonical (undetectable stacks "
          "tag — the M4 bypass via the SKILL's net-new hand-write path, surfaced every dream's Phase 1)",
          _rc == 0 and "fleet-dead canonical: 'dead-tag'" in _err and "release" in _err)

check("v0.1.75/F5: run() refuses a nonexistent project dir up front (phantom-store guard, rc=2, "
      "defense-in-depth behind _dispatch's CLI guard — sim Probe W pins the CLI half)",
      sg.run(Path("/nonexistent/typo-proj-xyz"), pull=True) == 2)

with _Env73() as _e:
    # F6 frozen-mirror lifecycle: relevant → pulled → stack dropped → FROZEN (distinct render) →
    # gc reports → gc --apply reclaims → stack returns → --pull re-pulls (safe by construction).
    (_e.proj / "pyproject.toml").write_text('[project]\nname = "p"\ndependencies = ["lancedb"]\n', encoding="utf-8")
    (_e.proj / "main.py").write_text("x = 1\n", encoding="utf-8")
    (_e.glob / "rag-tip.md").write_text(
        "---\nname: rag-tip\ndescription: \"r\"\nmetadata:\n  scope: stack-general\n  stacks: [rag]\n"
        "  type: feedback\n---\nbody\n", encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    _run73(_e.proj)
    check("v0.1.75/F6 setup: the rag mirror pulled while the stack was live", (_e.store / "rag-tip.md").exists())
    (_e.proj / "pyproject.toml").write_text('[project]\nname = "p"\ndependencies = []\n', encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    check("v0.1.75/F6: a dropped stack renders the mirror FROZEN, distinctly (was byte-identical to a "
          "never-pulled 'irrelevant' row)",
          "frozen(mirror)" in _out and "frozen mirror(s)" in _out)
    _g75a = _io73.StringIO()
    with _ctx73.redirect_stdout(_g75a):
        sg.gc(_e.proj, apply=False)
    check("v0.1.75/F6: gc REPORTS the frozen mirror (report-only default; file untouched)",
          "FROZEN" in _g75a.getvalue() and "rag-tip" in _g75a.getvalue() and (_e.store / "rag-tip.md").exists())
    _g75b = _io73.StringIO()
    with _ctx73.redirect_stdout(_g75b):
        sg.gc(_e.proj, apply=True)
    check("v0.1.75/F6: gc --apply reclaims the frozen mirror (file + index pointer)",
          not (_e.store / "rag-tip.md").exists()
          and "(rag-tip.md)" not in (_e.store / "MEMORY.md").read_text(encoding="utf-8"))
    (_e.proj / "pyproject.toml").write_text('[project]\nname = "p"\ndependencies = ["lancedb"]\n', encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    check("v0.1.75/F6: the reclaim is SAFE BY CONSTRUCTION — the stack's return re-pulls the mirror "
          "(replica of a live canonical; no memory can be lost)",
          "pulled 1 new" in _out and (_e.store / "rag-tip.md").exists())

# --- v0.1.76: robustness batch (audit minors) — every check ran RED pre-fix (7/7, 2026-07-10). ---
check("v0.1.76/a: _holders parses the SAME token space _sanitize_token writes — dot/dash-prefixed "
      "holders survive whole ('.claude' was read back as 'claude'); separator noise still dropped",
      sg._holders({"projects": "[.claude, -scope, job-app]"}) == [".claude", "-scope", "job-app"]
      and sg._holders({"projects": "[a]"}) == ["a"]
      and sg._holders({"projects": "[-, .]"}) == [])
check("v0.1.76/f: a poetry DOTTED subtable dep ([tool.poetry.dependencies.torch]) is parsed "
      "(was invisible to the key-scan); the inline form still works",
      "torch" in sg._dep_names_from_text('[tool.poetry.dependencies.torch]\nversion = "^2.0"\n')
      and "torch" in sg._dep_names_from_text('[tool.poetry.dependencies]\ntorch = "^2.0"\n'))
with _tf73.TemporaryDirectory() as _td76:
    _p76 = Path(_td76); (_p76 / "main.py").write_text("x=1\n", encoding="utf-8")
    (_p76 / ".mypy.ini").write_text("[mypy]\nstrict = True\n", encoding="utf-8")
    _s76a = sg.detect_stacks(_p76)
with _tf73.TemporaryDirectory() as _td76b:
    _p76b = Path(_td76b); (_p76b / "main.py").write_text("x=1\n", encoding="utf-8")
    (_p76b / "setup.cfg").write_text("[metadata]\nname = x\n[mypy]\nstrict = True\n", encoding="utf-8")
    _s76b = sg.detect_stacks(_p76b)
check("v0.1.76/e: .mypy.ini AND setup.cfg [mypy] both detect the mypy stack (all four documented "
      "config locations; was pyproject+mypy.ini only — under-detection on a mypy-heavy fleet)",
      "mypy" in _s76a and "mypy" in _s76b)
with _tf73.TemporaryDirectory() as _td76c:
    _st76 = Path(_td76c)
    (_st76 / "MEMORY.md").write_text("# Memory Index\n- [f](f.md) — h\n", encoding="utf-8")
    (_st76 / "f.md").write_text("---\nname: f\n---\nbody\n", encoding="utf-8")
    (_st76 / "SHIPPED.md").write_text("# Shipped\n- [a](a.md) — x\n- [b](b.md) — y\n- [c](c.md) — z\n",
                                      encoding="utf-8")
    _nt76 = sg._node_tokens(_st76)
    check("v0.1.76/g: _node_tokens excludes an archive-index doc from recall facts/tokens "
          "(memory_status's own C1 split, applied to --tokens — a live SHIPPED.md inflated both)",
          _nt76["facts"] == 1 and _nt76["recall_tokens"] == ms.est_tokens("---\nname: f\n---\nbody\n"))
    check("graph-split: a local-only store reports 0 universal / 0 stack / 0 shared (keys present)",
          _nt76.get("universal") == 0 and _nt76.get("stack") == 0 and _nt76.get("shared") == 0)

# --- Shared-consciousness split: everyone-holds vs this-stack (HTML graph data) ---
_ug_body = ("---\nname: ug\ndescription: \"d\"\nmetadata:\n  node_type: memory\n"
            "  scope: user-global\n---\nug-body\n")
_st_body = ("---\nname: st\ndescription: \"d\"\nmetadata:\n  node_type: memory\n"
            "  scope: stack-general\n  stacks: [python]\n---\nst-body\n")
with _tf73.TemporaryDirectory() as _td_share:
    _st_share = Path(_td_share)
    (_st_share / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    (_st_share / "ug.md").write_text(sg._as_mirror(_ug_body, "ug"), encoding="utf-8")
    (_st_share / "st.md").write_text(sg._as_mirror(_st_body, "st"), encoding="utf-8")
    (_st_share / "local.md").write_text("---\nname: local\n---\nonly here\n", encoding="utf-8")
    _nt_share = sg._node_tokens(_st_share)
    check("graph-split: _node_tokens splits mixed shared into universal + stack (local stays in facts)",
          _nt_share["facts"] == 3 and _nt_share["shared"] == 2
          and _nt_share["universal"] == 1 and _nt_share["stack"] == 1)
# canon fallback: a scope-less mirror still classifies when the canonical map is passed
with _tf73.TemporaryDirectory() as _td_fb:
    _st_fb = Path(_td_fb)
    (_st_fb / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    (_st_fb / "st.md").write_text("---\nname: st\nmetadata:\n  global_ref: st\n---\nbody\n", encoding="utf-8")
    _nt_bare = sg._node_tokens(_st_fb)
    _nt_fb = sg._node_tokens(_st_fb, {"st": "stack-general"})
    check("graph-split: a scope-less mirror is unclassified without the canonical, stack with it",
          _nt_bare["shared"] == 1 and _nt_bare["stack"] == 0 and _nt_bare["universal"] == 0
          and _nt_fb["stack"] == 1 and _nt_fb["universal"] == 0)
check("graph-split: _pairwise_stack_edges emits only n>0 pairs, stable (weight desc, then names)",
      sg._pairwise_stack_edges({"A": {"x", "y"}, "B": {"y", "z"}, "C": {"x"}})
      == [{"a": "A", "b": "B", "n": 1}, {"a": "A", "b": "C", "n": 1}])
with _Env73() as _e:
    (_e.glob / "ug.md").write_text(_ug_body, encoding="utf-8")
    (_e.glob / "st.md").write_text(_st_body, encoding="utf-8")
    (_e.store / "ug.md").write_text(sg._as_mirror(_ug_body, "ug"), encoding="utf-8")
    (_e.store / "st.md").write_text(sg._as_mirror(_st_body, "st"), encoding="utf-8")
    (_e.store / "local.md").write_text("---\nname: local\n---\nonly here\n", encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    _sib = Path(_os73.environ["HOME"]) / ".claude" / "projects" / "-sib-proj" / "memory"
    _sib.mkdir(parents=True)
    (_sib / "ug.md").write_text(sg._as_mirror(_ug_body, "ug"), encoding="utf-8")
    (_sib / "st.md").write_text(sg._as_mirror(_st_body, "st"), encoding="utf-8")
    (_sib / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    _net_share = sg.token_network(_e.proj)
    _edges = _net_share.get("stack_edges") or []
    _nodes_by = {n["node"]: n for n in _net_share["nodes"]}
    _trig = _nodes_by.get("proj73") or next(n for n in _net_share["nodes"] if n.get("trigger"))
    check("graph-split: token_network emits unique totals + one this-stack edge (not mixed shared)",
          _net_share["totals"].get("universal") == 1
          and _net_share["totals"].get("stack") == 1
          and _trig["facts"] == 3 and _trig["shared"] == 2
          and _trig["universal"] == 1 and _trig["stack"] == 1
          and len(_net_share["nodes"]) == 2
          and len(_edges) == 1 and _edges[0]["n"] == 1)
check("graph-split: validate_cycle_record warns on a non-list stack_edges (never crashes)",
      any("stack_edges is not a list" in w for w in
          ms.validate_cycle_record({"network": {"stack_edges": "nope"}})))
_split_ascii = rd.render(cast(ms.CycleRecord, {
    "project": "p", "session": "s", "scope": {}, "entries": [],
    "network": {"basis": "x", "trigger": "p",
                "nodes": [{"node": "p", "trigger": True, "always_loaded_tokens": 10,
                           "recall_tokens": 20, "facts": 3, "shared": 2,
                           "universal": 1, "stack": 1}],
                "stack_edges": [{"a": "p", "b": "q", "n": 1}],
                "totals": {"nodes": 1, "always_loaded_tokens": 10, "recall_tokens": 20,
                           "universal": 1, "stack": 1}}}))
check("graph-split: ASCII dashboard names the baseline / this-stack split when the keys are present",
      "baseline" in _split_ascii and "this-stack" in _split_ascii)
_legacy_ascii = rd.render(cast(ms.CycleRecord, {
    "project": "p", "session": "s", "scope": {}, "entries": [],
    "network": {"basis": "x", "trigger": "p",
                "nodes": [{"node": "p", "trigger": True, "always_loaded_tokens": 10,
                           "recall_tokens": 20, "facts": 2, "shared": 1}],
                "totals": {"nodes": 1, "always_loaded_tokens": 10, "recall_tokens": 20}}}))
check("graph-split: ASCII dashboard stays silent on the split for a pre-split (legacy) record",
      "this-stack" not in _legacy_ascii and "NEURAL NETWORK" in _legacy_ascii)
with _Env73() as _e:
    (_e.glob / "gfact.md").write_text(
        "---\nname: gfact\ndescription: \"d\"\nmetadata:\n  scope: user-global\n"
        "  projects: [ghost-proj, proj73]\n  type: feedback\n---\nbody\n", encoding="utf-8")
    _seed_holders(_e.proj, "gfact", ["ghost-proj", "proj73"])
    _nout = _io73.StringIO()
    with _ctx73.redirect_stdout(_nout):
        sg.network(_e.proj)
    _no = _nout.getvalue()
    check("v0.1.76/h: network() flags a DEAD provenance mind with '?' + footnote (display-only; the "
          "live mind — whose slug store exists — is unflagged)",
          "ghost-proj?" in _no and "proj73?" not in _no and "no matching store" in _no)
with _Env73() as _e:
    (_e.glob / "git-fact.md").write_text(
        "---\nname: git-fact\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: project\n---\nbody\n",
        encoding="utf-8")
    (_e.glob / "bad-osid.md").write_text(
        "---\nname: bad-osid\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: project\n"
        "  originSessionId: not-a-uuid\n---\nbody\n", encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    check("v0.1.76/i: originSessionId warn split — ABSENT is silent (legitimate for git-derived facts "
          "per harness-map), present-but-INVALID still warns",
          "git-fact" not in _err and "bad-osid" in _err and "INVALID originSessionId" in _err)
with _Env73() as _e:
    (_e.store / "loc.md").write_text(
        "---\nname: loc\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: feedback\n---\nbody\n",
        encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n- [loc](loc.md) — d\n", encoding="utf-8")
    _orig_link76 = _os73.link

    def _no_link76(*a, **k):
        raise PermissionError(1, "Operation not permitted (fixture: no-hardlink fs)")
    _os73.link = _no_link76
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()) as _perr76:
            _rc76 = sg.promote(_e.proj, "loc", "loc")
    finally:
        _os73.link = _orig_link76
    import store_context as _sc76
    _canon76 = _sc76.resolve_store(_e.proj).canonical_domain_dir / "loc.md"
    check("v0.1.76/b: promote on a no-hardlink filesystem still CREATES via upsert/os.replace "
          "(hardlink is no longer the ingress; local is converted to a mirror)",
          _rc76 == 0 and _canon76.exists()
          and (_e.store / "loc.md").exists() and "global_ref:" in (_e.store / "loc.md").read_text(encoding="utf-8")
          and list(_canon76.parent.glob("*.tmp*")) == [])

# --- v0.1.78: evidence-clock stamps (docs/evidence-clock-stamps.spec.md — audit F9's starvation fix).
# RED pre-fix (measured): one probative window accrued, one DESCRIPTION-only canonical edit + --pull,
# fleet windows 1 → 0 (mtime clock wiped by the refresh). Post-fix: carried lineage preserves them;
# a BODY edit still resets (old zero-reads don't indict new content).
_t78 = ("---\nname: cx\ndescription: \"v1\"\nmetadata:\n  node_type: memory\n  scope: user-global\n"
        "  type: feedback\n---\nthe body\n")
_m78 = sg._as_mirror(_t78, "cx", since="2026-01-05T00:00:00Z", body_hash=sg._body_hash(_t78))
check("v0.1.78: a stamped mirror round-trips — _is_mirror recognizes it, _frontmatter reads both stamps "
      "back, and the body hash is the BODY-only sha1-12",
      ms._is_mirror(_m78) and ms._frontmatter(_m78).get("global_ref_since") == "2026-01-05T00:00:00Z"
      and ms._frontmatter(_m78).get("global_ref_body") == sg._body_hash(_t78)
      and sg._body_hash(_t78) == sg._body_hash(_t78.replace('description: "v1"', 'description: "v2 changed"')))


def _uw78(window, per_fact):
    return _jsonB.dumps({"usage": {"window": window, "transcripts": 1, "dream_excluded": 0,
                                   "reads": sum(f.get("reads", 0) for f in per_fact),
                                   "facts_read": len(per_fact), "per_fact": per_fact}})


def _canon78(desc, body):
    return (f"---\nname: canon-x\ndescription: \"{desc}\"\nmetadata:\n  node_type: memory\n"
            f"  scope: user-global\n  type: feedback\n---\n{body}\n")


import re as _re78  # noqa: E402
with _Env73() as _e:
    (_e.glob / "canon-x.md").write_text(_canon78("v1 description", "the body"), encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    _run73(_e.proj)
    # backdate the mirror's LINEAGE stamp so a probative window can start after it (the fact-age rule)
    _mir78 = _re78.sub(r"(?m)^  global_ref_since: .*$", "  global_ref_since: 2025-12-01T00:00:00Z",
                       (_e.store / "canon-x.md").read_text(encoding="utf-8"))
    (_e.store / "canon-x.md").write_text(_mir78, encoding="utf-8")
    (_e.store / ".consolidation-log.jsonl").write_text(
        _uw78("2026-01-01T00:00:00Z..2026-01-02T00:00:00Z", [{"name": "other", "reads": 1, "last": "t"}]) + "\n",
        encoding="utf-8")
    _w78 = lambda: {x["name"]: x for x in sg.fleet_utility(_e.proj)["canonicals"]}["canon-x"]["windows"]  # noqa: E731
    _w0 = _w78()
    (_e.glob / "canon-x.md").write_text(_canon78("v2 description grew much longer", "the body"), encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    _w1 = _w78()
    check("v0.1.78: a DESCRIPTION-only canonical edit + refresh PRESERVES accrued fleet windows "
          "(was 1→0, the F9 starvation; the refreshed mirror carries its lineage stamp)",
          _w0 == 1 and _w1 == 1 and "refreshed 1" in _out)
    _in_sync = _run73(_e.proj)
    check("v0.1.78: the carry is STABLE — an immediate re-pull is in-sync (no refresh churn from the stamps)",
          "refreshed 0" in _in_sync[1] and "pulled 0" in _in_sync[1])
    (_e.glob / "canon-x.md").write_text(_canon78("v2 description grew much longer", "a genuinely NEW body"),
                                        encoding="utf-8")
    _run73(_e.proj)
    check("v0.1.78: a BODY edit RESETS the lineage (windows → 0 — old zero-reads don't indict new content)",
          _w78() == 0)

with _Env73() as _e:
    # legacy migration wave: an UNSTAMPED (pre-upgrade) mirror refreshes → since seeds from its
    # mtime (never now() — don't restart the fleet's evidence from zero) and RESULT says restamped.
    (_e.glob / "canon-x.md").write_text(_canon78("v1", "the body"), encoding="utf-8")
    _legacy78 = sg._as_mirror((_e.glob / "canon-x.md").read_text(encoding="utf-8"), "canon-x")  # bare = no stamps
    (_e.store / "canon-x.md").write_text(_legacy78, encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n- [canon-x](canon-x.md) — v1 [user-global]\n",
                                        encoding="utf-8")
    _old78 = ms._parse_ts("2025-12-01T00:00:00Z")
    assert _old78 is not None
    _osB.utime(_e.store / "canon-x.md", (_old78.timestamp(), _old78.timestamp()))
    (_e.store / ".consolidation-log.jsonl").write_text(
        _uw78("2026-01-01T00:00:00Z..2026-01-02T00:00:00Z", [{"name": "other", "reads": 1, "last": "t"}]) + "\n",
        encoding="utf-8")
    _fu78 = {x["name"]: x for x in sg.fleet_utility(_e.proj)["canonicals"]}["canon-x"]
    check("v0.1.78: an UNSTAMPED mirror stays on the mtime fallback clock, disclosed via fallback_nodes",
          _fu78["windows"] == 1 and _fu78.get("fallback_nodes") == 1)
    _rc, _out, _err = _run73(_e.proj)   # description unchanged → but legacy mirror lacks stamps → STALE
    _fu78b = {x["name"]: x for x in sg.fleet_utility(_e.proj)["canonicals"]}["canon-x"]
    check("v0.1.78: the migration wave restamps a legacy mirror — since seeds from its OLD mtime, so the "
          "accrued window SURVIVES the upgrade refresh, and RESULT reports 'restamped'",
          "restamped 1" in _out and _fu78b["windows"] == 1 and "fallback_nodes" not in _fu78b)

# --- PR-#91 review-team pins (three LOW findings, fixed on-branch before merge) ---
_t78r = ("---\nname: gr\ndescription: >-\n  global_reference architecture notes for the fleet\n"
         "global_reference: a-legit-hypothetical-key\nmetadata:\n  node_type: memory\n"
         "  scope: user-global\n  type: feedback\n---\nbody\n")
_m78r = sg._as_mirror(_t78r, "gr", since="2026-01-05T00:00:00Z", body_hash=sg._body_hash(_t78r))
check("v0.1.78/review-F1: the stamp strip targets the EXACT three keys — a folded-scalar description "
      "continuation beginning 'global_reference' AND a 'global_reference:' frontmatter key both SURVIVE "
      "mirroring (the wide 'global_ref' prefix re-ate what the v0.1.70 narrowing protects)",
      "global_reference architecture notes for the fleet" in _m78r
      and "global_reference: a-legit-hypothetical-key" in _m78r
      and ms._is_mirror(_m78r) and "global_ref_since: 2026-01-05T00:00:00Z" in _m78r)
check("v0.1.78/review-F3: stamp seconds are CEILED, never floored — a floored clock would over-credit a "
      "window starting inside [floor(t), t) against the pinned undercount bias",
      sg._ceil_iso(100.2) == "1970-01-01T00:01:41Z" and sg._ceil_iso(100.0) == "1970-01-01T00:01:40Z")
with _Env73() as _e:
    (_e.glob / "nm.md").write_text("---\nname: nm\ndescription: \"v1\"\nscope: user-global\n---\nbody\n",
                                   encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    _run73(_e.proj)
    _nm = (_e.store / "nm.md").read_text(encoding="utf-8") if (_e.store / "nm.md").exists() else ""
    check("v0.1.78/review-F2a: a no-metadata canonical still receives a metadata mirror block",
          "canonical_fact_id:" in _nm and "  global_ref:" in _nm and "canonical_domain:" in _nm)

# --- v0.1.79: fleet usage HARVEST (docs/fleet-usage-harvest.spec.md — audit enhancement P1).
# RED baseline (measured): a node holding a mirror, a real organic Read in its transcript, NO cycle
# log → fleet_utility reads=0/windows=0/nodes_reporting=0 — the evidence rotting unobserved (live
# fleet: 1/3 nodes reporting). The harvest captures it into the shared 0o600 ledger, watermarked.
import stat as _stat79  # noqa: E402
with _Env73() as _e:
    _ct79 = ("---\nname: canon-x\ndescription: \"d\"\nmetadata:\n  node_type: memory\n"
             "  scope: user-global\n  type: feedback\n  projects: [nodeB]\n---\nbody\n")
    (_e.glob / "canon-x.md").write_text(_ct79, encoding="utf-8")
    _nB79 = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-nodeB" / "memory"
    _nB79.mkdir(parents=True)
    (_nB79 / "canon-x.md").write_text(sg._as_mirror(_ct79, "canon-x", since="2025-12-01T00:00:00Z",
                                                    body_hash=sg._body_hash(_ct79)), encoding="utf-8")
    (_nB79.parent / "sess1.jsonl").write_text(_jsonB.dumps({
        "timestamp": "2026-01-15T10:00:00Z",
        "message": {"content": [{"type": "tool_use", "name": "Read",
                                 "input": {"file_path": str(_nB79 / "canon-x.md")}}]}}) + "\n", encoding="utf-8")
    _fu79pre = sg.fleet_utility(_e.proj)
    _e79pre = {x["name"]: x for x in _fu79pre["canonicals"]}["canon-x"]
    check("v0.1.79: PRE-harvest, a non-dreaming node's organic read is invisible (the measured hole: "
          "reads=0, no harvested keys, nodes_reporting=0)",
          _e79pre["reads"] == 0 and "harvested_reads" not in _e79pre and _fu79pre["nodes_reporting"] == 0)
    _hout79 = _io73.StringIO()
    with _ctx73.redirect_stdout(_hout79):
        _hrc79a = sg.harvest(_e.proj)
    with _ctx73.redirect_stdout(_io73.StringIO()):
        _hrc79b = sg.harvest(_e.proj)   # idempotence: watermark makes the re-run a no-op
    from store_context import plugin_data_dir as _pdd79
    _lp79 = _pdd79() / "fleet-usage.jsonl"
    _rows79 = _lp79.read_text(encoding="utf-8").splitlines()
    _w79 = _jsonB.loads(_rows79[0])["window"]
    _s79raw, _end79raw = _w79.split("..")
    _s79dt, _end79dt = ms._parse_ts(_s79raw), ms._parse_ts(_end79raw)
    check("v0.1.79: --harvest appends ONE 0o600 ledger row (start ≤ end), reports the capture, and a "
          "re-run appends NOTHING (watermark idempotence — evidence accrues from time, not invocations)",
          _hrc79a == 0 and _hrc79b == 0 and len(_rows79) == 1
          and _stat79.S_IMODE(_lp79.stat().st_mode) == 0o600
          and _s79dt is not None and _end79dt is not None
          and _s79dt.timestamp() <= _end79dt.timestamp()
          and "organic reads 1" in _hout79.getvalue()
          and not (_e.glob / ".fleet-usage.jsonl").exists())
    _fu79 = sg.fleet_utility(_e.proj)
    _e79 = {x["name"]: x for x in _fu79["canonicals"]}["canon-x"]
    check("v0.1.79: --utility surfaces the harvested evidence SOURCE-LABELED for the no-own-usage node "
          "(harvested_reads/windows_harvested — never blended into own-log reads)",
          _e79["reads"] == 0 and _e79.get("harvested_reads") == 1 and _e79.get("windows_harvested") == 1
          and _fu79["nodes_harvested"] == 1 and _e79["last"] == "2026-01-15T10:00:00Z")
    with _lp79.open("a", encoding="utf-8") as _f79:
        _f79.write("NOT JSON — a torn/garbage ledger line\n")
    check("v0.1.79: a garbage ledger line is skipped, never fatal",
          {x["name"]: x for x in sg.fleet_utility(_e.proj)["canonicals"]}["canon-x"].get("harvested_reads") == 1)
    # own-log strictly primary (the v1 rule): once the node has ANY own usage, its harvested rows
    # are ignored entirely — no interval math, no double-count.
    (_nB79 / ".consolidation-log.jsonl").write_text(
        _uw78("2026-02-01T00:00:00Z..2026-02-02T00:00:00Z", [{"name": "canon-x", "reads": 2, "last": "2026-02-01T12:00:00Z"}]) + "\n",
        encoding="utf-8")
    _fu79b = sg.fleet_utility(_e.proj)
    _e79b = {x["name"]: x for x in _fu79b["canonicals"]}["canon-x"]
    check("v0.1.79: a node WITH own-log usage ignores its harvested rows (own-log strictly primary — "
          "the v1 no-double-count rule), own reads attributed normally",
          _e79b["reads"] == 2 and "harvested_reads" not in _e79b and _fu79b["nodes_harvested"] == 0)

# --- v0.1.80: fleet STALENESS (docs/fleet-staleness-report.spec.md — beacon Stage A). The blind
# spot is structural: absorption latency was unbounded AND unmeasured (a lagging node by definition
# never runs the only flows that report lag). Live first-run proof: a real node 18d behind with 11
# missing globals + 4 content-stale mirrors, previously invisible.
with _Env73() as _e:
    def _canon80(name, body):
        return (f"---\nname: {name}\ndescription: \"d\"\nmetadata:\n  node_type: memory\n"
                f"  scope: user-global\n  type: feedback\n---\n{body}\n")
    (_e.glob / "g-one.md").write_text(_canon80("g-one", "body one"), encoding="utf-8")
    (_e.glob / "g-two.md").write_text(_canon80("g-two", "body two"), encoding="utf-8")
    _nA80 = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-fresh" / "memory"
    _nA80.mkdir(parents=True)
    for _n80 in ("g-one", "g-two"):
        _t80 = (_e.glob / f"{_n80}.md").read_text(encoding="utf-8")
        (_nA80 / f"{_n80}.md").write_text(sg._as_mirror(_t80, _n80, since="2026-07-01T00:00:00Z",
                                                        body_hash=sg._body_hash(_t80)), encoding="utf-8")
    (_nA80 / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    (_nA80 / ".consolidation-state.json").write_text(
        _jsonB.dumps({"commit": "x", "timestamp": "2026-07-09T00:00:00Z"}), encoding="utf-8")
    _nB80 = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-starved" / "memory"
    _nB80.mkdir(parents=True)
    _old80 = _canon80("g-one", "an OLD body")
    (_nB80 / "g-one.md").write_text(sg._as_mirror(_old80, "g-one", since="2026-01-01T00:00:00Z",
                                                  body_hash=sg._body_hash(_old80)), encoding="utf-8")
    (_nB80 / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")   # the trigger's own store
    import hashlib as _hl80

    def _hash80(root: Path) -> dict:
        """Content hashes of store files. Ignore sqlite sidecars a readonly
        open of a WAL DB may create (`-wal`/`-shm`) — those are not fact writes."""
        out = {}
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix in (".sqlite", ".lock") or p.name.endswith(("-wal", "-shm", ".lock")):
                continue
            out[p] = _hl80.sha1(p.read_bytes()).hexdigest()
        return out

    _pre80 = _hash80(Path(_osB.environ["HOME"]) / ".claude")
    _s80 = sg.fleet_staleness(_e.proj)
    _post80 = _hash80(Path(_osB.environ["HOME"]) / ".claude")
    _by80 = {d["node"]: d for d in _s80["nodes"]}
    check("v0.1.80: fleet_staleness measures the starved node exactly — never-dreamed (age null-safe), "
          "1 missing user-global, 1 content-stale mirror — and the fresh node reads clean",
          _by80["src-starved"]["missing_globals"] == 1 and _by80["src-starved"]["stale_mirrors"] == 1
          and _by80["src-starved"]["age_days"] is None and _by80["src-starved"]["last_dream"] == ""
          and _by80["src-fresh"]["missing_globals"] == 0 and _by80["src-fresh"]["stale_mirrors"] == 0
          and _by80["src-fresh"]["age_days"] is not None
          and _s80["behind"] == 2 and _s80["never_dreamed"] == 2)   # starved + the trigger's own empty store
    check("v0.1.80: scope basis is HONEST per node — full (live stacks) only for the trigger; non-trigger "
          "nodes labeled user-global-only (a slug is never guessed back to a path)",
          _by80["src-starved"]["scope_basis"] == "user-global only (no stacks cache)"
          and {d["node"]: d for d in _s80["nodes"] if d["trigger"]} != {}
          and all(d["scope_basis"] == "full (live stacks)" for d in _s80["nodes"] if d["trigger"]))
    check("v0.1.80: the sweep is READ-ONLY over every store, and the payload is JSON-safe (null age)",
          _pre80 == _post80 and isinstance(_jsonB.dumps(_s80), str))

# --- PR-#93 review-team pins (two reviewers, convergent top finding) ---
with _Env73() as _e:
    # F1: an EMPTY trigger store (0 *.md) — previously silently omitted from its own report, the
    # maximally-starved case. Now force-appended (the harvest/fleet_utility precedent).
    (_e.glob / "g-one.md").write_text(
        "---\nname: g-one\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: feedback\n---\nb\n",
        encoding="utf-8")
    _s93 = sg.fleet_staleness(_e.proj)
    _trig93 = [d for d in _s93["nodes"] if d["trigger"]]
    check("v0.1.80/review-F1: an EMPTY trigger store still yields the trigger row — never-dreamed, "
          "all relevant globals MISSING (was: silently omitted from its own report)",
          len(_trig93) == 1 and _trig93[0]["missing_globals"] == 1 and _trig93[0]["age_days"] is None
          and _s93["behind"] >= 1 and _s93["never_dreamed"] >= 1)
    # F3: a present-but-MALFORMED marker must read as never-dreamed EVERYWHERE (render, sort, and
    # the aggregate — the old aggregate keyed on last_dream=="" and contradicted the row display).
    _nM93 = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-badmarker" / "memory"
    _nM93.mkdir(parents=True)
    (_nM93 / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    (_nM93 / ".consolidation-state.json").write_text(
        _jsonB.dumps({"commit": "x", "timestamp": "not-a-date"}), encoding="utf-8")
    _s93b = sg.fleet_staleness(_e.proj)
    _bad93 = [d for d in _s93b["nodes"] if d["node"] == "src-badmarker"][0]
    check("v0.1.80/review-F3: a present-but-UNPARSEABLE marker counts as never-dreamed in the "
          "AGGREGATE too (age_days is the one predicate; raw marker kept in last_dream for audit)",
          _bad93["age_days"] is None and _bad93["last_dream"] == "not-a-date"
          and _s93b["never_dreamed"] == 2)   # the empty trigger + the bad-marker node

# --- Pre-merge train-review pins (#86/#88/#89 merge-gate team, 2026-07-10) ---
with _Env73() as _e:
    # F-A (HIGH, verified E2E by the reviewer): the LATERAL-SWAP evict — freeing room lets the
    # alphabetically-earlier LARGER global (aaa) displace the later smaller one (zzz): old
    # set-difference gate ACCEPTED (gain=['aaa']) and destroyed the authored fact for zero net
    # gain; the count gate must REFUSE. Constraints (seed = C - cost_zzz): cost_aaa > cost_zzz;
    # freed ∈ [cost_aaa - cost_zzz, cost_aaa).
    (_e.glob / "aaa-big.md").write_text(_fact73("aaa-big", "a deliberately much longer description "
                                                "string to fatten this pointer"), encoding="utf-8")
    (_e.glob / "zzz-sml.md").write_text(_fact73("zzz-sml", "s"), encoding="utf-8")
    _cA = ms.est_tokens(sg._pointer_line("aaa-big", sg._frontmatter((_e.glob / "aaa-big.md").read_text(encoding="utf-8"))))
    _cZ = ms.est_tokens(sg._pointer_line("zzz-sml", sg._frontmatter((_e.glob / "zzz-sml.md").read_text(encoding="utf-8"))))
    (_e.store / "evictme.md").write_text(
        "---\nname: evictme\ndescription: \"" + "d" * 64 + "\"\nmetadata:\n  type: reference\n---\nirreplaceable\n",
        encoding="utf-8")
    _evl86 = sg._pointer_line("evictme", sg._frontmatter((_e.store / "evictme.md").read_text(encoding="utf-8")))
    _fr86 = ms.est_tokens(_evl86)
    assert _cA > _cZ and _cA - _cZ <= _fr86 < _cA, (_cA, _cZ, _fr86)
    (_e.store / "MEMORY.md").write_text(_pad_index73(_C73 - _cZ, [_evl86]), encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj, evict="evictme")
    check("train-review/F-A: a LATERAL-SWAP evict is REFUSED by the count gate (earlier-bigger global "
          "would displace the later-smaller one — gain non-empty, count unchanged; the authored fact "
          "survives; was: destroyed for zero net gain with a '✓ lands:' success message)",
          _rc == 1 and "lateral swap" in _err and (_e.store / "evictme.md").exists()
          and "gains nothing" in _err)

with _Env73() as _e:
    # F-B: MIXED stack tags ([python, fastpai]) are NOT fleet-dead — the blanket "can never match
    # any project" wording was false for them; they get the dead-weight wording instead.
    (_e.glob / "mixed-tag.md").write_text(
        "---\nname: mixed-tag\ndescription: \"d\"\nmetadata:\n  scope: stack-general\n"
        "  stacks: [python, fastpai]\n  type: feedback\n---\nbody\n", encoding="utf-8")
    (_e.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    _rc, _out, _err = _run73(_e.proj)
    check("train-review/F-B: a MIXED-tag stack-general canonical warns 'dead weight' naming the live "
          "tags — never the false 'fleet-dead / can never match any project' claim",
          "dead weight" in _err and "fleet-dead" not in _err and "fastpai" in _err and "python" in _err)

with _Env73() as _e:
    # train-robust F1 (measured live): _mind_unresolved must normalize in SLUG space — a live
    # underscore-basename project (Doc_Flo → slug …-Doc-Flo) was falsely flagged dead because
    # _sanitize_token preserves '_' while slug dirs map it to '-'.
    _dfd = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-Doc-Flo" / "memory"
    _dfd.mkdir(parents=True)
    check("train-review/robust-F1: an underscore-basename LIVE project (Doc_Flo) resolves to its slug "
          "store (not flagged '?'); a truly storeless mind still flags",
          sg._mind_unresolved("Doc_Flo") is False and sg._mind_unresolved("ghost_project_x") is True)

# --- v0.1.81: the SessionStart beacon (Stage B — docs/session-beacon.spec.md). Premise MEASURED
# by Stage A (12/13 stores behind); constraints MEASURED (detect_stacks 2003ms on the biggest
# fleet repo vs the 2s hook budget → the --pull-written stacks cache; beacon wall ~40ms).
import subprocess as _sp81  # noqa: E402
_HOOKS81 = _jsonB.loads((ROOT / "plugins" / "consolidate-memory" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
_SS81 = _HOOKS81.get("hooks", {}).get("SessionStart", [])
check("v0.1.81: hooks.json pins the documented contract — double nesting, EXACTLY the startup+resume "
      "matchers (never clear/compact — those are mid-flow), command type, seconds timeout ≤ 2, "
      "${CLAUDE_PLUGIN_ROOT} command path",
      [g.get("matcher") for g in _SS81] == ["startup", "resume"]
      and all(g["hooks"][0]["type"] == "command" and g["hooks"][0]["timeout"] <= 2
              and "${CLAUDE_PLUGIN_ROOT}" in g["hooks"][0]["command"]
              and "session_beacon.py" in g["hooks"][0]["command"] for g in _SS81))
_BEACON81 = ROOT / "plugins" / "consolidate-memory" / "scripts" / "session_beacon.py"


def _beacon81(home, cwd, stdin_obj=None):
    return _sp81.run([sys.executable, str(_BEACON81)],
                     input=_jsonB.dumps(stdin_obj if stdin_obj is not None else {"cwd": str(cwd)}),
                     env=dict(_osB.environ, HOME=str(home)), capture_output=True, text=True, timeout=10)


with _tf73.TemporaryDirectory() as _td81:
    _h81 = Path(_td81)
    _p81 = (_h81 / "src" / "proj").resolve(); _p81.mkdir(parents=True)
    _st81 = _h81 / ".claude" / "projects" / ms.slug_for(_p81) / "memory"; _st81.mkdir(parents=True)
    _g81 = _h81 / ".claude" / "memory"; _g81.mkdir(parents=True)
    # Ordinary pull/beacon never live-read ~/.claude/memory (ADR 008/013). Shared
    # facts for this fixture live in the enrolled domain dir — planting them in
    # the legacy tree would now be silence, not "2 shared global fact(s)".
    _df81 = _h81 / ".claude" / "consolidate-memory" / "domains" / "personal" / "facts"
    _r = _beacon81(_h81, _p81)
    check("v0.1.81: a NEVER-PARTICIPATED store (no *.md) is silent — the plugin is user-wide, random "
          "dirs must cost zero (discovery is --staleness's job)",
          _r.returncode == 0 and _r.stdout == "")
    (_st81 / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    _oldH81e = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_h81)
    try:
        _enroll_personal(_p81)
    finally:
        if _oldH81e is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH81e
    _df81.mkdir(parents=True, exist_ok=True)
    for _n81 in ("g-one", "g-two"):
        (_df81 / f"{_n81}.md").write_text(_v3_canon(_n81), encoding="utf-8")
    _r = _beacon81(_h81, _p81)
    check("v0.1.81: a BEHIND store gets exactly ONE factual line — token-bounded, no-cache basis "
          "labeled, no imperative 'always/never' phrasing (context-injection guidance)",
          _r.returncode == 0 and len(_r.stdout.splitlines()) == 1
          and "2 shared global fact(s)" in _r.stdout and "no stacks cache" in _r.stdout
          and ms.est_tokens(_r.stdout) <= 60)
    (_st81 / ".consolidation-state.json").write_text(
        _jsonB.dumps({"beacon_snooze_until": "2099-01-01T00:00:00Z"}), encoding="utf-8")
    check("v0.1.81: beacon_snooze_until in the future silences the beacon (per-store, explicit-ask key)",
          _beacon81(_h81, _p81).stdout == "")
    (_st81 / ".consolidation-state.json").write_text("NOT JSON", encoding="utf-8")
    _r = _beacon81(_h81, _p81)
    check("v0.1.81: a GARBAGE state file never hides a real gap (line still emitted) and never crashes",
          _r.returncode == 0 and len(_r.stdout.splitlines()) == 1)
    _bad81 = _h81 / "afile"; _bad81.write_text("x", encoding="utf-8")
    _r = _beacon81(_bad81, _p81)
    check("v0.1.81: FAILURE POSTURE — sabotaged environment (HOME=a file) yields rc=0 + EMPTY stdout "
          "(a best-effort advisory never injects noise or an error notice into session start)",
          _r.returncode == 0 and _r.stdout == "")
    # the cache: --pull writes script-truth stacks+project_path, MERGE-preserving model keys;
    # the beacon then drops its no-cache label; --staleness upgrades the node's basis.
    (_st81 / ".consolidation-state.json").write_text(
        _jsonB.dumps({"commit": "abc", "timestamp": "2026-07-01T00:00:00Z"}), encoding="utf-8")
    _oldH81, _oldG81 = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h81); sg.GLOBAL = _g81
    try:
        _enroll_personal(_p81)
        with _ctx73.redirect_stdout(_io73.StringIO()):
            sg.run(_p81, pull=True)
    finally:
        sg.GLOBAL = _oldG81
        _osB.environ["HOME"] = _oldH81 if _oldH81 else ""
    _st81j = _jsonB.loads((_st81 / ".consolidation-state.json").read_text(encoding="utf-8"))
    check("v0.1.81: --pull MERGE-writes the script-truth stacks cache + project_path, preserving the "
          "model-written marker keys verbatim",
          _st81j.get("commit") == "abc" and _st81j.get("timestamp") == "2026-07-01T00:00:00Z"
          and isinstance(_st81j.get("stacks"), list) and _st81j.get("project_path") == str(_p81))
    _trig81 = (_h81 / "src" / "othertrig").resolve(); _trig81.mkdir(parents=True)
    _oldH81b, _oldG81b = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h81); sg.GLOBAL = _g81
    try:
        _stale81u = {d["node"]: d for d in sg.fleet_staleness(_trig81)["nodes"]}
        check("0.2.2: unenrolled --staleness is local-only (sibling enrolled stores stay off the fleet)",
              not any(k.endswith("src-proj") for k in _stale81u))
        _enroll_personal(_trig81)
        _stale81 = {d["node"]: d for d in sg.fleet_staleness(_trig81)["nodes"]}
    finally:
        sg.GLOBAL = _oldG81b
        _osB.environ["HOME"] = _oldH81b if _oldH81b else ""
    _prow81 = next(v for k, v in _stale81.items() if k.endswith("src-proj"))   # label = slug tail (truncated)
    check("v0.1.81: --staleness assesses a NON-trigger node at 'cached stacks (as of last pull)' once "
          "the cache exists (the honest basis ladder: live → cached → user-global-only)",
          _prow81["scope_basis"] == "cached stacks (as of last pull)")
    # v0.4.2 (P1): the stacks cache on the sync paths — cache hit skips the rescan, marker-file
    # changes invalidate the stamp, the TTL bounds the .py blind spot, the kill-switch forces a rescan.
    check("v0.4.2 P1: stacks_with_cache HITS the pull-written cache (from_cache, no rescan)",
          sg.stacks_with_cache(_st81, _p81) == (set(_st81j["stacks"]), True))
    _old_sc_env = _osB.environ.get("CM_RESCAN_STACKS")
    _osB.environ["CM_RESCAN_STACKS"] = "1"
    _sc_forced, _sc_fc = sg.stacks_with_cache(_st81, _p81)
    _osB.environ.pop("CM_RESCAN_STACKS", None)
    if _old_sc_env:
        _osB.environ["CM_RESCAN_STACKS"] = _old_sc_env
    check("v0.4.2 P1: CM_RESCAN_STACKS=1 forces a rescan (from_cache False)",
          _sc_fc is False and _sc_forced == sg.detect_stacks(_p81))
    (_p81 / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n", encoding="utf-8")
    check("v0.4.2 P1: a marker-file change invalidates the stamp (rescan)",
          sg.stacks_with_cache(_st81, _p81)[1] is False)
    # re-write the cache for the new signature, then prove the unchanged write is a no-op.
    # The runs are HOME/GLOBAL-patched (the fixture store must be the one written — a bare
    # run resolves against the REAL home and the mtime pin would pass vacuously).
    _oldH81r, _oldG81r = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h81); sg.GLOBAL = _g81
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()):
            sg.run(_p81, pull=True)
        _m81 = (_st81 / ".consolidation-state.json").stat().st_mtime_ns
        with _ctx73.redirect_stdout(_io73.StringIO()):
            sg.run(_p81, pull=True)
        _m81b = (_st81 / ".consolidation-state.json").stat().st_mtime_ns
    finally:
        sg.GLOBAL = _oldG81r
        _osB.environ["HOME"] = _oldH81r if _oldH81r else ""
    check("v0.4.2 P1: a no-change pull skips the stacks-cache write entirely (state-file mtime stable)",
          _m81b == _m81)
    # TTL: an old stacks_at re-detects even with a matching stamp
    _st81j2 = _jsonB.loads((_st81 / ".consolidation-state.json").read_text(encoding="utf-8"))
    _st81j2["stacks_at"] = 0.0
    (_st81 / ".consolidation-state.json").write_text(_jsonB.dumps(_st81j2), encoding="utf-8")
    check("v0.4.2 P1: an expired TTL re-detects (from_cache False)",
          sg.stacks_with_cache(_st81, _p81)[1] is False)
    # P1 review fix: an expired cache with an UNCHANGED value must RE-ARM on the pull (the
    # early return used to skip the write forever once the TTL elapsed — the cache stayed
    # dead for exactly the stable projects it exists for)
    _oldH81t, _oldG81t = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h81); sg.GLOBAL = _g81
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()):
            sg.run(_p81, pull=True)
    finally:
        sg.GLOBAL = _oldG81t
        _osB.environ["HOME"] = _oldH81t if _oldH81t else ""
    _st81j2b = _jsonB.loads((_st81 / ".consolidation-state.json").read_text(encoding="utf-8"))
    _age81b = __import__("time").time() - float(_st81j2b.get("stacks_at") or 0)
    check("v0.4.2 P1: an expired cache RE-ARMS on the pull (the early return honors the TTL)",
          _age81b < 60 and sg.stacks_with_cache(_st81, _p81)[1] is True)
    check("v0.1.81: after the pull the store is in-sync and the beacon returns to SILENT (the common "
          "case stays free)",
          _beacon81(_h81, _p81).stdout == "")
    # PR-#94 review F1 (verified divergence fixture): the held parenthetical must count STALE
    # refresh deltas exactly like a real --pull — a description-drifted mirror sorting BEFORE a
    # near-ceiling MISSING fact consumes the headroom; the first draft's MISSING-only loop said
    # held=0 while run() held 1. The beacon now calls _plan_pull (one accounting replay).
    (_df81 / "aaa-drift.md").write_text(
        _v3_canon("aaa-drift", description="g" * 80, body="drift body\n"),
        encoding="utf-8")
    _adm81 = sg._as_mirror((_df81 / "aaa-drift.md").read_text(encoding="utf-8"), "aaa-drift",
                           since="2026-01-01T00:00:00Z",
                           body_hash=sg._body_hash((_df81 / "aaa-drift.md").read_text(encoding="utf-8")))
    (_st81 / "aaa-drift.md").write_text(_adm81, encoding="utf-8")
    (_df81 / "zzz-miss.md").write_text(
        _v3_canon("zzz-miss", description="m", body="mb\n"), encoding="utf-8")
    _short81 = "- [aaa-drift](aaa-drift.md) — old"   # real line much leaner than the derived pointer
    _drift81 = ms.est_tokens(sg._pointer_line("aaa-drift", sg._frontmatter(_adm81))) - ms.est_tokens(_short81)
    _cz81 = ms.est_tokens(sg._pointer_line("zzz-miss", sg._frontmatter((_df81 / "zzz-miss.md").read_text(encoding="utf-8"))))
    assert _drift81 > 0 and _cz81 > 0
    (_st81 / "MEMORY.md").write_text(_pad_index73(_C73 - _cz81, [_short81]), encoding="utf-8")
    _r = _beacon81(_h81, _p81)
    check("v0.1.81/review-F1: the beacon's held projection counts STALE pointer-drift deltas via "
          "_plan_pull — it reports the missing fact as ceiling-held exactly where a real --pull "
          "would hold it (the hand-rolled loop said absorbable)",
          "would be ceiling-held" in _r.stdout and "1 shared global fact(s)" in _r.stdout)

# --- v0.1.82: distill-template persistence (W-A — docs/distill-template-persistence.spec.md).
# RED baseline is the contract itself: before this, --into persisted COUNTS only (the pre-change
# scan-contract pin asserted the exact key set WITHOUT `used`; the record block had no rows), so
# template evidence died with each scan and fleet aggregation (W-B) was impossible.
check("v0.1.82: the persist-cap mirrors cannot drift (producer == memory_status, the _DISTILL_CAPS "
      "cross-module pin pattern)",
      ds._DISTILL_PERSIST_CAP == ms._DISTILL_PERSIST_CAP and ds._USED_CAP == ms._DISTILL_USED_CAP)
with _tf73.TemporaryDirectory() as _td82:
    _seed82 = Path(_td82) / "cycle.json"
    _seed82.write_text(_jsonB.dumps({"project": "p", "session": "s",
                                     "distill": {"verdict": "model-authored, must survive"}}),
                       encoding="utf-8")
    _scan82 = {"window": "2026-06-10T00:00:00Z..2026-07-10T00:00:00Z",
               "scanned": {"sessions": 3, "commands": 50, "days": 4, "secrets_omitted": 1},
               "recurring": [{"template": f"tpl-{i:02d}", "count": 20 - i, "days": 5,
                              "sample": "RAW COMMAND TEXT — must never persist"} for i in range(15)],
               "chains": [{"templates": [f"a{i}", f"b{i}"], "count": 9 - (i % 3), "days": 2}
                          for i in range(10)],
               "used": [{"a": f"skill-{i}", "n": 30 - i} for i in range(14)]}
    check("v0.1.82: inject_into persists the TOP rows capped + projected to {t,n,d} — NO sample ever "
          "reaches the durable record (privacy tier), model verdict preserved, counts still script-truth",
          ds.inject_into(str(_seed82), _scan82, "", [], []) is True)
    _rec82 = _jsonB.loads(_seed82.read_text(encoding="utf-8"))["distill"]
    check("v0.1.82: the persisted block — top ≤12 in scan order, top_chains ≤8, used ≤12, "
          "sample-free, verdict intact, n_recurring counts the FULL scan (15) not the persisted head",
          len(_rec82["top"]) == 12 and _rec82["top"][0] == {"t": "tpl-00", "n": 20, "d": 5}
          and all(set(r) == {"t", "n", "d"} for r in _rec82["top"])
          and "sample" not in _jsonB.dumps(_rec82) and "RAW COMMAND" not in _jsonB.dumps(_rec82)
          and len(_rec82["top_chains"]) == 8 and _rec82["top_chains"][0]["t"] == ["a0", "b0"]
          and len(_rec82["used"]) == 12 and _rec82["verdict"] == "model-authored, must survive"
          and _rec82["n_recurring"] == 15)
    _w82 = ms.validate_cycle_record(cast(ms.CycleRecord, {"project": "p", "session": "s",
                                                          "distill": {"top": [{"t": "x"}] * 13}}))
    check("v0.1.82: validate_cycle_record backstops an over-cap top (impossible from --into — the "
          "n_recurring=47 hand-fill lesson, row edition)",
          any("exceeds the persist cap" in w for w in _w82))
with _tf73.TemporaryDirectory() as _td82b:
    # the Skill-adoption tally end-to-end: one in-window Skill invocation counts, one pre-window
    # is excluded (the same per-line instant rule Bash uses); Bash templates unaffected.
    _h82 = Path(_td82b)
    _pj82 = (_h82 / "src" / "dproj").resolve(); _pj82.mkdir(parents=True)
    _pr82 = _h82 / ".claude" / "projects" / ms.slug_for(_pj82); _pr82.mkdir(parents=True)
    _lines82 = [
        _jsonB.dumps({"timestamp": "2026-07-01T00:00:00Z", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "code-review"}}]}}),
        _jsonB.dumps({"timestamp": "2026-05-01T00:00:00Z", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "old-skill"}}]}}),
        _jsonB.dumps({"timestamp": "2026-07-02T00:00:00Z", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "code-review"}}]}}),
    ]
    (_pr82 / "s1.jsonl").write_text("\n".join(_lines82) + "\n", encoding="utf-8")
    _oldH82 = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_h82)
    try:
        _sc82 = ds.scan(_pj82, "2026-06-01T00:00:00Z")
    finally:
        _osB.environ["HOME"] = _oldH82 if _oldH82 else ""
    check("v0.1.82: scan tallies Skill invocations by name, window-scoped (the pre-window one excluded) "
          "— the adoption denominator, accrued while transcripts are on disk",
          _sc82["used"] == [{"a": "code-review", "n": 2}])

# --- v0.1.83: the fleet WORKFLOWS lens (W-B — docs/fleet-workflows.spec.md). RED baseline is
# structural: before this, "template X recurs in N nodes" was uncomputable (no lens existed over
# the W-A rows); live cold-start renders 0/N reporting honestly while the verdict lineage already
# carries real historical dispositions.
def _wblog(session, top, chains=None, used=None, verdict=""):
    d: dict = {"window": "2026-06-10..2026-07-10", "top": top, "top_chains": chains or [], "used": used or []}
    if verdict:
        d["verdict"] = verdict
    return _jsonB.dumps({"session": session, "distill": d})


with _Env73() as _e:
    _nA83 = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-alpha" / "memory"
    _nB83 = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-beta" / "memory"
    _nA83.mkdir(parents=True); _nB83.mkdir(parents=True)
    (_nA83 / ".consolidation-log.jsonl").write_text(
        _wblog("old", [{"t": "python3 tests/smoke.py", "n": 99, "d": 9}],
               verdict="proposed gate-check — declined") + "\n" +
        _wblog("new", [{"t": "python3 tests/smoke.py", "n": 4, "d": 3},
                       {"t": "mypy --config-file mypy.ini", "n": 3, "d": 2}],
               chains=[{"t": ["python3 tests/smoke.py", "mypy --config-file mypy.ini"], "n": 3, "d": 2}],
               used=[{"a": "code-review", "n": 5}]) + "\n", encoding="utf-8")
    (_nB83 / ".consolidation-log.jsonl").write_text(
        _wblog("b1", [{"t": "python3 tests/smoke.py", "n": 2, "d": 2},
                      {"t": "python3 tests/smoke.py --quick", "n": 2, "d": 1}],
               used=[{"a": "code-review", "n": 1}]) + "\n", encoding="utf-8")
    _w83 = sg.fleet_workflows(_e.proj)
    _by83 = {r["template"]: r for r in _w83["templates"]}
    check("v0.1.83: the fleet join — exact-string across nodes' LATEST rows only (the stale record's "
          "n=99 IGNORED — the overlapping-window trap honored), fleet flag at ≥2 nodes, single-node "
          "rows unflagged",
          _w83["nodes_reporting"] == 2
          and _by83["python3 tests/smoke.py"]["fleet"] is True
          and _by83["python3 tests/smoke.py"]["n"] == 6
          and sorted(_by83["python3 tests/smoke.py"]["nodes"]) == ["src-alpha", "src-beta"]
          and _by83["mypy --config-file mypy.ini"]["fleet"] is False)
    check("v0.1.83: head-signature FAMILIES hint (same tool, drifting flags) — variants grouped, "
          "counts never merged; adoption summed latest-per-node; the DECLINED disposition survives "
          "in the cross-node lineage (fleet-wide decline-dedup)",
          any(len(f["templates"]) == 2 for f in _w83["families"])
          and _w83["used"][0] == {"skill": "code-review", "nodes": ["src-alpha", "src-beta"], "n": 6}
          and any("declined" in v["verdict"] and v["node"] == "src-alpha" for v in _w83["verdicts"]))
    check("v0.1.83: chains join like templates; the fleet gate applies (single-node chain unflagged)",
          len(_w83["chains"]) == 1 and _w83["chains"][0]["fleet"] is False
          and _w83["chains"][0]["n"] == 3)
    import hashlib as _hl83
    _pre83 = {p: _hl83.sha1(p.read_bytes()).hexdigest()
              for p in (Path(_osB.environ["HOME"]) / ".claude").rglob("*") if p.is_file()}
    sg.fleet_workflows(_e.proj)
    check("v0.1.83: the lens is READ-ONLY over every store, and the payload is JSON-safe",
          _pre83 == {p: _hl83.sha1(p.read_bytes()).hexdigest()
                     for p in (Path(_osB.environ["HOME"]) / ".claude").rglob("*") if p.is_file()}
          and isinstance(_jsonB.dumps(_w83), str))
check("v0.1.83: distill_history returns latest-row-block + full verdict lineage; absent log → "
      "empty-honest shape",
      ms.distill_history(Path("/nonexistent")) ==
      {"latest": None, "verdicts": [], "proposal_declines": []})

# ── v0.1.87/W-C1 (docs/wc-registrar.spec.md §7): the registrar's Tier-2 gates + D-8 states + D-2.5 anchors ──
with _Env73() as _e:
    import io as _ioW, contextlib as _ctxW
    import hashlib as _hlW
    _wch = Path(_osB.environ["HOME"])
    _wca = _wch / ".claude" / "projects" / "-src-alpha" / "memory"
    _wcb = _wch / ".claude" / "projects" / "-src-beta" / "memory"
    _wcg = _wch / ".claude" / "projects" / "-src-gamma" / "memory"
    _wcd = _wch / ".claude" / "projects" / "-src-delta" / "memory"
    check("v0.1.87/W-C1 0: the fixture-builder guard — the fixture only ever builds under a "
          "TEMP home (the discovery-scope firewall, D-2a; a non-temp HOME is refused)",
          "smoke73-" in str(_wch))
    for _wcp in (_wca, _wcb, _wcg, _wcd):
        _wcp.mkdir(parents=True)
    # alpha: a DECLINED older record (the D-2.5 anchor) + ONE latest record carrying everything —
    #        the shared template, a single-node template, a single-node chain, and (with beta)
    #        a shared-d=1 day-spread blocker (latest-wins: rows split across records would vanish)
    _alpha_new = _jsonB.loads(_wblog(
        "new", [{"t": "python3 tests/smoke.py", "n": 4, "d": 3},
                {"t": "mypy --config-file mypy.ini", "n": 3, "d": 2},
                {"t": "rm -rf .tmp-out", "n": 1, "d": 1},
                {"t": "gh pr create --title", "n": 3, "d": 1},
                {"t": "git add", "n": 4, "d": 2},
                {"t": "python3 tests/validate_manifests.py", "n": 5, "d": 3}],
        chains=[{"t": ["python3 tests/smoke.py", "mypy --config-file mypy.ini"], "n": 3, "d": 2}],
        used=[{"a": "code-review", "n": 5}]))
    _alpha_new["workflow_proposals"] = {
        "verdict": "declined python3 tests/smoke.py — already covered",
        "candidates": [
            {"candidate": "python3 tests/smoke.py", "form": "command", "disposition": "declined",
             "evidence": {"nodes": ["src-alpha", "src-beta"], "d": 2, "n": 6}},
            {"candidate": "git add", "form": "command", "disposition": "declined",
             "evidence": {"nodes": ["src-alpha", "src-beta"], "d": 2, "n": 6}},
            {"candidate": "mypy --config-file mypy.ini", "form": "command", "disposition": "declined",
             "evidence": {"nodes": ["src-alpha"], "d": 2, "n": 3},
             "mechanical": {"fleet_recurrence": False, "day_spread": True, "distinctive": True}},
        ]}
    (_wca / ".consolidation-log.jsonl").write_text(
        _wblog("old", [{"t": "gh pr create --title", "n": 8, "d": 5}],
               chains=[{"t": ["gh pr create --title", "gh pr view"], "n": 2, "d": 1}],
               verdict="proposed gh-pr-workflow — declined (local-only evidence)") + "\n" +
        _jsonB.dumps(_alpha_new) + "\n", encoding="utf-8")
    # beta: the SHARED template again (fleet ✓) + the rm -rf pair (shared across nodes but d=1 → day-spread blocker)
    # + git add (generic-cli) + validate_manifests d=1 (min(3,1)=1 → day-spread, not max-infection)
    (_wcb / ".consolidation-log.jsonl").write_text(
        _wblog("b0", [{"t": "git log --oneline -1", "n": 1, "d": 1}],
               verdict="nothing: covered by release.sh") + "\n" +
        _wblog("b1", [{"t": "python3 tests/smoke.py", "n": 2, "d": 2},
                      {"t": "rm -rf .tmp-out", "n": 1, "d": 1},
                      {"t": "git add", "n": 2, "d": 2},
                      {"t": "python3 tests/validate_manifests.py", "n": 1, "d": 1}],
               chains=[{"t": ["python3 tests/smoke.py", "mypy --config-file mypy.ini"], "n": 2, "d": 2}]) + "\n",
        encoding="utf-8")
    # gamma: LEGACY — a record with NO distill block at all (no top key)
    (_wcg / ".consolidation-log.jsonl").write_text(
        _jsonB.dumps({"session": "old", "dream": {"sleep": "*s*", "beats": ["*b*"], "wake": "*w*"}}) + "\n",
        encoding="utf-8")
    # delta: INSTRUMENTED-EMPTY — top: [] IS a measurement (counts as reporting; never legacy)
    (_wcd / ".consolidation-log.jsonl").write_text(
        _wblog("d1", []) + "\n", encoding="utf-8")

    _bufW = _ioW.StringIO()
    with _ctxW.redirect_stdout(_bufW):
        sg.registrar_report(_e.proj, as_json=True)
    _rcj = _jsonB.loads(_bufW.getvalue())
    _wcw = sg.fleet_workflows(_e.proj)
    _wchist = ms.distill_history(_wca)

    check("v0.1.87/W-C1 1: D-8 node_states — legacy (no top key) · instrumented_empty (top: []) · "
          "reporting (rows) are DISTINCT, and instrumented-empty counts as reporting",
          {s["node"]: s["state"] for s in _wcw["node_states"] if s["node"].startswith("src-")} ==
          {"src-alpha": "reporting", "src-beta": "reporting", "src-gamma": "legacy",
           "src-delta": "instrumented_empty"}
          and _wcw["nodes_reporting"] == 3)
    check("v0.1.87/W-C1 2: D-2.5 decline-anchor — the DECLINED record's row snapshot surfaces "
          "({t,n,d} from decline time, not the latest window)",
          any(v.get("decline_evidence") and v["decline_evidence"]["top"][0]["t"] == "gh pr create --title"
              and v["decline_evidence"]["top"][0]["n"] == 8
              for v in _wchist["verdicts"]))
    _rc_by = {c["candidate"]: c for c in _rcj["candidates"]}
    check("v0.1.87/W-C1 3: registrar JSON — mechanical gates evaluated, model legs LISTED never "
          "evaluated, dispositions correct (fleet-candidate / blocked)",
          _rcj["nodes"] >= 4 and _rcj["nodes_reporting"] == 3
          and {c["candidate"]: c["disposition"] for c in _rcj["candidates"]}
          == {"python3 tests/smoke.py": "fleet-candidate",
              "python3 tests/smoke.py → mypy --config-file mypy.ini": "fleet-candidate",
              "rm -rf .tmp-out": "blocked: day-spread",
              "python3 tests/validate_manifests.py": "blocked: day-spread",
              "mypy --config-file mypy.ini": "blocked: fleet-recurrence",
              "gh pr create --title": "blocked: generic-cli",
              "git add": "blocked: generic-cli"}
          and all(c["gates"]["model_judged"] == ["stable_inputs", "coverage", "decline_lineage"]
                  and "stable_inputs" not in c["gates"]["mechanical"]
                  for c in _rcj["candidates"])
          and any(a["node"] == "src-alpha" and a["top"][0]["t"] == "gh pr create --title"
                  for a in _rcj["decline_anchors"]))
    check("v0.1.90: fleet d is MIN of per-node d (loudest-node infection is day-spread, not a pass)",
          _rc_by["python3 tests/smoke.py"]["evidence"]["d"] == 2
          and _rc_by["python3 tests/validate_manifests.py"]["evidence"]["d"] == 1
          and _rc_by["python3 tests/validate_manifests.py"]["disposition"] == "blocked: day-spread")
    check("v0.1.90: distinctive mechanical flag — git add is generic-cli; smoke.py is distinctive",
          _rc_by["git add"]["gates"]["mechanical"]["distinctive"] is False
          and _rc_by["python3 tests/smoke.py"]["gates"]["mechanical"]["distinctive"] is True
          and _rc_by["python3 tests/smoke.py → mypy --config-file mypy.ini"]["gates"]["mechanical"]["distinctive"] is True)
    check("v0.1.90: WP disposition=declined attaches a decline-anchor (the production channel); "
          "generic git add declined does NOT",
          any(a.get("top") and a["top"][0].get("t") == "python3 tests/smoke.py"
              for a in _rcj["decline_anchors"])
          and all(not (a.get("top") and a["top"][0].get("t") == "git add")
                  for a in _rcj["decline_anchors"]))
    check("v0.1.90: declined single-node distinctive (mypy) is NOT a fleet decline-anchor",
          all(not (a.get("top") and a["top"][0].get("t") == "mypy --config-file mypy.ini")
              for a in _rcj["decline_anchors"]))
    check("v0.1.87/W-C1 4: the chain path of the cascade is exercised (the shared chain crosses "
          "the fleet tier)",
          any(c["form"] == "chain" and c["disposition"] == "fleet-candidate"
              for c in _rcj["candidates"]))
    check("v0.1.87/W-C1 6: a NON-declined verdict carries NO decline_evidence (the canonical "
          "pattern gate — 'previously declined, now confirmed' must not anchor)",
          all("decline_evidence" not in v for v in _wchist["verdicts"]
              if "nothing:" in v["verdict"])
          and any("decline_evidence" in v and v["decline_evidence"]["top_chains"]
                  and v["decline_evidence"]["top"][0]["t"] == "gh pr create --title"
                  for v in _wchist["verdicts"]))
    _tmpDec = Path(_osB.environ["HOME"]) / "dec-hist"; _tmpDec.mkdir()
    (_tmpDec / ".consolidation-log.jsonl").write_text(
        _jsonB.dumps({"distill": {"verdict": "proposed X — previously declined, now confirmed",
                                  "top": [{"t": "x", "n": 1, "d": 1}]}}) + "\n", encoding="utf-8")
    check("v0.1.90: 'proposed X — previously declined, now confirmed' does NOT attach a decline-anchor",
          all("decline_evidence" not in v for v in ms.distill_history(_tmpDec)["verdicts"]))
    _tmpCh = Path(_osB.environ["HOME"]) / "dec-hist-chain"; _tmpCh.mkdir()
    (_tmpCh / ".consolidation-log.jsonl").write_text(
        _jsonB.dumps({"distill": {"verdict": "proposed the gate-chain — declined",
                                  "top_chains": [{"t": ["a", "b"], "n": 3, "d": 2}]}}) + "\n",
        encoding="utf-8")
    check("v0.1.90: a chain-only declined verdict (no top[]) still attaches a decline-anchor",
          any(v.get("decline_evidence") and v["decline_evidence"].get("top_chains")
              for v in ms.distill_history(_tmpCh)["verdicts"]))
    check("v0.1.87/W-C1 7: the declined-still-recurring pairing — the anchor's template ALSO sits in "
          "the current candidate window (the data the model leg compares against)",
          any(c["candidate"] == "gh pr create --title" and c["disposition"] == "blocked: generic-cli"
              for c in _rcj["candidates"])
          and any(a["node"] == "src-alpha" and a["top"][0]["t"] == "gh pr create --title"
                  for a in _rcj["decline_anchors"]))
    _preW = {p: _hlW.sha1(p.read_bytes()).hexdigest()
             for p in _wch.rglob("*") if p.is_file()}
    _bufW2 = _ioW.StringIO()
    with _ctxW.redirect_stdout(_bufW2):
        sg.registrar_report(_e.proj, as_json=True)
    check("v0.1.87/W-C1 5: the registrar is READ-ONLY over every store",
          _preW == {p: _hlW.sha1(p.read_bytes()).hexdigest()
                    for p in _wch.rglob("*") if p.is_file()})

    # W-C2: --into SCRIPT-TRUTH injection (D-7) — mechanical rows land in the seed; model fields absent
    _seedW = Path(_osB.environ["HOME"]) / "seed.json"
    _seedW.write_text(_jsonB.dumps({"project": "p", "session": "s"}), encoding="utf-8")
    _bufI = _ioW.StringIO()
    with _ctxW.redirect_stdout(_bufI):
        _rcI = sg.registrar_report(_e.proj, as_json=False, into=str(_seedW))
    _seedD = _jsonB.loads(_seedW.read_text(encoding="utf-8"))
    _wp = _seedD.get("workflow_proposals") or {}
    check("v0.1.87/W-C2 1: --into injects the SCRIPT-TRUTH block (mechanical gates per row; the model's "
          "disposition/name/verdict fields are ABSENT — never hand-mirrored)",
          _rcI == 0 and isinstance(_wp.get("candidates"), list)
          and all({"candidate", "form", "evidence", "mechanical"} <= set(r) for r in _wp["candidates"])
          and all("disposition" not in r and "name" not in r for r in _wp["candidates"])
          and any(r["mechanical"]["fleet_recurrence"] is True for r in _wp["candidates"])
          and isinstance(_wp.get("decline_anchors"), list))
    _n_f = int(_wp.get("n_fleet") or 0); _n_b = int(_wp.get("n_blocked") or 0)
    check("v0.1.90: --into writes full n_* counts and caps blocked persist (fleet-candidates kept)",
          _wp.get("n_candidates") == _n_f + _n_b
          and _n_f + _n_b >= len(_wp["candidates"])
          and len(_wp["candidates"]) <= _n_f + ms._REGISTRAR_BLOCKED_CAP
          and int(_wp.get("n_generic") or 0) + int(_wp.get("n_day_spread") or 0) <= _n_b)
    check("v0.1.90: --into persists fleet-candidates + distinctive day-spread only "
          "(generic-cli / single-node are counts, not rows)",
          all(r["candidate"] not in ("git add", "mypy --config-file mypy.ini",
                                     "gh pr create --title")
              for r in _wp["candidates"])
          and any(r["candidate"] == "python3 tests/smoke.py" for r in _wp["candidates"])
          and any(r["candidate"] == "rm -rf .tmp-out" for r in _wp["candidates"])
          and all((r.get("mechanical") or {}).get("distinctive") is True
                  for r in _wp["candidates"]))
    _spread_row = next(r for r in _wp["candidates"] if r["candidate"] == "rm -rf .tmp-out")
    _spread_row["disposition"] = "declined"
    _seedW.write_text(_jsonB.dumps(_seedD), encoding="utf-8")
    with _ctxW.redirect_stdout(_ioW.StringIO()):
        sg.registrar_report(_e.proj, as_json=False, into=str(_seedW))
    _re_spread = _jsonB.loads(_seedW.read_text(encoding="utf-8"))["workflow_proposals"]["candidates"]
    check("v0.1.90: re-consult strips declined from a day-spread (non-fleet) row",
          any(r["candidate"] == "rm -rf .tmp-out"
              and r.get("disposition") not in ("declined", "awaiting-confirmation")
              for r in _re_spread))
    _bufI2 = _ioW.StringIO()
    with _ctxW.redirect_stdout(_bufI2):
        _rcI2 = sg.registrar_report(_e.proj, as_json=False, into=str(Path(_osB.environ["HOME"]) / "nope" / "x.json"))
    check("v0.1.87/W-C2 2: an unwritable --into target exits 2 (a typo'd path is caught, never a silent drop)",
          _rcI2 == 2)
    # --into SEED must not be collected as PROJECT_DIR when DIR is omitted (or last).
    _seedPos = Path(_osB.environ["HOME"]) / "seed-pos.json"
    _seedPos.write_text("{}", encoding="utf-8")
    _oldArgv = sys.argv[:]
    _errPos = _ioW.StringIO()
    try:
        sys.argv = ["sync_global.py", "--workflows", "--registrar", "--into", str(_seedPos)]
        with _ctxW.redirect_stdout(_ioW.StringIO()), _ctxW.redirect_stderr(_errPos):
            _rcPos = sg._dispatch()
    finally:
        sys.argv = _oldArgv
    _seedPosD = _jsonB.loads(_seedPos.read_text(encoding="utf-8")) if _seedPos.exists() else {}
    check("v0.1.90: --into SEED is not stolen as PROJECT_DIR when DIR is omitted",
          "PROJECT_DIR" not in _errPos.getvalue()
          and _rcPos == 0
          and isinstance((_seedPosD.get("workflow_proposals") or {}).get("candidates"), list))
    # W-C2 polish: seed-key survival + the re-consult MERGE (model fields preserved on re-run)
    _seedW2 = Path(_osB.environ["HOME"]) / "seed2.json"
    _seedW2.write_text(_jsonB.dumps({"project": "p", "session": "s", "verdict": "keep-me",
                                     "workflow_proposals": {"verdict": "keep-too"}}), encoding="utf-8")
    _bufI3 = _ioW.StringIO()
    with _ctxW.redirect_stdout(_bufI3):
        sg.registrar_report(_e.proj, as_json=False, into=str(_seedW2))
    _seedD2 = _jsonB.loads(_seedW2.read_text(encoding="utf-8"))
    check("v0.1.87/W-C2 4: pre-existing seed keys SURVIVE the injection (project/session/verdict + a "
          "pre-existing workflow_proposals.verdict)",
          _seedD2.get("project") == "p" and _seedD2.get("session") == "s"
          and _seedD2.get("verdict") == "keep-me"
          and _seedD2["workflow_proposals"].get("verdict") == "keep-too"
          and isinstance(_seedD2["workflow_proposals"].get("candidates"), list))
    # the MODEL writes per-row fields post-injection, then a RE-CONSULT must preserve them
    _seedD2["workflow_proposals"]["candidates"][0]["disposition"] = "confirmed"
    _seedD2["workflow_proposals"]["candidates"][0]["name"] = "gate-check-cmd"
    _seedW2.write_text(_jsonB.dumps(_seedD2), encoding="utf-8")
    _bufI4 = _ioW.StringIO()
    with _ctxW.redirect_stdout(_bufI4):
        sg.registrar_report(_e.proj, as_json=False, into=str(_seedW2))
    _seedD3 = _jsonB.loads(_seedW2.read_text(encoding="utf-8"))
    check("v0.1.87/W-C2 5: a RE-CONSULT merges on (candidate, form) — the model-written "
          "disposition/name SURVIVE the evidence refresh (the split-ownership contract)",
          _seedD3["workflow_proposals"]["candidates"][0].get("disposition") == "confirmed"
          and _seedD3["workflow_proposals"]["candidates"][0].get("name") == "gate-check-cmd"
          and "evidence" in _seedD3["workflow_proposals"]["candidates"][0])
    _seedD3["workflow_proposals"]["candidates"].append(
        {"candidate": "out-of-window-cmd", "form": "command", "disposition": "confirmed",
         "name": "kept-artifact", "evidence": {"nodes": ["gone"], "d": 2, "n": 2},
         "mechanical": {"fleet_recurrence": True, "day_spread": True}})
    _seedD3["workflow_proposals"]["candidates"].append(
        {"candidate": "stale-awaiting", "form": "command",
         "disposition": "awaiting-confirmation",
         "evidence": {"nodes": ["gone"], "d": 1, "n": 1},
         "mechanical": {"fleet_recurrence": False, "day_spread": False}})
    _seedD3["workflow_proposals"]["candidates"].append(
        {"candidate": "stale-declined-blocked", "form": "command", "disposition": "declined",
         "evidence": {"nodes": ["a"], "d": 2, "n": 2},
         "mechanical": {"fleet_recurrence": False, "day_spread": True, "distinctive": True}})
    _seedD3["workflow_proposals"]["candidates"].append(
        {"candidate": "stale-declined-fleet", "form": "command", "disposition": "declined",
         "evidence": {"nodes": ["a", "b"], "d": 2, "n": 2},
         "mechanical": {"fleet_recurrence": True, "day_spread": True, "distinctive": True}})
    _seedW2.write_text(_jsonB.dumps(_seedD3), encoding="utf-8")
    with _ctxW.redirect_stdout(_ioW.StringIO()):
        sg.registrar_report(_e.proj, as_json=False, into=str(_seedW2))
    _kept_cands = _jsonB.loads(_seedW2.read_text(encoding="utf-8"))["workflow_proposals"]["candidates"]
    check("v0.1.90: a confirmed row that left the window SURVIVES a re-consult; awaiting does not",
          any(r.get("candidate") == "out-of-window-cmd" and r.get("disposition") == "confirmed"
              for r in _kept_cands)
          and all(r.get("candidate") != "stale-awaiting" for r in _kept_cands))
    check("v0.1.90: out-of-window declined fleet-candidate is kept; declined blocked is dropped",
          any(r.get("candidate") == "stale-declined-fleet" and r.get("disposition") == "declined"
              for r in _kept_cands)
          and all(r.get("candidate") != "stale-declined-blocked" for r in _kept_cands))
    _vrW = ms.validate_cycle_record({"project": "p", "workflow_proposals": {"candidates": "not-a-list"}})
    check("v0.1.87/W-C2 3: validate_cycle_record warns on a wrong-container workflow_proposals sub-key "
          "(the model-slip class), and is quiet on the correct shape",
          any("workflow_proposals.candidates is not a list" in wmsg for wmsg in _vrW)
          and ms.validate_cycle_record({"project": "p", "workflow_proposals": {"candidates": [], "decline_anchors": []}}) == [])
    check("v0.1.90: validate_cycle_record warns on an unknown WP disposition",
          any("disposition is not a known value" in w for w in
              ms.validate_cycle_record({"project": "p", "workflow_proposals": {
                  "candidates": [{"candidate": "x", "disposition": "maybe"}]}})))
    check("v0.1.90: validate_cycle_record warns on declined/awaiting on a non-fleet-candidate",
          any("non-fleet-candidate" in w for w in
              ms.validate_cycle_record({"project": "p", "workflow_proposals": {
                  "candidates": [{"candidate": "mypy --config-file mypy.ini",
                                  "disposition": "declined",
                                  "mechanical": {"fleet_recurrence": False, "day_spread": True,
                                                 "distinctive": True}}]}})))

# v0.1.90: distinctive-template gate — unit cases (the registrar's generic-cli stoplist)
check("v0.1.90: distinctive — git/gh never; bare python3 --flag never; script path yes; chain any-side",
      ms._is_distinctive_template("git add", "command") is False
      and ms._is_distinctive_template("git commit -q -m", "command") is False
      and ms._is_distinctive_template("gh pr create --title", "command") is False
      and ms._is_distinctive_template("python3 --json", "command") is False
      and ms._is_distinctive_template("python3 --pull .", "command") is False
      and ms._is_distinctive_template("python3 tests/smoke.py", "command") is True
      and ms._is_distinctive_template("mypy --config-file mypy.ini", "command") is True
      and ms._is_distinctive_template("git add → git commit -q -m", "chain") is False
      and ms._is_distinctive_template(
          "python3 tests/smoke.py → mypy --config-file mypy.ini", "chain") is True)
check("v0.1.90: fleet-proposal row — distinctive+≥2 nodes+d≥2 only",
      ms._is_fleet_proposal_row({"candidate": "python3 tests/smoke.py", "form": "command",
                                 "mechanical": {"fleet_recurrence": True, "day_spread": True,
                                                "distinctive": True}}) is True
      and ms._is_fleet_proposal_row({"candidate": "mypy --config-file mypy.ini", "form": "command",
                                    "mechanical": {"fleet_recurrence": False, "day_spread": True,
                                                   "distinctive": True}}) is False
      and ms._is_fleet_proposal_row({"candidate": "git add", "form": "command",
                                    "mechanical": {"fleet_recurrence": True, "day_spread": True,
                                                   "distinctive": False}}) is False)

# --- PR-#95 review pins (persistence-core lens — all three findings fire only on the
# hand-edited / pre-v0.1.82 --from path; the dream path was already clean) ---
with _tf73.TemporaryDirectory() as _td95:
    _seed95 = Path(_td95) / "cycle.json"
    _seed95.write_text(_jsonB.dumps({"project": "p", "session": "s"}), encoding="utf-8")
    _old95 = {"window": "w", "scanned": {"sessions": 1, "commands": 2, "days": 1, "secrets_omitted": 0},
              "recurring": [{"template": "x" * 500, "count": "47", "days": None, "sample": "s"}],
              "chains": [{"templates": 5, "count": 1, "days": 1},
                         {"templates": "ab", "count": 2, "days": 1},
                         {"templates": ["real-a", "real-b"], "count": 3, "days": 2}]}
    check("v0.1.82/review: a pre-v0.1.82 --from scan (no `used` key) injects WITHOUT crashing — the "
          "old bare list() poison-pill (templates=5 → TypeError → WHOLE capture lost) is now a "
          "per-row skip",
          ds.inject_into(str(_seed95), _old95, "", [], []) is True)
    _r95 = _jsonB.loads(_seed95.read_text(encoding="utf-8"))["distill"]
    check("v0.1.82/review: absent-vs-empty honesty — an UNMEASURED scan writes NO `used` key (an "
          "empty list would register a false 'measured, zero invocations' window in W-B's adoption "
          "view — the usage_history discipline)",
          "used" not in _r95)
    check("v0.1.82/review: per-row value coercion — t clamped to 200 chars (the compact contract is "
          "on VALUES), garbage n/d coerced to 0, the string-templates char-split garbage gone, the "
          "one valid chain row survives",
          len(_r95["top"][0]["t"]) == 200 and _r95["top"][0]["n"] == 0 and _r95["top"][0]["d"] == 0
          and _r95["top_chains"] == [{"t": ["real-a", "real-b"], "n": 3, "d": 2}])
    _old95b = {"window": "w", "scanned": {"sessions": 1, "commands": 1, "days": 1, "secrets_omitted": 0},
               "recurring": [], "chains": [],
               "used": [{"a": "code-review", "n": 2, "EXTRA_LEAK": "/home/x/secret-passthrough"},
                        {"a": "AKIAIOSFODNN7EXAMPLE", "n": 1}]}
    _seed95b = Path(_td95) / "cycle2.json"
    _seed95b.write_text(_jsonB.dumps({"project": "p", "session": "s"}), encoding="utf-8")
    ds.inject_into(str(_seed95b), _old95b, "", [], [])
    _r95b = _jsonB.loads(_seed95b.read_text(encoding="utf-8"))["distill"]
    check("v0.1.82/seams-review: `used` rows are REPROJECTED to {a,n} (extra-key passthrough dead) "
          "and names screened through the emission firewall (a secret-shaped name is dropped)",
          _r95b["used"] == [{"a": "code-review", "n": 2}]
          and "EXTRA_LEAK" not in _jsonB.dumps(_r95b) and "AKIA" not in _jsonB.dumps(_r95b))

# --- v0.1.84: provenance liveness + edge triage (P4 — docs/provenance-liveness.spec.md).
# RED baseline MEASURED live: 16/76 edges (21%) ghost, ≈20% of fleet tax ghost-attributed; the
# live acceptance (the spec's own stated test) ran clean: 59 live · 1 stale · 16 unresolved ·
# 0 ambiguous, the ghosts exactly the two known dead fixtures.
with _Env73() as _e:
    _h84 = Path(_osB.environ["HOME"])
    # four stores: live-holder (mirror present), stale (store, no mirror), two ambiguity twins
    _live84 = _h84 / ".claude" / "projects" / "-src-liveproj" / "memory"; _live84.mkdir(parents=True)
    _stale84 = _h84 / ".claude" / "projects" / "-src-staleproj" / "memory"; _stale84.mkdir(parents=True)
    for _tw in ("-a-twinproj", "-b-twinproj"):
        (_h84 / ".claude" / "projects" / _tw / "memory").mkdir(parents=True)
    _ct84 = ("---\nname: canon-x\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: feedback\n"
             "  projects: [liveproj, staleproj, ghost-proj, twinproj]\n---\nbody\n")
    (_e.glob / "canon-x.md").write_text(_ct84, encoding="utf-8")
    (_live84 / "canon-x.md").write_text(sg._as_mirror(_ct84, "canon-x", since="2026-01-01T00:00:00Z",
                                                      body_hash=sg._body_hash(_ct84)), encoding="utf-8")
    _seed_holders(_e.proj, "canon-x", ["liveproj", "staleproj", "ghost-proj", "twinproj"])
    check("v0.1.84: _classify_edge — all four classes (live=mirror-holding store; stale=one match no "
          "mirror; unresolved=zero matches; ambiguous=multi-match none holding); degenerate token is "
          "ambiguous (not provably ghost), never unresolved",
          sg._classify_edge("liveproj", "canon-x") == "live"
          and sg._classify_edge("staleproj", "canon-x") == "stale"
          and sg._classify_edge("ghost-proj", "canon-x") == "unresolved"
          and sg._classify_edge("twinproj", "canon-x") == "ambiguous"
          and sg._classify_edge("---", "canon-x") == "ambiguous")
    _fu84 = sg.fleet_utility(_e.proj)
    _e84 = {x["name"]: x for x in _fu84["canonicals"]}["canon-x"]
    check("v0.1.84: fleet_utility classifies holders per canonical and prints the LIVE basis BESIDE "
          "the provenance upper bound (never replacing it; live ≤ provenance always)",
          _e84["holders"] == 4 and _e84.get("holders_live") == 1 and _e84.get("holders_stale") == 1
          and _e84.get("holders_unresolved") == 1 and _e84.get("holders_ambiguous") == 1
          and _e84["fleet_tax_live"] == _e84["pointer_tok"]
          and _fu84["total_fleet_tax_live"] <= _fu84["total_fleet_tax"])
    _gout84 = _io73.StringIO()
    with _ctx73.redirect_stdout(_gout84):
        sg.gc(_e.proj, apply=False, edges=True)
    # PR-#97 review F4: assert the POSITIVE counts line (strictly stronger than the old degenerate
    # `"16" not in`, which couldn't appear on a 4-edge fixture anyway) + the twin absent from ghosts.
    _greport84 = _gout84.getvalue()
    _gzone84 = _greport84.split("EDGES", 1)[1].split("RESULT", 1)[0]
    check("v0.1.84: --gc --edges REPORTS the exact class breakdown (4 total · 1 live · 1 stale · "
          "1 unresolved · 1 ambiguous) and lists ONLY the ghost (stale AND ambiguous twin never offered)",
          "4 total · 1 live · 1 stale · 1 unresolved · 1 ambiguous" in _greport84
          and "ghost-proj" in _gzone84 and "would prune" in _greport84
          and "staleproj" not in _gzone84 and "twinproj" not in _gzone84)
    with _ctx73.redirect_stdout(_io73.StringIO()):
        sg.gc(_e.proj, apply=True, edges=True)
    _ct84b = (_e.glob / "canon-x.md").read_text(encoding="utf-8")
    # ADR 023 (#142): --apply writes the SQLite authority ONLY — the Markdown body is
    # byte-verbatim (projects: is migration input / frozen display, never rewritten).
    import control_plane as _cp84
    import store_context as _sc84
    _conn84 = _cp84.connect(_cp84.db_path(_sc84.resolve_store(_e.proj)))
    try:
        _rows84 = [str(r["project_id"]) for r in _conn84.execute(
            "SELECT project_id FROM holders WHERE fact_id=?",
            (_cp84.stable_fact_id("personal", "canon-x"),)).fetchall()]
    finally:
        _conn84.close()
    check("v0.1.84: --edges --apply prunes ONLY the unresolved token from SQLITE holders — "
          "live/stale/ambiguous rows intact, canonical body byte-verbatim",
          _ct84b == _ct84
          and "ghost-proj" not in _rows84
          and {"liveproj", "staleproj", "twinproj"} <= set(_rows84))
    # the self-heal: a pull from a live project re-adds ITS OWN edge (a wrong prune is a
    # temporary undercount, never a loss)
    _p84 = _e.glob / "canon-x.md"
    _t84 = _p84.read_text(encoding="utf-8")
    _p84.write_text(sg.apply_provenance(_t84, "ghost-proj"), encoding="utf-8")
    check("P1-6: apply_provenance strips Markdown projects: (SQLite holders are authoritative)",
          "ghost-proj" not in _p84.read_text(encoding="utf-8")
          or "projects:" not in _p84.read_text(encoding="utf-8"))
# PR-#97 review F1 (the mass-prune blocker): a present-but-STORELESS projects tree (unmounted /
# transcript-only) must REFUSE — every edge resolves to nothing, indistinguishable from a wiped
# store tree; --apply must NOT write `projects: []` fleet-wide.
with _Env73() as _e:
    (_e.glob / "canon-y.md").write_text(
        "---\nname: canon-y\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: feedback\n"
        "  projects: [proj-a, proj-b]\n---\nbody\n", encoding="utf-8")
    _seed_holders(_e.proj, "canon-y", ["proj-a", "proj-b"])
    # present but STORELESS: _Env73 makes the trigger's OWN store; delete it so no memory/ store
    # dir exists anywhere → every holder resolves to nothing (the unmounted-tree degenerate state).
    import shutil as _sh84
    _sh84.rmtree(_e.store)
    (Path(_osB.environ["HOME"]) / ".claude" / "projects").mkdir(parents=True, exist_ok=True)
    _gy84 = _io73.StringIO()
    with _ctx73.redirect_stdout(_gy84):
        _rc = sg.gc(_e.proj, apply=True, edges=True)
    check("v0.1.84/review-F1: --edges --apply REFUSES when nothing resolves to a live store (guard on "
          "the resolved COUNT, not dir existence) — provenance survives verbatim, no mass-prune",
          _rc == 0 and "refusing --edges" in _gy84.getvalue()
          and "projects: [proj-a, proj-b]" in (_e.glob / "canon-y.md").read_text(encoding="utf-8"))
# PR-#97 review F3: the tightened predicate — a name-matching slug dir WITHOUT a memory store
# classifies unresolved (store-deleted = dead), the direction the F1 fixture masks by mkdir'ing memory.
with _Env73() as _e:
    (_e.glob / "canon-z.md").write_text(
        "---\nname: canon-z\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: feedback\n---\nz\n",
        encoding="utf-8")
    (Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-storeless").mkdir(parents=True, exist_ok=True)  # dir, NO memory/
    check("v0.1.84/review-F3: a slug dir WITHOUT a memory store is unresolved (store-deleted = dead — "
          "a holder had a store by construction), and _mind_unresolved agrees",
          sg._classify_edge("storeless", "canon-z") == "unresolved" and sg._mind_unresolved("storeless") is True)

# --- v0.1.85: mention-tier attribution (P3 — docs/mention-tier-attribution.spec.md). The hook
# channel (fact stems NAMED in assistant text without a body read) is the layer's actual product
# and was entirely unmeasured; MEASURED live premise: mentions ≫ reads, 13 stems named-never-read.
import extract_signals as _es85  # noqa: E402
# split_dream_span now partitions read AND mention items; a mention inside the arc span is excluded.
_items85 = [{"i": 0, "kind": "read", "stem": "r-out", "ts": "t"},
            {"i": 5, "kind": "arc", "stem": "", "ts": "t"},
            {"i": 6, "kind": "mention", "stem": "m-in", "ts": "t"},     # inside span → dream-excluded
            {"i": 9, "kind": "arc", "stem": "", "ts": "t"},
            {"i": 12, "kind": "mention", "stem": "m-out", "ts": "t"}]   # outside → organic
_org85, _exc85 = _es85.split_dream_span(_items85)
check("v0.1.85: split_dream_span partitions reads AND mentions by the arc span (a mention inside a "
      "dream is procedure, excluded; outside is organic) — reads-only fixtures unaffected",
      {(o["kind"], o["stem"]) for o in _org85} == {("read", "r-out"), ("mention", "m-out")}
      and _exc85 == 1)
with _tf73.TemporaryDirectory() as _td85:
    _mh85 = Path(_td85)
    _proj85 = (_mh85 / "src" / "mproj").resolve(); _proj85.mkdir(parents=True)
    _st85 = _mh85 / ".claude" / "projects" / ms.slug_for(_proj85) / "memory"; _st85.mkdir(parents=True)
    for _s in ("gh-pr-edit-broken-in-env", "measure-dont-assert-before-acting",
               "prefer-typed-stubs-over-ignore", "cli-stdout-stderr-contract", "short"):
        (_st85 / f"{_s}.md").write_text(f"---\nname: {_s}\n---\nbody\n", encoding="utf-8")
    (_st85 / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")

    def _amsg(text):
        return _jsonB.dumps({"timestamp": "2026-07-05T10:00:00Z",
                             "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
    (_st85.parent / "s1.jsonl").write_text("\n".join([
        _amsg("per gh-pr-edit-broken-in-env I used the REST fallback"),          # 1 stem → counts
        _amsg("gh-pr-edit-broken-in-env again and again gh-pr-edit-broken-in-env"),  # same stem, binary
        _amsg("index dump: gh-pr-edit-broken-in-env measure-dont-assert-before-acting "
              "prefer-typed-stubs-over-ignore cli-stdout-stderr-contract"),      # ≥4 stems → all dropped
        _jsonB.dumps({"timestamp": "2026-07-05T10:00:00Z", "message": {"role": "user",
                     "content": [{"type": "text", "text": "measure-dont-assert-before-acting"}]}}),  # user → excluded
    ]) + "\n", encoding="utf-8")
    _oldH85 = _osB.environ.get("HOME"); _osB.environ["HOME"] = str(_mh85)
    try:
        _rc85 = _es85.recall_scan(_proj85, "2026-07-01T00:00:00Z")
    finally:
        _osB.environ["HOME"] = _oldH85 if _oldH85 else ""
    check("v0.1.85: the mention detector — binary per window (a stem named twice counts once), the "
          "≥4-stem index-DUMP message dropped wholesale, USER text excluded, the degenerate 'short' "
          "stem never matched → exactly {gh-pr-edit-broken-in-env}",
          _rc85["mentions"] == 1 and _rc85["mention_stems"] == ["gh-pr-edit-broken-in-env"])
    check("v0.1.85: per_fact stays READS-ONLY — mentions are their own channel (the facts_read == "
          "len(per_fact) probative-window invariant is untouched; demotion gate unaffected)",
          _rc85["per_fact"] == [] and _rc85["facts_read"] == 0)
# usage_history unions mention_stems across windows (positive evidence, like miss_stems); display-only.
with _tf73.TemporaryDirectory() as _td85b:
    _st85b = Path(_td85b)
    (_st85b / ".consolidation-log.jsonl").write_text(
        _jsonB.dumps({"usage": {"window": "w1", "transcripts": 1, "facts_read": 0, "per_fact": [],
                                "mention_stems": ["a-fact-stem"]}}) + "\n" +
        _jsonB.dumps({"usage": {"window": "w2", "transcripts": 1, "facts_read": 0, "per_fact": [],
                                "mention_stems": ["b-fact-stem"]}}) + "\n", encoding="utf-8")
    check("v0.1.85: usage_history unions mention_stems across windows (positive hook evidence never "
          "discarded), and validate_cycle_record backstops an over-cap list",
          ms.usage_history(_st85b)["mention_stems"] == ["a-fact-stem", "b-fact-stem"]
          and any("mention_stems exceeds" in w for w in ms.validate_cycle_record(
              cast(ms.CycleRecord, {"project": "p", "session": "s",
                                    "usage": {"mention_stems": ["x"] * 41}}))))
# fleet_utility attributes a mention through a MIRROR only (like reads), display-only column.
with _Env73() as _e:
    _ct85 = ("---\nname: canon-m\ndescription: \"d\"\nmetadata:\n  scope: user-global\n  type: feedback\n"
             "  projects: [mnode]\n---\nbody\n")
    (_e.glob / "canon-m.md").write_text(_ct85, encoding="utf-8")
    _nm85 = Path(_osB.environ["HOME"]) / ".claude" / "projects" / "-src-mnode" / "memory"; _nm85.mkdir(parents=True)
    (_nm85 / "canon-m.md").write_text(sg._as_mirror(_ct85, "canon-m", since="2026-01-01T00:00:00Z",
                                                    body_hash=sg._body_hash(_ct85)), encoding="utf-8")
    (_nm85 / ".consolidation-log.jsonl").write_text(
        _jsonB.dumps({"usage": {"window": "w", "transcripts": 1, "facts_read": 0, "per_fact": [],
                                "mention_stems": ["canon-m"]}}) + "\n", encoding="utf-8")
    _e85 = {x["name"]: x for x in sg.fleet_utility(_e.proj)["canonicals"]}["canon-m"]
    check("v0.1.85: fleet_utility attributes a mention through a MIRROR (like reads) — a 0-reads "
          "canonical reads as hook-active, not dormant; display-only key emitted only when non-zero",
          _e85.get("mentions") == 1 and _e85["reads"] == 0)
# PR-#98 review F4: the per-cycle dashboard renders the mentions channel + the corrected
# dream-procedure-excluded label (was "dream read(s) excluded" — imprecise once mentions joined
# the span split); a legacy usage block with no mentions renders neither (key-presence gated).
_mrec85 = cast(ms.CycleRecord, {"project": "p", "session": "s", "scope": {}, "entries": [],
               "usage": {"reads": 0, "facts_read": 0, "transcripts": 2, "dream_excluded": 3,
                         "per_fact": [], "mentions": 4, "mention_stems": ["a", "b", "c", "d"]}})
_mout85 = rd.render(_mrec85)
check("v0.1.85/review-F4: dashboard renders the hook-mentions count + 'dream-procedure recall(s) "
      "excluded' (never the stale 'read(s)' label); a legacy no-mentions record shows neither",
      "4 hook mention(s)" in _mout85 and "dream-procedure recall(s) excluded" in _mout85
      and "dream read(s) excluded" not in _mout85
      and "hook mention(s)" not in rd.render(cast(ms.CycleRecord, {"project": "p", "session": "s",
          "scope": {}, "entries": [], "usage": {"reads": 1, "facts_read": 1, "transcripts": 1,
          "dream_excluded": 0, "per_fact": [{"name": "x", "reads": 1, "last": "t"}]}})))

# --- v0.1.86: budget-trajectory early-warning (docs/budget-trajectory-early-warning.spec.md).
# The index-budget TRAJECTORY read: port the dashboard's lsSlope onto the logged
# budget.index.after_tokens series, project a rising fit to the next uncrossed threshold, and
# attach staleness age. Read-only + never-raise (degradation invariant). Synthetic inline logs
# only (never a live personal store). See the spec's 8 acceptance gates.
def _traj_log(d: Path, *vals: int) -> None:
    (d / ".consolidation-log.jsonl").write_text(
        "\n".join(_jsonB.dumps({"budget": {"index": {"after_tokens": v}}}) for v in vals) + "\n",
        encoding="utf-8")

_M86 = "2026-08-20T00:00:00Z"   # ~8 days before the 2026-08-28 fixture clock -> a computable age

# Gate 2b -- _ls_slope is a hand-computed numeric port (independent of the JS source).
check("v0.1.86 2b: _ls_slope hand-computed [1,2,3]=1 [2,4,6,8]=2 [0,10,20]=10 negative=-1",
      ms._ls_slope([1.0, 2.0, 3.0]) == 1.0 and ms._ls_slope([2.0, 4.0, 6.0, 8.0]) == 2.0
      and ms._ls_slope([0.0, 10.0, 20.0]) == 10.0 and ms._ls_slope([10.0, 9.0, 8.0, 7.0]) == -1.0)
check("v0.1.86 2b: _ls_slope degenerate k<2 and zero-denominator both return 0.0",
      ms._ls_slope([]) == 0.0 and ms._ls_slope([7.0]) == 0.0 and ms._ls_slope([5.0, 5.0, 5.0]) == 0.0)

# Gate 2a -- structural source-text pin on the dashboard's literal lsSlope formula (no JS exec).
check("v0.1.86 2a: dashboard lsSlope formula still present (structural pin, not executed)",
      "var d=k*sxx-sx*sx;return d===0?0:(k*sxy-sx*sy)/d" in _tpl54)

# Gate 1a -- shrinking under-target: silent, no new rendering.
with _tf73.TemporaryDirectory() as _td1a:
    _s1a = Path(_td1a); _traj_log(_s1a, 1500, 1450, 1400, 1350)
    check("v0.1.86 1a: shrinking under-target -> (None, None) silent",
          ms.budget_trajectory_advisory(_s1a, 1350, _M86) == (None, None))

# Gate 1b -- over-target sustained uptrend: suffix (age + ceiling-breach), no new line.
with _tf73.TemporaryDirectory() as _td1b:
    _s1b = Path(_td1b); _traj_log(_s1b, 1800, 2000, 2200)
    _suf, _lin = ms.budget_trajectory_advisory(_s1b, 2200, _M86)
    check("v0.1.86 1b: over-target uptrend -> suffix (age + ceiling breach), line None",
          _suf is not None and "hard ceiling" in _suf and "last dream" in _suf and _lin is None)

# Gate 1c -- flat stale over-target: suffix carries ONLY the age (no breach), line None.
with _tf73.TemporaryDirectory() as _td1c:
    _s1c = Path(_td1c); _traj_log(_s1c, 2200, 2200, 2200, 2200)
    _suf, _lin = ms.budget_trajectory_advisory(_s1c, 2200, _M86)
    check("v0.1.86 1c: flat stale over-target -> suffix age-only (no breach), line None",
          _suf is not None and "last dream" in _suf and "hard ceiling" not in _suf and _lin is None)

# Gate 1d -- frozen cycle-16 replay (cur=1402, last-4 slope 78) -> suffix None, line breach=1.
with _tf73.TemporaryDirectory() as _td1d:
    _s1d = Path(_td1d)
    _traj_log(_s1d, 856, 934, 1012, 1090, 1168, 1246, 1324, 1402)  # last-4 diffs 78 -> slope 78
    _suf, _lin = ms.budget_trajectory_advisory(_s1d, 1402, _M86)
    check("v0.1.86 1d: frozen cycle-16 replay -> suffix None, line carries breach=1 + age",
          _suf is None and _lin is not None and "in ~1 dream" in _lin and "last dream" in _lin)

# Gate 3 -- live cur_tokens diverges from the logged last point: the over-target suffix fires
# on the LIVE value even though the logged series' last point is still under target.
with _tf73.TemporaryDirectory() as _td3:
    _s3 = Path(_td3); _traj_log(_s3, 1300, 1340, 1380, 1400)
    _suf, _lin = ms.budget_trajectory_advisory(_s3, 2200, _M86)   # live 2200 > 1500, logged last 1400
    check("v0.1.86 3: live cur_tokens anchors the over-target suffix (logged last point under)",
          _suf is not None and "hard ceiling" in _suf and _lin is None)

# Gate 4 -- degradation invariant on a FIRING series (4a non-string marker, 4b out-of-range
# marker, 4c malformed log line): the line still fires, the age is simply absent, never a crash.
with _tf73.TemporaryDirectory() as _td4:
    _s4 = Path(_td4); _traj_log(_s4, 1300, 1340, 1380, 1402)
    _suf, _lin = ms.budget_trajectory_advisory(_s4, 1402, cast(str, 12345))   # 4a: truthy non-string marker
    check("v0.1.86 4a: non-string marker -> line fires, age absent, no crash",
          _lin is not None and "last dream" not in _lin and _suf is None)
    _suf, _lin = ms.budget_trajectory_advisory(_s4, 1402, "9999-12-31T23:59:59-14:00")  # 4b
    check("v0.1.86 4b: out-of-range marker -> line fires, age absent, no crash",
          _lin is not None and "last dream" not in _lin and _suf is None)
    (_s4 / ".consolidation-log.jsonl").write_text(
        "\n".join([_jsonB.dumps({"budget": {"index": {"after_tokens": 1300}}}),
                   "NOT JSON",
                   _jsonB.dumps({"budget": {"index": {"after_tokens": 1340}}}),
                   _jsonB.dumps({"budget": {"index": {"after_tokens": 1380}}}),
                   _jsonB.dumps({"budget": {"index": {"after_tokens": 1402}}})]) + "\n",
        encoding="utf-8")   # 4c: malformed line skipped by iter_cycle_log
    _suf, _lin = ms.budget_trajectory_advisory(_s4, 1402, _M86)
    check("v0.1.86 4c: malformed log line skipped -- series still fires with the breach",
          _lin is not None and "in ~3 dream" in _lin and _suf is None)

# Gate 6 -- rounding tie (bf=2.5): Python round-half-to-even -> breach 2 (not JS Math.round's 3).
with _tf73.TemporaryDirectory() as _td6:
    _s6 = Path(_td6); _traj_log(_s6, 1280, 1320, 1360, 1400)   # slope 40.0, bf=(1500-1400)/40=2.5
    _suf, _lin = ms.budget_trajectory_advisory(_s6, 1400, _M86)
    check("v0.1.86 6: bf=2.5 tie rounds to 2 (round-half-to-even), not Math.round's 3",
          _lin is not None and "in ~2 dream" in _lin)

# Gate 7 -- over target + no marker + n<3: the tightened silence rule collapses to None (no
# empty decoration), since neither age nor breach is computable.
with _tf73.TemporaryDirectory() as _td7:
    _s7 = Path(_td7); _traj_log(_s7, 1600, 1700)
    check("v0.1.86 7: over target + no marker + n<3 -> (None, None), never an empty suffix",
          ms.budget_trajectory_advisory(_s7, 1750, "") == (None, None))

with _tf73.TemporaryDirectory() as _td0:
    _s0 = Path(_td0); _traj_log(_s0, 1900, 2000, 2100, 0)
    check("v0.1.90: genuine after_tokens=0 is data — emptied index does NOT fire a false early-warning",
          ms.budget_trajectory_advisory(_s0, 0, _M86) == (None, None))
with _tf73.TemporaryDirectory() as _td13:
    _s13 = Path(_td13); _traj_log(_s13, 1808, 1939, 2070, 2200)   # last-4 slope ≈130.7, bf≈12.55 → ~13
    _suf13, _lin13 = ms.budget_trajectory_advisory(_s13, 2200, _M86)
    check("v0.1.90: live over-target climber (~130 tok/cycle) projects ~13 dreams to the hard ceiling",
          _suf13 is not None and "hard ceiling" in _suf13 and "~13 dream" in _suf13 and _lin13 is None)

# Gate 5 -- seed_record() unchanged (no new schema key): covered by the existing cycle-record
# smoke coverage; this feature adds no seed key by construction (display-only, read-only).

# ── v0.1.8/A1 (SPEC-A §10): cycle-probe teeth · inert seam · canary wiring · tolerance pins ──────
_bts = ROOT / "plugins" / "dream-beta-tester" / "scripts"
_bcf = ROOT / "plugins" / "dream-beta-tester" / "fixtures" / "make_fixture.py"
_bcp = ROOT / "plugins" / "dream-beta-tester" / "fixtures" / "make_cycle_probe.py"
_bck = ROOT / "plugins" / "dream-beta-tester" / "maintainer" / "ci_check.sh"


def _run_home_a1(env_home: str, *args: str) -> "tuple[str, str, int]":
    env = {**_os53.environ, "HOME": env_home}
    env.pop("CM_DREAM_ARC", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    p = _sp53.run([sys.executable, *args], capture_output=True, text=True, timeout=120, env=env)
    return p.stdout, p.stderr, p.returncode


with _tf43.TemporaryDirectory() as _tdA1:
    _homeA1 = str(Path(_tdA1) / "home")
    Path(_homeA1).mkdir()
    _repoA1 = str(Path(_tdA1) / "gate-repo")
    _stateA1 = str(Path(_tdA1) / "state")
    Path(_stateA1).mkdir()

    _oA1, _eA1, _rcA1 = _run_home_a1(_homeA1, str(_bcf), _repoA1)
    check("v0.1.8/A1 F1: re-baselined fixture generates (mirror present)",
          _rcA1 == 0 and "1 mirror (trigger node)" in _oA1)

    _envA1 = {**_os53.environ, "DREAM_BETA_STATE": _stateA1}
    _pA1 = _sp53.run([sys.executable, str(_bcp), "--skill", str(_scripts54),
                      "--out", str(Path(_stateA1) / "cycle-probe.json")],
                     capture_output=True, text=True, timeout=120, env=_envA1)
    check("v0.1.8/A1 F1: probe record generates (contaminated + stamped)",
          _pA1.returncode == 0 and "after_tokens=9999" in _pA1.stdout)
    _probeA1 = str(Path(_stateA1) / "cycle-probe.json")

    _oA1, _eA1, _rcA1 = _run_home_a1(_homeA1, str(_bts / "beta_checks.py"),
                                     "--repo", _repoA1, "--skill", str(_scripts54), "--json")
    _dA1 = _json43.loads(_oA1)
    check("v0.1.8/A1 F4: flag absent → no cycle_probe key (inert seam)",
          "cycle_probe" not in _dA1 and _rcA1 == 0 and _dA1["summary"]["fail"] == 0)
    check("v0.1.8/A1 F4: re-baselined fixture is 0 FAIL / 0 WARN (the mirror added no noise)",
          _dA1["summary"]["fail"] == 0 and _dA1["summary"]["warn"] == 0)
    check("v0.1.8/A1 F1: CHK-CYCLE-BUDGET present on the re-baselined fixture (trigger node exists)",
          any(r["id"] == "CHK-CYCLE-BUDGET" for r in _dA1["results"]))

    _oA2, _eA2, _rcA2 = _run_home_a1(_homeA1, str(_bts / "beta_checks.py"),
                                     "--repo", _repoA1, "--skill", str(_scripts54), "--json",
                                     "--cycle-probe", _probeA1)
    _dA2 = _json43.loads(_oA2)
    _cpA2 = _dA2.get("cycle_probe") or {}
    check("v0.1.8/A1 F1: teeth intact — stamp verified + BOTH expected FAILs detected, exactly",
          _cpA2.get("stamp_verified") is True and _cpA2.get("ok") is True
          and set(_cpA2.get("detected_ids", [])) == {"CHK-CYCLE-PROJECT", "CHK-CYCLE-BUDGET"})
    check("v0.1.8/A1 F1: probe FAILs are partitioned — main summary + results unchanged, exit still 0",
          _rcA2 == 0 and _dA2["summary"] == _dA1["summary"]
          and len(_dA2["results"]) == len(_dA1["results"])
          and _dA2["families_ran"] == _dA1["families_ran"])

    # clean-record leg: the target's OWN seed → both probe checks PASS (no false red)
    _oA3, _eA3, _rcA3 = _run_home_a1(_homeA1, str(_scripts54 / "memory_status.py"), _repoA1, "--json")
    _cleanA1 = str(Path(_tdA1) / "clean-seed.json")
    Path(_cleanA1).write_text(_oA3, encoding="utf-8")
    _oA4, _eA4, _rcA4 = _run_home_a1(_homeA1, str(_bts / "beta_checks.py"),
                                     "--repo", _repoA1, "--skill", str(_scripts54), "--json",
                                     "--cycle-probe", _cleanA1)
    _cpA4 = (_json43.loads(_oA4).get("cycle_probe") or {})
    check("v0.1.8/A1 F1: clean record → both probe checks PASS (no false red)",
          {r.get("id") for r in _cpA4.get("results", [])} == {"CHK-CYCLE-PROJECT", "CHK-CYCLE-BUDGET"}
          and all(r.get("status") == "PASS" for r in _cpA4.get("results", [])))

    # missing record → teeth-loss, never ok/clean
    _oA5, _eA5, _rcA5 = _run_home_a1(_homeA1, str(_bts / "beta_checks.py"),
                                     "--repo", _repoA1, "--skill", str(_scripts54), "--json",
                                     "--cycle-probe", str(Path(_tdA1) / "nope.json"))
    _cpA5 = (_json43.loads(_oA5).get("cycle_probe") or {})
    check("v0.1.8/A1 F4: missing probe file → ok false + error (teeth-loss, never clean)",
          _cpA5.get("ok") is False and bool(_cpA5.get("error")) and _rcA5 == 0)

    # F6: tolerance margin — contaminant stays ≫ tolerance vs the LIVE trigger node
    _oA6, _eA6, _rcA6 = _run_home_a1(_homeA1, str(_scripts54 / "sync_global.py"),
                                     "--tokens", _repoA1, "--json")
    _trigA6 = [n for n in (_json43.loads(_oA6).get("nodes") or []) if n.get("trigger")]
    check("v0.1.8/A1 F6: fixture IS a trigger node (mirror present)", len(_trigA6) == 1)
    if _trigA6:
        _tokA6 = _trigA6[0].get("always_loaded_tokens")
        check("v0.1.8/A1 F6: contaminant 9999 ≫ tolerance max(50, 10%×trigger)",
              isinstance(_tokA6, int) and (9999 - _tokA6) > max(50, int(0.10 * _tokA6)))

# F5: static wiring pin — the probe flag appears ONLY on the MAIN invocation (never run_oracle()/
# the canary leg), and every emit_result invocation carries --probe-ok explicitly.
_ckA1 = _bck.read_text(encoding="utf-8")
_roA1 = _ckA1[_ckA1.index("run_oracle()"):_ckA1.index("SELF-TEST")]
check("v0.1.8/A1 F5: run_oracle()/canary leg never passes the probe flag",
      "--cycle-probe" not in _roA1)
check("v0.1.8/A1 F5: --cycle-probe appears only as the MAIN-invocation array assignment",
      sum(1 for ln in _ckA1.splitlines() if "--cycle-probe" in ln) == 1
      and any("PROBE_ARGS=(--cycle-probe" in ln for ln in _ckA1.splitlines()))
_emitA1 = [i for i, ln in enumerate(_ckA1.splitlines())
           if 'python3 "$SCRIPTS/emit_result.py"' in ln]
check("v0.1.8/A1 F5: every emit_result invocation carries --probe-ok (within the call's 4-line window)",
      len(_emitA1) == 2
      and all("--probe-ok" in "\n".join(_ckA1.splitlines()[i:i + 4]) for i in _emitA1))

# ── v0.1.8/A2 (SPEC-A §10.3): claimed-writes seam pins (snapshot.diff pure-function) ─────────────
def _mfA2(files: "list[tuple[str, str, str, int]]") -> "_snap.Manifest":
    return _snap.Manifest(
        manifest_version=_snap.MANIFEST_VERSION, created="2026-08-28T00:00:00Z",
        repo="/r", store="/r/store", snapshot_dir="/snap", store_present=True,
        repo_docs_present=[], marker={}, files=[
            _snap.FileEntry(o, n, f"{o}/{n}", f"/src/{n}", sha, int(sz), n in _snap.DERIVED_SIDE_FILES)
            for o, n, sha, sz in files])


_mA2a = _mfA2([("store", "a.md", "sha1", 10), ("store", "MEMORY.md", "sha2", 20),
               ("store", ".consolidation-state.json", "sha3", 30)])
_mA2b = _mfA2([("store", "a.md", "sha9", 12), ("store", "b.md", "sha4", 5),   # a modified, b created
               ("store", "MEMORY.md", "sha8", 24),                           # index modified
               ("store", ".consolidation-state.json", "sha3", 30)])          # allowlisted, UNCHANGED

_dA2a = _snap.diff(_mA2a, _mA2b, claimed=frozenset({"a.md", "b.md", "MEMORY.md"}))
check("v0.1.8/A2 1: fully-claimed pass → nothing unexpected, no phantoms",
      _dA2a.unexpected_store_mutations == [] and _dA2a.phantom_claims == []
      and _dA2a.summary["phantom_claims"] == 0)
_dA2b = _snap.diff(_mA2a, _mA2b, claimed=frozenset({"a.md"}))
check("v0.1.8/A2 2: unclaimed fact + index changes ARE unexpected (claim set is the contract)",
      set(_dA2b.unexpected_store_mutations) == {"b.md", "MEMORY.md"} and _dA2b.phantom_claims == [])
_dA2c = _snap.diff(_mA2a, _mA2b, claimed=frozenset({"a.md", "x.md"}))
check("v0.1.8/A2 3: a claimed write with no delta is a PHANTOM claim (dishonest report)",
      "x.md" in _dA2c.phantom_claims and _dA2c.summary["phantom_claims"] == 1)
_dA2d = _snap.diff(_mA2a, _mA2b,
                   claimed=frozenset({"a.md", "b.md", "MEMORY.md", ".consolidation-state.json"}))
check("v0.1.8/A2 4: an allowlisted name never phantoms (unchanged derived file ≠ claim failure)",
      _dA2d.phantom_claims == [])
_dA2e = _snap.diff(_mA2a, _mA2b)
check("v0.1.8/A2 5: claimed=None is pre-A2 behavior (every non-allowlisted store delta unexpected)",
      set(_dA2e.unexpected_store_mutations) == {"a.md", "b.md", "MEMORY.md"}
      and _dA2e.phantom_claims == [])
# (summary gains the phantom_claims key additively; the legacy-callers contract is the unexpected
# list itself, pinned in 5 — summary is an additive field, not a frozen shape)
check("v0.1.8/A2 5b: legacy summary keys intact + phantom count present and additive",
      all(k in _dA2e.summary for k in ("total", "created", "modified", "deleted",
                                       "unexpected_store", "marker_advanced"))
      and _dA2e.summary.get("phantom_claims") == 0)

# ── v0.1.8/A3 (SPEC-A §10.2): mutating-pass pins — clean pass, determinism, hermeticity ───────────
import hashlib as _hlA3


def _norm_mutate_tree(root: Path) -> "dict[str, str]":
    """Content hashes of a kept world, with the promote-minted `global_ref_since:` stamp
    normalized (it is wall-clock; the rest of the world must be byte-identical — D-7)."""
    import re as _reA3
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root)).replace("\\", "/")
            if (p.suffix in (".sqlite", ".lock") or p.name.endswith(".lock")
                    or "/plugins/data/" in "/" + rel or p.name in (
                        "control.sqlite", "fleet-usage.jsonl", ".fleet-usage.jsonl",
                        "migrate-rollback.json")):
                continue
            if "/quarantine/" in "/" + rel and rel.endswith(".md"):
                parts = rel.split("/")
                stem = parts[-1][:-3].split(".")[0]
                parts[-1] = stem + ".NORMALIZED.md"
                rel = "/".join(parts)
            t = p.read_bytes().decode("utf-8", errors="replace")
            t = _reA3.sub(r"global_ref_since: .*", r"global_ref_since: NORMALIZED", t)
            t = _reA3.sub(r"content_modified: .*", r"content_modified: NORMALIZED", t)
            t = _reA3.sub(r"last_observed_at: .*", r"last_observed_at: NORMALIZED", t)
            t = _reA3.sub(r"mirrored_at: .*", r"mirrored_at: NORMALIZED", t)
            t = _reA3.sub(r"base_revision: .*", r"base_revision: NORMALIZED", t)
            t = _reA3.sub(r"canonical_revision: .*", r"canonical_revision: NORMALIZED", t)
            out[rel] = _hlA3.sha256(t.encode("utf-8")).hexdigest()[:16]
    return out


with _tf43.TemporaryDirectory() as _tdA3:
    _homeA3 = str(Path(_tdA3) / "home")
    Path(_homeA3).mkdir()
    _repoA3 = str(Path(_tdA3) / "gate-repo")
    _repA3 = str(Path(_tdA3) / "reports")
    Path(_repA3).mkdir()
    _oA3, _eA3, _rcA3 = _run_home_a1(_homeA3, str(_bcf), _repoA3)
    _fixA3 = _homeA3 + "/.claude"   # hash the whole fixture home tree (store + global absent)
    _fix_beforeA3 = _norm_mutate_tree(Path(_fixA3))
    # ambient env during the pass = a THIRD "leak" home: a driver that fails to pin HOME would drop
    # the promote canonical HERE — provable without ever reading the user's real store.
    _leakA3 = str(Path(_tdA3) / "leak-home")
    Path(_leakA3).mkdir()

    # the pass resolves the store from ITS OWN HOME — pass --store explicitly so the fixture
    # (generated under _homeA3) is found even though the pass's ambient env is the leak home
    _storeA3 = str(Path(_homeA3) / ".claude" / "projects" / ms.slug_for(Path(_repoA3)) / "memory")

    def _run_mutate_a3(ambient_home: str, keep: bool) -> "tuple[str, str, int]":
        env = {**_os53.environ, "HOME": ambient_home}
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        p = _sp53.run([sys.executable, str(_bts / "run_beta.py"), "--repo", _repoA3,
                       "--store", _storeA3,
                       "--skill", str(_scripts54), "--reports-dir", _repA3, "--mutate", "--json"]
                      + (["--keep"] if keep else []),
                      capture_output=True, text=True, timeout=180, env=env)
        return p.stdout, p.stderr, p.returncode

    _soA31, _seA31, _rcA31 = _run_mutate_a3(_leakA3, keep=True)
    _soA32, _seA32, _rcA32 = _run_mutate_a3(_leakA3, keep=True)
    _dA31 = _json43.loads(_soA31)
    _dA32 = _json43.loads(_soA32)
    check("v0.1.8/A3 1: both passes CLEAN — 0 unexpected, 0 phantom, oob green, marker advanced",
          _rcA31 == 0 and _rcA32 == 0 and _dA31["pass_clean"] and _dA32["pass_clean"]
          and _dA31["out_of_band"]["ok"] and _dA31["marker_advanced"]
          and _dA31["diff_summary"]["unexpected_store"] == 0
          and _dA31["diff_summary"]["phantom_claims"] == 0)
    check("v0.1.8/A3 2: hermeticity — the ambient (leak) home was NEVER written (env pinning works)",
          not (Path(_leakA3) / ".claude").exists())
    check("v0.1.8/A3 3: the frozen fixture store was NEVER touched (the pass ran on its copy)",
          _norm_mutate_tree(Path(_fixA3)) == _fix_beforeA3)
    _keepA3 = sorted(Path(_repA3).glob(".mutate-keep-*"))
    check("v0.1.8/A3 4: --keep retained both hermetic copies", len(_keepA3) == 2)
    if len(_keepA3) == 2:
        _tA31 = _norm_mutate_tree(_keepA3[0] / "home" / ".claude")
        _tA32 = _norm_mutate_tree(_keepA3[1] / "home" / ".claude")
        check("v0.1.8/A3 5: cross-run byte-identity modulo the promote-minted since: stamp",
              _tA31 == _tA32)

# ── v0.1.8/A5: vendored-canary pins — manifest integrity + the LIVE canary leg (caveat closed) ──
_canA5 = ROOT / "plugins" / "dream-beta-tester" / "fixtures" / "canary-v0.1.19"
_manifestA5 = {}
for _lnA5 in (_canA5 / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    _hA5, _nA5 = _lnA5.split()
    _manifestA5[_nA5] = _hA5
check("v0.1.8/A5 1: the vendored canary manifest verifies (byte-faithful to the v0.1.19 tag)",
      len(_manifestA5) == 5
      and all(_hlA3.sha256((_canA5 / n).read_bytes()).hexdigest() == h
              for n, h in _manifestA5.items()))


def _graftA5(canary_scripts: Path, graft: bool) -> bool:
    """Replicate install-gate.sh's M3-slug graft (or not) on a canary copy; return True iff at
    least ONE file carried the old slug pattern (files without it are sed-style no-ops — the
    total-absence case means the vendored canary no longer matches v0.1.19 and the self-test
    would false-green)."""
    applied = 0
    for f in canary_scripts.glob("*.py"):
        t = f.read_text(encoding="utf-8")
        if graft:
            if 're.sub(r"[/_]"' in t:
                applied += 1
            t = t.replace('re.sub(r"[/_]"', 're.sub(r"[^A-Za-z0-9]"')
            f.write_text(t, encoding="utf-8")
    return applied >= 1


def _run_gateA5(home: str, state: str) -> "tuple[str, str, int]":
    env = {**_os53.environ, "HOME": home, "DREAM_BETA_STATE": state,
           "DBT_GATE_SKILL": str(_scripts54)}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    p = _sp53.run(["bash", str(_bck)], capture_output=True, text=True, timeout=300,
                  env=env, cwd=str(ROOT))
    return p.stdout, p.stderr, p.returncode


def _make_canaryA5(state: str, graft: bool) -> None:
    dst = Path(state) / "canary-v0.1.19" / "scripts"
    dst.mkdir(parents=True, exist_ok=True)
    for f in _canA5.glob("*.py"):
        (dst / f.name).write_bytes(f.read_bytes())
    if graft and not _graftA5(dst, graft):
        raise RuntimeError("canary graft pattern missing — the vendored canary no longer "
                           "carries the old slug rule; the self-test would false-green")


with _tf43.TemporaryDirectory() as _tdA5:
    _homeA5 = str(Path(_tdA5) / "home")
    Path(_homeA5).mkdir()
    _stateA5 = str(Path(_tdA5) / ".dt-state")   # DOT in the path — the graft's whole reason to exist
    Path(_stateA5).mkdir()
    _repoA5 = str(Path(_stateA5) / "gate-repo")
    _oA5, _eA5, _rcA5 = _run_home_a1(_homeA5, str(_bcf), _repoA5)
    _envA5 = {**_os53.environ, "DREAM_BETA_STATE": _stateA5}
    _pA5 = _sp53.run([sys.executable, str(_bcp), "--skill", str(_scripts54),
                      "--out", str(Path(_stateA5) / "cycle-probe.json")],
                     capture_output=True, text=True, timeout=120, env=_envA5)

    # grafted leg: the REAL canary self-test fires by identity → clean verdict end-to-end
    _make_canaryA5(_stateA5, graft=True)
    _goA5, _geA5, _grA5 = _run_gateA5(_homeA5, _stateA5)
    _ljA5 = _json43.loads((Path(_stateA5) / "reports" / "latest.json").read_text(encoding="utf-8"))
    check("v0.1.8/A5 2: grafted canary leg — self-test fires by identity, verdict clean, probe green",
          _grA5 == 0 and _ljA5["verdict"] == "clean" and _ljA5["self_test"]["ok"] is True
          and set(_ljA5["self_test"]["expected_ids"]).issubset(set(_ljA5["self_test"]["detected_ids"]))
          and _ljA5["cycle_probe"]["ok"] is True)

    # B6 sabotage leg: an UNGRAFTED canary on a dot-path resolves the WRONG store → spurious FAILs
    # with the wrong identity → selftest_broken (the 2026-06-22 false-green class, now pinned)
    with _tf43.TemporaryDirectory() as _tdA6:
        _homeA6 = str(Path(_tdA6) / "home")
        Path(_homeA6).mkdir()
        _stateA6 = str(Path(_tdA6) / ".dt-state")
        Path(_stateA6).mkdir()
        _repoA6 = str(Path(_stateA6) / "gate-repo")
        _oA6, _eA6, _rcA6 = _run_home_a1(_homeA6, str(_bcf), _repoA6)
        _envA6 = {**_os53.environ, "DREAM_BETA_STATE": _stateA6}
        _sp53.run([sys.executable, str(_bcp), "--skill", str(_scripts54),
                   "--out", str(Path(_stateA6) / "cycle-probe.json")],
                  capture_output=True, text=True, timeout=120, env=_envA6)
        _make_canaryA5(_stateA6, graft=False)
        _soA6, _seA6, _srA6 = _run_gateA5(_homeA6, _stateA6)
        _ljA6 = _json43.loads((Path(_stateA6) / "reports" / "latest.json").read_text(encoding="utf-8"))
        check("v0.1.8/A5 3: UNGRAFTED canary on a dot-path → selftest_broken (fail-open, loud) — the B6 false-green class stays closed",
              _srA6 == 0 and _ljA6["verdict"] == "selftest_broken" and _ljA6["self_test"]["ok"] is False
              and not set(_ljA6["self_test"]["expected_ids"]).issubset(set(_ljA6["self_test"]["detected_ids"])))

# ── v0.1.8/A6: GC-reclaim self-heal — the maintainer's own --gc reclaims the orphan mirror;
#    the gate must regenerate the fixture and still reach a clean verdict with teeth intact ────
with _tf43.TemporaryDirectory() as _tdA7:
    _homeA7 = str(Path(_tdA7) / "home")
    Path(_homeA7).mkdir()
    _stateA7 = str(Path(_tdA7) / ".dt-state")
    Path(_stateA7).mkdir()
    _repoA7 = str(Path(_stateA7) / "gate-repo")
    _run_home_a1(_homeA7, str(_bcf), _repoA7)
    # Live canonicals for GC sit in the enrolled domain dir (ADR 008). A leftover
    # in ~/.claude/memory is migrate-inventory only and must not keep GC alive.
    _run_home_a1(_homeA7, str(_scripts54 / "cm_ops.py"),
                 "project", "enroll", _repoA7, "--domain", "personal", "--apply",
                 "--confirm", "enroll-personal")
    _dfA7 = Path(_homeA7) / ".claude" / "consolidate-memory" / "domains" / "personal" / "facts"
    _dfA7.mkdir(parents=True, exist_ok=True)
    (_dfA7 / "real-canonical.md").write_text(
        "---\nname: real-canonical\ndescription: a real canonical for the GC-reclaim pin\n"
        "domain: personal\n"
        "metadata:\n  node_type: memory\n  type: reference\n  projects: [gate-repo]\n---\n\nA real canonical fact.\n",
        encoding="utf-8")
    _goA7, _geA7, _grcA7 = _run_home_a1(_homeA7, str(_scripts54 / "sync_global.py"),
                                        "--gc", _repoA7, "--apply")
    _storeA7 = Path(_homeA7) / ".claude" / "projects" / ms.slug_for(Path(_repoA7)) / "memory"
    check("v0.1.8/A6 1: --gc --apply reclaims the fixture's orphan mirror (the trigger-node loss vector)",
          _grcA7 == 0 and not (_storeA7 / "fixture-mirror-01.md").exists())
    _envA7 = {**_os53.environ, "DREAM_BETA_STATE": _stateA7}
    _sp53.run([sys.executable, str(_bcp), "--skill", str(_scripts54),
               "--out", str(Path(_stateA7) / "cycle-probe.json")],
              capture_output=True, text=True, timeout=120, env=_envA7)
    _make_canaryA5(_stateA7, graft=True)
    _goA7b, _geA7b, _grA7b = _run_gateA5(_homeA7, _stateA7)
    _ljA7 = _json43.loads((Path(_stateA7) / "reports" / "latest.json").read_text(encoding="utf-8"))
    check("v0.1.8/A6 2: the gate self-heals (regenerates the mirror) and the verdict stays clean with teeth intact",
          _grA7b == 0 and _ljA7["verdict"] == "clean" and _ljA7["cycle_probe"]["ok"] is True
          and (_storeA7 / "fixture-mirror-01.md").exists()
          and "global_ref:" in (_storeA7 / "fixture-mirror-01.md").read_text(encoding="utf-8"))

# ── v0.1.87/ARC-C: the standing calibration report — pure-function + hermetic CLI pins ───────────
import calibration_report as _crep  # noqa: E402

check("v0.1.87/C1: store-name derivation (slug tail after -project-)",
      _crep._store_name("-home-you-project-consolidate-memory") == "consolidate-memory"
      and _crep._store_name("-home-you-project-Doc-Flo") == "Doc-Flo")
check("v0.1.87/C2: synthetic-store exclusion — fixture/gate/scratch/-tmp-/probe slugs excluded, real slugs not",
      all(_crep._EXCLUDE_RE.search(s) for s in ("-home-you--dream-beta-test-gate-repo",
                                              "-tmp-g2test", "x-scratchpad-y", "dbt-repro-repro-repo",
                                              "-tmp-claude-1000-fixture-test-gate-repo"))
      and not any(_crep._EXCLUDE_RE.search(s) for s in ("-home-you-project-consolidate-memory",
                                                      "-home-you-project-Doc-Flo")))
check("v0.1.87/C3: aggregate shape == baseline shape (the single-shape pin — a new block must update BOTH)",
      set(_crep.aggregate({})) == set(_crep.BASELINE))

_rec_c3 = [
    {"scope": {"git_commits": 1, "session_candidates": 0}, "verification": {"confirmed": 2, "corrected": 0, "unverifiable": 0},
     "budget": {"index": {"after_tokens": 1400}}, "usage": {"window": "w", "reads": 1, "facts_read": 1, "misses": []},
     "demotion": {"windows_observed": 3, "eligible": 0, "surfaced": [], "struck": []},
     "distill": {"n_recurring": 0}, "remediation": {}, "rigor": {}},
    {"scope": {"git_commits": 5, "session_candidates": 5}, "verification": {"confirmed": 0, "corrected": 1, "unverifiable": 1},
     "budget": {"index": {"after_tokens": 1600}}, "usage": {"window": "w", "reads": 0, "facts_read": 0, "misses": ["x"]},
     "demotion": {"windows_observed": 1, "eligible": 1, "surfaced": ["s"], "struck": []},
     "distill": {"n_recurring": 2}, "remediation": {"required": True}, "rigor": {"prune_pressure": True}},
]
_agg_c3 = _crep.aggregate({"store-a": _rec_c3})
check("v0.1.87/C4: aggregate math (bands LIGHT 1/HEAVY 1 · median upper-mid 10 · over_budget 1/2 · misses 1 · miss_by_band)",
      _agg_c3["records"] == 2 and _agg_c3["magnitude"]["bands"] == {"LIGHT": 1, "SUBSTANTIAL": 0, "HEAVY": 1}
      and _agg_c3["magnitude"]["median"] == 10 and _agg_c3["index"]["over_budget"] == 1
      and _agg_c3["index"]["over_ceiling"] == 0 and _agg_c3["usage"]["misses"] == 1
      and _agg_c3["usage"]["windows"] == 2 and _agg_c3["miss_by_band"]["HEAVY"] == 1
      and _agg_c3["demotion"]["windows_observed"] == 4 and _agg_c3["pressure"]["remediation_required"] == 1)
_mut_c3 = dict(_crep.BASELINE)
_mut_c3["usage"] = dict(_crep.BASELINE["usage"], misses=2)
_del_c3 = _crep.delta(_mut_c3, _crep.BASELINE)
check("v0.1.87/C5: baseline delta — only moved keys surface",
      list(_del_c3) == ["usage"] and _del_c3["usage"] == {"misses": {"baseline": 0, "current": 2}})
check("v0.1.87/C6: baseline delta — an unchanged fleet reads empty (the standing no-op)",
      _crep.delta(dict(_crep.BASELINE), _crep.BASELINE) == {})

# hermetic CLI: HOME=<empty tmp> → zero stores, but the JSON shape + exit codes must hold
with _tf43.TemporaryDirectory() as _tdC:
    _envC = {**_os53.environ, "HOME": str(_tdC)}
    _envC.pop("CLAUDE_PLUGIN_ROOT", None)
    _pC = _sp53.run([sys.executable, str(_scripts54 / "calibration_report.py"), "--json"],
                    capture_output=True, text=True, timeout=60, env=_envC)
    _dC = _json43.loads(_pC.stdout)
    check("v0.1.87/C7: hermetic CLI — JSON carries current/baseline/delta/ledger/refit_gate, exit 0 on an empty fleet",
          _pC.returncode == 0 and set(_dC) == {"current", "baseline", "delta", "ledger", "refit_gate"}
          and _dC["current"]["records"] == 0 and _dC["refit_gate"] == "wait")
    _pC2 = _sp53.run([sys.executable, str(_scripts54 / "calibration_report.py"), "--sicne"],
                     capture_output=True, text=True, timeout=60, env=_envC)
    check("v0.1.87/C8: an unknown flag is a usage error (exit 2), never a silent ignore",
          _pC2.returncode == 2)

# ── cross-project hardening (ADR 002–007): shipped StoreContext + policy ─────
import os as _os_xp
import json as _json_xp
import tempfile as _tf_xp
import subprocess as _sp_xp
import store_context as sc  # noqa: E402
import domain_policy as dp  # noqa: E402
import mirror_conflict as mc  # noqa: E402
import index_admission as ia  # noqa: E402
import capabilities as cap  # noqa: E402
import control_plane as cp  # noqa: E402
import canonical_ingress as ci  # noqa: E402
import retention as ret  # noqa: E402
import cm_ops as cmo  # noqa: E402

_xp_home0 = _os_xp.environ.get("HOME")
_xp_cfg0 = _os_xp.environ.get("CLAUDE_CONFIG_DIR")
_xp_slot0 = _os_xp.environ.get("CLAUDE_CODE_PROJECT_DIR_NAME")
_xp_dis0 = _os_xp.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")
_xp_set0 = _os_xp.environ.get("CLAUDE_CODE_SETTINGS")


def _xp_env(home: Path, extra: dict | None = None) -> dict:
    env = {**_os_xp.environ, "HOME": str(home)}
    for k in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_PROJECT_DIR_NAME",
              "CLAUDE_CODE_DISABLE_AUTO_MEMORY", "CLAUDE_CODE_SETTINGS",
              "CM_STORE_OVERRIDE", "CM_DOMAIN", "CM_CRASH_AFTER"):
        env.pop(k, None)
    if extra:
        env.update(extra)
    return env


with _tf_xp.TemporaryDirectory() as _tdxp:
    _home = Path(_tdxp) / "home"
    _home.mkdir()
    _proj = Path(_tdxp) / "proj"
    _proj.mkdir()
    (_proj / "readme.txt").write_text("x\n", encoding="utf-8")
    env = _xp_env(_home)
    ctx = sc.resolve_store(_proj, environ=env)
    check("StoreContext: default config_root is $HOME/.claude",
          ctx.config_root == _home / ".claude")
    check("StoreContext: default native store is config/projects/<slug>/memory (no hard-coded ~/.claude in caller)",
          ctx.native_memory_dir == _home / ".claude" / "projects" / ms.slug_for(_proj) / "memory")
    check("StoreContext: unknown domain by default (not silently personal/universal)",
          ctx.domain_id == "unknown")
    check("StoreContext: auto-memory enabled by default", ctx.auto_memory_enabled is True)
    check("StoreContext: non-Git project_id is a bound UUID (p_ + 32 hex)",
          ctx.project_id.startswith("p_") and len(ctx.project_id) == 34)

    env2 = _xp_env(_home, {"CLAUDE_CONFIG_DIR": str(Path(_tdxp) / "cfg")})
    ctx2 = sc.resolve_store(_proj, environ=env2)
    check("StoreContext: CLAUDE_CONFIG_DIR moves config_root",
          ctx2.config_root == Path(_tdxp) / "cfg")
    check("StoreContext: CLAUDE_CONFIG_DIR moves native store off $HOME/.claude",
          str(ctx2.native_memory_dir).startswith(str(Path(_tdxp) / "cfg")))

    env3 = _xp_env(_home, {"CLAUDE_CODE_PROJECT_DIR_NAME": "shared-slot"})
    ctx3 = sc.resolve_store(_proj, environ=env3)
    check("StoreContext: CLAUDE_CODE_PROJECT_DIR_NAME changes the projects slot",
          ctx3.project_slot == "shared-slot"
          and ctx3.native_memory_dir == _home / ".claude" / "projects" / "shared-slot" / "memory")

    (_proj / ".claude").mkdir()
    _proj_mem = _proj / "custom-mem"
    (_proj / ".claude" / "settings.json").write_text(
        _json_xp.dumps({"autoMemoryDirectory": str(_proj_mem)}), encoding="utf-8")
    ctx4 = sc.resolve_store(_proj, environ=_xp_env(_home))
    check("StoreContext: autoMemoryDirectory from project settings wins",
          ctx4.native_memory_dir == _proj_mem
          and ctx4.resolution_source == "autoMemoryDirectory")
    (_proj / ".claude" / "settings.json").unlink()

    env5 = _xp_env(_home, {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
    ctx5 = sc.resolve_store(_proj, environ=env5)
    check("StoreContext: CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 disables auto-memory",
          ctx5.auto_memory_enabled is False and ctx5.write_allowed is False)

    # two live MEMORY.md stores without override → fail-closed writes
    _a = _home / ".claude" / "projects" / ms.slug_for(_proj) / "memory"
    _b = Path(_tdxp) / "other-mem"
    _a.mkdir(parents=True)
    _b.mkdir(parents=True)
    (_a / "MEMORY.md").write_text("# a\n", encoding="utf-8")
    (_b / "MEMORY.md").write_text("# b\n", encoding="utf-8")
    (_proj / ".claude" / "settings.json").write_text(
        _json_xp.dumps({"autoMemoryDirectory": str(_b)}), encoding="utf-8")
    ctx6 = sc.resolve_store(_proj, environ=_xp_env(_home))
    check("StoreContext: disagreeing live stores refuse writes",
          ctx6.write_allowed is False and len(ctx6.ambiguity) >= 1)
    wrote = False
    try:
        sc.assert_writable(ctx6)
        wrote = True
    except sc.WriteRefused:
        wrote = False
    check("StoreContext: assert_writable raises WriteRefused on disagreement", wrote is False)
    (_proj / ".claude" / "settings.json").unlink()

    missing_settings = Path(_tdxp) / "gone-settings.json"
    ctx7 = sc.resolve_store(_proj, environ=_xp_env(_home, {
        "CLAUDE_CODE_SETTINGS": str(missing_settings)}))
    check("StoreContext: ephemeral --settings that cannot be reconstructed fails closed",
          ctx7.write_allowed is False
          and any("settings" in a for a in ctx7.ambiguity))

    # git worktree + nested subdir share one native store
    _grepo = Path(_tdxp) / "grepo"
    _grepo.mkdir()
    (_grepo / "f.txt").write_text("hi\n", encoding="utf-8")
    (_grepo / "src").mkdir()
    (_grepo / "src" / "nested.txt").write_text("n\n", encoding="utf-8")
    _gwd = str(_grepo)
    _sp_xp.run(["git", "init"], check=True, cwd=_gwd, capture_output=True, text=True)
    _sp_xp.run(["git", "config", "user.email", "you@example.com"], check=True, cwd=_gwd, capture_output=True, text=True)
    _sp_xp.run(["git", "config", "user.name", "you"], check=True, cwd=_gwd, capture_output=True, text=True)
    _sp_xp.run(["git", "add", "-A"], check=True, cwd=_gwd, capture_output=True, text=True)
    _sp_xp.run(["git", "commit", "-m", "init"], check=True, cwd=_gwd, capture_output=True, text=True)
    _wt = Path(_tdxp) / "gworktree"
    _sp_xp.run(["git", "worktree", "add", str(_wt), "HEAD"], check=True, cwd=_gwd, capture_output=True, text=True)
    envg = _xp_env(_home)
    c_root = sc.resolve_store(_grepo, environ=envg)
    c_nest = sc.resolve_store(_grepo / "src", environ=envg)
    c_wt = sc.resolve_store(_wt, environ=envg)
    check("StoreContext: nested subdir of a git repo shares the native store",
          c_root.native_memory_dir == c_nest.native_memory_dir)
    check("StoreContext: two worktrees of one git_common_dir share the native store",
          c_root.native_memory_dir == c_wt.native_memory_dir
          and c_root.git_common_dir is not None
          and c_wt.git_common_dir is not None
          and c_root.git_common_dir.resolve() == c_wt.git_common_dir.resolve())
    check("StoreContext: same basename, two roots → distinct project_id",
          sc.resolve_store(_proj, environ=envg).project_id
          != sc.resolve_store(Path(_tdxp) / "proj2" if False else _grepo, environ=envg).project_id)
    _other = Path(_tdxp) / "also-proj"
    _other.mkdir()
    check("StoreContext: two non-git dirs named similarly stay distinct",
          sc.resolve_store(_proj, environ=envg).project_id
          != sc.resolve_store(_other, environ=envg).project_id)
    env_p1 = _xp_env(_home, {"CLAUDE_CONFIG_DIR": str(Path(_tdxp) / "profile-a")})
    env_p2 = _xp_env(_home, {"CLAUDE_CONFIG_DIR": str(Path(_tdxp) / "profile-b")})
    check("StoreContext: same repo under two profiles → distinct project_id",
          sc.resolve_store(_grepo, environ=env_p1).project_id
          != sc.resolve_store(_grepo, environ=env_p2).project_id)

    # domain / sensitivity (shipped admit_cross_project)
    check("domain: unknown-domain project admits zero domain-tagged facts",
          dp.admit_cross_project("unknown", {"domain": "personal", "scope": "user-global"}) is False)
    check("domain: unknown is local-only (untagged dual-read no longer admits)",
          dp.admit_cross_project("unknown", {"scope": "user-global"},
                                 migration_mode=dp.MIGRATION_DUAL_READ) is False)
    check("domain: unknown+untagged enforced admits zero",
          dp.admit_cross_project("unknown", {"scope": "user-global"},
                                 migration_mode=dp.MIGRATION_ENFORCED) is False)
    check("domain: cross-domain replicate is denied",
          dp.admit_cross_project("personal", {"domain": "employer"}) is False)
    check("domain: same-domain admitted",
          dp.admit_cross_project("personal", {"domain": "personal"}) is True)
    check("domain: confidential stays inside its domain",
          dp.admit_cross_project("personal", {"domain": "employer", "sensitivity": "confidential"},
                                 authorized_pairs={("employer", "personal")}) is False)
    check("domain: untagged confidential is denied under dual-read (no migration exception)",
          dp.admit_cross_project("work", {"sensitivity": "confidential", "scope": "user-global"},
                                 migration_mode=dp.MIGRATION_DUAL_READ) is False
          and dp.admit_cross_project("unknown", {"sensitivity": "confidential"},
                                     migration_mode=dp.MIGRATION_DUAL_READ) is False)
    _sec_err = dp.validate_write_policy(
        "---\nname: x\ndescription: key\n---\npassword = hunter2-and-a-long-token\n",
        {"description": "key"}, looks_secret=ms._looks_secret, domain="personal")
    check("domain: secret-shaped body is rejected as a fact", _sec_err is not None)

    import fact_schema as fsch  # noqa: E402
    check("fact_schema: name must equal stem",
          fsch.validate_canonical_frontmatter({"name": "other"}, stem="deploy", domain="work")
          is not None)
    check("fact_schema: matching name+domain is ok",
          fsch.validate_canonical_frontmatter(
              {"name": "deploy", "domain": "work", "scope": "user-global",
               "schema_version": "3", "fact_id": fsch.stable_fact_id("work", "deploy"),
               "description": "d", "sensitivity": "internal", "status": "active",
               "applies_any": "[]", "applies_all": "[]", "applies_exclude": "[]",
               "content_modified": "2026-01-01T00:00:00Z",
               "last_observed_at": "2026-01-01T00:00:00Z"},
              stem="deploy", domain="work") is None)
    check("fact_schema: missing required v3 field is refused",
          fsch.validate_canonical_frontmatter(
              {"name": "deploy", "domain": "work", "scope": "user-global"},
              stem="deploy", domain="work") is not None)

    # three-way classifier (shipped)
    _canon = "---\nname: f\ndescription: d1\n---\nbody A\n"
    _local = "---\nname: f\ndescription: d1\n  global_ref: f\n  global_ref_body: " + mc.body_hash(_canon) + "\n---\nbody A\n"
    _canon2 = "---\nname: f\ndescription: d2 NEW KEY\n---\nbody A\n"
    check("three-way: local unchanged + canonical desc changed → refresh (Probe C class)",
          mc.classify_mirror(_local, _canon2)["action"] == mc.REFRESH)
    _local_edit = "---\nname: f\ndescription: d1\n  global_ref: f\n  global_ref_body: " + mc.body_hash(_canon) + "\n---\nbody LOCAL\n"
    check("three-way: local body edited, canonical unchanged → stop (never overwrite)",
          mc.classify_mirror(_local_edit, _canon)["action"] == mc.STOP_LOCAL)
    _canon3 = "---\nname: f\ndescription: d1\n---\nbody CANON\n"
    check("three-way: both changed differently → conflict",
          mc.classify_mirror(_local_edit, _canon3)["action"] == mc.CONFLICT)
    check("three-way: unstamped same-content restamps; missing base + divergent body quarantines; empty local quarantines",
          mc.classify_mirror("---\nname: f\ndescription: d1\nmodified: 2099-01-01\n---\nbody A\n",
                             _canon)["action"] == mc.RESTAMP
          and mc.classify_mirror("---\nname: f\n---\nbody\n", _canon)["action"] == mc.QUARANTINE
          and mc.classify_mirror("", _canon)["action"] == mc.QUARANTINE)
    _base = mc.semantic_hash(_canon)
    _same = "---\nname: f\ndescription: d1\nmodified: 2099-01-01\n---\nbody A\n"
    check("three-way: semantic equality ignores native modified",
          mc.semantic_hash(_canon) == mc.semantic_hash(_same)
          and mc.classify_mirror(_canon, _same, base_revision=_base)["action"] in (mc.IN_SYNC, mc.RESTAMP))

    # exact index admission (shipped)
    _lim_l = ia.line_limit_with_reserve()
    _lim_b = ia.byte_limit_with_reserve()
    _lines = "# Memory Index\n\n" + "\n".join(f"- [f{i}](f{i}.md) — x" for i in range(_lim_l + 5)) + "\n"
    _dec_l = ia.project_index(_lines)
    check("admission: 200-line-first terse index is refused below the byte cap",
          _dec_l["admitted"] is False and _dec_l["projected_bytes"] < ia.NATIVE_INDEX_CAP_BYTES
          and _dec_l["projected_lines"] > _lim_l)
    _fat = "# Memory Index\n\n" + ("- [x](x.md) — " + ("字" * 400) + "\n") * 30
    _dec_b = ia.project_index(_fat)
    check("admission: 25KB-first (multibyte UTF-8) is refused below the line cap",
          _dec_b["admitted"] is False and _dec_b["projected_lines"] < ia.NATIVE_INDEX_CAP_LINES
          and _dec_b["projected_bytes"] > _lim_b)

    # capabilities + applies
    (_proj / "package.json").write_text('{"name":"n"}\n', encoding="utf-8")
    (_proj / "go.mod").write_text("module n\n", encoding="utf-8")
    (_proj / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    _caps = cap.capability_tags(cap.detect_capabilities(_proj))
    check("capabilities: extensible detectors include node/go/docker classes (not only python)",
          {"node", "go", "docker"}.issubset(_caps) or ({"node", "go"} <= _caps and "docker" in _caps))
    check("applies: exclude windows against linux host",
          cap.applies_match({"any": ["python"], "exclude": ["windows"]}, {"python", "linux"}) is True)
    check("applies: all: [pdf, gpu] fails without gpu",
          cap.applies_match({"all": ["pdf", "gpu"]}, {"pdf"}) is False)

    # v0.4.0: dormant hook-sketch infra REMOVED — the module must be gone.
    try:
        import hook_sketches  # type: ignore[import-not-found]  # noqa: F401
        _hk_gone = False
    except ImportError:
        _hk_gone = True
    check("v0.4.0: hook-sketch infra removed — hook_sketches module is gone", _hk_gone)
    # …and the doc inventories must not resurrect the name (the CHANGELOG
    # legitimately keeps it — history is the record, not a live inventory).
    _hk_docs = (ROOT / "CLAUDE.md").read_text(encoding="utf-8") \
        + (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    check("v0.4.0: hook_sketches absent from the CLAUDE.md and AGENTS.md inventories",
          "hook_sketches" not in _hk_docs)

    # ── v0.4.0 Phase-4 authority pins (#145 grants, #149 replacement cycles,
    #    #8 capability cache, #12 export/import round-trip, #11 CLI envelope) ──
    with _tf_xp.TemporaryDirectory() as _td40:
        import types as _ty40
        _pdata40 = Path(_td40) / "pdata"; _pdata40.mkdir(parents=True)
        _ns40a = Path(_td40) / "ns-a"
        # P1-6 (#145): ONE owner per normalized path in SQLite — grant-vs-grant
        # refused, revoke frees the path, transfer moves the owner.
        _g140 = sc.write_store_grant(_pdata40, "proj-a", _ns40a)
        _refused40 = False
        try:
            sc.write_store_grant(_pdata40, "proj-b", _ns40a)
        except sc.WriteRefused:
            _refused40 = True
        _rev40 = sc.revoke_store_grant(_pdata40, "proj-a", _ns40a)
        _g240 = sc.write_store_grant(_pdata40, "proj-b", _ns40a)
        _tr40 = sc.transfer_store_grant(_pdata40, _ns40a, "proj-c")
        _rows40 = sc.load_store_grants(_pdata40)
        _own40 = [g for g in _rows40 if g["path"] == str(_ns40a.resolve())]
        check("P1-6 (#145): one owner per normalized path — grant-vs-grant refused, "
              "revoke frees it, transfer moves it (SQLite, not store-grants.json)",
              bool(_g140.get("ok") and _refused40 and _rev40.get("removed") == 1
                   and _g240.get("ok") and _tr40.get("ok") and _tr40.get("to") == "proj-c"
                   and len(_own40) == 1 and _own40[0]["project_id"] == "proj-c"))
        # P1-10 (#149): replacement cycles + self-replacement refused.
        _fdir40 = Path(_td40) / "facts"; _fdir40.mkdir()
        _ctx40 = _ty40.SimpleNamespace(domain_id="personal", canonical_domain_dir=_fdir40)
        (_fdir40 / "a.md").write_text(
            "---\nname: a\nstatus: active\nreplacement_id: b\n---\nbody\n", encoding="utf-8")
        (_fdir40 / "b.md").write_text(
            "---\nname: b\nstatus: active\nreplacement_id: a\n---\nbody\n", encoding="utf-8")
        check("P1-10 (#149): replacement cycle refused (a→b→a) and self-replacement refused",
              "cycle" in str(ci._validate_replacement_id(_ctx40, "a", "b"))  # type: ignore[arg-type]
              and "same fact" in str(ci._validate_replacement_id(_ctx40, "a", "a")))  # type: ignore[arg-type]
        # P1-10 (#149): a legacy (non-ACTIVE) target is not a valid dependency.
        (_fdir40 / "old.md").write_text(
            "---\nname: old\nmetadata:\n  node_type: memory\n---\nlegacy body\n", encoding="utf-8")
        (_fdir40 / "new.md").write_text(
            "---\nname: new\nmetadata:\n  scope: user-global\n  type: feedback\n---\nsee [[old]]\n",
            encoding="utf-8")
        _lerr40 = ci.validate_links((_fdir40 / "new.md").read_text(encoding="utf-8"),
                                    "user-global", _fdir40)
        check("P1-10 (#149): a legacy (non-ACTIVE) target is not a valid dependency",
              isinstance(_lerr40, str) and "not a valid active canonical" in _lerr40)
        # P1-10 (#149): the CANONICAL writer refuses duplicate reserved keys too
        # (the local path is pinned by R128-3; this pins the canonical codec).
        _dup40 = ci.upsert(_ctx40, "new", (  # type: ignore[arg-type]
            "---\nname: new\nname: new\nmetadata:\n  scope: user-global\n  type: feedback\n---\nbody\n"))
        check("P1-10 (#149): canonical upsert refuses a duplicate reserved frontmatter key",
              _dup40.get("ok") is False and "duplicate reserved key" in str(_dup40.get("error") or ""))
        # (#8): capability cache — a sig hit returns the cached rows; a marker
        # change (go.mod appears) re-detects instead of serving the stale cache.
        _proj40 = Path(_td40) / "caproj"; _proj40.mkdir()
        (_proj40 / "package.json").write_text("{}\n", encoding="utf-8")
        _capcache40 = Path(_td40) / "cache"
        _r140 = cap.detect_capabilities(_proj40, cache_dir=_capcache40, project_id="p40")
        _r240 = cap.detect_capabilities(_proj40, cache_dir=_capcache40, project_id="p40")
        (_proj40 / "go.mod").write_text("module x\n", encoding="utf-8")
        _r340 = cap.detect_capabilities(_proj40, cache_dir=_capcache40, project_id="p40")
        check("v0.4.0 (#8): capability cache — sig-hit returns cached rows, a marker "
              "change re-detects (monorepo/go detected only after go.mod lands)",
              _r140 == _r240 and any(x["tag"] == "go" for x in _r340))
        # (#12): export→import round-trips plugin-data; a path-escape member refused.
        import sqlite3 as _sq40
        _src40 = Path(_td40) / "srcdata"; _src40.mkdir()
        _conn40 = _sq40.connect(str(_src40 / "control.sqlite"))
        _conn40.execute("CREATE TABLE t (k TEXT)")
        _conn40.execute("INSERT INTO t VALUES ('v1')")
        _conn40.commit(); _conn40.close()
        (_src40 / "ops" / "slot").mkdir(parents=True)
        (_src40 / "ops" / "slot" / ".consolidation-log.jsonl").write_text("{}\n", encoding="utf-8")
        _bundle40 = Path(_td40) / "bundle.tar.gz"
        ret.export_ops(_src40, _bundle40)
        _dst40 = Path(_td40) / "dstdata"
        _out40 = ret.import_ops(_bundle40, _dst40)
        _conn40b = _sq40.connect(str(_dst40 / "control.sqlite"))
        _v40 = _conn40b.execute("SELECT k FROM t").fetchone()
        _conn40b.close()
        check("v0.4.0 (#12): export→import restores plugin-data (round-trip, DB queryable)",
              bool(_out40.get("ok") and _v40 is not None and _v40[0] == "v1"
                   and (_dst40 / "ops" / "slot" / ".consolidation-log.jsonl").is_file()))
        import tarfile as _tar40
        _evil40 = Path(_td40) / "evil.tar.gz"
        with _tar40.open(str(_evil40), "w:gz") as _t40:
            _info40 = _tar40.TarInfo("plugin-data/../../evil.md")
            _info40.size = 4
            _t40.addfile(_info40, __import__("io").BytesIO(b"evil"))
        _imp_evil = ret.import_ops(_evil40, _dst40)
        check("v0.4.0 (#12): import refuses a path-escape member",
              not _imp_evil.get("ok")
              and str(_imp_evil.get("error", "")).startswith("import path escape"))
        # a tampered member must FAIL the import (the export's sha256 manifest
        # is now CHECKED, not skipped).
        _tampered40 = Path(_td40) / "tampered.tar.gz"
        with _tar40.open(str(_bundle40), "r:gz") as _src_t:
            _mems40 = []
            for _m40s in _src_t.getmembers():
                _f40s = _src_t.extractfile(_m40s)
                _d40s = _f40s.read() if (_m40s.isfile() and _f40s is not None) else b""
                _mems40.append((_m40s, _d40s))
        with _tar40.open(str(_tampered40), "w:gz") as _t40b:
            for _m40, _d40 in _mems40:
                if not _m40.isfile():
                    continue
                if _m40.name == "plugin-data/control.sqlite" and _d40:
                    _d40 = _d40[:-1] + (b"X" if _d40[-1:] != b"X" else b"Y")
                _info40 = _tar40.TarInfo(name=_m40.name)
                _info40.size = len(_d40)
                _t40b.addfile(_info40, __import__("io").BytesIO(_d40))
        _imp_tam40 = ret.import_ops(_tampered40, Path(_td40) / "dsttampered")
        check("v0.4.0 (#12): a tampered member fails the import (manifest sha256 checked)",
              not _imp_tam40.get("ok")
              and "sha256 mismatch" in str(_imp_tam40.get("error") or ""))
        # (#9): the registry indexes exist in a FRESH DB and cm doctor reports
        # the integrity check.
        _reg40 = Path(_td40) / "regproj"; _reg40.mkdir()
        _enroll_personal(_reg40)
        _ctx40r = sc.resolve_store(_reg40)
        _conn40r = cp.connect(cp.db_path(_ctx40r))
        try:
            _inames40 = {r[0] for r in _conn40r.execute(
                "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        finally:
            _conn40r.close()
        check("v0.4.0 (#9): registry indexes exist in a fresh DB + doctor reports integrity",
              {"idx_facts_domain_stem", "idx_holders_project",
               "idx_tombstones_domain"} <= _inames40
              and isinstance(sc.doctor_dict(_ctx40r).get("integrity_check"), str))
        # (#9b): the dormant sketch tables are GONE from a FRESH registry too —
        # the removal is complete at the schema level, not just the module.
        _conn40t = cp.connect(cp.db_path(_ctx40r))
        try:
            _tnames40 = {r[0] for r in _conn40t.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        finally:
            _conn40t.close()
        check("v0.4.0 (#9): fresh control.sqlite has NEITHER usage_events NOR workflow_sketches",
              {"usage_events", "workflow_sketches"} & _tnames40 == set()
              and {"projects", "facts", "holders"} <= _tnames40)
        # (#9c): the v3→v4 migration DROPs the dormant tables on an EXISTING
        # install — simulate a pre-drop v3 registry (full current schema + the
        # old literal DDL + sentinel rows + user_version 3) and reopen it.
        _dbp40 = cp.db_path(_ctx40r)
        _c40m = _sq40.connect(str(_dbp40))
        try:
            _c40m.executescript(cp.SCHEMA_SQL)
            _c40m.executescript(
                "CREATE TABLE IF NOT EXISTS usage_events ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, day TEXT, sketch TEXT);"
                "CREATE TABLE IF NOT EXISTS workflow_sketches ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, day TEXT, sketch TEXT);")
            _c40m.execute("INSERT INTO usage_events (project_id, day, sketch) "
                          "VALUES ('probe','2026-08-31','x')")
            _c40m.execute("INSERT INTO workflow_sketches (project_id, day, sketch) "
                          "VALUES ('probe','2026-08-31','x')")
            _c40m.execute("PRAGMA user_version = 3")
            _c40m.commit()
            # pre-reopen self-check: the tables + sentinels must exist BEFORE
            # the migration runs, or the pin would pass vacuously.
            _pre40 = {r[0] for r in _c40m.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            _npre40 = _c40m.execute(
                "SELECT COUNT(*) AS n FROM usage_events").fetchone()[0]
        finally:
            _c40m.close()
        _conn40m = cp.connect(_dbp40)   # ver 3 < REGISTRY_USER_VERSION → migration runs
        try:
            _t40m = {r[0] for r in _conn40m.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            _ver40m = int(_conn40m.execute("PRAGMA user_version").fetchone()[0])
        finally:
            _conn40m.close()
        check("v0.4.0 (#9): reopening a v3 registry with sketch tables drops them and "
              "lands user_version == REGISTRY_USER_VERSION",
              {"usage_events", "workflow_sketches"} <= _pre40 and _npre40 == 1
              and {"usage_events", "workflow_sketches"} & _t40m == set()
              and {"projects", "facts", "holders"} <= _t40m
              and _ver40m == cp.REGISTRY_USER_VERSION)
        # (#11): CLI error envelope — a refused grant with --json emits
        # {ok:false, error, code:2} and exits 2.
        _env40_u, _env40_e = _io73.StringIO(), _io73.StringIO()
        with _ctx73.redirect_stdout(_env40_u), _ctx73.redirect_stderr(_env40_e):
            _rc40_env = cmo.main(["project", "grant-native", "--path", str(_pdata40),
                                  "--apply", "--confirm", "grant-native", "--json"])
        _env40_j = _json_xp.loads(_env40_u.getvalue().strip() or "{}")
        check("v0.4.0 (#11): CLI error envelope — {ok, error, code} on --json with exit 2",
              _rc40_env == 2 and _env40_j.get("ok") is False and _env40_j.get("code") == 2
              and isinstance(_env40_j.get("error"), str) and bool(_env40_j["error"]))

    # generated catalog overwrites a hand-edited index
    _facts = Path(_tdxp) / "facts"
    _facts.mkdir()
    (_facts / "alpha.md").write_text(_v3_canon("alpha", description="A"), encoding="utf-8")
    (_facts / "MEMORY.md").write_text("# HAND EDITED INDEX\n", encoding="utf-8")
    _cat = ci.hand_edit_refused_or_regenerated(_facts)
    check("canonical catalog: hand-edited global index is overwritten by generation",
          "HAND EDITED" not in (_facts / "MEMORY.md").read_text(encoding="utf-8")
          and "alpha.md" in _cat)

    # link monotonicity
    check("links: domain-global must not require a project-local target",
          ci.link_allowed("user-global", "project-local") is False)
    check("links: project-local may link upward",
          ci.link_allowed("project-local", "user-global") is True)

    # retention reverse-tail + native plane cleanliness
    _ops = Path(_tdxp) / "ops.jsonl"
    with _ops.open("w", encoding="utf-8") as _fh:
        for i in range(20):
            _fh.write(_json_xp.dumps({"n": i, "day": "2026-08-31"}) + "\n")
    _tail = ret.reverse_tail_jsonl_lines(_ops, 3)
    check("retention: reverse-tail returns last N records (not full-file split-then-tail of the API)",
          [r["n"] for r in _tail] == [17, 18, 19])
    _native = Path(_tdxp) / "native-clean"
    _native.mkdir()
    (_native / "MEMORY.md").write_text("# i\n", encoding="utf-8")
    (_native / "fact.md").write_text("x\n", encoding="utf-8")
    check("native plane: MEMORY.md + facts only is clean (no logs/locks/ledgers)",
          ret.native_plane_is_clean(_native) is True)
    (_native / ".fleet-usage.jsonl").write_text("{}\n", encoding="utf-8")
    check("native plane: fleet ledger makes it unclean",
          ret.native_plane_is_clean(_native) is False)
    check("inventory: canonical must not live under plugin data",
          ret.inventory(Path(_tdxp) / "pdata", Path(_tdxp) / "canon", _native)["canonical_inside_plugin_data"] is False)

    _pstore = sc.resolve_store(_proj, environ=_xp_env(_home)).native_memory_dir
    _pstore.mkdir(parents=True, exist_ok=True)
    rd._persist({"project": "p", "entries": [],
                 "marker": {"commit": "abc", "timestamp": "2026-08-31T00:00:00Z"}},
                str(_pstore))
    _clog = ret.cycle_log_write_path(_pstore)
    check("persist: cycle log lands in plugin-data, native plane has no .consolidation-log.jsonl",
          _clog.is_file() and not (_pstore / ".consolidation-log.jsonl").exists())
    _nat_ops = Path(_tdxp) / "native-ops"
    _nat_ops.mkdir()
    (_nat_ops / ".consolidation-log.jsonl").write_text('{"c":1}\n', encoding="utf-8")
    (_nat_ops / ".mutation-log.jsonl").write_text('{"m":1}\n', encoding="utf-8")
    (_nat_ops / ".fleet-usage.jsonl").write_text('{"f":1}\n', encoding="utf-8")
    _pdata_ops = Path(_tdxp) / "pdata-ops"
    _reloc = ret.relocate_native_operational(_nat_ops, _pdata_ops, "sha-must-not-be-the-ops-key")
    _sha_ops = _pdata_ops / "ops" / "sha-must-not-be-the-ops-key"
    check("relocate: leftover native logs leave the native plane",
          _reloc["ok"] is True and ret.native_plane_is_clean(_nat_ops) is True)
    check("relocate: cycle+mutation land on persist/audit write paths (slot, not SHA project_id)",
          ret.cycle_log_write_path(_nat_ops, plugin_data=_pdata_ops).is_file()
          and ret.mutation_log_write_path(_nat_ops, plugin_data=_pdata_ops).is_file()
          and not (_sha_ops / ".consolidation-log.jsonl").exists()
          and not (_sha_ops / ".mutation-log.jsonl").exists())
    check("relocate: leftover .fleet-usage.jsonl merges onto the harvest write path",
          (_pdata_ops / "fleet-usage.jsonl").is_file()
          and not (_sha_ops / ".fleet-usage.jsonl").exists())

    # journal crash + recovery (shipped transact)
    envj = _xp_env(_home)
    ctxj = sc.resolve_store(_proj, environ=envj)
    ctxj = sc.resolve_store(_proj, environ=envj)  # domain unknown, writes allowed (no live disagreement now)
    # clear the two live MEMORY.md disagreement from earlier: remove custom other-mem live? already unlinked settings
    # The default native may still have MEMORY.md from disagreement test — only one live now.
    try:
        sc.assert_writable(sc.resolve_store(_proj, environ=envj))
        _crash_ok = True
    except sc.WriteRefused:
        _crash_ok = False
    if _crash_ok:
        _crashed = False
        _jdest = sc.resolve_store(_proj, environ=envj).native_memory_dir / "journal-probe.md"

        def _jmut(conn, temps):
            temps[str(_jdest)] = "journal probe body\n"
            return {"x": 1}

        try:
            cp.transact(sc.resolve_store(_proj, environ=envj), "noop", {"k": 1},
                        _jmut, crash_after="publish")
        except cp.CrashSimulated:
            _crashed = True
        check("journal: crash_after=publish raises CrashSimulated AFTER dest landed, pending op remains",
              _crashed is True and _jdest.exists())
        _conn = cp.connect_journal(sc.resolve_store(_proj, environ=envj))
        _pending_xp = cp.pending_ops(_conn)
        check("journal: pending op is recoverable",
              len(_pending_xp) >= 1)
        _rconn_xp = cp.connect(cp.db_path(sc.resolve_store(_proj, environ=envj)))
        _recovered_xp = cp.recover_pending(
            _conn, ctx=sc.resolve_store(_proj, environ=envj), registry_conn=_rconn_xp)
        check("journal: recover_pending is idempotent (second call empty) and dest remains",
              len(_recovered_xp) >= 1 and cp.pending_ops(_conn) == [] and _jdest.exists()
              and "journal probe body" in _jdest.read_text(encoding="utf-8"))
        _rconn_xp.close()
        _conn.close()
    else:
        check("journal: writable fixture available", False)

    # doctor twice-run equality is a CLI test; here pin doctor_report stability
    _doc1 = sc.doctor_report(sc.resolve_store(_proj, environ=_xp_env(_home)))
    _doc2 = sc.doctor_report(sc.resolve_store(_proj, environ=_xp_env(_home)))
    check("doctor_report: twice-run content equality (shipped)",
          _doc1 == _doc2 and "native_memory_dir:" in _doc1 and "resolution_source:" in _doc1
          and "profile_id:" in _doc1 and "domain_id:" in _doc1 and "auto_memory_enabled:" in _doc1
          and "ambiguity:" in _doc1 and "registry_state:" in _doc1
          and "unenrolled_share_warning:" in _doc1)

    # no sixth slug_for: store_context.slug_for IS memory_status.slug_for
    check("slug_for: store_context aliases memory_status (no sixth reimplementation)",
          sc.slug_for(_proj) == ms.slug_for(_proj))

    _parser_cm = cmo.build_parser()
    _a_plan = _parser_cm.parse_args(["data", "compact", "--plan", "--project", str(_proj)])
    _a_show = _parser_cm.parse_args(["data", "retention", "show", "--project", str(_proj)])
    check("cm data compact --plan is accepted (dry-run flag; compact still plans unless --apply)",
          _a_plan.data_cmd == "compact" and _a_plan.plan is True and _a_plan.apply is False)
    check("cm data retention show is accepted (optional show token)",
          _a_show.data_cmd == "retention" and _a_show.show == "show")

    check("apply_provenance is pure (strips projects:, idempotent, no I/O)",
          sg.apply_provenance("---\nname: x\nmetadata:\n  scope: user-global\n---\n", "beta")
          == "---\nname: x\nmetadata:\n  scope: user-global\n---\n"
          and sg.apply_provenance(
              "---\nname: x\nmetadata:\n  scope: user-global\n  projects: [beta]\n---\n", "beta")
          == "---\nname: x\nmetadata:\n  scope: user-global\n---\n")

# restore env
if _xp_home0 is None:
    _os_xp.environ.pop("HOME", None)
else:
    _os_xp.environ["HOME"] = _xp_home0
for _k, _v in (("CLAUDE_CONFIG_DIR", _xp_cfg0), ("CLAUDE_CODE_PROJECT_DIR_NAME", _xp_slot0),
               ("CLAUDE_CODE_DISABLE_AUTO_MEMORY", _xp_dis0), ("CLAUDE_CODE_SETTINGS", _xp_set0)):
    if _v is None:
        _os_xp.environ.pop(_k, None)
    else:
        _os_xp.environ[_k] = _v

# ── P0: enrollment, identifier containment, journal hashes, forget/catalog ──
import hashlib as _hl_p0
import identifiers as ident  # noqa: E402

_id_ok = True
for _p0_raw in ("../work", "/etc/passwd", "unknown", "Work", "has space", "a" * 80, ""):
    try:
        ident.validate_domain_id(_p0_raw)
        _id_ok = False
    except ident.IdentifierRefused:
        pass
try:
    ident.validate_domain_id("work")
    ident.validate_domain_id("unknown", allow_unknown=True)
except ident.IdentifierRefused:
    _id_ok = False
check("identifiers: validate_domain_id accepts work, refuses traversal/absolute/reserved/case", _id_ok)

_st_ok = True
for _p0_stem in ("../x", "/tmp/x", "MEMORY", "a/b", ".."):
    try:
        ident.validate_fact_stem(_p0_stem)
        _st_ok = False
    except ident.IdentifierRefused:
        pass
try:
    ident.validate_fact_stem("ok-stem_1.md".replace(".md", ""))
except ident.IdentifierRefused:
    _st_ok = False
check("identifiers: validate_fact_stem refuses traversal/absolute/MEMORY", _st_ok)

_pid_ok = True
try:
    ident.validate_project_id("not-a-pid")
    _pid_ok = False
except ident.IdentifierRefused:
    pass
try:
    ident.validate_project_id("p_" + "ab" * 16)
except ident.IdentifierRefused:
    _pid_ok = False
check("identifiers: validate_project_id requires p_ + 32 hex", _pid_ok)

with _tf_xp.TemporaryDirectory() as _td_sc:
    _root = Path(_td_sc) / "root"
    _root.mkdir()
    try:
        ident.safe_child(_root, "../outside")
        _sc_ok = False
    except ident.IdentifierRefused:
        _sc_ok = True
    try:
        ident.safe_child(_root, "/tmp/abs")
        _sc_ok = False
    except ident.IdentifierRefused:
        pass
    _inside = ident.safe_child(_root, "ok.md")
    check("identifiers: safe_child stays inside root",
          _sc_ok and _inside.parent == _root)

with _tf_xp.TemporaryDirectory() as _td_p0:
    _home_p0 = Path(_td_p0) / "home"
    _home_p0.mkdir()
    _pa = Path(_td_p0) / "alpha"
    _pb = Path(_td_p0) / "beta"
    _ph = Path(_td_p0) / "hostile"
    _pu = Path(_td_p0) / "unena"
    _pv = Path(_td_p0) / "unenb"
    for _p0_proj in (_pa, _pb, _ph, _pu, _pv):
        _p0_proj.mkdir()
        (_p0_proj / "main.py").write_text("x=1\n", encoding="utf-8")
    (_ph / ".claude").mkdir()
    (_ph / ".claude" / "settings.json").write_text(
        _json_xp.dumps({"consolidateMemory": {"domain": "employer"}}), encoding="utf-8")
    _env_p0 = _xp_env(_home_p0)
    _ctx_h = sc.resolve_store(_ph, environ=_env_p0)
    check("P0-1: hostile project settings cannot enroll a protected domain",
          _ctx_h.domain_id == "unknown" and _ctx_h.requested_domain == "employer"
          and _ctx_h.enrolled is False)

    _old_h_p0 = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_p0)
    for _k in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_PROJECT_DIR_NAME",
               "CLAUDE_CODE_DISABLE_AUTO_MEMORY", "CLAUDE_CODE_SETTINGS",
               "CM_DOMAIN", "CM_STORE_OVERRIDE", "CM_CRASH_AFTER"):
        _os_xp.environ.pop(_k, None)
    try:
        import io as _io_p0
        import contextlib as _cl_p0
        _env_cm = _xp_env(_home_p0, {"CM_DOMAIN": "employer"})
        _ctx_cm = sc.resolve_store(_pa, environ=_env_cm)
        check("P0-1: CM_DOMAIN requests a domain but does not grant without enroll",
              _ctx_cm.domain_id == "unknown" and _ctx_cm.requested_domain == "employer"
              and _ctx_cm.enrolled is False)
        (_home_p0 / ".claude").mkdir(parents=True, exist_ok=True)
        (_home_p0 / ".claude" / "settings.json").write_text(
            _json_xp.dumps({"consolidateMemory": {"domain": "personal"}}), encoding="utf-8")
        _ctx_us = sc.resolve_store(_pa, environ=_xp_env(_home_p0))
        check("P0-1: user settings.json requests a domain but does not grant without enroll",
              _ctx_us.domain_id == "unknown" and _ctx_us.requested_domain == "personal"
              and _ctx_us.enrolled is False)

        _ctx_u = sc.resolve_store(_pu, environ=_xp_env(_home_p0))
        _ctx_v = sc.resolve_store(_pv, environ=_xp_env(_home_p0))
        _share = ("---\nname: share-me\ndescription: unenrolled fleet share\n"
                  "metadata:\n  node_type: memory\n  type: reference\n  scope: user-global\n"
                  "---\n\nUNENROLLED SHARED BODY\n")
        _up_u = ci.upsert(_ctx_u, "share-me", _share)
        with _cl_p0.redirect_stdout(_io_p0.StringIO()), _cl_p0.redirect_stderr(_io_p0.StringIO()):
            _rc_v = sg.run(_pv, pull=True)
        _got_v = _ctx_v.native_memory_dir / "share-me.md"
        check("P0-3: unenrolled projects cannot create or pull cross-project canonicals",
              _ctx_u.domain_id == "unknown" and _ctx_v.domain_id == "unknown"
              and _up_u.get("ok") is False
              and not (_ctx_u.canonical_domain_dir / "share-me.md").is_file()
              and not _got_v.is_file())
        _err_pull = _io_p0.StringIO()
        with _cl_p0.redirect_stdout(_io_p0.StringIO()), _cl_p0.redirect_stderr(_err_pull):
            _rc_skip = sg.run(_pv, pull=True)
        check("0.2.2: unenrolled --pull skips before connect() (local-only)",
              _rc_skip == 0 and "local-only" in _err_pull.getvalue())
        _ctx_v.native_memory_dir.mkdir(parents=True, exist_ok=True)
        (_ctx_v.native_memory_dir / "promo-local.md").write_text(
            "---\nname: promo-local\ndescription: d\nmetadata:\n  node_type: memory\n"
            "  type: feedback\n  scope: user-global\n---\nbody\n", encoding="utf-8")
        _err_pr = _io_p0.StringIO()
        with _cl_p0.redirect_stdout(_io_p0.StringIO()), _cl_p0.redirect_stderr(_err_pr):
            _rc_pr = sg.promote(_pv, "promo-local", "promo-local")
        _unk = _ctx_v.config_root / "consolidate-memory" / "domains" / "unknown" / "facts"
        check("0.2.2: unenrolled --promote refuses before mkdir domains/unknown/facts",
              _rc_pr == 2 and "enrollment" in _err_pr.getvalue() and not _unk.exists())
        _doc_u = sc.doctor_report(_ctx_u)
        check("0.2.2: doctor warns UNENROLLED LOCAL-ONLY when unenrolled",
              "UNENROLLED LOCAL-ONLY" in _doc_u)

        _rc_en_bad = cmo.main(["project", "enroll", str(_ph), "--domain", "../employer"])
        _rc_en_a = cmo.main(["project", "enroll", str(_pa), "--domain", "work", "--apply",
                             "--confirm", "enroll-work"])
        _rc_en_b = cmo.main(["project", "enroll", str(_pb), "--domain", "personal", "--apply",
                             "--confirm", "enroll-personal"])
        _ctx_a = sc.resolve_store(_pa, environ=_xp_env(_home_p0))
        _ctx_b = sc.resolve_store(_pb, environ=_xp_env(_home_p0))
        check("P0-1: cm project enroll is the operator grant; ../domain is refused",
              _rc_en_bad == 2 and _rc_en_a == 0 and _rc_en_b == 0
              and _ctx_a.enrolled is True and _ctx_a.domain_id == "work"
              and _ctx_b.enrolled is True and _ctx_b.domain_id == "personal"
              and sc.resolve_store(_ph, environ=_xp_env(_home_p0)).domain_id == "unknown")
        _rc_en_switch = cmo.main(["project", "enroll", str(_pa), "--domain", "personal"])
        check("0.2.2: enroll refuses switching domains (use move-domain)",
              _rc_en_switch == 2)
        _rc_en_dry = cmo.main(["project", "enroll", str(_pv), "--domain", "personal"])
        check("0.2.2: enroll without --apply is dry-run (does not grant)",
              _rc_en_dry == 0
              and sc.resolve_store(_pv, environ=_xp_env(_home_p0)).enrolled is False)

        _rc_res = cmo.main(["resolve", "../passwd", "--project", str(_pa)])
        _rc_rep = cmo.main(["repair-mirror", "../passwd", "--project", str(_pa)])
        _rc_fg = cmo.main(["canonical", "forget", "../x", "--project", str(_pa)])
        _rc_pu = cmo.main(["data", "purge", "--project-id", "../oops", "--project", str(_pa)])
        _rc_pud = cmo.main(["data", "purge", "--domain", "/tmp/x", "--project", str(_pa)])
        check("P0-2/P0-6: resolve/repair/forget/purge refuse traversal and unsafe ids",
              _rc_res == 2 and _rc_rep == 2 and _rc_fg == 1 and _rc_pu == 2 and _rc_pud == 2)

        _wa = ("---\nname: deploy\ndescription: work deploy\ndomain: work\n"
               "metadata:\n  node_type: memory\n  type: reference\n  scope: user-global\n"
               "---\n\nWORK-ONLY BODY\n")
        _pbod = ("---\nname: deploy\ndescription: personal deploy\ndomain: personal\n"
                 "metadata:\n  node_type: memory\n  type: reference\n  scope: user-global\n"
                 "---\n\nPERSONAL-ONLY BODY\n")
        _up_wa = ci.upsert(_ctx_a, "deploy", _wa)
        _up_pbod = ci.upsert(_ctx_b, "deploy", _pbod)
        _p0_legacy = _home_p0 / ".claude" / "memory"
        _p0_legacy.mkdir(parents=True, exist_ok=True)
        (_p0_legacy / "conf.md").write_text(
            "---\nname: conf\ndescription: untagged confidential\nsensitivity: confidential\n"
            "metadata:\n  node_type: memory\n  type: reference\n  scope: user-global\n"
            "---\n\nCONFIDENTIAL LEGACY\n", encoding="utf-8")
        with _cl_p0.redirect_stdout(_io_p0.StringIO()), _cl_p0.redirect_stderr(_io_p0.StringIO()):
            _rc_pa = sg.run(_pa, pull=True)
        with _cl_p0.redirect_stdout(_io_p0.StringIO()), _cl_p0.redirect_stderr(_io_p0.StringIO()):
            _rc_pb = sg.run(_pb, pull=True)
        _sa = _ctx_a.native_memory_dir / "deploy.md"
        _sb = _ctx_b.native_memory_dir / "deploy.md"
        _sconf_a = _ctx_a.native_memory_dir / "conf.md"
        _sconf_b = _ctx_b.native_memory_dir / "conf.md"
        check("P0-3: same-stem facts in two domains stay distinct and domain-bound",
              _up_wa.get("ok") is True and _up_pbod.get("ok") is True
              and _rc_pa == 0 and _rc_pb == 0
              and _sa.is_file() and "WORK-ONLY BODY" in _sa.read_text(encoding="utf-8")
              and _sb.is_file() and "PERSONAL-ONLY BODY" in _sb.read_text(encoding="utf-8")
              and "PERSONAL-ONLY BODY" not in _sa.read_text(encoding="utf-8")
              and "WORK-ONLY BODY" not in _sb.read_text(encoding="utf-8"))
        _t_m = _sa.read_text(encoding="utf-8")
        _sa.write_text(_t_m.replace("WORK-ONLY BODY", "LOCAL EDIT BODY"), encoding="utf-8")
        _rc_un = cmo.main(["project", "unenroll", str(_pa), "--apply",
                           "--confirm", "unenroll-work"])
        _qdir = _ctx_a.native_memory_dir / "quarantine"
        _qs = list(_qdir.glob("deploy*.md")) if _qdir.is_dir() else []
        check("0.2.2: unenroll quarantines a locally edited mirror (does not delete the body)",
              _rc_un == 0 and len(_qs) == 1
              and "LOCAL EDIT BODY" in _qs[0].read_text(encoding="utf-8")
              and not _sa.exists())
        # re-enroll work so later crash/forget pins still have a domain
        cmo.main(["project", "enroll", str(_pa), "--domain", "work", "--apply",
                  "--confirm", "enroll-work"])
        _ctx_a = sc.resolve_store(_pa, environ=_xp_env(_home_p0))
        _rc_mv = cmo.main(["project", "move-domain", str(_pb), "--to", "client-x", "--apply",
                           "--confirm", "move-personal-to-client-x"])
        _ctx_b2 = sc.resolve_store(_pb, environ=_xp_env(_home_p0))
        check("0.2.2: move-domain grants the dest domain",
              _rc_mv == 0 and _ctx_b2.domain_id == "client-x")
        cmo.main(["project", "move-domain", str(_pb), "--to", "personal", "--apply",
                  "--confirm", "move-client-x-to-personal"])
        _ctx_b = sc.resolve_store(_pb, environ=_xp_env(_home_p0))
        check("P0-4: untagged confidential is not pulled under dual-read",
              not _sconf_a.exists() and not _sconf_b.exists())
        _fg_a = ci.forget(_ctx_a, "deploy", reason="p0-cross-domain")
        if _sb.exists():
            _sb.unlink()
        _bidx = _ctx_b.native_memory_dir / "MEMORY.md"
        if _bidx.exists():
            _bidx.write_text(
                "\n".join(ln for ln in _bidx.read_text(encoding="utf-8").splitlines()
                          if "deploy.md" not in ln) + "\n", encoding="utf-8")
        with _cl_p0.redirect_stdout(_io_p0.StringIO()), _cl_p0.redirect_stderr(_io_p0.StringIO()):
            _rc_pb_fg = sg.run(_pb, pull=True)
        check("P0-8: forget deploy in work does not make personal deploy inadmissible",
              _fg_a.get("ok") is True and _rc_pb_fg == 0 and _sb.is_file()
              and "PERSONAL-ONLY BODY" in _sb.read_text(encoding="utf-8"))

        # journal: crash-after-verify rolls back registry; crash-after-publish recovers hash+DB
        _body_cv = ("---\nname: crash-v\ndescription: crash verify\nscope: user-global\n"
                    "---\n\nverify body\n")
        _up_cv = ci.upsert(_ctx_a, "crash-v", _body_cv, crash_after="verify_unchanged")
        _dest_cv = _ctx_a.canonical_domain_dir / "crash-v.md"
        _rconn_cv = cp.connect(cp.db_path(_ctx_a))
        _n_cv = int(_rconn_cv.execute(
            "SELECT count(*) AS n FROM facts WHERE stem='crash-v'").fetchone()["n"])
        _n_hold = int(_rconn_cv.execute("SELECT count(*) AS n FROM holders").fetchone()["n"])
        _rconn_cv.close()
        check("P0-5: crash-after-verify rolls back registry (no dest bytes, no fact row)",
              _up_cv.get("ok") is False and "crash-after" in str(_up_cv.get("error") or "")
              and not _dest_cv.exists() and _n_cv == 0)

        _body_cp = ("---\nname: crash-p\ndescription: crash publish\nscope: user-global\n"
                    "---\n\npublish body\n")
        _up_cp = ci.upsert(_ctx_a, "crash-p", _body_cp, crash_after="publish")
        _dest_cp = _ctx_a.canonical_domain_dir / "crash-p.md"
        _jconn = cp.connect_journal(_ctx_a)
        _pending = cp.pending_ops(_jconn)
        _want_hash = ""
        for _op in _pending:
            _pl = _json_xp.loads(_op["payload"] or "{}")
            for _item in _pl.get("publishes") or []:
                if str(_item.get("dest") or "").endswith("crash-p.md"):
                    _want_hash = str(_item.get("sha256") or "")
        _got_hash = _hl_p0.sha256(_dest_cp.read_bytes()).hexdigest() if _dest_cp.exists() else ""
        _rconn_cp = cp.connect(cp.db_path(_ctx_a))
        _n_cp_before = int(_rconn_cp.execute(
            "SELECT count(*) AS n FROM facts WHERE stem='crash-p'").fetchone()["n"])
        # wrong-context recover from domain B must not complete against B
        _jrec_b = cp.recover_pending(_jconn, ctx=_ctx_b, registry_conn=_rconn_cp)
        _dest_b = _ctx_b.canonical_domain_dir / "crash-p.md"
        _still = cp.pending_ops(_jconn)
        _jrec_a = cp.recover_pending(_jconn, ctx=_ctx_a, registry_conn=_rconn_cp)
        _n_cp_after = int(_rconn_cp.execute(
            "SELECT count(*) AS n FROM facts WHERE stem='crash-p'").fetchone()["n"])
        _got_after = _hl_p0.sha256(_dest_cp.read_bytes()).hexdigest() if _dest_cp.exists() else ""
        _rconn_cp.close()
        _jconn.close()
        check("P0-5: crash-after-publish dest hash matches journal; recover applies matching DB",
              _up_cp.get("ok") is False and _dest_cp.exists()
              and bool(_want_hash) and _got_hash == _want_hash
              and _n_cp_before == 0 and _n_cp_after >= 1 and _got_after == _want_hash)
        check("P0-5: recover of domain-A op from domain-B command does not complete against B",
              not _dest_b.exists() and len(_still) >= 1 and len(_jrec_b) == 0
              and len(_jrec_a) >= 1)

        _body_fg = ("---\nname: keep-secret\ndescription: to forget\nscope: user-global\n"
                    "---\n\nPREVIOUS SECRET BODY\n")
        _up_fg = ci.upsert(_ctx_a, "keep-secret", _body_fg)
        _fg = ci.forget(_ctx_a, "keep-secret", reason="p0-test")
        _tomb = (_ctx_a.canonical_domain_dir / "keep-secret.md").read_text(encoding="utf-8")
        _cat = ci.generate_catalog(_ctx_a.canonical_domain_dir)
        check("P0-8: forget tombstone omits previous body; catalog omits tombstones",
              _up_fg.get("ok") is True and _fg.get("ok") is True
              and "PREVIOUS SECRET BODY" not in _tomb
              and "<!-- previous" not in _tomb
              and "deleted_revision_hash:" in _tomb
              and "keep-secret.md" not in _cat)
        _cat_disk = (_ctx_a.canonical_domain_dir / "MEMORY.md").read_text(encoding="utf-8")
        check("0.2.2: forget regenerates the domain catalog in the same transact",
              "keep-secret.md" not in _cat_disk)
        _doc_a = sc.doctor_report(_ctx_a)
        check("0.2.2: enrolled doctor does not emit the unenrolled-share warning",
              "unenrolled_share_warning: (none)" in _doc_a)
        _up_udep = ci.upsert(
            _ctx_u, "deploy",
            "---\nname: deploy\ndescription: unknown deploy\nscope: user-global\n"
            "---\n\nU-DEPLOY\n")
        check("0.2.2: unenrolled upsert is refused (local-only sentinel)",
              _up_udep.get("ok") is False)
        _up_b2 = ci.upsert(
            _ctx_b, "deploy",
            "---\nname: deploy\ndescription: personal deploy\ndomain: personal\n"
            "scope: user-global\n---\n\nPERSONAL-ONLY BODY\n")
        _pers_b = _ctx_b.canonical_domain_dir / "deploy.md"
        _work_tomb = _ctx_a.canonical_domain_dir / "deploy.md"
        check("0.2.2: same-stem forget in work does not tombstone personal deploy",
              _up_b2.get("ok") is True
              and _pers_b.is_file()
              and "PERSONAL-ONLY BODY" in _pers_b.read_text(encoding="utf-8")
              and "tombstoned" not in _pers_b.read_text(encoding="utf-8").lower()
              and (not _work_tomb.exists()
                   or "tombstoned" in _work_tomb.read_text(encoding="utf-8").lower()))

        # admission-refused promote leaves origin
        _p0_nmem_a = _ctx_a.native_memory_dir
        _p0_nmem_a.mkdir(parents=True, exist_ok=True)
        _idx_lines = ["# Memory Index", ""] + [
            f"- [pad{i}](pad{i}.md) — x" for i in range(ia.NATIVE_INDEX_CAP_LINES + 2)]
        (_p0_nmem_a / "MEMORY.md").write_text("\n".join(_idx_lines) + "\n", encoding="utf-8")
        _orig = _p0_nmem_a / "overcap.md"
        _orig.write_text("---\nname: overcap\ndescription: d\nmetadata:\n  node_type: memory\n"
                         "  type: feedback\n  scope: user-global\n---\n\norigin body\n",
                         encoding="utf-8")
        _up_ad = ci.upsert(_ctx_a, "overcap", _orig.read_text(encoding="utf-8"),
                           origin_local=_orig)
        check("P0-7: admission-refused upsert leaves the origin file unconverted",
              _up_ad.get("ok") is False and "admission" in str(_up_ad.get("error") or "").lower()
              and _orig.exists() and "global_ref:" not in _orig.read_text(encoding="utf-8"))

        # admission-refused evict leaves origin
        _p0_nmem_b = _ctx_b.native_memory_dir
        _p0_nmem_b.mkdir(parents=True, exist_ok=True)
        _ev = _p0_nmem_b / "evict-me.md"
        _ev.write_text("---\nname: evict-me\ndescription: local\n---\nlocal\n", encoding="utf-8")
        _cap_idx = ["# Memory Index", ""] + [
            f"- [z{i}](z{i}.md) — x" for i in range(ia.NATIVE_INDEX_CAP_LINES - 1)]
        _cap_idx.append("- [evict-me](evict-me.md) — local")
        (_p0_nmem_b / "MEMORY.md").write_text("\n".join(_cap_idx) + "\n", encoding="utf-8")
        _job_fm = {"name": "n1", "description": "d", "scope": "user-global"}
        _jobs = [
            ("n1", _job_fm, "MISSING", _p0_nmem_b / "n1.md", "---\nname: n1\n---\nb\n"),
            ("n2", dict(_job_fm, name="n2"), "MISSING", _p0_nmem_b / "n2.md", "---\nname: n2\n---\nb\n"),
        ]
        _ev_out = sg._execute_pull_writes(_ctx_b, _p0_nmem_b, _jobs, "evict-me", _ev)
        _ev_refused = "admission" in str(_ev_out.get("error") or "").lower()
        check("P0-7: admission-refused evict leaves the origin file",
              _ev.exists() and _ev_refused and int(_ev_out.get("pulled") or 0) == 0)
    finally:
        if _old_h_p0 is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_h_p0

# ── 0.2.2 guardrails: read-only sqlite + refuse mutation on a corrupt registry ──
import sqlite3 as _sql_022  # noqa: E402
with _tf_xp.TemporaryDirectory() as _td_022:
    _home_022 = Path(_td_022) / "home"
    _home_022.mkdir()
    _proj_022 = Path(_td_022) / "p"
    _proj_022.mkdir()
    (_proj_022 / "main.py").write_text("x=1\n", encoding="utf-8")
    _old_h_022 = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_022)
    try:
        _ctx_h022 = sc.resolve_store(_proj_022, environ=_xp_env(_home_022))
        cmo.main(["project", "enroll", str(_proj_022), "--domain", "personal", "--apply",
                  "--confirm", "enroll-personal"])
        _ctx_h022 = sc.resolve_store(_proj_022, environ=_xp_env(_home_022))
        _missing_db = Path(_td_022) / "no-control.sqlite"
        check("0.2.2: connect_if_exists does not mint a missing DB",
              cp.connect_if_exists(_missing_db) is None and not _missing_db.exists())
        _st_abs, _err_abs = cp.classify_registry(_missing_db)
        check("0.2.2: classify_registry reports absent when the file is missing",
              _st_abs == "absent" and _err_abs == "")
        # mint a healthy DB via a first upsert, then prove readonly
        _up_h = ci.upsert(
            _ctx_h022, "ro-fact",
            "---\nname: ro-fact\ndescription: d\nscope: user-global\n---\n\nb\n")
        _db_h = cp.db_path(_ctx_h022)
        _ro_failed = False
        _ro_conn = cp.connect_readonly(_db_h)
        try:
            _ro_conn.execute(
                "INSERT INTO migration_state(key, value) VALUES('ro-probe','x')")
            _ro_conn.commit()
        except _sql_022.Error:
            _ro_failed = True
        finally:
            _ro_conn.close()
        check("0.2.2: connect_readonly refuses writes on an existing DB",
              _up_h.get("ok") is True and _ro_failed is True)
        _ife = cp.connect_if_exists(_db_h)
        _ife_failed = False
        if _ife is None:
            _ife_failed = False
        else:
            try:
                _ife.execute(
                    "INSERT INTO migration_state(key, value) VALUES('ife-probe','x')")
                _ife.commit()
            except _sql_022.Error:
                _ife_failed = True
            finally:
                _ife.close()
        check("0.2.2: connect_if_exists is read-only (does not migrate/write)",
              _ife is not None and _ife_failed is True)
    finally:
        if _old_h_022 is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_h_022

with _tf_xp.TemporaryDirectory() as _td_cor:
    _home_cor = Path(_td_cor) / "home"
    _home_cor.mkdir()
    _proj_cor = Path(_td_cor) / "p"
    _proj_cor.mkdir()
    (_proj_cor / "main.py").write_text("x=1\n", encoding="utf-8")
    _old_h_cor = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_cor)
    try:
        _ctx_cor = sc.resolve_store(_proj_cor, environ=_xp_env(_home_cor))
        _db_cor = cp.db_path(_ctx_cor)
        _db_cor.parent.mkdir(parents=True, exist_ok=True)
        _db_cor.write_bytes(b"this is not a sqlite database")
        _st_cor, _err_cor = cp.classify_registry(_db_cor)
        _mut_refused = False
        try:
            cp.assert_mutation_allowed(_ctx_cor)
        except sc.WriteRefused:
            _mut_refused = True
        _up_cor = ci.upsert(
            _ctx_cor, "x",
            "---\nname: x\ndescription: d\nscope: user-global\n---\n\nb\n")
        _rc_en_cor = cmo.main(["project", "enroll", str(_proj_cor), "--domain", "work"])
        _ctx_cor2 = sc.resolve_store(_proj_cor, environ=_xp_env(_home_cor))
        _doc_cor = sc.doctor_report(_ctx_cor2)
        check("0.2.2: classify_registry reports corrupt/incompatible for a non-sqlite file",
              _st_cor in ("corrupt", "incompatible"))
        check("0.2.2: assert_mutation_allowed refuses a corrupt registry",
              _mut_refused is True)
        check("0.2.2: upsert refuses when registry is corrupt (does not fail open to unknown writes)",
              _up_cor.get("ok") is False)
        check("0.2.2: enroll refuses when registry is corrupt",
              _rc_en_cor == 2)
        check("0.2.2: doctor names registry_state and still emits the unenrolled-share warning",
              "registry_state:" in _doc_cor
              and any(s in _doc_cor for s in ("corrupt", "incompatible", _st_cor))
              and "UNENROLLED LOCAL-ONLY" in _doc_cor)
    finally:
        if _old_h_cor is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_h_cor

# ── remaining AC pins (docs + shipped fleet/provenance paths) ───────────────
_hmap_ac = (ROOT / "plugins" / "consolidate-memory" / "skills" / "consolidate-memory"
            / "references" / "harness-map.md").read_text(encoding="utf-8")
check("harness-map persist writer is plugin-data ops/<slot>/.consolidation-log.jsonl (native leftover dual-read)",
      "ops/<slot>/.consolidation-log.jsonl" in _hmap_ac
      and "leftover native" in _hmap_ac
      and "appends each cycle record to `<store>/.consolidation-log.jsonl`" not in _hmap_ac)
check("harness-map harvest writer is plugin-data fleet-usage.jsonl (native leftover dual-read)",
      "plugin-data `fleet-usage.jsonl`" in _hmap_ac
      and "`~/.claude/memory/.fleet-usage.jsonl`, 0o600)" not in _hmap_ac)
_p5_ac = _skill_md.read_text(encoding="utf-8").split("### Phase 5")[1].split("## Safety rules")[0]
_pj_022 = (ROOT / "plugins" / "consolidate-memory" / ".claude-plugin" / "plugin.json").read_text(
    encoding="utf-8")
check("0.2.2: plugin description does not promise unenrolled whole-fleet sharing",
      "whole fleet" not in _pj_022.lower())
_cmd_dir = ROOT / "plugins" / "consolidate-memory" / "commands"
check("0.2.2: packaged admin commands ship inside the plugin",
      (_cmd_dir / "cm-doctor.md").is_file()
      and (_cmd_dir / "cm-domain.md").is_file()
      and (_cmd_dir / "cm-data.md").is_file())
_live_docs = "\n".join([
    _skill_md.read_text(encoding="utf-8"),
    (ROOT / "README.md").read_text(encoding="utf-8"),
    (ROOT / "SECURITY.md").read_text(encoding="utf-8"),
    _pj_022,
    (_cmd_dir / "cm-doctor.md").read_text(encoding="utf-8"),
    (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"),
    (ROOT / "cm").read_text(encoding="utf-8"),
])
check("0.2.2: live docs do not claim unenrolled projects share a compatibility pool",
      "compatibility pool" not in _live_docs.lower()
      and "unenrolled projects currently share" not in _live_docs.lower()
      and "unknown`-pool" not in _live_docs
      and "UNENROLLED SHARED COMPATIBILITY DOMAIN" not in _live_docs
      and "whole fleet" not in _pj_022.lower())
_skill_now = _skill_md.read_text(encoding="utf-8")
check("0.2.2: SKILL/harness-map do not instruct writing live ~/.claude/memory as the canonical plane",
      "demote/delete the canonical in `~/.claude/memory/`" not in _skill_now
      and "body** in `~/.claude/memory/`" not in _skill_now
      and "both write to `~/.claude/memory`" not in _hmap_ac
      and "canonical_domain_dir" in _skill_now)
check("0.2.2: README does not claim an unlocked non-POSIX flock fallback",
      "import-fallback to unlocked" not in (ROOT / "README.md").read_text(encoding="utf-8"))
import fact_schema as _fsch_022  # noqa: E402
check("0.2.2: fact_schema refuses nested applies.any",
      _fsch_022.validate_canonical_frontmatter(
          {"name": "deploy", "domain": "work", "applies.any": "[python]"},
          stem="deploy", domain="work") is not None)
check("0.2.2: retention_show does not advertise unimplemented aggregate months",
      "daily_aggregates_months" not in ret.retention_show())

with _Env73() as _e_ic:
    (_e_ic.glob / "canon-r.md").write_text(_fact73("canon-r", "ref"), encoding="utf-8")
    import identity as _id_022
    _refs_ic = sg.iter_canonicals(sc.resolve_store(_e_ic.proj))
    check("0.2.2: iter_canonicals yields CanonicalRef keyed by (domain, stem)",
          all(isinstance(r, _id_022.CanonicalRef) for r in _refs_ic)
          and any(r.stem == "canon-r" and r.domain_id for r in _refs_ic))

_stamped = sg._stamp_harvest_identity(
    {"per_fact": [{"name": "deploy", "reads": 1, "last": "t"}]}, "personal")
check("0.2.2: harvest per_fact rows carry domain_id + fact_id",
      _stamped["domain_id"] == "personal"
      and _stamped["per_fact"][0]["domain_id"] == "personal"
      and str(_stamped["per_fact"][0].get("fact_id") or "").startswith("f_"))

with _Env73() as _e_ov:
    import capabilities as _cap_ov
    (_e_ov.proj / "x.py").write_text("x=1\n", encoding="utf-8")
    _ov_dir = sc.resolve_store(_e_ov.proj).plugin_data_dir
    _ov_dir.mkdir(parents=True, exist_ok=True)
    (_ov_dir / "capability-overrides.json").write_text(
        _json_xp.dumps({"add": ["gpu-override"], "remove": ["python"]}) + "\n",
        encoding="utf-8")
    _ov = _cap_ov.load_capability_overrides(_ov_dir, "unused")
    _plain = _cap_ov.capability_tags(_cap_ov.detect_capabilities(_e_ov.proj))
    _honored = _cap_ov.capability_tags(
        _cap_ov.detect_capabilities(_e_ov.proj, overrides=_ov))
    check("0.2.2: capability user overrides add/remove on the detector path",
          "python" in _plain and "python" not in _honored
          and "gpu-override" in _honored)

with _Env73() as _e_ex:
    import tarfile as _tar_ex
    _pdata_ex = sc.resolve_store(_e_ex.proj).plugin_data_dir
    _pdata_ex.mkdir(parents=True, exist_ok=True)
    (_pdata_ex / "note.json").write_text("{}\n", encoding="utf-8")
    (_pdata_ex / "secret.bin").write_bytes(b"\x00\x01")
    _ex = ret.export_ops(_pdata_ex, _pdata_ex / "bundle.tar.gz")
    _tnames = _tar_ex.open(_ex["path"]).getnames()
    check("0.2.2: export tar members match the sha256 manifest (no unlisted bytes)",
          _ex.get("ok") is True
          and any(n.endswith("note.json") for n in _tnames)
          and not any(n.endswith("secret.bin") for n in _tnames)
          and "manifest.json" in _tnames)

with _Env73() as _e_pg:
    _buf_pg = _io73.StringIO()
    with _ctx73.redirect_stdout(_buf_pg), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_pg = cmo.main(["data", "purge", "--scope", "managed-mirrors",
                           "--project", str(_e_pg.proj)])
    check("0.2.2: data purge without --apply is dry-run (confirmation phrase)",
          _rc_pg == 0 and "purge plan" in _buf_pg.getvalue()
          and "purge-managed-mirrors" in _buf_pg.getvalue())

with _Env73() as _e_rec:
    _ctx_rec = sc.resolve_store(_e_rec.proj)
    _j_rec = cp.connect_journal(_ctx_rec)
    _j_rec.executescript(cp.JOURNAL_ONLY_SQL)
    _r_rec = cp.connect(cp.db_path(_ctx_rec))
    _payload_rec = {
        "origin_domain_id": _ctx_rec.domain_id,
        "origin_project_id": _ctx_rec.project_id,
        "publishes": [],
        "deletes": [],
        "registry_ops": [{"op": "migration_state_set", "mode": "dual-read"}],
    }
    _oid_rec = cp.journal_insert(_j_rec, "domain-transition", _payload_rec, "prepare_temps")
    _got_rec = cp.recover_pending(_j_rec, ctx=_ctx_rec, registry_conn=_r_rec)
    _st_rec = _j_rec.execute(
        "SELECT status FROM journal WHERE op_id=?", (_oid_rec,)).fetchone()["status"]
    _j_rec.close(); _r_rec.close()
    check("0.2.2: recover_pending applies registry_ops when publishes is empty",
          _oid_rec in _got_rec and _st_rec == "complete")

with _Env73() as _e_miss:
    _ctx_miss = sc.resolve_store(_e_miss.proj)
    _dest_miss = _ctx_miss.native_memory_dir / "appeared.md"
    _dest_miss.write_text(
        "---\nname: appeared\ndescription: local\nmetadata:\n  node_type: memory\n"
        "  type: project\n---\nKEEP LOCAL\n", encoding="utf-8")
    _want_miss = _fact73("appeared", "from canon")
    _jobs_miss = [("appeared", sg._frontmatter(_want_miss), "MISSING",
                   _dest_miss, _want_miss)]
    sg._execute_pull_writes(_ctx_miss, _ctx_miss.native_memory_dir,
                            _jobs_miss, None, None)
    check("0.2.2: pull MISSING does not overwrite a local file that appeared after classify",
          "KEEP LOCAL" in _dest_miss.read_text(encoding="utf-8")
          and "global_ref:" not in _dest_miss.read_text(encoding="utf-8"))

with _tf_xp.TemporaryDirectory() as _td_resu:
    _home_resu = Path(_td_resu) / "home"; _home_resu.mkdir()
    _proj_resu = Path(_td_resu) / "proj"; _proj_resu.mkdir()
    (_proj_resu / "a.py").write_text("x=1\n", encoding="utf-8")
    _old_resu = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_resu)
    try:
        _err_resu = _io73.StringIO()
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_err_resu):
            _rc_resu = cmo.main(["resolve", "x", "--keep-canonical",
                                 "--project", str(_proj_resu)])
        _err_rmu = _io73.StringIO()
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_err_rmu):
            _rc_rmu = cmo.main(["repair-mirror", "x", "--project", str(_proj_resu)])
        check("0.2.2: resolve/repair-mirror refuse when unenrolled",
              _rc_resu == 2 and "enrollment" in _err_resu.getvalue()
              and _rc_rmu == 2 and "enrollment" in _err_rmu.getvalue())
    finally:
        if _old_resu is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_resu

with _Env73() as _e_dt:
    _ctx_dt = sc.resolve_store(_e_dt.proj)
    _j_dt = cp.connect_journal(_ctx_dt)
    _j_dt.executescript(cp.JOURNAL_ONLY_SQL)
    _r_dt = cp.connect(cp.db_path(_ctx_dt))
    _payload_dt = {
        "origin_domain_id": "unknown",
        "origin_project_id": _ctx_dt.project_id,
        "dest": _ctx_dt.domain_id,
        "publishes": [],
        "deletes": [],
        "registry_ops": [{"op": "migration_state_set", "mode": "dual-read"}],
    }
    _oid_dt = cp.journal_insert(_j_dt, "domain-transition", _payload_dt, "prepare_temps")
    _got_dt = cp.recover_pending(_j_dt, ctx=_ctx_dt, registry_conn=_r_dt)
    _st_dt = _j_dt.execute(
        "SELECT status FROM journal WHERE op_id=?", (_oid_dt,)).fetchone()["status"]
    _payload_fx = dict(_payload_dt)
    _payload_fx["origin_project_id"] = "p_" + ("ab" * 16)
    _oid_fx = cp.journal_insert(_j_dt, "domain-transition", _payload_fx, "prepare_temps")
    _got_fx = cp.recover_pending(_j_dt, ctx=_ctx_dt, registry_conn=_r_dt)
    _st_fx = _j_dt.execute(
        "SELECT status FROM journal WHERE op_id=?", (_oid_fx,)).fetchone()["status"]
    _j_dt.close(); _r_dt.close()
    check("0.2.2: domain-transition recover matches dest domain; foreign project stays pending",
          _oid_dt in _got_dt and _st_dt == "complete"
          and _oid_fx not in _got_fx and _st_fx == "pending")

# dest-hash mismatch must not delete (ADR 010)
with _tf_xp.TemporaryDirectory() as _td_hash:
    _p_hash = Path(_td_hash) / "keep.md"
    _p_hash.write_text("keep me\n", encoding="utf-8")
    _del_out = cp._apply_deletes([{"path": str(_p_hash), "preimage": "0" * 64}])
    check("0.2.2: dest-hash / preimage mismatch skips the origin delete",
          _p_hash.exists() and _p_hash.read_text(encoding="utf-8") == "keep me\n"
          and _del_out["preimage_mismatch"] == [str(_p_hash)])

_unk_raised = False
try:
    with _Env73() as _e_unk:
        _cu = cp.connect(cp.db_path(sc.resolve_store(_e_unk.proj)))
        try:
            cp.apply_registry_ops(_cu, [{"op": "not-a-real-op"}])
        finally:
            _cu.close()
except sc.WriteRefused as _e_unk_wr:
    _unk_raised = "unknown registry_op" in str(_e_unk_wr)
check("0.3.0: unknown registry_op is WriteRefused (not silently ignored)", _unk_raised)

with _tf_xp.TemporaryDirectory() as _td_fe:
    _home_fe = Path(_td_fe) / "home"; _home_fe.mkdir()
    _proj_fe = Path(_td_fe) / "src" / "firstenroll"; _proj_fe.mkdir(parents=True)
    (_proj_fe / "a.py").write_text("x=1\n", encoding="utf-8")
    _old_fe = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_fe)
    try:
        _ctx_fe = sc.resolve_store(_proj_fe)
        _ops_fe = [
            cp.project_upsert_op(_ctx_fe, domain_id="personal", status="enrolled"),
            {"op": "project_domain_change", "project_id": _ctx_fe.project_id,
             "domain_id": "personal", "status": "enrolled"},
        ]
        _crash_fe = False
        try:
            cp.transact(_ctx_fe, "enroll-first", {"dest": "personal"},
                        lambda _c, _t: {"registry_ops": _ops_fe},
                        crash_after="publish")
        except cp.CrashSimulated:
            _crash_fe = True
        _r_fe = cp.connect(cp.db_path(_ctx_fe))
        _pre_fe = _r_fe.execute(
            "SELECT status, domain_id FROM projects WHERE project_id=?",
            (_ctx_fe.project_id,)).fetchone()
        _j_fe = cp.connect_journal(_ctx_fe)
        _got_fe = cp.recover_pending(_j_fe, ctx=_ctx_fe, registry_conn=_r_fe)
        cp.assert_enrolled(_r_fe, _ctx_fe.project_id, "personal")
        _j_fe.close(); _r_fe.close()
        check("0.3.0: first-enroll crash-before-commit recovers the project row",
              _crash_fe and _pre_fe is None and len(_got_fe) >= 1)
    finally:
        if _old_fe is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_fe

with _Env73() as _e_dm:
    _ctx_dm = sc.resolve_store(_e_dm.proj)
    _victim = _ctx_dm.native_memory_dir / "edited.md"
    _victim.write_text("LOCAL EDIT\n", encoding="utf-8")
    _refused_dm = False
    try:
        cp.transact(_ctx_dm, "gc-apply", {"n": 1},
                    lambda _c, _t: {"deletes": [
                        {"path": str(_victim), "preimage": "ab" * 32}]})
    except sc.WriteRefused as _wr_dm:
        _refused_dm = "preimage mismatch" in str(_wr_dm)
    check("0.3.0: delete preimage mismatch refuses transact (journal not complete)",
          _refused_dm and _victim.exists()
          and _victim.read_text(encoding="utf-8") == "LOCAL EDIT\n")

check("0.3.0: untagged legacy is not admitted to a named domain",
      dp.admit_cross_project("personal", {"scope": "user-global"},
                             migration_mode=dp.MIGRATION_DUAL_READ) is False)
check("0.3.0: applies_from_fm reads applies_exclude (production pull path)",
      _fsch_022.applies_from_fm({"applies_exclude": "[windows]"}).get("exclude") == ["windows"])
_rc_noconfirm = None
with _tf_xp.TemporaryDirectory() as _td_nc:
    _h_nc = Path(_td_nc) / "h"; _h_nc.mkdir()
    _p_nc = Path(_td_nc) / "p"; _p_nc.mkdir()
    _old_nc = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_h_nc)
    try:
        _err_nc = _io73.StringIO()
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_err_nc):
            _rc_noconfirm = cmo.main(["project", "enroll", str(_p_nc),
                                      "--domain", "personal", "--apply"])
        check("0.3.0: --apply without --confirm is refused (non-TTY included)",
              _rc_noconfirm == 2 and "confirm" in _err_nc.getvalue())
    finally:
        if _old_nc is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_nc

_saved_fc = sys.modules.get("fcntl")
sys.modules["fcntl"] = None  # type: ignore[assignment]
try:
    _fc_refused = False
    try:
        cp.require_interprocess_lock()
    except sc.WriteRefused:
        _fc_refused = True
    check("0.2.2: missing fcntl is WriteRefused (POSIX mutation / Windows fail-closed)",
          _fc_refused is True)
finally:
    if _saved_fc is None:
        sys.modules.pop("fcntl", None)
    else:
        sys.modules["fcntl"] = _saved_fc
check("SKILL Phase 5 persist/store/marker use native_memory_dir (do not hand-build projects/<slug>/memory)",
      "--persist ~/.claude/projects/<slug>/memory" not in _p5_ac
      and "--store ~/.claude/projects/<slug>/memory" not in _p5_ac
      and "~/.claude/projects/<slug>/memory/.consolidation-state.json" not in _p5_ac
      and "native_memory_dir" in _p5_ac
      and "--persist <native_memory_dir from Phase 0 / cm doctor>" in _p5_ac)

with _Env73() as _e_h:
    (_e_h.glob / "ug-hold.md").write_text(_fact73("ug-hold", "holder pin"), encoding="utf-8")
    _rc_h, _out_h, _err_h = _run73(_e_h.proj)
    _ctx_h = sc.resolve_store(_e_h.proj)
    _conn_h = cp.connect(cp.db_path(_ctx_h))
    _nhold = _conn_h.execute("SELECT count(*) AS n FROM holders").fetchone()["n"]
    _conn_h.close()
    check("pull records holders on the control plane (no post-lock GLOBAL rewrite)",
          _rc_h == 0 and int(_nhold) >= 1
          and (_e_h.store / "ug-hold.md").is_file())

with _Env73() as _e_p:
    (_e_p.store / "promo-x.md").write_text(
        "---\nname: promo-x\ndescription: d\nmetadata:\n  node_type: memory\n"
        "  type: feedback\n  scope: user-global\n---\nsame body\n", encoding="utf-8")
    (_e_p.store / "MEMORY.md").write_text(
        "# Memory Index\n\n- [promo-x](promo-x.md) — d\n", encoding="utf-8")
    _seen_up: list = []
    _real_up = ci.upsert

    def _up_wrap(*a: Any, **k: Any) -> dict:
        _seen_up.append(dict(k))
        return _real_up(*a, **k)

    ci.upsert = _up_wrap
    try:
        _rc_p1 = sg.promote(_e_p.proj, "promo-x", "promo-x")
        (_e_p.store / "promo-y.md").write_text(
            "---\nname: promo-y\ndescription: d\nmetadata:\n  node_type: memory\n"
            "  type: feedback\n  scope: user-global\n---\nsame body\n", encoding="utf-8")
        _rc_p2 = sg.promote(_e_p.proj, "promo-y", "promo-x")
    finally:
        ci.upsert = _real_up
    _create_kw = _seen_up[0] if _seen_up else {}
    _recon_kw = _seen_up[1] if len(_seen_up) > 1 else {}
    check("promote CREATE calls upsert(create_only, origin_local); reconcile uses preserve_canonical",
          _rc_p1 == 0 and _rc_p2 == 0
          and _create_kw.get("create_only") is True
          and _create_kw.get("origin_local") is not None
          and _recon_kw.get("preserve_canonical") is True
          and "global_ref:" in (_e_p.store / "promo-x.md").read_text(encoding="utf-8")
          and not (_e_p.store / "promo-y.md").exists())

with _tf_xp.TemporaryDirectory() as _td_slot:
    _home_s = Path(_td_slot) / "home"; _home_s.mkdir()
    _grepo_s = Path(_td_slot) / "grepo"; _grepo_s.mkdir()
    (_grepo_s / "src").mkdir()
    (_grepo_s / "src" / "n.txt").write_text("n\n", encoding="utf-8")
    _gwd_s = str(_grepo_s)
    _sp_xp.run(["git", "init"], check=True, cwd=_gwd_s, capture_output=True, text=True)
    _sp_xp.run(["git", "config", "user.email", "you@example.com"], check=True, cwd=_gwd_s,
               capture_output=True, text=True)
    _sp_xp.run(["git", "config", "user.name", "you"], check=True, cwd=_gwd_s,
               capture_output=True, text=True)
    _sp_xp.run(["git", "add", "-A"], check=True, cwd=_gwd_s, capture_output=True, text=True)
    _sp_xp.run(["git", "commit", "-m", "i"], check=True, cwd=_gwd_s, capture_output=True, text=True)
    _old_hs = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_s)
    try:
        _bc = ms.build_context(_grepo_s / "src")
        _slot = sc.resolve_store(_grepo_s / "src").project_slot
        check("build_context slug is StoreContext.project_slot (git-root), not slug_for(nested cwd)",
              _bc["slug"] == _slot == ms.slug_for(_grepo_s)
              and _bc["slug"] != ms.slug_for(_grepo_s / "src"))
    finally:
        if _old_hs is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_hs

with _tf_xp.TemporaryDirectory() as _td_cust:
    _home_c = Path(_td_cust) / "home"; _home_c.mkdir()
    _proj_c = Path(_td_cust) / "custp"; _proj_c.mkdir()
    _custom = Path(_td_cust) / "relocated-mem"; _custom.mkdir()
    # User/managed settings may name an absolute dir; project/local may not.
    (_home_c / ".claude").mkdir()
    (_home_c / ".claude" / "settings.json").write_text(
        _json_xp.dumps({"autoMemoryDirectory": str(_custom)}), encoding="utf-8")
    _ct_c = ("---\nname: canon-c\ndescription: \"d\"\nmetadata:\n  node_type: memory\n"
             "  scope: user-global\n  type: feedback\n---\nbody\n")
    _mir_c = sg._as_mirror(_ct_c, "canon-c", since="2026-01-01T00:00:00Z",
                           body_hash=sg._body_hash(_ct_c))
    (_custom / "canon-c.md").write_text(_mir_c, encoding="utf-8")
    _old_hc = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_c)
    _old_g = sg.GLOBAL
    try:
        _env_c = _xp_env(_home_c)
        _ctx_c = sc.resolve_store(_proj_c, environ=_env_c)
        check("custom autoMemoryDirectory native is off the projects/*/memory default",
              _ctx_c.native_memory_dir == _custom)

        def _mut_reg(conn: Any, temps: dict) -> dict:
            return {"deletes": []}

        cp.transact(_ctx_c, "noop-register", {"k": 1}, _mut_reg)
        _nodes_c = sg._network_nodes()
        check("iter_native_stores/registry union: custom autoMemoryDirectory store is a fleet node",
              any(_path_eq == _custom for _path_eq in (p if p == _custom else p.resolve()
                                                       for p in _nodes_c))
              or _custom in _nodes_c or any(
                  str(p.resolve()) == str(_custom.resolve()) for p in _nodes_c))
        _sess_c = sg.session_dir_for_store(_custom)
        check("session_dir_for_store uses registry session_dir (not store.parent) for relocated memory",
              _sess_c == _ctx_c.session_dir and _sess_c != _custom.parent)
        _sess_c.mkdir(parents=True, exist_ok=True)
        (_sess_c / "t.jsonl").write_text(_json_xp.dumps({
            "timestamp": "2026-01-15T10:00:00Z",
            "message": {"content": [{"type": "tool_use", "name": "Read",
                                     "input": {"file_path": str(_custom / "canon-c.md")}}]}}) + "\n",
            encoding="utf-8")
        _row_c = sg._harvest_node(_custom, "", by="custp")
        check("harvest reads transcripts from session_dir, not the relocated store.parent",
              _row_c is not None and int(_row_c["reads"]) == 1
              and _row_c["node"] == _sess_c.name)
    finally:
        sg.GLOBAL = _old_g
        if _old_hc is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_hc

# ── PR #116 review fixes (managed settings, catalog caps, control-plane honesty) ──
with _tf_xp.TemporaryDirectory() as _td_r:
    _home_r = Path(_td_r) / "home"; _home_r.mkdir()
    _proj_r = Path(_td_r) / "rproj"; _proj_r.mkdir()
    (_proj_r / "readme.txt").write_text("x\n", encoding="utf-8")
    _cfg_r = _home_r / ".claude"
    _cfg_r.mkdir(parents=True)
    _policy_mem = Path(_td_r) / "policy-mem"
    _user_mem = Path(_td_r) / "user-mem"
    (_cfg_r / "managed-settings.json").write_text(
        _json_xp.dumps({"autoMemoryDirectory": str(_policy_mem),
                        "autoMemoryEnabled": False}), encoding="utf-8")
    (_cfg_r / "settings.json").write_text(
        _json_xp.dumps({"autoMemoryDirectory": str(_user_mem),
                        "autoMemoryEnabled": True}), encoding="utf-8")
    _ctx_pol = sc.resolve_store(_proj_r, environ=_xp_env(_home_r))
    check("review-1: managed-settings autoMemoryDirectory survives conflicting user settings",
          _ctx_pol.native_memory_dir == _policy_mem
          and _ctx_pol.resolution_source == "autoMemoryDirectory")
    check("review-1: managed autoMemoryEnabled:false is not overridden by user true",
          _ctx_pol.auto_memory_enabled is False and _ctx_pol.write_allowed is False)
    (_cfg_r / "managed-settings.json").unlink()
    (_cfg_r / "settings.json").unlink()

    _env_r = _xp_env(_home_r)
    _ctx_r = sc.resolve_store(_proj_r, environ=_env_r)
    try:
        sc.assert_writable(_ctx_r)
        _writable_r = True
    except sc.WriteRefused:
        _writable_r = False
    if _writable_r:
        _conn_r = cp.connect(cp.db_path(_ctx_r))
        try:
            cp.enroll_project(_conn_r, _ctx_r, "personal")
            _conn_r.commit()
        except Exception:
            pass
        _conn_r.close()
        _ctx_r = sc.resolve_store(_proj_r, environ=_env_r)
        _tiny = ("---\nname: tiny-cat\ndescription: d\nmetadata:\n  node_type: memory\n"
                 "  type: feedback\n  scope: user-global\n---\nbody\n")
        _seen_pi: list = []
        _real_pi = ia.project_index

        def _spy_pi(text: str, *a: Any, **k: Any) -> dict:
            _seen_pi.append(text)
            return _real_pi(text, *a, **k)

        setattr(ia, "project_index", _spy_pi)
        try:
            _up_r = ci.upsert(_ctx_r, "tiny-cat", _tiny)
        finally:
            setattr(ia, "project_index", _real_pi)
        check("review-2: canonical upsert does not run native index admission on the generated catalog",
              bool(_up_r.get("ok"))
              and not any("generated by cm canonical upsert" in (t or "") for t in _seen_pi))
        _dem = ci.demirror_text(
            "---\nname: tiny-cat\ndescription: d\n  global_ref: tiny-cat\n"
            "  global_ref_body: abc\n  base_revision: x\n  canonical_revision: y\n"
            "mirrored_at: 2026-01-01T00:00:00Z\n---\nedited body\n")
        check("review-9: demirror_text strips global_ref/revision keys and keeps the local body",
              "global_ref:" not in _dem and "base_revision:" not in _dem
              and "mirrored_at:" not in _dem and "edited body" in _dem)
    else:
        check("review-2: writable fixture available", False)
        check("review-9: demirror_text strips global_ref/revision keys and keeps the local body", False)

    _old_hr = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_r)
    _old_gr = sg.GLOBAL
    try:
        _glob_r = _home_r / ".claude" / "memory"; _glob_r.mkdir(parents=True)
        sg.GLOBAL = _glob_r
        (_glob_r / "ug-r.md").write_text(
            "---\nname: ug-r\ndescription: d\nmetadata:\n  scope: user-global\n"
            "  type: feedback\n---\nbody\n", encoding="utf-8")
        _store_r = _ctx_r.native_memory_dir
        _store_r.mkdir(parents=True, exist_ok=True)
        (_store_r / "MEMORY.md").write_text("# Memory Index\n\n", encoding="utf-8")
        _db_before = _ctx_r.plugin_data_dir / "control.sqlite"
        if _db_before.exists():
            _db_before.unlink()
        _out_l, _err_l = _io73.StringIO(), _io73.StringIO()
        with _ctx73.redirect_stdout(_out_l), _ctx73.redirect_stderr(_err_l):
            _rc_list = sg.run(_proj_r, pull=False)
        check("review-3: --list does not mint control.sqlite",
              _rc_list == 0 and not (_ctx_r.plugin_data_dir / "control.sqlite").exists())
        _enroll_personal(_proj_r)
        # pull once to mint, then a STOP_LOCAL conflict recorded once not twice
        (_glob_r / "ed.md").write_text(_v3_canon("ed", body="canon body\n"), encoding="utf-8")
        _canon_ed = _ctx_r.canonical_domain_dir
        _canon_ed.mkdir(parents=True, exist_ok=True)
        (_canon_ed / "ed.md").write_text((_glob_r / "ed.md").read_text(encoding="utf-8"),
                                         encoding="utf-8")
        _mir_ed = sg._as_mirror((_glob_r / "ed.md").read_text(encoding="utf-8"), "ed",
                                since="2026-01-01T00:00:00Z",
                                body_hash=sg._body_hash((_glob_r / "ed.md").read_text(encoding="utf-8")))
        # local edit of a stamped mirror
        _mir_ed_local = _mir_ed.replace("canon body", "LOCAL EDIT")
        (_store_r / "ed.md").write_text(_mir_ed_local, encoding="utf-8")
        _out_p, _err_p = _io73.StringIO(), _io73.StringIO()
        with _ctx73.redirect_stdout(_out_p), _ctx73.redirect_stderr(_err_p):
            _rc_p = sg.run(_proj_r, pull=True)
        _out_p2, _err_p2 = _io73.StringIO(), _io73.StringIO()
        with _ctx73.redirect_stdout(_out_p2), _ctx73.redirect_stderr(_err_p2):
            sg.run(_proj_r, pull=True)
        _conn_c = cp.connect(cp.db_path(_ctx_r))
        _nrows = _conn_c.execute(
            "SELECT count(*) AS n FROM conflicts WHERE fact_stem='ed' AND resolved=''"
        ).fetchone()["n"]
        check("review-3: pull records one open conflict row per stem (upsert, not append)",
              _rc_p == 0 and int(_nrows) == 1)
        # resolve keep-canonical marks it resolved
        import argparse as _ap_r
        _ns = _ap_r.Namespace(project=str(_proj_r), fact="ed", keep_canonical=True,
                              fork_local=None, promote_local=False, json=False, all=False)
        _rc_keep = cmo.cmd_resolve(_ns)
        _nopen = _conn_c.execute(
            "SELECT count(*) AS n FROM conflicts WHERE fact_stem='ed' AND resolved=''"
        ).fetchone()["n"]
        _nres = _conn_c.execute(
            "SELECT count(*) AS n FROM conflicts WHERE fact_stem='ed' AND resolved='keep-canonical'"
        ).fetchone()["n"]
        _body_after = (_store_r / "ed.md").read_text(encoding="utf-8")
        check("review-4: resolve --keep-canonical marks the conflict resolved and restamps the mirror",
              _rc_keep == 0 and int(_nopen) == 0 and int(_nres) == 1
              and "LOCAL EDIT" not in _body_after and "global_ref:" in _body_after)
        # compact keys slot, not SHA, and does not mint events.jsonl
        _slot = _ctx_r.project_slot
        _clog = ret.cycle_log_write_path(_store_r, plugin_data=_ctx_r.plugin_data_dir)
        _clog.parent.mkdir(parents=True, exist_ok=True)
        with _clog.open("w", encoding="utf-8") as _fh:
            for i in range(3):
                _fh.write(_json_xp.dumps({"n": i, "ts": "2026-08-31T00:00:00Z"}) + "\n")
        _nsd = _ap_r.Namespace(project=str(_proj_r), data_cmd="compact", json=True,
                               apply=False, plan=True, show=None, dest=None,
                               purge_project=None, purge_domain=None)
        _buf_c = _io73.StringIO()
        with _ctx73.redirect_stdout(_buf_c):
            cmo.cmd_data(_nsd)
        _plan_c = _json_xp.loads(_buf_c.getvalue())
        _sha_events = _ctx_r.plugin_data_dir / "ops" / _ctx_r.project_id / "events.jsonl"
        check("review-5: compact plan keys cycle_log on ops/<slot or project_id>/ not events.jsonl",
              str(_clog) == _plan_c.get("cycle_log")
              and (_slot in _plan_c.get("cycle_log", "")
                   or _ctx_r.project_id in _plan_c.get("cycle_log", ""))
              and "events.jsonl" not in _plan_c.get("cycle_log", "")
              and not _sha_events.exists())
        _purged = ret.purge_project(_ctx_r.plugin_data_dir, _ctx_r.project_id, _store_r)
        check("review-5: purge_project deletes the slot-keyed cycle log",
              _purged["ok"] is True and not _clog.exists())
        _conn_c.close()
    finally:
        sg.GLOBAL = _old_gr
        if _old_hr is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_hr

with _tf_xp.TemporaryDirectory() as _td_g:
    _home_g = Path(_td_g) / "home"; _home_g.mkdir()
    _cfg_g = Path(_td_g) / "cfg"
    _gdir = _cfg_g / "memory"; _gdir.mkdir(parents=True)
    (_gdir / "net-fact.md").write_text(
        "---\nname: net-fact\ndescription: d\nmetadata:\n  scope: user-global\n---\nbody\n",
        encoding="utf-8")
    _proj_g = Path(_td_g) / "gproj"; _proj_g.mkdir()
    _old_hg = _os_xp.environ.get("HOME")
    _old_cg = _os_xp.environ.get("CLAUDE_CONFIG_DIR")
    _old_gg = sg.GLOBAL
    _os_xp.environ["HOME"] = str(_home_g)
    _os_xp.environ["CLAUDE_CONFIG_DIR"] = str(_cfg_g)
    sg.GLOBAL = _cfg_g / "unused-fixture-global"
    sg.GLOBAL.mkdir(parents=True)
    try:
        _enroll_personal(_proj_g)
        _ctx_g = sc.resolve_store(_proj_g)
        _ctx_g.canonical_domain_dir.mkdir(parents=True, exist_ok=True)
        (_ctx_g.canonical_domain_dir / "keep.md").write_text(
            "---\nname: keep\ndescription: d\ndomain: personal\nmetadata:\n"
            "  scope: user-global\n  type: feedback\n---\nKEEP\n", encoding="utf-8")
        _bc_g = ms.build_context(_proj_g)
        check("review-6: Phase-0 global_store_facts counts domain canonicals, not leftover memory",
              int(_bc_g.get("global_store_facts") or 0) == 1
              and (_gdir / "net-fact.md").is_file())
        _seed_g = ms.seed_record(_bc_g)
        check("review-6: cycle-record seed global_store_facts matches build_context count",
              int(_seed_g["cross_project"]["global_store_facts"]) == 1)
    finally:
        sg.GLOBAL = _old_gg
        if _old_hg is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_hg
        if _old_cg is None:
            _os_xp.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            _os_xp.environ["CLAUDE_CONFIG_DIR"] = _old_cg

with _tf_xp.TemporaryDirectory() as _td_b:
    import session_beacon as sb
    _home_b = Path(_td_b) / "home"; _home_b.mkdir()
    _glob_b = Path(_td_b) / "glob"; _glob_b.mkdir()
    (_glob_b / "tagged.md").write_text(
        "---\nname: tagged\ndescription: d\ndomain: personal\nmetadata:\n"
        "  scope: user-global\n---\nbody\n", encoding="utf-8")
    _store_b = Path(_td_b) / "store"; _store_b.mkdir()
    (_store_b / "local.md").write_text("x\n", encoding="utf-8")
    _old_hb = _os_xp.environ.get("HOME")
    _old_gb = sg.GLOBAL
    _os_xp.environ["HOME"] = str(_home_b)
    sg.GLOBAL = _glob_b
    try:
        _line_b = sb.beacon_line(_store_b, domain_id="unknown",
                                 migration_mode=dp.MIGRATION_ENFORCED)
        check("review-7: beacon is silent for domain-tagged facts this project cannot pull",
              _line_b == "")
        _gf_b = [(s, fm, t) for s, fm, t, _p in sg._all_domain_records()]
        _miss, _stale = sg._store_gaps(
            _store_b, None,
            _gf_b,
            {n: sg._body_hash(t) for n, _fm, t in _gf_b},
            domain_id="unknown", migration_mode=dp.MIGRATION_ENFORCED)
        check("review-7: _store_gaps admits none of a tagged-only fleet for unknown+enforced",
              _miss == 0 and _stale == 0)
    finally:
        sg.GLOBAL = _old_gb
        if _old_hb is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_hb

with _tf_xp.TemporaryDirectory() as _td_m:
    _home_m = Path(_td_m) / "home"; _home_m.mkdir()
    _proj_m = Path(_td_m) / "mproj"; _proj_m.mkdir()
    (_proj_m / "main.py").write_text("x=1\n", encoding="utf-8")
    _leg = _home_m / ".claude" / "memory"
    _leg.mkdir(parents=True)
    (_leg / "legacy-m.md").write_text(
        "---\nname: legacy-m\ndescription: a legacy fact\nmetadata:\n"
        "  scope: user-global\n  type: feedback\n---\nlegacy body\n", encoding="utf-8")
    (_leg / "MEMORY.md").write_text(
        "# Memory Index\n\n- [legacy-m](legacy-m.md) — a legacy fact\n", encoding="utf-8")
    _old_hm = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_m)
    try:
        _ctx_m = sc.resolve_store(_proj_m, environ=_xp_env(_home_m))
        import argparse as _ap_m
        _nsm = _ap_m.Namespace(project=str(_proj_m), apply=False, rollback=False,
                               json=False, plan=True)
        _buf_dry = _io73.StringIO()
        with _ctx73.redirect_stdout(_buf_dry):
            _rc_dry = cmo.cmd_migrate(_nsm)
        _db_m = _ctx_m.plugin_data_dir / "control.sqlite"
        check("review-8: migrate --plan is dry and does not mint control.sqlite",
              _rc_dry == 0 and "dry" in _buf_dry.getvalue() and not _db_m.exists())
        _nsm.apply = True
        _nsm.assign = None
        _nsm.exclude = None
        _nsm.domain = None
        _nsm.finalize = False
        _nsm.status = False
        _buf_app = _io73.StringIO()
        _buf_app_err = _io73.StringIO()
        with _ctx73.redirect_stdout(_buf_app), _ctx73.redirect_stderr(_buf_app_err):
            _rc_app = cmo.cmd_migrate(_nsm)
        check("review-8: migrate --apply refuses while facts are unresolved (no legacy-unassigned)",
              _rc_app == 2 and "unresolved" in _buf_app_err.getvalue()
              and not (_ctx_m.canonical_domain_dir / "legacy-m.md").exists())
        _nsm.apply = False
        _nsm.assign = "legacy-m"
        _nsm.domain = "personal"
        with _ctx73.redirect_stdout(_io73.StringIO()):
            _rc_as = cmo.cmd_migrate(_nsm)
        _nsm.assign = None
        _nsm.apply = True
        _nsm.confirm = "migrate-apply"
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            cmo.main(["project", "enroll", str(_proj_m), "--domain", "personal", "--apply",
                      "--confirm", "enroll-personal"])
        _buf_app2 = _io73.StringIO()
        with _ctx73.redirect_stdout(_buf_app2):
            _rc_app2 = cmo.cmd_migrate(_nsm)
        _copy_m = (_home_m / ".claude" / "consolidate-memory" / "domains"
                   / "personal" / "facts" / "legacy-m.md")
        _copy_txt = _copy_m.read_text(encoding="utf-8") if _copy_m.exists() else ""
        check("review-8: migrate --assign then --apply stamps the assigned domain",
              _rc_as == 0 and _rc_app2 == 0 and _copy_m.exists()
              and "domain: personal" in _copy_txt
              and "legacy-unassigned" not in _copy_txt)
    finally:
        if _old_hm is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_hm

with _tf_xp.TemporaryDirectory() as _td_l:
    _home_l = Path(_td_l) / "home"; _home_l.mkdir()
    _proj_l = Path(_td_l) / "lproj"; _proj_l.mkdir()
    _env_l = _xp_env(_home_l)
    _ctx_l = sc.resolve_store(_proj_l, environ=_env_l)
    _old_hl = _os_xp.environ.get("HOME")
    _os_xp.environ["HOME"] = str(_home_l)
    try:
        sc.assert_writable(_ctx_l)
        _released = {"n": 0}

        class _Boom(cp.FileLock):
            def acquire(self) -> None:
                if self.path.name == "global.lock":
                    raise OSError("boom")
                super().acquire()

            def release(self) -> None:
                _released["n"] += 1
                super().release()

        _real_fl = cp.FileLock
        setattr(cp, "FileLock", _Boom)
        _boom = False
        try:
            cp.acquire_mutation_locks(_ctx_l, [_ctx_l.project_id])
        except OSError:
            _boom = True
        finally:
            setattr(cp, "FileLock", _real_fl)
        check("review-s2: acquire_mutation_locks releases already-held locks when a later acquire fails",
              _boom is True and _released["n"] >= 1)

        _conn_l = cp.connect_journal(_ctx_l)
        _op_ab = cp.journal_insert(_conn_l, "pull", {"project_id": "x", "n": 0}, "journal_start")
        _rec_ab = cp.recover_pending(_conn_l, ctx=_ctx_l)
        _row_ab = _conn_l.execute("SELECT status FROM journal WHERE op_id=?", (_op_ab,)).fetchone()
        _st_ab = _row_ab["status"] if _row_ab is not None else ""
        check("review-s3: recover_pending abandons a non-replayable pull with no temps (does not mark complete)",
              _op_ab in _rec_ab and _st_ab == "abandoned" and cp.pending_ops(_conn_l) == [])
        _conn_l.close()

        # repair-mirror refuses when auto-memory is disabled
        import argparse as _ap_l
        _nsr = _ap_l.Namespace(project=str(_proj_l), fact="nope")
        _old_dis = _os_xp.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")
        _os_xp.environ["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        try:
            _buf_e = _io73.StringIO()
            with _ctx73.redirect_stderr(_buf_e):
                _rc_rm = cmo.cmd_repair_mirror(_nsr)
            check("review-s1: repair-mirror assert_writable refuses when auto-memory is disabled",
                  _rc_rm == 2 and "disabled" in _buf_e.getvalue())
        finally:
            if _old_dis is None:
                _os_xp.environ.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)
            else:
                _os_xp.environ["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = _old_dis
    except sc.WriteRefused:
        check("review-s2: writable fixture available", False)
        check("review-s3: recover_pending abandons a non-replayable pull with no temps (does not mark complete)", False)
        check("review-s1: repair-mirror assert_writable refuses when auto-memory is disabled", False)
    finally:
        if _old_hl is None:
            _os_xp.environ.pop("HOME", None)
        else:
            _os_xp.environ["HOME"] = _old_hl

# ── 0.3.0 remaining substrate pins (classify-under-lock, migrate, forget, races) ──
_fix021 = ROOT / "tests" / "fixtures" / "upgrade-0.2.1"
check("0.3.0: vendored 0.2.1 upgrade fixture is present",
      (_fix021 / "legacy" / "plain.md").is_file()
      and (_fix021 / "legacy" / "dup.md").is_file()
      and (_fix021 / "unknown-pool" / "dup.md").is_file()
      and (_fix021 / "personal" / "already.md").is_file())

_canon_ug = (
    "---\nname: lock-m\ndescription: \"classify under lock\"\n"
    "metadata:\n  node_type: memory\n  type: reference\n"
    "scope: user-global\ndomain: personal\n---\ncanon body lock-m\n"
)

with _Env73() as _e_lock:
    _ctx_lock = sc.resolve_store(_e_lock.proj)
    _origin_lock = _e_lock.store / "lock-m.md"
    _origin_lock.write_text(_canon_ug, encoding="utf-8")
    _up_lock = ci.upsert(_ctx_lock, "lock-m", _canon_ug, origin_local=_origin_lock)
    _dry_u, _dry_e = _io73.StringIO(), _io73.StringIO()
    with _ctx73.redirect_stdout(_dry_u), _ctx73.redirect_stderr(_dry_e):
        _rc_dry = cmo.main(["project", "unenroll", str(_e_lock.proj)])
    _edited = _origin_lock.read_text(encoding="utf-8").replace("canon body lock-m",
                                                               "LOCAL EDIT AFTER DRY PLAN")
    _origin_lock.write_text(_edited, encoding="utf-8")
    _app_u, _app_e = _io73.StringIO(), _io73.StringIO()
    with _ctx73.redirect_stdout(_app_u), _ctx73.redirect_stderr(_app_e):
        _rc_app = cmo.main(["project", "unenroll", str(_e_lock.proj),
                            "--apply", "--confirm", "unenroll-personal"])
    _qdir = _e_lock.store / "quarantine"
    _qhits = list(_qdir.glob("lock-m*.md")) if _qdir.is_dir() else []
    check("0.3.0: classify-under-lock quarantines an edit after dry-plan delete",
          _up_lock.get("ok") is True and _rc_dry == 0 and "revoke" in _dry_u.getvalue()
          and _rc_app == 0 and not _origin_lock.exists()
          and len(_qhits) == 1
          and "LOCAL EDIT AFTER DRY PLAN" in _qhits[0].read_text(encoding="utf-8"))

with _Env73() as _e_fg:
    _ctx_fg = sc.resolve_store(_e_fg.proj)
    _orig_fg = _e_fg.store / "fg-edit.md"
    _body_fg = (
        "---\nname: fg-edit\ndescription: \"forget local edit\"\n"
        "metadata:\n  node_type: memory\n  type: reference\n"
        "scope: user-global\ndomain: personal\n---\nforget canon\n"
    )
    _orig_fg.write_text(_body_fg, encoding="utf-8")
    ci.upsert(_ctx_fg, "fg-edit", _body_fg, origin_local=_orig_fg)
    _orig_fg.write_text(_orig_fg.read_text(encoding="utf-8").replace(
        "forget canon", "KEEP THIS LOCAL EDIT"), encoding="utf-8")
    _fg_out = ci.forget(_ctx_fg, "fg-edit")
    _qfg = list((_e_fg.store / "quarantine").glob("fg-edit*.md"))
    check("0.3.0: forget quarantines a locally edited mirror (does not destroy the body)",
          _fg_out.get("ok") is True and len(_qfg) == 1
          and "KEEP THIS LOCAL EDIT" in _qfg[0].read_text(encoding="utf-8")
          and not _orig_fg.exists())

with _Env73() as _e_rb:
    _ctx_rb = sc.resolve_store(_e_rb.proj)
    _conn_rb = cp.connect(cp.db_path(_ctx_rb))
    try:
        _old_rb = "p_" + ("ab" * 16)
        _conn_rb.execute(
            "INSERT INTO projects(project_id, profile_id, domain_id, status, current_root, "
            "git_common_dir, native_memory_dir, session_dir, display_name, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (_old_rb, _ctx_rb.profile_id, "personal", "enrolled", str(_ctx_rb.project_root),
             "", str(_ctx_rb.native_memory_dir), str(_ctx_rb.session_dir),
             "old", "t"))
        _computed_rb = "p_" + ("cd" * 16)
        _conn_rb.execute(
            "INSERT INTO projects(project_id, profile_id, domain_id, status, current_root) "
            "VALUES (?,?,?,?,?)",
            (_computed_rb, _ctx_rb.profile_id, "personal", "enrolled", "/tmp/other"))
        _conn_rb.commit()
        cp.apply_registry_ops(_conn_rb, [{
            "op": "project_rebind", "project_id": _old_rb, "retire_id": _computed_rb,
            "alias_id": _computed_rb, "current_root": str(_ctx_rb.project_root),
            "git_common_dir": "", "native_memory_dir": str(_ctx_rb.native_memory_dir),
            "session_dir": str(_ctx_rb.session_dir), "display_name": "rebound",
        }])
        _kept = _conn_rb.execute(
            "SELECT project_id FROM projects WHERE project_id=?", (_old_rb,)
        ).fetchone()
        _gone = _conn_rb.execute(
            "SELECT project_id FROM projects WHERE project_id=?", (_computed_rb,)
        ).fetchone()
        check("0.3.0: project_rebind leaves one enrolled row and deletes the computed id",
              _kept is not None and _gone is None)
    finally:
        _conn_rb.close()

with _Env73() as _e_ap:
    (_e_ap.proj / "mod.py").write_text("x = 1\n", encoding="utf-8")
    _excl = (
        "---\nname: no-py\ndescription: \"exclude python\"\n"
        "metadata:\n  node_type: memory\n  type: reference\n"
        "scope: user-global\ndomain: personal\napplies_exclude: [python]\n---\nbody\n"
    )
    _anyf = (
        "---\nname: yes-py\ndescription: \"any python\"\n"
        "metadata:\n  node_type: memory\n  type: reference\n"
        "scope: stack-general\nstacks: [python]\ndomain: personal\n"
        "applies_any: [python]\n---\nbody\n"
    )
    _nest = (
        "---\nname: nest-ap\ndescription: \"nested applies refused\"\n"
        "metadata:\n  node_type: memory\n  type: reference\n"
        "scope: user-global\ndomain: personal\napplies.any: [python]\n---\nbody\n"
    )
    (_e_ap.glob / "no-py.md").write_text(_excl, encoding="utf-8")
    (_e_ap.glob / "yes-py.md").write_text(_anyf, encoding="utf-8")
    (_e_ap.glob / "nest-ap.md").write_text(_nest, encoding="utf-8")
    _rc_ap, _out_ap, _err_ap = _run73(_e_ap.proj)
    check("0.3.0: pull honors applies_exclude / applies_any and refuses nested applies.*",
          _rc_ap == 0 and not (_e_ap.store / "no-py.md").exists()
          and (_e_ap.store / "yes-py.md").exists()
          and not (_e_ap.store / "nest-ap.md").exists())

with _Env73() as _e_mg:
    _ctx_mg = sc.resolve_store(_e_mg.proj)
    _leg_mg = _ctx_mg.config_root / "memory"
    _unk = _ctx_mg.config_root / "consolidate-memory" / "domains" / "unknown" / "facts"
    _pdir_mg = _ctx_mg.canonical_domain_dir
    _leg_mg.mkdir(parents=True, exist_ok=True)
    _unk.mkdir(parents=True, exist_ok=True)
    _pdir_mg.mkdir(parents=True, exist_ok=True)
    import shutil as _sh_mg
    _sh_mg.copy2(_fix021 / "legacy" / "plain.md", _leg_mg / "plain.md")
    _sh_mg.copy2(_fix021 / "legacy" / "dup.md", _leg_mg / "dup.md")
    _sh_mg.copy2(_fix021 / "unknown-pool" / "dup.md", _unk / "dup.md")
    _sh_mg.copy2(_fix021 / "legacy" / "already.md", _leg_mg / "already.md")
    _sh_mg.copy2(_fix021 / "personal" / "already.md", _pdir_mg / "already.md")
    # P1-2: keep-existing requires a valid v3 dest. The vendored 0.2.1 dest
    # declares schema 3 without the full key set (CLASS_INVALID).
    (_pdir_mg / "already.md").write_text(
        _v3_canon("already",
                  body="Pre-existing dest body — migrate must not overwrite.\n"),
        encoding="utf-8")
    _dest_before = (_pdir_mg / "already.md").read_text(encoding="utf-8")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["migrate", str(_e_mg.proj)])
        cmo.main(["migrate", str(_e_mg.proj), "--resolve-collision", "dup", "--keep", "legacy"])
        cmo.main(["migrate", str(_e_mg.proj), "--assign", "plain", "--domain", "personal"])
        cmo.main(["migrate", str(_e_mg.proj), "--assign", "dup", "--domain", "personal"])
        cmo.main(["migrate", str(_e_mg.proj), "--assign", "already", "--domain", "personal"])
    _plan_mg = _json_xp.loads((_ctx_mg.plugin_data_dir / "migrate-plan.json").read_text(
        encoding="utf-8"))
    check("0.3.0: --keep legacy clears collisions when the primary origin is kept",
          not (_plan_mg.get("facts") or {}).get("dup", {}).get("collisions"))
    _ref_u, _ref_e = _io73.StringIO(), _io73.StringIO()
    with _ctx73.redirect_stdout(_ref_u), _ctx73.redirect_stderr(_ref_e):
        _rc_ref = cmo.main(["migrate", str(_e_mg.proj), "--apply",
                            "--confirm", "migrate-apply"])
    check("0.3.0: migrate apply refuses an existing dest without --on-existing",
          _rc_ref == 2 and "dest exists" in _ref_e.getvalue()
          and (_pdir_mg / "already.md").read_text(encoding="utf-8") == _dest_before)
    # P1-7 (#146): mangle the domain catalog so the kept-existing stem is MISSING —
    # the apply must REPAIR the projection (every active kept-existing gets a pointer).
    _cat_mg = _pdir_mg / "MEMORY.md"
    if _cat_mg.is_file():
        _cat_mg.write_text(
            "\n".join(ln for ln in _cat_mg.read_text(encoding="utf-8").splitlines()
                      if "already" not in ln) + "\n", encoding="utf-8")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_keep = cmo.main(["migrate", str(_e_mg.proj), "--apply",
                             "--confirm", "migrate-apply",
                             "--on-existing", "keep-existing"])
    check("0.3.0: migrate --on-existing keep-existing leaves dest bytes and copies the rest",
          _rc_keep == 0
          and (_pdir_mg / "already.md").read_text(encoding="utf-8") == _dest_before
          and (_pdir_mg / "plain.md").is_file()
          and "LEGACY copy" in (_pdir_mg / "dup.md").read_text(encoding="utf-8")
          and "scope: user-global" in (_pdir_mg / "plain.md").read_text(encoding="utf-8"))
    check("P1-7: keep-existing active dest with a stale/missing catalog pointer is REPAIRED",
          "already" in (_pdir_mg / "MEMORY.md").read_text(encoding="utf-8"))
    (_pdir_mg / "plain.md").write_text(
        (_pdir_mg / "plain.md").read_text(encoding="utf-8").replace(
            "Legacy-only body", "EDITED AFTER APPLY"), encoding="utf-8")
    _rb_u, _rb_e = _io73.StringIO(), _io73.StringIO()
    with _ctx73.redirect_stdout(_rb_u), _ctx73.redirect_stderr(_rb_e):
        _rc_rb = cmo.main(["migrate", str(_e_mg.proj), "--rollback",
                           "--confirm", "migrate-rollback"])
    check("0.3.0: migrate rollback is all-or-nothing on an edited dest (no partial restore)",
          _rc_rb == 2 and "conflict" in _rb_e.getvalue().lower() + _rb_u.getvalue().lower()
          and "EDITED AFTER APPLY" in (_pdir_mg / "plain.md").read_text(encoding="utf-8")
          and (_pdir_mg / "already.md").read_text(encoding="utf-8") == _dest_before)

with _Env73() as _e_cr:
    _ctx_cr = sc.resolve_store(_e_cr.proj)
    _dest_cr = _ctx_cr.canonical_domain_dir / "race-create.md"
    _dest_cr.parent.mkdir(parents=True, exist_ok=True)
    _appeared = "APPEARED BEFORE PUBLISH\n"
    _crash_cr = False
    try:
        cp.transact(
            _ctx_cr, "race-create", {"stem": "race-create"},
            lambda _c, _t: (
                _t.__setitem__(str(_dest_cr), "NEW CANON\n") or {
                    "dest_modes": {str(_dest_cr): "create"},
                    "expected_revisions": {str(_dest_cr): cp.ABSENT},
                }
            ),
            crash_after="verify_unchanged", skip_recover=True)
    except cp.CrashSimulated:
        _crash_cr = True
    _dest_cr.write_text(_appeared, encoding="utf-8")
    _j_cr = cp.connect_journal(_ctx_cr)
    _r_cr = cp.connect(cp.db_path(_ctx_cr))
    _got_cr = cp.recover_pending(_j_cr, ctx=_ctx_cr, registry_conn=_r_cr)
    _st_cr = _j_cr.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _j_cr.close(); _r_cr.close()
    check("0.3.0: create dest that appears after verify is not clobbered (journal not complete)",
          _crash_cr and _dest_cr.read_text(encoding="utf-8") == _appeared
          and (_st_cr is None or str(_st_cr["status"] or "") != "complete")
          and len(_got_cr) == 0)

with _Env73() as _e_co:
    _ctx_co = sc.resolve_store(_e_co.proj)
    _d_co = _ctx_co.canonical_domain_dir / "exists.md"
    _d_co.parent.mkdir(parents=True, exist_ok=True)
    _d_co.write_text("ALREADY\n", encoding="utf-8")
    _up_co = ci.upsert(_ctx_co, "exists",
                       "---\nname: exists\ndescription: x\n"
                       "metadata:\n  node_type: memory\n  type: reference\n"
                       "scope: user-global\n---\nnew\n",
                       create_only=True)
    check("0.3.0: upsert create_only refuses when dest already exists",
          _up_co.get("ok") is False
          and "already exists" in str(_up_co.get("error") or "")
          and _d_co.read_text(encoding="utf-8") == "ALREADY\n")

check("0.3.0: SKILL/harness-map do not claim untagged dual-read pull",
      "legacy `~/.claude/memory/` dual-read until" not in _skill_md.read_text(encoding="utf-8")
      and "only while dual-read" not in _skill_md.read_text(encoding="utf-8")
      and "is a dual-read migration source until" not in (
          ROOT / "plugins" / "consolidate-memory" / "skills" / "consolidate-memory"
          / "references" / "harness-map.md").read_text(encoding="utf-8"))

with _Env73() as _e_pr:
    _ctx_pr = sc.resolve_store(_e_pr.proj)
    _j_pr = cp.connect_journal(_ctx_pr)
    _r_pr = cp.connect(cp.db_path(_ctx_pr))
    _r_pr.isolation_level = None
    _fid_pr = "f_" + ("ab" * 12)
    _oid_pr = cp.journal_insert(_j_pr, "test-partial", {
        "origin_domain_id": _ctx_pr.domain_id,
        "origin_project_id": _ctx_pr.project_id,
        "registry_ops": [
            {"op": "fact_upsert", "fact_id": _fid_pr, "stem": "partial",
             "domain_id": _ctx_pr.domain_id, "canonical_path": "/x",
             "revision": "r", "status": "active", "sensitivity": "internal"},
            {"op": "not-a-real-op"},
        ],
    }, "publish")
    _got_pr = cp.recover_pending(_j_pr, ctx=_ctx_pr, registry_conn=_r_pr)
    _row_pr = _r_pr.execute("SELECT 1 FROM facts WHERE fact_id=?", (_fid_pr,)).fetchone()
    _st_pr = _j_pr.execute("SELECT status FROM journal WHERE op_id=?", (_oid_pr,)).fetchone()
    _j_pr.close(); _r_pr.close()
    check("0.3.0: recover_pending rolls back a partial registry replay",
          _row_pr is None and len(_got_pr) == 0
          and str(_st_pr["status"] or "") == "pending")

with _Env73() as _e_id:
    _ctx_id = sc.resolve_store(_e_id.proj)
    _dest_id = _ctx_id.canonical_domain_dir / "already-ok.md"
    _dest_id.parent.mkdir(parents=True, exist_ok=True)
    _body_id = "ALREADY PUBLISHED\n"
    _dest_id.write_text(_body_id, encoding="utf-8")
    _tmp_id = _dest_id.with_suffix(".md.tmpid")
    _tmp_id.write_text(_body_id, encoding="utf-8")
    _want_id = _hlA3.sha256(_body_id.encode("utf-8")).hexdigest()
    _n_id, _bad_id = cp._publish_destinations([{
        "tmp": str(_tmp_id), "dest": str(_dest_id), "sha256": _want_id, "mode": "create",
    }])
    check("0.3.0: create-mode dest with matching hash is already-published (not pending)",
          _n_id == 1 and not _bad_id and not _tmp_id.exists()
          and _dest_id.read_text(encoding="utf-8") == _body_id)

with _Env73() as _e_mp:
    _ctx_mp = sc.resolve_store(_e_mp.proj)
    (_e_mp.store / "MEMORY.md").write_text("# Memory Index\n\n", encoding="utf-8")
    _path_mp = _e_mp.store / "miss-race.md"
    _want_mp = (
        "---\nname: miss-race\ndescription: d\nmetadata:\n  node_type: memory\n"
        "  type: reference\n  global_ref: miss-race\nscope: user-global\n"
        "domain: personal\n---\nmirror body\n"
    )
    _fm_mp = sg._frontmatter(_want_mp)
    _old_ca = _os_xp.environ.get("CM_CRASH_AFTER")
    _os_xp.environ["CM_CRASH_AFTER"] = "verify_unchanged"
    _crash_mp = False
    try:
        sg._execute_pull_writes(
            _ctx_mp, _e_mp.store, [("miss-race", _fm_mp, "MISSING", _path_mp, _want_mp)],
            None, None)
    except cp.CrashSimulated:
        _crash_mp = True
    finally:
        if _old_ca is None:
            _os_xp.environ.pop("CM_CRASH_AFTER", None)
        else:
            _os_xp.environ["CM_CRASH_AFTER"] = _old_ca
    _path_mp.write_text("LOCAL APPEARED\n", encoding="utf-8")
    _j_mp = cp.connect_journal(_ctx_mp)
    _r_mp = cp.connect(cp.db_path(_ctx_mp))
    _got_mp = cp.recover_pending(_j_mp, ctx=_ctx_mp, registry_conn=_r_mp)
    _hold_mp = _r_mp.execute(
        "SELECT 1 FROM holders WHERE project_id=?", (_ctx_mp.project_id,)).fetchall()
    _j_mp.close(); _r_mp.close()
    check("0.3.0: MISSING pull does not clobber a file that appeared after classify",
          _crash_mp and _path_mp.read_text(encoding="utf-8") == "LOCAL APPEARED\n"
          and "global_ref:" not in _path_mp.read_text(encoding="utf-8")
          and len(_got_mp) == 0)

with _Env73() as _e_src:
    _ctx_src = sc.resolve_store(_e_src.proj)
    _leg_src = _ctx_src.config_root / "memory"
    _leg_src.mkdir(parents=True, exist_ok=True)
    _src_p = _leg_src / "chg.md"
    _src_p.write_text(
        "---\nname: chg\ndescription: reviewed\nscope: user-global\n"
        "metadata:\n  node_type: memory\n  type: reference\n---\nV1\n",
        encoding="utf-8")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["migrate", str(_e_src.proj)])
        cmo.main(["migrate", str(_e_src.proj), "--assign", "chg", "--domain", "personal"])
    _src_p.write_text(_src_p.read_text(encoding="utf-8").replace("V1", "V2"), encoding="utf-8")
    _e_src_err = _io73.StringIO()
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_e_src_err):
        _rc_src = cmo.main(["migrate", str(_e_src.proj), "--apply",
                            "--confirm", "migrate-apply"])
    check("0.3.0: migrate apply refuses when reviewed source bytes changed",
          _rc_src == 2 and "source changed" in _e_src_err.getvalue())

check("0.3.0: migrate CLI does not advertise unimplemented fork-migrated-as",
      "fork-migrated-as" not in (ROOT / "plugins" / "consolidate-memory"
                                 / "scripts" / "cm_ops.py").read_text(encoding="utf-8"))

with _Env73() as _e_pg:
    _ctx_pg = sc.resolve_store(_e_pg.proj)
    _canon_pg = _ctx_pg.canonical_domain_dir / "keep-me.md"
    _canon_pg.parent.mkdir(parents=True, exist_ok=True)
    _canon_pg.write_text("STAY\n", encoding="utf-8")
    _conn_pg = cp.connect(cp.db_path(_ctx_pg))
    _conn_pg.execute(
        "INSERT INTO projects(project_id, profile_id, domain_id, status, current_root, "
        "native_memory_dir) VALUES (?,?,?,?,?,?)",
        ("p_" + ("ee" * 16), _ctx_pg.profile_id, "personal", "enrolled", "", ""))
    _conn_pg.commit()
    _conn_pg.close()
    _pg_err = _io73.StringIO()
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_pg_err):
        _rc_pg = cmo.main(["data", "purge", "--project", str(_e_pg.proj),
                           "--scope", "domain-canonicals",
                           "--apply", "--confirm", "purge-domain-canonicals"])
    check("0.3.0: domain purge aborts when a project's revoke cannot run",
          _rc_pg == 2 and "revoke" in _pg_err.getvalue().lower()
          and _canon_pg.exists() and _canon_pg.read_text(encoding="utf-8") == "STAY\n")

# ── post-cadc9fb: recovery source re-verify, fail-closed delete, repair isolation ──
with _Env73() as _e_rs:
    _ctx_rs = sc.resolve_store(_e_rs.proj)
    _dest_rs = _ctx_rs.native_memory_dir / "refresh.md"
    _dest_rs.parent.mkdir(parents=True, exist_ok=True)
    _dest_rs.write_text("ORIGINAL\n", encoding="utf-8")
    _h_orig = cp._file_hash(_dest_rs)
    _crashed = False
    try:
        cp.transact(
            _ctx_rs, "pull-refresh", {"stem": "refresh"},
            lambda _c, _t: (_t.__setitem__(str(_dest_rs), "REPLACEMENT\n") or {
                "expected_revisions": {str(_dest_rs): _h_orig},
            }),
            expected_revisions={str(_dest_rs): _h_orig},
            crash_after="prepare_temps", skip_recover=True)
    except cp.CrashSimulated:
        _crashed = True
    _dest_rs.write_text("USER EDIT\n", encoding="utf-8")
    _j_rs = cp.connect_journal(_ctx_rs)
    _r_rs = cp.connect(cp.db_path(_ctx_rs))
    _got_rs = cp.recover_pending(_j_rs, ctx=_ctx_rs, registry_conn=_r_rs)
    _st_rs = _j_rs.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _j_rs.close(); _r_rs.close()
    check("0.3.1: recover refuses a replace-mode dest that changed after prepare_temps",
          _crashed and _dest_rs.read_text(encoding="utf-8") == "USER EDIT\n"
          and (_st_rs is None or str(_st_rs["status"] or "") != "complete")
          and len(_got_rs) == 0)

with _Env73() as _e_regf:
    _ctx_rf = sc.resolve_store(_e_regf.proj)
    _dest_rf = _ctx_rf.canonical_domain_dir / "no-pub.md"
    _dest_rf.parent.mkdir(parents=True, exist_ok=True)
    _raised_rf = False
    try:
        cp.transact(
            _ctx_rf, "bad-reg", {"stem": "no-pub"},
            lambda _c, _t: (_t.__setitem__(str(_dest_rf), "SHOULD NOT LAND\n") or {
                "registry_ops": [{"op": "not-a-real-op"}],
            }),
            skip_recover=True)
    except sc.WriteRefused as _e_rf:
        _raised_rf = "unknown registry_op" in str(_e_rf)
    check("0.3.1: malformed registry_op is refused before dest publish",
          _raised_rf and (not _dest_rf.exists()
                          or "SHOULD NOT LAND" not in _dest_rf.read_text(encoding="utf-8")))

with _tempfile.TemporaryDirectory() as _td_ud:
    _dir_ud = Path(_td_ud) / "not-a-file"
    _dir_ud.mkdir()
    _del_ud = cp._apply_deletes([{"path": str(_dir_ud), "preimage": "a" * 64}])
    check("0.3.1: unreadable delete preimage is an error (not a delete)",
          _dir_ud.exists() and str(_dir_ud) in _del_ud["errors"]
          and str(_dir_ud) not in _del_ud["deleted"])
    _file_ud = Path(_td_ud) / "live.md"
    _file_ud.write_text("x\n", encoding="utf-8")
    _del_np = cp._apply_deletes([{"path": str(_file_ud), "preimage": ""}])
    check("0.3.1: existing file with empty preimage is not deleted",
          _file_ud.exists() and str(_file_ud) in _del_np["errors"])

with _Env73() as _e_leg:
    _ctx_leg = sc.resolve_store(_e_leg.proj)
    _enroll_personal(_e_leg.proj)
    _ctx_leg = sc.resolve_store(_e_leg.proj)
    _legf = _ctx_leg.config_root / "memory"
    _legf.mkdir(parents=True, exist_ok=True)
    (_legf / "deploy.md").write_text(
        "---\nname: deploy\ndescription: d\ndomain: work\nscope: user-global\n---\nLEGACY WORK\n",
        encoding="utf-8")
    _ns_rm = __import__("argparse").Namespace(project=str(_e_leg.proj), fact="deploy")
    _rc_rm = cmo.cmd_repair_mirror(_ns_rm)
    check("0.3.1: repair-mirror does not restamp a personal project from a legacy work-tagged file",
          _rc_rm == 1 and not (_ctx_leg.native_memory_dir / "deploy.md").exists())

with _Env73() as _e_v3:
    _bad_v3 = (
        "---\nschema_version: 3\nname: bad-v3\ndescription: d\n"
        "domain: personal\nscope: user-global\n---\nbody\n"
    )
    (_e_v3.glob / "bad-v3.md").write_text(_bad_v3, encoding="utf-8")
    _ctx_v3 = sc.resolve_store(_e_v3.proj)
    _enroll_personal(_e_v3.proj)
    _ctx_v3 = sc.resolve_store(_e_v3.proj)
    _ctx_v3.canonical_domain_dir.mkdir(parents=True, exist_ok=True)
    (_ctx_v3.canonical_domain_dir / "bad-v3.md").write_text(_bad_v3, encoding="utf-8")
    _rc_v3, _out_v3, _err_v3 = _run73(_e_v3.proj)
    check("0.3.1: invalid schema-v3 canonical is not pulled",
          _rc_v3 == 0 and not (_e_v3.store / "bad-v3.md").exists())

with _tempfile.TemporaryDirectory() as _td_cat:
    _fd = Path(_td_cat)
    (_fd / "live.md").write_text(_v3_canon("live", description="keep"), encoding="utf-8")
    (_fd / "old.md").write_text(
        _v3_canon("old", description="drop").replace("status: active", "status: superseded"),
        encoding="utf-8")
    (_fd / "dead.md").write_text(
        _v3_canon("dead", description="drop").replace("status: active", "status: tombstoned"),
        encoding="utf-8")
    _cat = ci.generate_catalog(_fd)
    check("0.3.1: catalog lists only status=active facts",
          "live.md" in _cat and "old.md" not in _cat and "dead.md" not in _cat)

from fact_schema import validate_canonical_frontmatter as _vcf
check("0.3.1: applies_any scalar is refused (flow-list required)",
      _vcf({"schema_version": "3", "fact_id": "f_" + "ab" * 12, "name": "x",
            "description": "d", "domain": "personal", "sensitivity": "internal",
            "scope": "user-global", "status": "active",
            "applies_any": "python", "applies_all": "[]", "applies_exclude": "[]",
            "content_modified": "2026-09-01T00:00:00Z",
            "last_observed_at": "2026-09-01T00:00:00Z"},
           stem="x", domain="personal") is not None)

with _Env73() as _e_esc:
    _ctx_esc = sc.resolve_store(_e_esc.proj)
    _outside = Path(_e_esc._td.name) / "outside.md"
    _outside.write_text(
        "---\nname: outside\ndescription: d\nscope: user-global\n---\nX\n", encoding="utf-8")
    _plan_esc = {"facts": {"outside": {"stem": "outside", "source": str(_outside),
                                       "assignment": "personal", "sha256": "00"}}}
    (_ctx_esc.plugin_data_dir).mkdir(parents=True, exist_ok=True)
    (_ctx_esc.plugin_data_dir / "migrate-plan.json").write_text(
        __import__("json").dumps(_plan_esc), encoding="utf-8")
    _esc_e = _io73.StringIO()
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_esc_e):
        _rc_esc = cmo.main(["migrate", str(_e_esc.proj), "--apply",
                            "--confirm", "migrate-apply"])
    check("0.3.1: migrate apply refuses a source outside approved roots",
          _rc_esc == 2 and "outside approved" in _esc_e.getvalue().lower())

with _Env73() as _e_re:
    _ctx_re = sc.resolve_store(_e_re.proj)
    _enroll_personal(_e_re.proj)
    _leg = _ctx_re.config_root / "memory"
    _leg.mkdir(parents=True, exist_ok=True)
    (_leg / "plain2.md").write_text(
        "---\nname: plain2\ndescription: d\nscope: user-global\n---\nbody\n", encoding="utf-8")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["migrate", str(_e_re.proj)])
        cmo.main(["migrate", str(_e_re.proj), "--assign", "plain2", "--domain", "personal"])
        _rc_a1 = cmo.main(["migrate", str(_e_re.proj), "--apply", "--confirm", "migrate-apply"])
        _rc_a2 = cmo.main(["migrate", str(_e_re.proj), "--apply", "--confirm", "migrate-apply"])
    check("0.3.1: second migrate apply refuses until rollback or finalize",
          _rc_a1 == 0 and _rc_a2 == 2)

# ── 0.3.3 Wave 1: dual-read pull / enroll keep-path / dry-run sqlite ─────────
import inspect as _insp033  # noqa: E402

_src_adm033 = _insp033.getsource(sg._admissible_records)
_idx_fix033 = _src_adm033.find("if _global_is_fixture():")
_idx_g033 = _src_adm033.find("g = global_store()")
check("0.3.3: _admissible_records walks global_store only behind _global_is_fixture",
      _idx_fix033 != -1 and _idx_g033 != -1 and _idx_fix033 < _idx_g033
      and "_consider(f, untagged_only=False)" in _src_adm033[_idx_g033:]
      and "_hermetic_home" not in _src_adm033[_idx_fix033:_idx_g033])

with _tf73.TemporaryDirectory() as _td_w1:
    _h_w1 = Path(_td_w1)
    _p_w1 = (_h_w1 / "src" / "proj").resolve(); _p_w1.mkdir(parents=True)
    _oldH_w1, _oldG_w1 = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h_w1)
    # Production-shaped: GLOBAL == HOME/.claude/memory so _global_is_fixture is false.
    sg.GLOBAL = _h_w1 / ".claude" / "memory"
    sg.GLOBAL.mkdir(parents=True)
    try:
        _enroll_personal(_p_w1)
        _ctx_w1 = sc.resolve_store(_p_w1)
        _ddir_w1 = _ctx_w1.canonical_domain_dir
        _ddir_w1.mkdir(parents=True, exist_ok=True)
        (_ddir_w1 / "keep.md").write_text(
            _v3_canon("keep", body="KEEP\n"), encoding="utf-8")
        (sg.GLOBAL / "pwn.md").write_text(
            "---\nname: pwn\ndescription: d\ndomain: personal\nmetadata:\n"
            "  scope: user-global\n  type: feedback\n---\nPWN\n", encoding="utf-8")
        _names_dual = {s for s, _fm, _t in sg.iter_admissible_facts(_ctx_w1)}
        check("0.3.3: dual-read pull does not admit tagged legacy either",
              "keep" in _names_dual and "pwn" not in _names_dual)
        _conn_w1 = cp.connect(cp.db_path(_ctx_w1))
        try:
            cp.set_migration_mode(_conn_w1, "enforced")
            _conn_w1.commit()
        finally:
            _conn_w1.close()
        _names_enf = {s for s, _fm, _t in sg.iter_admissible_facts(_ctx_w1)}
        check("0.3.3: enforced pull does not admit tagged ~/.claude/memory",
              "keep" in _names_enf and "pwn" not in _names_enf)
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_pull_w1 = sg.run(_p_w1, pull=True)
        _nat_w1 = _ctx_w1.native_memory_dir
        check("0.3.3: --pull copies domain keep.md and ignores tagged leftover pwn.md",
              _rc_pull_w1 == 0 and (_nat_w1 / "keep.md").is_file()
              and not (_nat_w1 / "pwn.md").exists())
        import session_beacon as _sb_w1
        _line_w1 = _sb_w1.beacon_line(
            _nat_w1, domain_id="personal", migration_mode="enforced",
            gfacts=sg.iter_admissible_facts(_ctx_w1))
        check("0.3.3: beacon fixture lives in domains/<id>/facts",
              "pwn" not in _line_w1
              and "keep" not in _line_w1)  # keep already mirrored; leftover never listed
    finally:
        sg.GLOBAL = _oldG_w1
        if _oldH_w1 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_w1

with _tf73.TemporaryDirectory() as _td_dry:
    _h_dry = Path(_td_dry)
    _p_dry = (_h_dry / "src" / "proj").resolve(); _p_dry.mkdir(parents=True)
    _oldH_dry = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_h_dry)
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_dry_e = cmo.main(["project", "enroll", str(_p_dry), "--domain", "personal"])
        _ctx_dry = sc.resolve_store(_p_dry)
        _db_dry = cp.db_path(_ctx_dry)
        check("0.3.3: enroll dry-run does not mint control.sqlite",
              _rc_dry_e == 0 and not _db_dry.exists()
              and _ctx_dry.registry_state == "absent")
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_app_e = cmo.main(["project", "enroll", str(_p_dry), "--domain", "personal",
                                  "--apply", "--confirm", "enroll-personal"])
        check("0.3.3: enroll --apply --confirm enroll-personal creates control.sqlite",
              _rc_app_e == 0 and _db_dry.is_file())
    finally:
        if _oldH_dry is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_dry

with _tf73.TemporaryDirectory() as _td_mv:
    _h_mv = Path(_td_mv)
    _p_mv = (_h_mv / "src" / "proj").resolve(); _p_mv.mkdir(parents=True)
    _oldH_mv, _oldG_mv = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h_mv)
    sg.GLOBAL = _h_mv / "global-mem"
    sg.GLOBAL.mkdir(parents=True)
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_en_w = cmo.main(["project", "enroll", str(_p_mv), "--domain", "work",
                                 "--apply", "--confirm", "enroll-work"])
        _ctx_mv = sc.resolve_store(_p_mv)
        _nat_mv = _ctx_mv.native_memory_dir
        _nat_mv.mkdir(parents=True, exist_ok=True)
        _spoof_body = (
            "---\nname: spoof\ndescription: d\ndomain: personal\n"
            "metadata:\n  node_type: memory\n  type: reference\n"
            "  scope: user-global\n---\nspoof body\n"
        )
        (_nat_mv / "spoof.md").write_text(sg._as_mirror(_spoof_body, "spoof"), encoding="utf-8")
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_mv = cmo.main(["project", "move-domain", str(_p_mv), "--to", "personal",
                               "--apply", "--confirm", "move-work-to-personal"])
        _q_mv = list((_nat_mv / "quarantine").glob("spoof*.md")) if (_nat_mv / "quarantine").is_dir() else []
        check("0.3.3: move-domain does not keep a mirror that spoofs dest domain:",
              _rc_en_w == 0 and _rc_mv == 0
              and not (_nat_mv / "spoof.md").exists()
              and len(_q_mv) == 1
              and "spoof body" in _q_mv[0].read_text(encoding="utf-8")
              and sc.resolve_store(_p_mv).domain_id == "personal")
    finally:
        sg.GLOBAL = _oldG_mv
        if _oldH_mv is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_mv

# ── 0.3.3 Wave 2: journal crash windows + temps 0600 ─────────────────────────
with _Env73() as _e_co:
    _ctx_co = sc.resolve_store(_e_co.proj)
    _dest_co = _ctx_co.native_memory_dir / "d.md"
    _dest_co.parent.mkdir(parents=True, exist_ok=True)
    _dest_co.write_text("OLD-DEST\n", encoding="utf-8")
    _origin_co = _ctx_co.native_memory_dir / "o.md"
    _origin_co.write_text("ORIGIN\n", encoding="utf-8")
    _h_origin_co = cp._file_hash(_origin_co)
    _crash_co = False
    try:
        cp.transact(
            _ctx_co, "complete-old", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_co), "NEW-DEST\n") or {
                "deletes": [{"path": str(_origin_co), "preimage": _h_origin_co}],
            }),
            crash_after="after_dests")
    except cp.CrashSimulated:
        _crash_co = True
    check("0.3.3: after_dests crash leaves dest published and origin already trashed",
          _crash_co and _dest_co.read_text(encoding="utf-8") == "NEW-DEST\n"
          and not _origin_co.exists())
    _j_co = cp.connect_journal(_ctx_co)
    _r_co = cp.connect(cp.db_path(_ctx_co))
    _got_co = cp.recover_pending(_j_co, ctx=_ctx_co, registry_conn=_r_co)
    _st_co = _j_co.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_co.close(); _r_co.close()
    check("0.3.4: after_dests recover completes (trash already done)",
          _dest_co.read_text(encoding="utf-8") == "NEW-DEST\n"
          and not _origin_co.exists()
          and _st_co == "complete" and bool(_got_co))

with _Env73() as _e_at:
    _ctx_at = sc.resolve_store(_e_at.proj)
    _dest_at = _ctx_at.native_memory_dir / "d-at.md"
    _dest_at.parent.mkdir(parents=True, exist_ok=True)
    _dest_at.write_text("OLD-AT\n", encoding="utf-8")
    _origin_at = _ctx_at.native_memory_dir / "o-at.md"
    _origin_at.write_text("ORIGIN-AT\n", encoding="utf-8")
    _h_origin_at = cp._file_hash(_origin_at)
    _crash_at = False
    try:
        cp.transact(
            _ctx_at, "after-trash-del", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_at), "NEW-AT\n") or {
                "deletes": [{"path": str(_origin_at), "preimage": _h_origin_at}],
                "expected_revisions": {str(_origin_at): _h_origin_at},
            }),
            crash_after="after_trash")
    except cp.CrashSimulated:
        _crash_at = True
    check("0.3.4: after_trash crash leaves dest unpublished and origin trashed",
          _crash_at and _dest_at.read_text(encoding="utf-8") == "OLD-AT\n"
          and not _origin_at.exists())
    _j_at = cp.connect_journal(_ctx_at)
    _r_at = cp.connect(cp.db_path(_ctx_at))
    _got_at = cp.recover_pending(_j_at, ctx=_ctx_at, registry_conn=_r_at)
    _st_at = _j_at.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_at.close(); _r_at.close()
    check("0.3.4: after_trash recover completes a delete+publish op",
          _dest_at.read_text(encoding="utf-8") == "NEW-AT\n"
          and not _origin_at.exists()
          and _st_at == "complete" and bool(_got_at))

with _Env73() as _e_nr:
    _ctx_nr = sc.resolve_store(_e_nr.proj)
    _j_nr = cp.connect_journal(_ctx_nr)
    _j_nr.executescript(cp.JOURNAL_ONLY_SQL)
    _payload_nr = {
        "origin_domain_id": _ctx_nr.domain_id,
        "origin_project_id": _ctx_nr.project_id,
        "publishes": [],
        "deletes": [],
        "registry_ops": [{"op": "migration_state_set", "value": "dual-read"}],
    }
    _oid_nr = cp.journal_insert(_j_nr, "domain-transition", _payload_nr, "prepare_temps")
    _before_nr = (cp.db_path(_ctx_nr)).read_bytes() if cp.db_path(_ctx_nr).exists() else b""
    _got_nr = cp.recover_pending(_j_nr)
    _st_nr = _j_nr.execute(
        "SELECT status FROM journal WHERE op_id=?", (_oid_nr,)).fetchone()["status"]
    _after_nr = (cp.db_path(_ctx_nr)).read_bytes() if cp.db_path(_ctx_nr).exists() else b""
    _j_nr.close()
    check("0.3.3: recover_pending without registry_conn does not complete registry_ops",
          _got_nr == [] and _st_nr == "pending" and _after_nr == _before_nr)
check("0.3.3: Probe Y / smoke recover pass ctx+registry_conn",
      "recover_pending(connY, ctx=ctxY, registry_conn=rconnY)" in
      (ROOT / "tests" / "simulate_accumulation.py").read_text(encoding="utf-8"))

with _Env73() as _e_pr:
    _ctx_pr = sc.resolve_store(_e_pr.proj)
    _dest_pr = _ctx_pr.native_memory_dir / "p.md"
    _dest_pr.parent.mkdir(parents=True, exist_ok=True)
    _dest_pr.write_text("KEEP\n", encoding="utf-8")
    _j_pr = cp.connect_journal(_ctx_pr)
    _j_pr.executescript(cp.JOURNAL_ONLY_SQL)
    _oid_pr = cp.journal_insert(
        _j_pr, "pull", {
            "origin_domain_id": _ctx_pr.domain_id,
            "origin_project_id": _ctx_pr.project_id,
            "publishes": [{"tmp": "/nope", "dest": str(_dest_pr),
                           "sha256": "ab" * 32, "mode": "replace"}],
            "sources": [{"path": str(_dest_pr), "sha256": ""}],
        }, "prepare_temps")
    _j_pr.close()
    _err_pr = _io73.StringIO()
    import control_plane as _cp_pr

    def _boom_rec(*_a, **_k):
        raise OSError("injected recover failure")

    _real_rec = _cp_pr.recover_pending
    setattr(_cp_pr, "recover_pending", _boom_rec)
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_err_pr):
            _rc_pr = sg.run(_e_pr.proj, pull=True)
    finally:
        setattr(_cp_pr, "recover_pending", _real_rec)
    check("0.3.3: pull recover OSError is rc≠0",
          bool(_rc_pr != 0 and "recover failed" in _err_pr.getvalue()
               and _dest_pr.read_text(encoding="utf-8") == "KEEP\n"))

with _Env73() as _e_ac:
    _ctx_ac = sc.resolve_store(_e_ac.proj)
    _dest_ac = _ctx_ac.canonical_domain_dir / "created.md"
    _dest_ac.parent.mkdir(parents=True, exist_ok=True)
    _old_cp = _osB.environ.get("CM_CRASH_PUBLISH")
    _osB.environ["CM_CRASH_PUBLISH"] = "after_link"
    _crash_ac = False
    try:
        cp.transact(
            _ctx_ac, "create-empty", {"stem": "created"},
            lambda _c, _t: (_t.__setitem__(str(_dest_ac), "NEW-CREATE\n") or {
                "dest_modes": {str(_dest_ac): "create"},
                "expected_revisions": {str(_dest_ac): cp.ABSENT},
            }),
            skip_recover=True)
    except cp.CrashSimulated:
        _crash_ac = True
    finally:
        if _old_cp is None:
            _osB.environ.pop("CM_CRASH_PUBLISH", None)
        else:
            _osB.environ["CM_CRASH_PUBLISH"] = _old_cp
    _tmps_ac = list(_dest_ac.parent.glob(_dest_ac.name + ".tmp-*"))
    check("0.3.4: after_link crash leaves full dest + tmp (no empty inode)",
          _crash_ac and _dest_ac.exists()
          and _dest_ac.read_text(encoding="utf-8") == "NEW-CREATE\n"
          and len(_tmps_ac) == 1
          and str(_osB.getpid()) not in _tmps_ac[0].name)
    _j_ac = cp.connect_journal(_ctx_ac)
    _r_ac = cp.connect(cp.db_path(_ctx_ac))
    _got_ac = cp.recover_pending(_j_ac, ctx=_ctx_ac, registry_conn=_r_ac)
    _st_ac = _j_ac.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_ac.close(); _r_ac.close()
    check("0.3.4: create after_link dest recovers",
          bool(_dest_ac.read_text(encoding="utf-8") == "NEW-CREATE\n"
               and list(_dest_ac.parent.glob(_dest_ac.name + ".tmp-*")) == []
               and _st_ac == "complete" and _got_ac))

with _Env73() as _e_tm:
    _ctx_tm = sc.resolve_store(_e_tm.proj)
    _dest_tm = _ctx_tm.native_memory_dir / "t.md"
    _dest_tm.parent.mkdir(parents=True, exist_ok=True)
    _crash_tm = False
    try:
        cp.transact(
            _ctx_tm, "tmp-mode", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_tm), "TMPBODY\n") or {"ok": True}),
            crash_after="prepare_temps")
    except cp.CrashSimulated:
        _crash_tm = True
    _tmps_tm = list(_dest_tm.parent.glob(_dest_tm.name + ".tmp-*"))
    _mode_tm = _tmps_tm[0].stat().st_mode & 0o777 if _tmps_tm else 0
    check("0.3.3: prepare_temps tmp is 0o600",
          _crash_tm and len(_tmps_tm) == 1 and _mode_tm == 0o600
          and ".tmp-op_" in _tmps_tm[0].name)

# ── 0.3.4: journal complete-old (trash, compensation, link create) ───────────
with _tf73.TemporaryDirectory() as _td_md:
    _a_md = Path(_td_md) / "a.md"
    _b_md = Path(_td_md) / "b.md"
    _a_md.write_text("A-BODY\n", encoding="utf-8")
    _b_md.write_text("B-BODY\n", encoding="utf-8")
    _ha_md = cp._file_hash(_a_md)
    _hb_md = cp._file_hash(_b_md)
    _blocked = Path(_td_md) / ".cm-trash-t35-1"
    _blocked.mkdir()
    _del_md = cp._apply_deletes(
        [{"path": str(_a_md), "preimage": _ha_md},
         {"path": str(_b_md), "preimage": _hb_md}],
        op_id="t35")
    check("0.3.4: multi-delete rolls back trash when a later rename fails",
          _a_md.read_text(encoding="utf-8") == "A-BODY\n"
          and _b_md.read_text(encoding="utf-8") == "B-BODY\n"
          and str(_b_md) in _del_md["errors"]
          and str(_a_md) not in _del_md["deleted"])

with _tf73.TemporaryDirectory() as _td_zb:
    _dest_zb = Path(_td_zb) / "empty.md"
    _dest_zb.write_bytes(b"")
    _tmp_zb = Path(_td_zb) / "empty.md.tmpx"
    _tmp_zb.write_text("NEW-CREATE\n", encoding="utf-8")
    _want_zb = __import__("hashlib").sha256(b"NEW-CREATE\n").hexdigest()
    _n_zb, _bad_zb = cp._publish_destinations([{
        "tmp": str(_tmp_zb), "dest": str(_dest_zb),
        "sha256": _want_zb, "mode": "create",
    }])
    check("0.3.4: create-mode does not unlink a legitimate empty dest",
          _n_zb == 0 and bool(_bad_zb)
          and _dest_zb.exists() and _dest_zb.stat().st_size == 0
          and _tmp_zb.exists())

with _Env73() as _e_ed:
    _ctx_ed = sc.resolve_store(_e_ed.proj)
    _dest_ed = _ctx_ed.native_memory_dir / "edit.md"
    _dest_ed.parent.mkdir(parents=True, exist_ok=True)
    _dest_ed.write_text("OLD-EDIT\n", encoding="utf-8")
    try:
        cp.transact(
            _ctx_ed, "dest-edit", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_ed), "NEW-EDIT\n") or {"ok": True}),
            crash_after="after_dests")
    except cp.CrashSimulated:
        pass
    _dest_ed.write_text("USER-EDIT\n", encoding="utf-8")
    _j_ed = cp.connect_journal(_ctx_ed)
    _r_ed = cp.connect(cp.db_path(_ctx_ed))
    _got_ed = cp.recover_pending(_j_ed, ctx=_ctx_ed, registry_conn=_r_ed)
    _st_ed = _j_ed.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_ed.close(); _r_ed.close()
    _q_ed = list((_ctx_ed.native_memory_dir / "quarantine").glob("edit.md.*")) \
        if (_ctx_ed.native_memory_dir / "quarantine").is_dir() else []
    check("0.3.4: dest edited after publish is quarantined, not overwritten",
          _st_ed == "failed" and _got_ed == []
          and _dest_ed.read_text(encoding="utf-8") == "OLD-EDIT\n"
          and len(_q_ed) == 1
          and "USER-EDIT" in _q_ed[0].read_text(encoding="utf-8"))

with _tf73.TemporaryDirectory() as _td_qf:
    _dest_qf = Path(_td_qf) / "edit.md"
    _dest_qf.write_text("USER-EDIT\n", encoding="utf-8")
    (Path(_td_qf) / "quarantine").write_text("not-a-dir\n", encoding="utf-8")
    _rec_qf = Path(_td_qf) / "rec"
    _rec_qf.mkdir()
    _orig_qf = b"OLD-EDIT\n"
    _blob_qf = _rec_qf / "dest-0.bin"
    _blob_qf.write_bytes(_orig_qf)
    _pub_qf = _hlA3.sha256(b"NEW-EDIT\n").hexdigest()
    _raised_qf = False
    try:
        cp._restore_dest_preimages([{
            "dest": str(_dest_qf),
            "sha256": _hlA3.sha256(_orig_qf).hexdigest(),
            "absent": False,
            "blob": str(_blob_qf),
            "published_sha256": _pub_qf,
            "mode": "replace",
        }])
    except sc.WriteRefused:
        _raised_qf = True
    check("0.3.4: dest restore refuses to clobber when quarantine cannot move the occupant",
          _raised_qf and _dest_qf.read_text(encoding="utf-8") == "USER-EDIT\n")

with _Env73() as _e_pc:
    _ctx_pc = sc.resolve_store(_e_pc.proj)
    _dest_pc = _ctx_pc.native_memory_dir / "postc.md"
    _dest_pc.parent.mkdir(parents=True, exist_ok=True)
    _dest_pc.write_text("OLD-POST\n", encoding="utf-8")
    _old_pc = _osB.environ.get("CM_FAIL_POSTCONDITION")
    _osB.environ["CM_FAIL_POSTCONDITION"] = "post"
    _raised_pc = False
    try:
        cp.transact(
            _ctx_pc, "post-fail", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_pc), "NEW-POST\n") or {"ok": True}),
            skip_recover=True)
    except sc.WriteRefused:
        _raised_pc = True
    finally:
        if _old_pc is None:
            _osB.environ.pop("CM_FAIL_POSTCONDITION", None)
        else:
            _osB.environ["CM_FAIL_POSTCONDITION"] = _old_pc
    _j_pc = cp.connect_journal(_ctx_pc)
    _st_pc = _j_pc.execute(
        "SELECT status, payload FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _j_pc.close()
    _pl_pc = __import__("json").loads(_st_pc["payload"] or "{}") if _st_pc else {}
    check("0.3.5: registry postcondition failure does not publish dests",
          _raised_pc and _st_pc is not None
          and str(_st_pc["status"] or "") == "conflicted"
          and _dest_pc.read_text(encoding="utf-8") == "OLD-POST\n"
          and "bytes_b64" not in _pl_pc
          and "text" not in _pl_pc
          and not any("bytes_b64" in (x or {}) for x in (_pl_pc.get("dest_preimages") or [])))

with _Env73() as _e_occ:
    _ctx_occ = sc.resolve_store(_e_occ.proj)
    _dest_occ = _ctx_occ.native_memory_dir / "d3.md"
    _dest_occ.parent.mkdir(parents=True, exist_ok=True)
    _dest_occ.write_text("OLD-D3\n", encoding="utf-8")
    _origin_occ = _ctx_occ.native_memory_dir / "o3.md"
    _origin_occ.write_text("ORIGIN3\n", encoding="utf-8")
    _h_occ = cp._file_hash(_origin_occ)
    try:
        cp.transact(
            _ctx_occ, "origin-occupy", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_occ), "NEW-D3\n") or {
                "deletes": [{"path": str(_origin_occ), "preimage": _h_occ}],
            }),
            crash_after="after_dests")
    except cp.CrashSimulated:
        pass
    _origin_occ.write_text("MUTATED-ORIGIN\n", encoding="utf-8")
    _j_occ = cp.connect_journal(_ctx_occ)
    _r_occ = cp.connect(cp.db_path(_ctx_occ))
    _got_occ = cp.recover_pending(_j_occ, ctx=_ctx_occ, registry_conn=_r_occ)
    _st_occ = _j_occ.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_occ.close(); _r_occ.close()
    _q_occ = list((_ctx_occ.native_memory_dir / "quarantine").glob("o3.md.*")) \
        if (_ctx_occ.native_memory_dir / "quarantine").is_dir() else []
    check("0.3.4: occupant at a trashed path is quarantined; original body restored",
          _st_occ == "failed" and _got_occ == []
          and _dest_occ.read_text(encoding="utf-8") == "OLD-D3\n"
          and _origin_occ.read_text(encoding="utf-8") == "ORIGIN3\n"
          and len(_q_occ) == 1
          and "MUTATED-ORIGIN" in _q_occ[0].read_text(encoding="utf-8"))
    _j_occ2 = cp.connect_journal(_ctx_occ)
    _r_occ2 = cp.connect(cp.db_path(_ctx_occ))
    _got_occ2 = cp.recover_pending(_j_occ2, ctx=_ctx_occ, registry_conn=_r_occ2)
    _st_occ2 = _j_occ2.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_occ2.close(); _r_occ2.close()
    check("0.3.4: recover of failed is a no-op",
          _st_occ2 == "failed" and _got_occ2 == [])

with _Env73() as _e_src:
    _ctx_src = sc.resolve_store(_e_src.proj)
    _dest_src = _ctx_src.native_memory_dir / "srcd.md"
    _dest_src.parent.mkdir(parents=True, exist_ok=True)
    _src_src = _ctx_src.native_memory_dir / "srcs.md"
    _src_src.write_text("SRC\n", encoding="utf-8")
    _h_src = cp._file_hash(_src_src)
    try:
        cp.transact(
            _ctx_src, "src-drift", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_src), "NEW-SRC\n") or {
                "expected_revisions": {str(_src_src): _h_src},
            }),
            crash_after="prepare_temps")
    except cp.CrashSimulated:
        pass
    _src_src.write_text("CHANGED-SRC\n", encoding="utf-8")
    _j_src = cp.connect_journal(_ctx_src)
    _r_src = cp.connect(cp.db_path(_ctx_src))
    _got_src = cp.recover_pending(_j_src, ctx=_ctx_src, registry_conn=_r_src)
    _st_src = _j_src.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_src.close(); _r_src.close()
    check("0.3.4: source drift during recover becomes conflicted, not silent pending",
          _got_src == [] and _st_src == "conflicted"
          and not _dest_src.exists())

with _tf73.TemporaryDirectory() as _td_cat35:
    _cat_dir35 = Path(_td_cat35)
    (_cat_dir35 / "live.md").write_text(
        _v3_canon("live", description="recall-hook",
                  body="status: expired\ndescription: BODY-HOOK\n"),
        encoding="utf-8")
    _cat_out35 = ci.generate_catalog(_cat_dir35)
    check("0.3.4: catalog ignores body-level status/description",
          "- [live](live.md) — recall-hook" in _cat_out35
          and "BODY-HOOK" not in _cat_out35
          and "expired" not in _cat_out35)

with _tf73.TemporaryDirectory() as _td_ack:
    _home_ack = Path(_td_ack) / "home"; _home_ack.mkdir()
    _a_ack = Path(_td_ack) / "projA"; _b_ack = Path(_td_ack) / "projB"
    _a_ack.mkdir(); _b_ack.mkdir()
    _oldH_ack = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_ack)
    try:
        _enroll_personal(_a_ack)
        _enroll_personal(_b_ack)
        _ctx_a_ack = sc.resolve_store(_a_ack)
        _body_ack = (
            "---\nname: shared-fg\ndescription: d\nmetadata:\n  node_type: memory\n"
            "  type: reference\n  scope: user-global\n---\nSHARED-FORGET-BODY\n")
        _up_ack = ci.upsert(_ctx_a_ack, "shared-fg", _body_ack)
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_ack1 = sg.run(_b_ack, pull=True)
        _mir_ack = sc.resolve_store(_b_ack).native_memory_dir / "shared-fg.md"
        _had_ack = bool(_mir_ack.is_file()
                       and "SHARED-FORGET-BODY" in _mir_ack.read_text(encoding="utf-8"))
        _fg_ack = ci.forget(_ctx_a_ack, "shared-fg")
        _still_ack = _mir_ack.is_file()
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_ack2 = sg.run(_b_ack, pull=True)
        check("0.3.4: forget in A then pull in B removes B's clean mirror",
              bool(_up_ack.get("ok") is True and _rc_ack1 == 0 and _had_ack
                   and _fg_ack.get("ok") is True and _still_ack
                   and _rc_ack2 == 0 and not _mir_ack.exists()))
    finally:
        if _oldH_ack is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_ack

# ── 0.3.3 Wave 3: migrate stage machine ──────────────────────────────────────
with _Env73() as _e_fin:
    _ctx_fin = sc.resolve_store(_e_fin.proj)
    _leg_fin = _ctx_fin.config_root / "memory"
    _leg_fin.mkdir(parents=True, exist_ok=True)
    (_leg_fin / "plain2.md").write_text(
        "---\nname: plain2\ndescription: d\nscope: user-global\n---\nbody\n", encoding="utf-8")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["migrate", str(_e_fin.proj)])
        cmo.main(["migrate", str(_e_fin.proj), "--assign", "plain2", "--domain", "personal"])
        _rc_fa = cmo.main(["migrate", str(_e_fin.proj), "--apply", "--confirm", "migrate-apply"])
        _rc_ff = cmo.main(["migrate", str(_e_fin.proj), "--finalize"])
        _err_fa2 = _io73.StringIO()
        with _ctx73.redirect_stderr(_err_fa2):
            _rc_fa2 = cmo.main(["migrate", str(_e_fin.proj), "--apply",
                                "--confirm", "migrate-apply"])
        _err_fr = _io73.StringIO()
        with _ctx73.redirect_stderr(_err_fr):
            _rc_fr = cmo.main(["migrate", str(_e_fin.proj), "--rollback",
                               "--confirm", "migrate-rollback"])
        _err_both = _io73.StringIO()
        with _ctx73.redirect_stderr(_err_both):
            _rc_both = cmo.main(["migrate", str(_e_fin.proj), "--apply", "--rollback",
                                 "--confirm", "migrate-apply"])
    _mode_fin = "dual-read"
    _mc_fin = cp.connect_if_exists(cp.db_path(_ctx_fin))
    if _mc_fin is not None:
        _mode_fin = cp.get_migration_mode(_mc_fin)
        _mc_fin.close()
    check("0.3.3: apply after finalize refused; mode stays enforced",
          _rc_fa == 0 and _rc_ff == 0 and _rc_fa2 == 2
          and _mode_fin == "enforced"
          and "finalized" in _err_fa2.getvalue())
    check("0.3.3: rollback after finalize refused",
          _rc_fr == 2 and "finalized" in _err_fr.getvalue())
    check("0.3.3: --apply and --rollback together refused",
          _rc_both == 2 and "only one" in _err_both.getvalue())

with _Env73() as _e_kp:
    _ctx_kp = sc.resolve_store(_e_kp.proj)
    _leg_kp = _ctx_kp.config_root / "memory"
    _unk_kp = _ctx_kp.config_root / "consolidate-memory" / "domains" / "unknown" / "facts"
    _leg_kp.mkdir(parents=True, exist_ok=True)
    _unk_kp.mkdir(parents=True, exist_ok=True)
    import shutil as _sh_kp
    _sh_kp.copy2(_fix021 / "legacy" / "dup.md", _leg_kp / "dup.md")
    _sh_kp.copy2(_fix021 / "unknown-pool" / "dup.md", _unk_kp / "dup.md")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["migrate", str(_e_kp.proj)])
        cmo.main(["migrate", str(_e_kp.proj), "--resolve-collision", "dup",
                  "--keep", "unknown-pool"])
        cmo.main(["migrate", str(_e_kp.proj)])  # inventory refresh must not clobber keep
        cmo.main(["migrate", str(_e_kp.proj), "--assign", "dup", "--domain", "personal"])
        _rc_kp = cmo.main(["migrate", str(_e_kp.proj), "--apply",
                           "--confirm", "migrate-apply"])
    _dup_kp = (_ctx_kp.canonical_domain_dir / "dup.md").read_text(encoding="utf-8")
    check("0.3.3: --keep unknown-pool apply copies unknown-pool body",
          _rc_kp == 0 and "UNKNOWN-POOL copy" in _dup_kp
          and "LEGACY copy" not in _dup_kp)

with _Env73() as _e_tb:
    _ctx_tb = sc.resolve_store(_e_tb.proj)
    _conn_tb = cp.connect(cp.db_path(_ctx_tb))
    cp.write_tombstone(_conn_tb, cp.stable_fact_id("personal", "tom"),
                       "tom", "personal", "user-forget")
    _conn_tb.commit(); _conn_tb.close()
    _leg_tb = _ctx_tb.config_root / "memory"
    _leg_tb.mkdir(parents=True, exist_ok=True)
    (_leg_tb / "tom.md").write_text(
        "---\nname: tom\ndescription: d\nscope: user-global\n---\nRESURRECT?\n",
        encoding="utf-8")
    _err_tb = _io73.StringIO()
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_err_tb):
        cmo.main(["migrate", str(_e_tb.proj)])
        cmo.main(["migrate", str(_e_tb.proj), "--assign", "tom", "--domain", "personal"])
        _rc_tb = cmo.main(["migrate", str(_e_tb.proj), "--apply",
                           "--confirm", "migrate-apply"])
    check("0.3.3: migrate apply refuses a tombstoned dest stem",
          _rc_tb == 2 and "tombstoned" in _err_tb.getvalue())

with _Env73() as _e_rs:
    _ctx_rs = sc.resolve_store(_e_rs.proj)
    _fid_rs = cp.stable_fact_id("personal", "tom2")
    _conn_rs = cp.connect(cp.db_path(_ctx_rs))
    cp.write_tombstone(_conn_rs, _fid_rs, "tom2", "personal", "user-forget")
    _conn_rs.commit(); _conn_rs.close()
    _leg_rs = _ctx_rs.config_root / "memory"
    _leg_rs.mkdir(parents=True, exist_ok=True)
    (_leg_rs / "tom2.md").write_text(
        "---\nname: tom2\ndescription: d\nscope: user-global\n---\nRESURRECTED\n",
        encoding="utf-8")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["migrate", str(_e_rs.proj)])
        cmo.main(["migrate", str(_e_rs.proj), "--assign", "tom2", "--domain", "personal"])
        _rc_rs = cmo.main(["migrate", str(_e_rs.proj), "--apply", "--resurrect",
                           "--confirm", "migrate-apply"])
    _conn_rs2 = cp.connect(cp.db_path(_ctx_rs))
    _tom_row = _conn_rs2.execute(
        "SELECT 1 FROM tombstones WHERE fact_id=?", (_fid_rs,)).fetchone()
    _conn_rs2.close()
    check("0.3.4: --resurrect deletes the tombstone in the same apply transaction",
          _rc_rs == 0 and _tom_row is None
          and "RESURRECTED" in (_ctx_rs.canonical_domain_dir / "tom2.md").read_text(
              encoding="utf-8"))

with _Env73() as _e_md:
    _ctx_md = sc.resolve_store(_e_md.proj)
    _leg_md = _ctx_md.config_root / "memory"
    _leg_md.mkdir(parents=True, exist_ok=True)
    (_leg_md / "gone.md").write_text(
        "---\nname: gone\ndescription: d\nscope: user-global\n---\nG\n", encoding="utf-8")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["migrate", str(_e_md.proj)])
        cmo.main(["migrate", str(_e_md.proj), "--assign", "gone", "--domain", "personal"])
        _rc_mda = cmo.main(["migrate", str(_e_md.proj), "--apply",
                            "--confirm", "migrate-apply"])
    _gone_dest = _ctx_md.canonical_domain_dir / "gone.md"
    _gone_dest.unlink()
    _err_mdf = _io73.StringIO()
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_err_mdf):
        _rc_mdf = cmo.main(["migrate", str(_e_md.proj), "--finalize"])
    _mc_md = cp.connect_if_exists(cp.db_path(_ctx_md))
    _mode_md = cp.get_migration_mode(_mc_md) if _mc_md is not None else "dual-read"
    if _mc_md is not None:
        _mc_md.close()
    check("0.3.3: finalize missing dest rc=2",
          _rc_mda == 0 and _rc_mdf == 2 and _mode_md != "enforced"
          and "missing dest" in _err_mdf.getvalue())

# ── 0.3.3 Wave 4: StoreContext / schema / GC ─────────────────────────────────
import subprocess as _sp_gd
with _tf73.TemporaryDirectory() as _td_gd:
    _A = Path(_td_gd) / "projA"; _B = Path(_td_gd) / "projB"
    _A.mkdir(); _B.mkdir()
    _sp_gd.run(["git", "init"], cwd=str(_B), check=True, capture_output=True)
    _nested = _A / "nested"; _nested.mkdir()
    (_nested / ".git").write_text("gitdir: " + str((_B / ".git").resolve()) + "\n",
                                  encoding="utf-8")
    _oldH_gd = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(Path(_td_gd) / "home")
    Path(_osB.environ["HOME"]).mkdir()
    try:
        _ctxA_gd = sc.resolve_store(_nested)
        _ctxB_gd = sc.resolve_store(_B)
        check("0.3.3: gitdir: escape does not steal victim native store",
              str(_ctxA_gd.native_memory_dir) != str(_ctxB_gd.native_memory_dir)
              and _ctxA_gd.git_common_dir != _ctxB_gd.git_common_dir)
    finally:
        if _oldH_gd is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_gd

with _tf73.TemporaryDirectory() as _td_sm:
    _super = Path(_td_sm) / "super"; _sub = _super / "lib"
    _super.mkdir(); _sub.mkdir()
    _sp_gd.run(["git", "init"], cwd=str(_super), check=True, capture_output=True)
    _mod = _super / ".git" / "modules" / "lib"
    _mod.mkdir(parents=True)
    (_sub / ".git").write_text("gitdir: " + str(_mod.resolve()) + "\n", encoding="utf-8")
    _oldH_sm = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(Path(_td_sm) / "home")
    Path(_osB.environ["HOME"]).mkdir()
    try:
        _ctx_sub = sc.resolve_store(_sub)
        _ctx_sup = sc.resolve_store(_super)
        check("0.3.3: submodule gitfile native is the working tree",
              _ctx_sub.native_memory_dir != _ctx_sup.native_memory_dir
              and ms.slug_for(_sub) in str(_ctx_sub.native_memory_dir))
    finally:
        if _oldH_sm is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_sm

with _tf73.TemporaryDirectory() as _td_wtatk:
    _victim = Path(_td_wtatk) / "victim"; _attacker = Path(_td_wtatk) / "attacker"
    _victim.mkdir(); _attacker.mkdir()
    _sp_gd.run(["git", "init"], cwd=str(_victim), check=True, capture_output=True)
    _sp_gd.run(["git", "config", "user.email", "you@example.com"], cwd=str(_victim),
               check=True, capture_output=True)
    _sp_gd.run(["git", "config", "user.name", "you"], cwd=str(_victim),
               check=True, capture_output=True)
    (_victim / "f.txt").write_text("v\n", encoding="utf-8")
    _sp_gd.run(["git", "add", "-A"], cwd=str(_victim), check=True, capture_output=True)
    _sp_gd.run(["git", "commit", "-m", "i"], cwd=str(_victim), check=True, capture_output=True)
    _vwt = Path(_td_wtatk) / "victim-wt"
    _sp_gd.run(["git", "worktree", "add", str(_vwt), "HEAD"], cwd=str(_victim),
               check=True, capture_output=True)
    _wtdirs = list((_victim / ".git" / "worktrees").iterdir())
    _wt_admin = _wtdirs[0] if _wtdirs else None
    if _wt_admin is not None:
        (_attacker / ".git").write_text(
            "gitdir: " + str(_wt_admin.resolve()) + "\n", encoding="utf-8")
    _oldH_wa = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(Path(_td_wtatk) / "home")
    Path(_osB.environ["HOME"]).mkdir()
    try:
        _ctx_att = sc.resolve_store(_attacker)
        _ctx_vic = sc.resolve_store(_victim)
        check("0.3.4: crafted gitfile pointing at a victim worktree admin dir does not steal identity",
              _wt_admin is not None
              and str(_ctx_att.native_memory_dir) != str(_ctx_vic.native_memory_dir)
              and _ctx_att.git_common_dir != _ctx_vic.git_common_dir)
    finally:
        if _oldH_wa is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_wa

with _tf73.TemporaryDirectory() as _td_gsl:
    _vic_sl = Path(_td_gsl) / "victim"; _att_sl = Path(_td_gsl) / "attacker"
    _vic_sl.mkdir(); _att_sl.mkdir()
    _sp_gd.run(["git", "init"], cwd=str(_vic_sl), check=True, capture_output=True)
    _osB.symlink(str((_vic_sl / ".git").resolve()), str(_att_sl / ".git"))
    _oldH_sl = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(Path(_td_gsl) / "home")
    Path(_osB.environ["HOME"]).mkdir()
    try:
        _ctx_asl = sc.resolve_store(_att_sl)
        _ctx_vsl = sc.resolve_store(_vic_sl)
        check("0.3.4: symlinked .git directory does not inherit victim identity",
              str(_ctx_asl.native_memory_dir) != str(_ctx_vsl.native_memory_dir)
              and _ctx_asl.git_common_dir != _ctx_vsl.git_common_dir)
    finally:
        if _oldH_sl is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_sl

with _tf73.TemporaryDirectory() as _td_xmem:
    _home_xm = Path(_td_xmem) / "home"; _home_xm.mkdir()
    _proj_xm = Path(_td_xmem) / "proj"; _proj_xm.mkdir()
    _vic_xm = Path(_td_xmem) / "victim"; _vic_xm.mkdir()
    _oldH_xm = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_xm)
    try:
        _ctx_vic_xm = sc.resolve_store(_vic_xm)
        _stolen = _ctx_vic_xm.config_root / "projects" / ms.slug_for(_vic_xm) / "memory"
        _stolen.mkdir(parents=True)
        (_stolen / "MEMORY.md").write_text("# victim store\n", encoding="utf-8")
        (_proj_xm / ".claude").mkdir()
        (_proj_xm / ".claude" / "settings.json").write_text(
            _json_xp.dumps({"autoMemoryDirectory": str(_stolen)}), encoding="utf-8")
        _ctx_xm = sc.resolve_store(_proj_xm)
        check("0.3.4: project autoMemoryDirectory cannot select another project's native store",
              _ctx_xm.write_allowed is False
              and _ctx_xm.native_memory_dir != _stolen
              and any("escapes" in a for a in _ctx_xm.ambiguity))
    finally:
        if _oldH_xm is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_xm

with _Env73() as _e_am:
    _ctx_am = sc.resolve_store(_e_am.proj)
    _def_am = _ctx_am.config_root / "projects" / ms.slug_for(_e_am.proj) / "memory"
    _def_am.mkdir(parents=True, exist_ok=True)
    (_def_am / "MEMORY.md").write_text("# live default\n", encoding="utf-8")
    _empty_am = Path(_e_am._td.name) / "empty-mem"
    _empty_am.mkdir()
    _set_am = _e_am.proj / ".claude"
    _set_am.mkdir(parents=True, exist_ok=True)
    (_set_am / "settings.json").write_text(
        _json_xp.dumps({"autoMemoryDirectory": str(_empty_am)}), encoding="utf-8")
    _ctx_am2 = sc.resolve_store(_e_am.proj)
    _doc_am = sc.doctor_report(_ctx_am2)
    check("0.3.3: empty autoMemoryDirectory vs live default is disagreement",
          _ctx_am2.write_allowed is False
          and str(_empty_am) in _doc_am
          and str(_def_am) in _doc_am)

with _tf73.TemporaryDirectory() as _td_rm:
    _home_rm = Path(_td_rm) / "home"; _home_rm.mkdir()
    _proj_rm = Path(_td_rm) / "repo"; _proj_rm.mkdir()
    _sp_gd.run(["git", "init"], cwd=str(_proj_rm), check=True, capture_output=True)
    _oldH_rm = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_rm)
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            _rc_en_rm = cmo.main(["project", "enroll", str(_proj_rm), "--domain", "personal",
                                  "--apply", "--confirm", "enroll-personal"])
        _ctx_rm1 = sc.resolve_store(_proj_rm)
        _pid1 = _ctx_rm1.project_id
        _sp_gd.run(["git", "remote", "add", "origin", "https://example.com/r.git"],
                   cwd=str(_proj_rm), check=True, capture_output=True)
        _ctx_rm2 = sc.resolve_store(_proj_rm)
        _conn_rm = cp.connect(cp.db_path(_ctx_rm2))
        _n_rm = _conn_rm.execute("SELECT count(*) AS n FROM projects WHERE status='enrolled'"
                                 ).fetchone()["n"]
        _conn_rm.close()
        check("0.3.3: git remote add origin keeps enrolled project_id",
              _rc_en_rm == 0 and _ctx_rm2.enrolled is True
              and _ctx_rm2.domain_id == "personal"
              and _ctx_rm2.project_id == _pid1 and int(_n_rm) == 1)
    finally:
        if _oldH_rm is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_rm

_fm_applies = {
    "schema_version": "3", "fact_id": "f_" + "ab" * 12, "name": "nest",
    "description": "d", "domain": "personal", "sensitivity": "internal",
    "scope": "user-global", "status": "active",
    "applies": "", "applies.any": "[python]",
    "applies_any": "[]", "applies_all": "[]", "applies_exclude": "[]",
    "content_modified": "2026-09-01T00:00:00Z",
    "last_observed_at": "2026-09-01T00:00:00Z",
}
check("0.3.3: nested applies: mapping refused",
      _vcf(_fm_applies, stem="nest", domain="personal") is not None)

with _Env73() as _e_gc3:
    _ctx_gc3 = sc.resolve_store(_e_gc3.proj)
    _enroll_personal(_e_gc3.proj)
    _ctx_gc3 = sc.resolve_store(_e_gc3.proj)
    _bad_gc3 = (
        "---\nschema_version: 3\nname: bad-v3\ndescription: d\n"
        "domain: personal\nscope: user-global\n---\nbody\n"
    )
    _ctx_gc3.canonical_domain_dir.mkdir(parents=True, exist_ok=True)
    (_ctx_gc3.canonical_domain_dir / "bad-v3.md").write_text(_bad_gc3, encoding="utf-8")
    _mir_gc3 = sg._as_mirror(_bad_gc3, "bad-v3")
    (_e_gc3.store / "bad-v3.md").write_text(_mir_gc3, encoding="utf-8")
    _rc_g3, _o_g3, _e_g3 = _run73(_e_gc3.proj)
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_gc3 = sg.gc(_e_gc3.proj, apply=True)
    check("0.3.3: invalid v3 canonical is not GC-orphaned",
          _rc_g3 == 0 and not (_e_gc3.store / "bad-v3.md").read_text(encoding="utf-8") == ""
          and (_e_gc3.store / "bad-v3.md").exists()
          and _rc_gc3 == 0)

# ── 0.3.3 Wave 5: STALE / harvest / export ───────────────────────────────────
with _Env73() as _e_st:
    _canon_st = (
        "---\nname: stale-x\ndescription: new hook\ndomain: personal\n"
        "metadata:\n  scope: user-global\n  type: feedback\n---\nNEW BODY\n"
    )
    (_e_st.glob / "stale-x.md").write_text(_canon_st, encoding="utf-8")
    _ctx_st = sc.resolve_store(_e_st.proj)
    _ctx_st.canonical_domain_dir.mkdir(parents=True, exist_ok=True)
    (_ctx_st.canonical_domain_dir / "stale-x.md").write_text(_canon_st, encoding="utf-8")
    _old_st = sg._as_mirror(
        _canon_st.replace("NEW BODY", "OLD BODY").replace("new hook", "old hook"),
        "stale-x", since="2026-01-01T00:00:00Z",
        body_hash=sg._body_hash(_canon_st.replace("NEW BODY", "OLD BODY")))
    (_e_st.store / "stale-x.md").write_text(_old_st, encoding="utf-8")
    (_e_st.store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")
    import control_plane as _cp_st
    _real_tx = _cp_st.transact

    def _wrap_tx(*_a, **_k):
        (_e_st.store / "stale-x.md").write_text(
            "---\nname: stale-x\ndescription: local\nmetadata:\n  type: reference\n"
            "---\nLOCAL AUTHOR\n", encoding="utf-8")
        return _real_tx(*_a, **_k)

    setattr(_cp_st, "transact", _wrap_tx)
    try:
        _rc_st, _o_st, _e_stout = _run73(_e_st.proj)
    finally:
        setattr(_cp_st, "transact", _real_tx)
    check("0.3.3: STALE does not clobber a non-mirror",
          "LOCAL AUTHOR" in (_e_st.store / "stale-x.md").read_text(encoding="utf-8")
          and "global_ref:" not in (_e_st.store / "stale-x.md").read_text(encoding="utf-8"))

with _Env73() as _e_ut:
    _pB_ut = Path(_e_ut._td.name) / "src" / "otherB"
    _pB_ut.mkdir(parents=True)
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        cmo.main(["project", "enroll", str(_pB_ut), "--domain", "work",
                  "--apply", "--confirm", "enroll-work"])
    _ctxB_ut = sc.resolve_store(_pB_ut)
    _ctxB_ut.canonical_domain_dir.mkdir(parents=True, exist_ok=True)
    (_ctxB_ut.canonical_domain_dir / "dupstem.md").write_text(
        "---\nname: dupstem\ndescription: d\ndomain: work\nmetadata:\n"
        "  scope: user-global\n  type: feedback\n---\nW\n", encoding="utf-8")
    _natB = _ctxB_ut.native_memory_dir
    _natB.mkdir(parents=True, exist_ok=True)
    (_natB / "dupstem.md").write_text(
        sg._as_mirror((_ctxB_ut.canonical_domain_dir / "dupstem.md").read_text(encoding="utf-8"),
                      "dupstem"), encoding="utf-8")
    _row_ut = sg._stamp_harvest_identity(
        {"node": _natB.parent.name,
         "window": "2026-01-01T00:00:00Z..2026-01-02T00:00:00Z",
         "transcripts": 1, "reads": 4, "facts_read": 1,
         "per_fact": [{"name": "dupstem", "reads": 4, "last": "2026-01-01T00:00:00Z"}]},
        "personal")
    sg._append_ledger(_row_ut)
    _utilB = sg.fleet_utility(_pB_ut)
    _entryB = next((e for e in _utilB.get("canonicals") or []
                    if e.get("name") == "dupstem"), None)
    _readsB = 0
    if _entryB:
        _readsB = int(_entryB.get("reads") or 0) + int(_entryB.get("harvested_reads") or 0)
    check("0.3.3: utility does not attribute cross-domain same-stem harvest",
          _readsB == 0)

with _Env73() as _e_ex2:
    _pdata_ex2 = sc.resolve_store(_e_ex2.proj).plugin_data_dir
    _pdata_ex2.mkdir(parents=True, exist_ok=True)
    (_pdata_ex2 / "note.json").write_text("{}\n", encoding="utf-8")
    _ex2 = ret.export_ops(_pdata_ex2, _pdata_ex2 / "bundle.tar.gz")
    import tarfile as _tar_ex2, hashlib as _hl_ex2, json as _js_ex2
    _man_ex2 = _js_ex2.loads(Path(_ex2["manifest"]).read_text(encoding="utf-8"))
    _want_ex2 = {f["path"]: f["sha256"] for f in _man_ex2["files"]}
    _ok_ex2 = True
    with _tar_ex2.open(_ex2["path"]) as _t2:
        for _m2 in _t2.getmembers():
            if not _m2.name.startswith("plugin-data/") or _m2.isdir():
                continue
            _rel2 = _m2.name[len("plugin-data/"):]
            _fh2 = _t2.extractfile(_m2)
            if _fh2 is None:
                _ok_ex2 = False
                continue
            _raw2 = _fh2.read()
            if _hl_ex2.sha256(_raw2).hexdigest() != _want_ex2.get(_rel2):
                _ok_ex2 = False
    check("0.3.3: export tar member sha256 == manifest",
          bool(_ex2.get("ok") is True and _ok_ex2 and _want_ex2))

# ── 0.3.3 Wave 6: dashboard / SKILL honesty ──────────────────────────────────
_tpl033 = (ROOT / "plugins" / "consolidate-memory" / "scripts"
           / "dashboard.template.html").read_text(encoding="utf-8")
check("0.3.3: HTML does not label unverifiable as dropped",
      "+unv+' dropped'" not in _tpl033 and "0 dropped" not in _tpl033
      and "unverifiable" in _tpl033)
check("0.3.3: HTML does not label demotion eligible as unused",
      '+" unused"' not in _tpl033 and " eligible" in _tpl033)
check("0.3.3: prettyNode does not hard-code home-drei",
      "home-drei" not in _tpl033)
check("0.3.3: HTML git_range -N becomes recent N (no marker)",
      "recent " in _tpl033 and "(no marker)" in _tpl033)
check("0.3.3: HTML rigor derives suggested_tier when applied is empty",
      "session_candidates" in _tpl033 and 'applied==="HEAVY"' in _tpl033)
_idx_meter033 = _tpl033.find('meter(el("m-index")')
check("0.3.3: HTML index meter uses cycle budget_tokens",
      _idx_meter033 != -1 and "idxbM" in _tpl033[_idx_meter033 - 80:_idx_meter033 + 160]
      and 'g(CUR,"budget.index.budget_tokens")' in _tpl033)
check("0.3.3: HTML caption gates on verification tally",
      "(conf+corr+unv)>0" in _tpl033 and "Every recorded claim is checked" in _tpl033)
check("0.3.3: HTML over-budget unindexed is not schema drift",
      "index_mismatch) && !overIdx" in _tpl033)
check("0.3.3: HTML dream identOf does not fall back to live",
      "identOf(CUR,false)" in _tpl033)
check("0.3.3: HTML local-only when cross_project_allowed is false",
      "!id.cross_project_allowed" in _tpl033)

_yaml_applies = (
    "---\nschema_version: 3\nfact_id: f_" + "ab" * 12 + "\nname: nest2\n"
    "description: d\ndomain: personal\nsensitivity: internal\nscope: user-global\n"
    "status: active\napplies:\n  any: [python]\napplies_any: []\napplies_all: []\n"
    "applies_exclude: []\ncontent_modified: 2026-09-01T00:00:00Z\n"
    "last_observed_at: 2026-09-01T00:00:00Z\n---\nbody\n"
)
_fm_yaml_ap = ms._frontmatter(_yaml_applies)
check("0.3.3: nested applies YAML through _frontmatter is refused",
      "applies" in _fm_yaml_ap
      and _vcf(_fm_yaml_ap, stem="nest2", domain="personal") is not None)

with _Env73() as _e_fail:
    _ctx_fail = sc.resolve_store(_e_fail.proj)
    _dest_fail = _ctx_fail.native_memory_dir / "d2.md"
    _dest_fail.parent.mkdir(parents=True, exist_ok=True)
    _dest_fail.write_text("OLD-DEST\n", encoding="utf-8")
    _origin_fail = _ctx_fail.native_memory_dir / "o2.md"
    _origin_fail.write_text("ORIGIN\n", encoding="utf-8")
    _h_origin_fail = cp._file_hash(_origin_fail)
    try:
        cp.transact(
            _ctx_fail, "complete-old-2", {"k": 1},
            lambda _c, _t: (_t.__setitem__(str(_dest_fail), "NEW-DEST\n") or {
                "deletes": [{"path": str(_origin_fail), "preimage": _h_origin_fail}],
            }),
            crash_after="after_dests")
    except cp.CrashSimulated:
        pass
    _j_fail = cp.connect_journal(_ctx_fail)
    _r_fail = cp.connect(cp.db_path(_ctx_fail))
    cp.recover_pending(_j_fail, ctx=_ctx_fail, registry_conn=_r_fail)
    _st_fail1 = _j_fail.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _got_fail2 = cp.recover_pending(_j_fail, ctx=_ctx_fail, registry_conn=_r_fail)
    _st_fail2 = _j_fail.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()["status"]
    _j_fail.close(); _r_fail.close()
    check("0.3.4: recover of a completed after_dests op is a no-op on retry",
          _st_fail1 == "complete" and _st_fail2 == "complete" and _got_fail2 == []
          and _dest_fail.read_text(encoding="utf-8") == "NEW-DEST\n"
          and not _origin_fail.exists())

with _tf73.TemporaryDirectory() as _td_cp:
    _h_cp = Path(_td_cp)
    _p_cp = (_h_cp / "src" / "proj").resolve(); _p_cp.mkdir(parents=True)
    _oldH_cp, _oldG_cp = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h_cp)
    sg.GLOBAL = _h_cp / ".claude" / "memory"
    sg.GLOBAL.mkdir(parents=True)
    try:
        _enroll_personal(_p_cp)
        _ctx_cp = sc.resolve_store(_p_cp)
        (sg.GLOBAL / "pwn.md").write_text(
            "---\nname: pwn\ndescription: d\ndomain: personal\nmetadata:\n"
            "  scope: user-global\n  type: feedback\n---\nPWN-BODY\n", encoding="utf-8")
        _got_cp = sg._canonical_path(_ctx_cp, "pwn")
        check("0.3.3: leftover GLOBAL is not a production canonical lookup",
              not _got_cp.exists()
              and _got_cp == _ctx_cp.canonical_domain_dir / "pwn.md"
              and (sg.GLOBAL / "pwn.md").is_file())
        _look_cp = cmo._lookup_canonical_text(_ctx_cp, {"domain": "personal"}, "pwn.md")
        check("0.3.3: enroll lookup does not read leftover ~/.claude/memory",
              _look_cp is None)
    finally:
        sg.GLOBAL = _oldG_cp
        if _oldH_cp is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_cp

with _tf73.TemporaryDirectory() as _td_esc:
    _home_esc = Path(_td_esc) / "home"; _home_esc.mkdir()
    _proj_esc = Path(_td_esc) / "victim"; _proj_esc.mkdir()
    _other_esc = Path(_td_esc) / "other-store"; _other_esc.mkdir()
    (_other_esc / "MEMORY.md").write_text("# stolen\n", encoding="utf-8")
    (_proj_esc / ".claude").mkdir()
    (_proj_esc / ".claude" / "settings.json").write_text(
        _json_xp.dumps({"autoMemoryDirectory": str(_other_esc)}), encoding="utf-8")
    _oldH_esc = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_esc)
    try:
        _ctx_esc = sc.resolve_store(_proj_esc)
        check("0.3.3: project autoMemoryDirectory escape is not native",
              _ctx_esc.write_allowed is False
              and _ctx_esc.native_memory_dir != _other_esc
              and any("escapes" in a for a in _ctx_esc.ambiguity))
    finally:
        if _oldH_esc is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_esc

with _tf73.TemporaryDirectory() as _td_ed:
    _home_ed = Path(_td_ed) / "home"; _home_ed.mkdir()
    _st_ed = _home_ed / ".claude" / "projects" / "edgeholder" / "memory"
    _st_ed.mkdir(parents=True)
    _body_ed = (
        "---\nname: dupstem\ndescription: d\ndomain: work\n"
        "metadata:\n  scope: user-global\n  type: feedback\n---\nW\n"
    )
    (_st_ed / "dupstem.md").write_text(sg._as_mirror(_body_ed, "dupstem"), encoding="utf-8")
    _oldH_ed = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_ed)
    try:
        check("0.3.3: gc-edges liveness is domain-scoped",
              sg._classify_edge("edgeholder", "dupstem", "personal") != "live"
              and sg._classify_edge("edgeholder", "dupstem", "work") == "live")
    finally:
        if _oldH_ed is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_ed

# ── 0.3.4: one enumerator, no shadow GLOBAL ─────────────────────────────────
_banned034 = ("def global_facts", "def _canonical_dirs", "def _ensure_index_pointer",
              "def _record_provenance")
_hits034 = []
for _p034 in (ROOT / "plugins" / "consolidate-memory" / "scripts").glob("*.py"):
    _t034 = _p034.read_text(encoding="utf-8")
    for _b034 in _banned034:
        if _b034 in _t034:
            _hits034.append(f"{_p034.name}:{_b034}")
check("0.3.4: scripts/ has no global_facts/_canonical_dirs/_ensure_index_pointer/_record_provenance",
      not _hits034)
check("0.3.4: session_beacon does not import global_facts",
      "global_facts" not in (ROOT / "plugins" / "consolidate-memory" / "scripts"
                             / "session_beacon.py").read_text(encoding="utf-8"))

with _tf73.TemporaryDirectory() as _td_b34:
    _h34 = Path(_td_b34)
    _p34 = (_h34 / "src" / "proj").resolve(); _p34.mkdir(parents=True)
    _oldH34, _oldG34 = _osB.environ.get("HOME"), sg.GLOBAL
    _osB.environ["HOME"] = str(_h34)
    sg.GLOBAL = _h34 / ".claude" / "memory"
    sg.GLOBAL.mkdir(parents=True)
    try:
        _enroll_personal(_p34)
        _ctx34 = sc.resolve_store(_p34)
        (sg.GLOBAL / "pwn.md").write_text(
            "---\nname: pwn\ndescription: d\ndomain: personal\nmetadata:\n"
            "  scope: user-global\n  type: feedback\n---\nPWN\n", encoding="utf-8")
        import session_beacon as _sb34
        _line34 = _sb34.beacon_line(_ctx34.native_memory_dir, domain_id="personal")
        check("0.3.4: beacon_line does not default to leftover GLOBAL",
              _line34 == "")
        _unenr = sc.resolve_store(_p34)
        # fresh project without enroll: use a sibling
        _p34b = (_h34 / "src" / "other").resolve(); _p34b.mkdir(parents=True)
        _ctx_u = sc.resolve_store(_p34b)
        check("0.3.4: unenrolled facts_for_context is empty (no hermetic global_facts)",
              sg.facts_for_context(_ctx_u) == []
              and _ctx_u.cross_project_allowed is False)
        _buf_n = _io73.StringIO()
        with _ctx73.redirect_stdout(_buf_n), _ctx73.redirect_stderr(_io73.StringIO()):
            sg.network(_p34, all_domains=True)
        check("0.3.4: --network --all-domains does not list leftover ~/.claude/memory",
              "pwn" not in _buf_n.getvalue())
        _orph34 = sg._orphans(_ctx34.native_memory_dir)
        check("0.3.4: _orphans without canon does not scan GLOBAL",
              _orph34 == [])
        _led34 = sg.GLOBAL / ".fleet-usage.jsonl"
        _led34.write_text(_json_xp.dumps({
            "node": "x", "window": "a..b", "reads": 9, "facts_read": 1,
            "per_fact": [{"name": "pwn", "reads": 9}],
        }) + "\n", encoding="utf-8")
        _rows34 = sg._ledger_rows()
        check("0.3.4: harvest ignores leftover GLOBAL .fleet-usage.jsonl when plugin-data empty",
              _rows34 == [])
        import canonical_ingress as _ci34
        _err_pc = _ci34.upsert(_ctx34, "pwn",
                               (sg.GLOBAL / "pwn.md").read_text(encoding="utf-8"),
                               preserve_canonical=True)
        check("0.3.4: preserve_canonical does not read leftover GLOBAL",
              _err_pc.get("ok") is False
              and "missing" in str(_err_pc.get("error") or "").lower())
    finally:
        sg.GLOBAL = _oldG34
        if _oldH34 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH34

with _Env73() as _e_j34:
    _ctx_j = sc.resolve_store(_e_j34.proj)
    _dest_j = _ctx_j.native_memory_dir / "j.md"
    _dest_j.parent.mkdir(parents=True, exist_ok=True)
    cp.transact(
        _ctx_j, "pull", {"k": 1},
        lambda _c, _t: (_t.__setitem__(str(_dest_j), "J\n") or {
            "holders": [("f_ab" + "cd" * 11, _ctx_j.project_id, "r", "r", "r")],
            "registry_ops": [],
        }))
    _jc = cp.connect_journal(_ctx_j)
    _rowj = _jc.execute("SELECT payload FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _jc.close()
    _pj = _json_xp.loads(_rowj["payload"])
    check("0.3.4: new journal payload has registry_ops not holders tuples",
          list(_pj.get("holders") or []) == []
          and "registry_ops" in _pj)

# ── remaining P0 gaps (0.3.5) ────────────────────────────────────────────────
with _tf73.TemporaryDirectory() as _td_sm2:
    _vic2 = Path(_td_sm2) / "victim"
    _vic2.mkdir()
    _sp_gd.run(["git", "init"], cwd=str(_vic2), check=True, capture_output=True)
    _mod2 = _vic2 / ".git" / "modules" / "lib"
    _mod2.mkdir(parents=True)
    (_mod2 / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    _nested2 = _vic2 / "docs" / "evil"
    _nested2.mkdir(parents=True)
    (_nested2 / ".git").write_text("gitdir: " + str(_mod2.resolve()) + "\n", encoding="utf-8")
    _sib2 = Path(_td_sm2) / "attacker"
    _sib2.mkdir()
    (_sib2 / ".git").write_text("gitdir: " + str(_mod2.resolve()) + "\n", encoding="utf-8")
    _oldH_sm2 = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(Path(_td_sm2) / "home")
    Path(_osB.environ["HOME"]).mkdir()
    try:
        _ctx_n2 = sc.resolve_store(_nested2)
        _ctx_s2 = sc.resolve_store(_sib2)
        _ctx_v2 = sc.resolve_store(_vic2)
        check("0.3.5: nested crafted gitfile does not adopt victim submodule gitdir",
              _ctx_n2.git_common_dir != _mod2.resolve()
              and (_ctx_n2.git_common_dir is None
                   or str(_ctx_n2.git_common_dir) == str((_vic2 / ".git").resolve())
                   or str(_ctx_n2.git_common_dir) == str(_ctx_v2.git_common_dir)))
        check("0.3.5: sibling crafted gitfile at victim modules/lib does not steal identity",
              _ctx_s2.git_common_dir != _ctx_v2.git_common_dir
              and str(_ctx_s2.native_memory_dir) != str(_ctx_v2.native_memory_dir))
    finally:
        if _oldH_sm2 is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_sm2

with _tf73.TemporaryDirectory() as _td_hg:
    _home_hg = Path(_td_hg) / "home"
    _home_hg.mkdir()
    _sp_gd.run(["git", "init"], cwd=str(_home_hg), check=True, capture_output=True)
    _att_hg = _home_hg / "code" / "attacker"
    _att_hg.mkdir(parents=True)
    _vic_hg = _home_hg / "code" / "victim"
    _vic_hg.mkdir()
    _oldH_hg = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_hg)
    try:
        _ctx_vhg = sc.resolve_store(_vic_hg)
        _stolen_hg = (_ctx_vhg.config_root / "projects" / ms.slug_for(_vic_hg) / "memory")
        _stolen_hg.mkdir(parents=True)
        (_stolen_hg / "MEMORY.md").write_text("# victim\n", encoding="utf-8")
        (_home_hg / ".claude").mkdir(exist_ok=True)
        (_home_hg / ".claude" / "settings.json").write_text(
            _json_xp.dumps({"autoMemoryDirectory": str(_stolen_hg)}), encoding="utf-8")
        _ctx_ahg = sc.resolve_store(_att_hg)
        check("0.3.5: HOME git-root ~/.claude/settings.json stays user-scoped",
              _ctx_ahg.resolution_source == "autoMemoryDirectory"
              and "project" not in _ctx_ahg.settings_sources
              and str(_ctx_ahg.native_memory_dir) == str(_stolen_hg))
        (_att_hg / ".claude").mkdir()
        (_att_hg / ".claude" / "settings.json").write_text(
            _json_xp.dumps({"autoMemoryDirectory": str(_stolen_hg)}), encoding="utf-8")
        _sp_gd.run(["git", "init"], cwd=str(_att_hg), check=True, capture_output=True)
        _ctx_ahg2 = sc.resolve_store(_att_hg)
        check("0.3.5: nested-repo project settings cannot select another project's store",
              _ctx_ahg2.write_allowed is False
              and str(_ctx_ahg2.native_memory_dir) != str(_stolen_hg)
              and any("escapes" in a for a in _ctx_ahg2.ambiguity))
    finally:
        if _oldH_hg is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_hg

with _tf73.TemporaryDirectory() as _td_gr:
    _home_gr = Path(_td_gr) / "home"
    _home_gr.mkdir()
    _proj_gr = Path(_td_gr) / "proj"
    _proj_gr.mkdir()
    _ns_gr = Path(_td_gr) / "dedicated-ns"
    _ns_gr.mkdir()
    (_ns_gr / "MEMORY.md").write_text("# dedicated\n", encoding="utf-8")
    _oldH_gr = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_gr)
    try:
        _ctx_gr0 = sc.resolve_store(_proj_gr)
        (_proj_gr / ".claude").mkdir()
        (_proj_gr / ".claude" / "settings.json").write_text(
            _json_xp.dumps({"autoMemoryDirectory": str(_ns_gr)}), encoding="utf-8")
        _ctx_gr1 = sc.resolve_store(_proj_gr)
        sc.write_store_grant(_ctx_gr0.plugin_data_dir, _ctx_gr0.project_id, _ns_gr,
                             adopt=True)
        _ctx_gr2 = sc.resolve_store(_proj_gr)
        _pdata_gr = _ctx_gr0.plugin_data_dir
        _canon_gr = _ctx_gr0.canonical_domain_dir
        (_proj_gr / ".claude" / "settings.json").write_text(
            _json_xp.dumps({"autoMemoryDirectory": str(_pdata_gr)}), encoding="utf-8")
        _ctx_gr3 = sc.resolve_store(_proj_gr)
        check("0.3.5: project autoMemoryDirectory denied without operator grant",
              _ctx_gr1.write_allowed is False
              and str(_ctx_gr1.native_memory_dir) != str(_ns_gr))
        check("0.3.5: operator grant allows a dedicated per-project namespace",
              _ctx_gr2.write_allowed is True
              and str(_ctx_gr2.native_memory_dir.resolve()) == str(_ns_gr.resolve()))
        check("0.3.5: project autoMemoryDirectory cannot select plugin-data",
              _ctx_gr3.write_allowed is False
              and str(_ctx_gr3.native_memory_dir) != str(_pdata_gr))
        del _canon_gr
    finally:
        if _oldH_gr is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_gr

with _tf73.TemporaryDirectory() as _td_md2:
    _dest_md = Path(_td_md2) / "mode.md"
    _dest_md.write_text("OLD-MODE\n", encoding="utf-8")
    _osB.chmod(str(_dest_md), 0o640)
    _rec_md = Path(_td_md2) / "rec"
    _rec_md.mkdir()
    _sn_md = cp._snapshot_dest_preimages(
        [{"dest": str(_dest_md), "mode": "replace",
          "sha256": __import__("hashlib").sha256(b"NEW-MODE\n").hexdigest()}],
        recovery=_rec_md)
    _dest_md.write_text("NEW-MODE\n", encoding="utf-8")
    _osB.chmod(str(_dest_md), 0o600)
    cp._restore_dest_preimages(_sn_md, [{"dest": str(_dest_md),
                                         "sha256": _sn_md[0]["published_sha256"]}])
    check("0.3.5: dest restore verifies original mode",
          _dest_md.read_text(encoding="utf-8") == "OLD-MODE\n"
          and (_dest_md.stat().st_mode & 0o777) == 0o640)

with _Env73() as _e_jc:
    _ctx_jc = sc.resolve_store(_e_jc.proj)
    _j_jc = cp.connect_journal(_ctx_jc)
    _oid_jc = "op_legacybody0001"
    _j_jc.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (_oid_jc, "canonical-upsert",
         _json_xp.dumps({"stem": "secret", "text": "CONFIDENTIAL-BODY\n",
                         "dest_preimages": [{"dest": "x.md",
                                             "bytes_b64": "Q09ORklERU5USUFM",
                                             "sha256": "ab" * 32,
                                             "absent": False}]}),
         "journal_complete", "complete", "2026-01-01T00:00:00Z"))
    _j_jc.commit()
    _j_jc.close()
    _cout = cp.compact_journal(_ctx_jc)
    _j_jc2 = cp.connect_journal(_ctx_jc)
    _shown = cp.journal_show(_j_jc2, _oid_jc)
    _inv, _nxt_jc = cp.journal_inventory(_j_jc2)
    _j_jc2.close()
    _pl_jc = (_shown or {}).get("payload") or {}
    check("0.3.5: journal compact redacts fact bodies from completed rows",
          _cout.get("ok") is True
          and "text" not in _pl_jc
          and "bytes_b64" not in _pl_jc
          and "CONFIDENTIAL" not in _json_xp.dumps(_pl_jc)
          and any(r["op_id"] == _oid_jc and r["has_body"] is False for r in _inv))

with _Env73() as _e_upj:
    _ctx_upj = sc.resolve_store(_e_upj.proj)
    _body_upj = (
        "---\nname: no-body-log\ndescription: d\nmetadata:\n  node_type: memory\n"
        "  type: reference\n  scope: user-global\n---\nSECRET-FACT-BODY\n")
    _upj = ci.upsert(_ctx_upj, "no-body-log", _body_upj)
    _j_upj = cp.connect_journal(_ctx_upj)
    _row_upj = _j_upj.execute(
        "SELECT payload FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _j_upj.close()
    _pl_upj = _json_xp.loads(_row_upj["payload"] or "{}")
    check("0.3.5: completed canonical-upsert journal has no fact text",
          _upj.get("ok") is True
          and "text" not in _pl_upj
          and "SECRET-FACT-BODY" not in _json_xp.dumps(_pl_upj)
          and "text_sha256" in _pl_upj)

with _tf73.TemporaryDirectory() as _td_fgp:
    _home_fgp = Path(_td_fgp) / "home"
    _home_fgp.mkdir()
    _a_fgp = Path(_td_fgp) / "projA"
    _b_fgp = Path(_td_fgp) / "projB"
    _a_fgp.mkdir()
    _b_fgp.mkdir()
    _oldH_fgp = _osB.environ.get("HOME")
    _osB.environ["HOME"] = str(_home_fgp)
    try:
        _enroll_personal(_a_fgp)
        _enroll_personal(_b_fgp)
        _ctx_af = sc.resolve_store(_a_fgp)
        _body_fgp = (
            "---\nname: fleet-purge\ndescription: d\nmetadata:\n  node_type: memory\n"
            "  type: reference\n  scope: user-global\n---\nFLEET-PURGE-BODY\n")
        ci.upsert(_ctx_af, "fleet-purge", _body_fgp)
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
            sg.run(_b_fgp, pull=True)
        _mir_fgp = sc.resolve_store(_b_fgp).native_memory_dir / "fleet-purge.md"
        _had_fgp = _mir_fgp.is_file()
        _conn_del = cp.connect(cp.db_path(_ctx_af))
        _conn_del.execute(
            "INSERT INTO domains(domain_id, status, updated_at) VALUES (?,?,?)",
            ("personal", "deleting", "2026-09-01T00:00:00Z"))
        _conn_del.commit()
        _conn_del.close()
        _err_del = _io73.StringIO()
        with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_err_del):
            _rc_del = sg.run(_b_fgp, pull=True)
        check("0.3.5: pull refuses while domain is deleting",
              _rc_del != 0 and "deleting" in _err_del.getvalue())
        _ctx_bf = sc.resolve_store(_b_fgp)
        _root_b = _ctx_bf.project_root
        _nat_b = _ctx_bf.native_memory_dir
        _pid_b = _ctx_bf.project_id
        import shutil as _sh_fgp
        _sh_fgp.rmtree(_root_b)
        _conn_row = cp.connect(cp.db_path(_ctx_af))
        _row_b = _conn_row.execute(
            "SELECT project_id, display_name, current_root, git_common_dir, "
            "remote_fingerprint, profile_id, domain_id, native_memory_dir, "
            "session_dir, status FROM projects WHERE project_id=?",
            (_pid_b,)).fetchone()
        _conn_row.close()
        _from_reg = sc.store_context_from_registry(_row_b, template=_ctx_af)
        check("0.3.5: registry StoreContext keeps recorded project_id and native",
              _from_reg.project_id == _pid_b
              and str(_from_reg.native_memory_dir) == str(_nat_b)
              and _from_reg.resolution_source == "registry-row")
        del _had_fgp
    finally:
        if _oldH_fgp is None:
            _osB.environ.pop("HOME", None)
        else:
            _osB.environ["HOME"] = _oldH_fgp

with _Env73() as _e_cli:
    with _ctx73.redirect_stdout(_io73.StringIO()) as _o_cli, \
            _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_cli = cmo.main(["journal", "inventory", "--project", str(_e_cli.proj), "--json"])
    check("0.3.5: cm journal inventory exits 0",
          _rc_cli == 0)

import fact_schema as _fs_p1
check("P1-3: fact_id must match stable id",
      _fs_p1.validate_canonical_frontmatter(
          {"name": "deploy", "domain": "work", "scope": "user-global",
           "schema_version": "3", "fact_id": "f_" + ("ab" * 12),
           "description": "d", "sensitivity": "internal", "status": "active",
           "applies_any": "[]", "applies_all": "[]", "applies_exclude": "[]",
           "content_modified": "2026-01-01T00:00:00Z",
           "last_observed_at": "2026-01-01T00:00:00Z"},
          stem="deploy", domain="work") is not None)
check("P1-3: impossible timestamp is refused",
      _fs_p1.validate_canonical_frontmatter(
          {"name": "deploy", "domain": "work", "scope": "user-global",
           "schema_version": "3", "fact_id": _fs_p1.stable_fact_id("work", "deploy"),
           "description": "d", "sensitivity": "internal", "status": "active",
           "applies_any": "[]", "applies_all": "[]", "applies_exclude": "[]",
           "content_modified": "2026-02-30T00:00:00Z",
           "last_observed_at": "2026-01-01T00:00:00Z"},
          stem="deploy", domain="work") is not None)
check("P1-3: classify unversioned as legacy-migration",
      _fs_p1.classify_canonical("---\nname: x\ndescription: d\n---\n", stem="x")["class"]
      == _fs_p1.CLASS_LEGACY)
check("P1-9: degraded gated applies is unknown (hold)",
      _fs_p1.applies_decision({"any": ["python"]}, set(), degraded=True) == "unknown"
      and _fs_p1.applies_decision({"any": ["python"]}, {"python"}) == "match"
      and _fs_p1.applies_decision({"any": ["python"]}, {"go"}) == "no-match")

with _Env73() as _e_p1s:
    _ctx_p1s = sc.resolve_store(_e_p1s.proj)
    _pl_p1 = ci.upsert(_ctx_p1s, "local-only",
                       "---\nname: local-only\ndescription: d\nmetadata:\n"
                       "  scope: project-local\n  type: reference\n---\nL\n")
    check("P1-5: canonical upsert refuses project-local scope",
          _pl_p1.get("ok") is False and "stack-general|user-global" in str(_pl_p1.get("error") or ""))
    _in_p1 = ci.upsert(_ctx_p1s, "expired-x",
                       "---\nname: expired-x\ndescription: d\nstatus: expired\nmetadata:\n"
                       "  scope: user-global\n  type: reference\n---\nE\n")
    check("P1-5: canonical upsert refuses non-active status",
          _in_p1.get("ok") is False and "status: active" in str(_in_p1.get("error") or ""))

with _Env73() as _e_loc:
    _ctx_loc = sc.resolve_store(_e_loc.proj)
    _lf = _e_loc.store / "local-a.md"
    _lf.write_text("---\nname: local-a\ndescription: a local fact\n---\nBODY\n", encoding="utf-8")
    import local_ingress as li
    _upl = li.local_upsert(_ctx_loc, "local-a", _lf.read_text(encoding="utf-8"))
    check("P1-10: cm local upsert writes fact + index pointer",
          _upl.get("ok") is True
          and (_e_loc.store / "local-a.md").is_file()
          and "](local-a.md)" in (_e_loc.store / "MEMORY.md").read_text(encoding="utf-8"))
    _fgl = li.local_forget(_ctx_loc, "local-a")
    check("P1-10: cm local forget removes fact and pointer",
          _fgl.get("ok") is True
          and not (_e_loc.store / "local-a.md").exists()
          and "](local-a.md)" not in (_e_loc.store / "MEMORY.md").read_text(encoding="utf-8"))

check("P1-8: project_id_for ignores remote fingerprint",
      sc.project_id_for("default", "unknown", Path("/tmp/x/.git"), Path("/tmp/x"), "aaaa")
      == sc.project_id_for("default", "unknown", Path("/tmp/x/.git"), Path("/tmp/x"), "bbbb"))

check("P1-4: link scope uses opening frontmatter not body",
      ci._scope_of_text("---\nscope: user-global\n---\nscope: project-local\n")
      == "user-global")

with _Env73() as _e_exp:
    _ctx_exp = sc.resolve_store(_e_exp.proj)
    _conn_exp = cp.connect(cp.db_path(_ctx_exp))
    _nproj_exp = _conn_exp.execute("SELECT count(*) AS n FROM projects").fetchone()["n"]
    _conn_exp.close()
    _tar_exp = Path(_e_exp._td.name) / "exp.tar.gz"
    _ex_out = ret.export_ops(_ctx_exp.plugin_data_dir, _tar_exp)
    import sqlite3 as _sq_exp
    import tarfile as _tf_exp
    _restored_ok = False
    if _ex_out.get("ok") and Path(_ex_out["path"]).is_file():
        with _tf_exp.open(_ex_out["path"], "r:gz") as _tar:
            _mem = None
            for _n in _tar.getnames():
                if _n.endswith("control.sqlite"):
                    _mem = _tar.extractfile(_n)
                    break
            if _mem is not None:
                _db_exp = Path(_e_exp._td.name) / "restored.sqlite"
                _db_exp.write_bytes(_mem.read())
                _c2 = _sq_exp.connect(str(_db_exp))
                try:
                    _n2 = _c2.execute("SELECT count(*) AS n FROM projects").fetchone()[0]
                    _restored_ok = int(_n2) == int(_nproj_exp) and int(_n2) >= 1
                finally:
                    _c2.close()
    check("P1-12: export restoration opens a usable SQLite snapshot",
          _restored_ok)

with _Env73() as _e_ll:
    _ctx_ll = sc.resolve_store(_e_ll.proj)
    import local_ingress as _li_ll
    _bad_ll = _li_ll.local_upsert(
        _ctx_ll, "has-link",
        "---\nname: has-link\ndescription: d\n---\nsee [[missing-target]]\n")
    check("P1-10: cm local upsert refuses a dangling wikilink",
          _bad_ll.get("ok") is False and "dangling" in str(_bad_ll.get("error") or ""))
    _ok_code = _li_ll.local_upsert(
        _ctx_ll, "has-example",
        "---\nname: has-example\ndescription: d\n---\n"
        "format `[[link]]` is a placeholder\n```\n[[fenced]]\n```\n")
    check("dogfood D2: cm local upsert admits backticked/fenced [[link]] "
          "(same strip as dangling_links)",
          _ok_code.get("ok") is True
          and (_e_ll.store / "has-example.md").is_file())
    _long_desc = "x" * 400
    _ok_fat = _li_ll.local_upsert(
        _ctx_ll, "fat-hook",
        f"---\nname: fat-hook\ndescription: {_long_desc}\n---\nbody keeps the full key\n")
    _idx_fat = (_e_ll.store / "MEMORY.md").read_text(encoding="utf-8")
    _ptr_fat = next((ln for ln in _idx_fat.splitlines() if "](fat-hook.md)" in ln), "")
    _body_fat = (_e_ll.store / "fat-hook.md").read_text(encoding="utf-8")
    check("dogfood D1: cm local pointer truncates a long description (not a fat hook)",
          _ok_fat.get("ok") is True
          and "…" in _ptr_fat
          and _long_desc not in _ptr_fat
          and _long_desc in _body_fat
          and ms.est_tokens(_ptr_fat) <= ms.HOOK_TOKEN_WARN)

import local_ingress as _li_ptr
_sample_wl = "a [[real]] b `[[inline]]` c\n```\n[[fenced]]\n```\n[[tool.mypy.overrides]]"
check("dogfood D2: link_targets uses extract_wikilinks (inline/fenced stripped; dotted stems kept)",
      ci.link_targets(_sample_wl) == ["real", "tool.mypy.overrides"])
check("R128-7: every valid stem is a valid link target (periods kept)",
      ci.link_targets("see [[foo.bar]] and [[ok-stem_1]]") == ["foo.bar", "ok-stem_1"]
      and ident.validate_fact_stem("foo.bar") == "foo.bar")
_dot_bad = 0
for _dstem in ("x.", ".x", "a..b", "..x"):
    try:
        ident.validate_fact_stem(_dstem)
    except ident.IdentifierRefused:
        _dot_bad += 1
check("R128-7b: leading/trailing/consecutive dots are refused (Windows-path hazard)",
      _dot_bad == 4)
_local_parens = _li_ptr._pointer("foo", "keep (OPEN: 1.0 HOLD) in the cue", "project-local")
_glob_parens = sg._pointer_line("foo", {"description": "keep (OPEN: 1.0 HOLD) in the cue",
                                       "scope": "project-local"})
check("I1: local _pointer is not _pointer_line (keeps parens; global strips them)",
      _li_ptr._pointer is not sg._pointer_line
      and _local_parens != _glob_parens
      and "(OPEN: 1.0 HOLD)" in _local_parens
      and "(" not in _glob_parens.split("—", 1)[1].rsplit("[", 1)[0])
check("I1: local _pointer strips [] and control/newlines (no index injection)",
      "](http://x)" not in _li_ptr._pointer("foo", "evil](http://x) link")
      and "\n" not in _li_ptr._pointer("foo", "a\nb\x1b[31mc")
      and "\x1b" not in _li_ptr._pointer("foo", "a\nb\x1b[31mc"))
_long_tok = "supercalifragilisticexpialidocious"
_wb_desc = ("word " * 80) + _long_tok
_wb_line = _li_ptr._pointer("foo", _wb_desc, "project-local")
_wb_hook = _wb_line.split(" — ", 1)[1]
check("I1: word-boundary truncate; whole line ≤ HOOK_TOKEN_WARN",
      ms.est_tokens(_wb_line) <= ms.HOOK_TOKEN_WARN
      and "…" in _wb_line
      and (_long_tok in _wb_hook or _long_tok[:20] not in _wb_hook))
check("I2: local _pointer attaches [project-local] when scope is passed",
      _local_parens.endswith(" [project-local]"))

with _Env73() as _e_i1:
    _ctx_i1 = sc.resolve_store(_e_i1.proj)
    _desc_i1 = ("Roadmap + dev status — SHIPPED through v0.3.6 secure-default + identity "
                "+ dogfood/drift (OPEN: 1.0 HOLD)")
    _up_i1 = _li_ptr.local_upsert(
        _ctx_i1, "consolidate-memory-roadmap",
        "---\nname: consolidate-memory-roadmap\n"
        f"description: {_desc_i1}\n"
        "metadata:\n  scope: project-local\n  type: reference\n---\nbody keeps the key\n")
    _idx_i1 = (_e_i1.store / "MEMORY.md").read_text(encoding="utf-8")
    _ptr_i1 = next((ln for ln in _idx_i1.splitlines()
                    if "](consolidate-memory-roadmap.md)" in ln), "")
    _body_i1 = (_e_i1.store / "consolidate-memory-roadmap.md").read_text(encoding="utf-8")
    check("I1/I2: upsert keeps parens in hook when they fit, tags [project-local], body untouched",
          _up_i1.get("ok") is True
          and "(OPEN: 1.0 HOLD)" in _ptr_i1
          and _ptr_i1.endswith(" [project-local]")
          and ms.est_tokens(_ptr_i1) <= ms.HOOK_TOKEN_WARN
          and _desc_i1 in _body_i1)
    _ph_up = _li_ptr.local_upsert(
        _ctx_i1, "lesson-clause",
        "---\nname: lesson-clause\ndescription: d\n---\nsee [[link]] in the lesson\n")
    check("bare-[[link]]: placeholder target hints backticks",
          _ph_up.get("ok") is False
          and "dangling link [[link]]" in str(_ph_up.get("error") or "")
          and "backticks" in str(_ph_up.get("error") or ""))
    _real_miss = _li_ptr.local_upsert(
        _ctx_i1, "other-fact",
        "---\nname: other-fact\ndescription: d\n---\nsee [[missing-real-fact]]\n")
    check("bare-[[link]]: real missing stem has no format-examples clause",
          _real_miss.get("ok") is False
          and str(_real_miss.get("error") or "") == "dangling link [[missing-real-fact]]")

with _Env73() as _e_rb:
    _ctx_rb = sc.resolve_store(_e_rb.proj)
    (_e_rb.store / "local-rb.md").write_text(
        "---\nname: local-rb\ndescription: keep (parens) please\n"
        "metadata:\n  scope: project-local\n  type: reference\n---\nL\n",
        encoding="utf-8")
    _mir_rb = sg._as_mirror(_v3_canon("mir-rb", description="keep (parens) please"),
                            "mir-rb", since="2026-01-01T00:00:00Z", body_hash="abc")
    (_e_rb.store / "mir-rb.md").write_text(_mir_rb, encoding="utf-8")
    _rb = _li_ptr.local_rebuild_index(_ctx_rb, apply=True, confirm="rebuild-local-index")
    _idx_rb = (_e_rb.store / "MEMORY.md").read_text(encoding="utf-8")
    _loc_ln = next((ln for ln in _idx_rb.splitlines() if "](local-rb.md)" in ln), "")
    _mir_ln = next((ln for ln in _idx_rb.splitlines() if "](mir-rb.md)" in ln), "")
    check("I1: rebuild uses local _pointer (keeps parens) for locals and _pointer_line for mirrors",
          _rb.get("ok") is True
          and "(parens)" in _loc_ln
          and "(parens)" not in _mir_ln)

with _Env73() as _e_jd:
    _ctx_jd = sc.resolve_store(_e_jd.proj)
    _no_mk = ms.run_justify_demotion(_e_jd.proj, ["cadence-fact"])
    check("O1 CLI: does not mint a marker when none exists",
          _no_mk.get("ok") is False
          and "no .consolidation-state.json" in str(_no_mk.get("error") or "")
          and not (_e_jd.store / ".consolidation-state.json").exists())
    (_e_jd.store / ".consolidation-state.json").write_text(
        '{"commit": "deadbeef", "timestamp": "2026-09-01T00:00:00Z",'
        ' "stacks": ["python"], "beacon_snooze_until": "snooze",'
        ' "standing_justify": {"facts": 4}}\n', encoding="utf-8")
    _stamped = ms.run_justify_demotion(
        _e_jd.proj, ["cadence-fact"], now_iso="2026-09-01T21:23:45.446Z",
        force=True)
    _mk = _jsonB.loads((_e_jd.store / ".consolidation-state.json").read_text(encoding="utf-8"))
    check("O1 CLI: MERGE preserves stacks/snooze/standing_justify and stamps windows_full",
          _stamped.get("ok") is True
          and _mk.get("commit") == "deadbeef"
          and _mk.get("stacks") == ["python"]
          and _mk.get("beacon_snooze_until") == "snooze"
          and _mk.get("standing_justify") == {"facts": 4}
          and _mk["demotion_justify"]["cadence-fact"]["windows"] == _stamped["windows_full"]
          and _mk["demotion_justify"]["cadence-fact"]["at"] == "2026-09-01T21:23:45.446Z")

with _Env73() as _e_gc0:
    import io as _io_gc0, contextlib as _cl_gc0
    _buf0, _err0 = _io_gc0.StringIO(), _io_gc0.StringIO()
    with _cl_gc0.redirect_stdout(_buf0), _cl_gc0.redirect_stderr(_err0):
        _rc_gc0 = sg.gc(_e_gc0.proj, apply=False)
    check("GC: enrolled empty domain, no leftover mirrors → nothing to reclaim",
          _rc_gc0 == 0
          and "nothing to reclaim" in _buf0.getvalue()
          and "cannot distinguish that from all-canonicals-deleted" not in _buf0.getvalue())

with _Env73() as _e_gc1:
    _mir_gc = sg._as_mirror(_v3_canon("orphan-m"), "orphan-m",
                            since="2026-01-01T00:00:00Z", body_hash="abc")
    (_e_gc1.store / "orphan-m.md").write_text(_mir_gc, encoding="utf-8")
    import io as _io_gc1, contextlib as _cl_gc1
    _buf1, _err1 = _io_gc1.StringIO(), _io_gc1.StringIO()
    with _cl_gc1.redirect_stdout(_buf1), _cl_gc1.redirect_stderr(_err1):
        _rc_gc1 = sg.gc(_e_gc1.proj, apply=False)
    check("GC: leftover mirrors + no live canonicals still refuse (Probe G copy)",
          _rc_gc1 == 0
          and "cannot distinguish that from all-canonicals-deleted" in _buf1.getvalue())

with _Env73() as _e_mir:
    _ctx_mir = sc.resolve_store(_e_mir.proj)
    _mir_body = sg._as_mirror(_v3_canon("mir-loc"), "mir-loc",
                             since="2026-01-01T00:00:00Z",
                             body_hash="abc")
    (_e_mir.store / "mir-loc.md").write_text(_mir_body, encoding="utf-8")
    import local_ingress as _li_mir
    _up_mir = _li_mir.local_upsert(_ctx_mir, "mir-loc",
                                  "---\nname: mir-loc\ndescription: d\n---\nX\n")
    check("review: cm local upsert refuses a managed mirror",
          _up_mir.get("ok") is False and "managed mirror" in str(_up_mir.get("error") or ""))

with _Env73() as _e_gr:
    _ctx_gr = sc.resolve_store(_e_gr.proj)
    _raised_gr = False
    try:
        sc.write_store_grant(_ctx_gr.plugin_data_dir, _ctx_gr.project_id,
                             _ctx_gr.plugin_data_dir / "inside",
                             config_root=_ctx_gr.config_root)
    except sc.WriteRefused:
        _raised_gr = True
    check("review: grant-native refuses plugin-data",
          _raised_gr)

with _tf73.TemporaryDirectory() as _td_legcat:
    _ld = Path(_td_legcat)
    (_ld / "legacy.md").write_text(
        "---\nname: legacy\ndescription: d\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    check("review: catalog omits CLASS_LEGACY even if status=active",
          "legacy.md" not in ci.generate_catalog(_ld))

# ── R128 Phase-1 acceptance ──
_long_stem = "a" * 97
_stem_len_ok = False
try:
    ident.validate_fact_stem(_long_stem)
except ident.IdentifierRefused:
    _stem_len_ok = True
check("R128-7: stem longer than 96 chars is refused",
      _stem_len_ok and ident.validate_fact_stem("gh-pr-edit-broken_v2.1") == "gh-pr-edit-broken_v2.1")

with _Env73() as _e_v1:
    _ctx_v1 = sc.resolve_store(_e_v1.proj)
    import local_ingress as _li_v1
    _up_v1 = _li_v1.local_upsert(
        _ctx_v1, "local-v1",
        "---\nname: local-v1\ndescription: a v1 fact\n---\nBODY\n")
    _body_v1 = (_e_v1.store / "local-v1.md").read_text(encoding="utf-8")
    check("R128-3: local upsert injects LocalFactV1 and forces project-local",
          _up_v1.get("ok") is True
          and "local_schema_version: 1" in _body_v1
          and "scope: project-local" in _body_v1
          and "status: active" in _body_v1
          and "sensitivity: internal" in _body_v1
          and "](local-v1.md)" in (_e_v1.store / "MEMORY.md").read_text(encoding="utf-8")
          and (_e_v1.store / "MEMORY.md").read_text(encoding="utf-8").count("[project-local]"))
    _bad_sc = _li_v1.local_upsert(
        _ctx_v1, "wide-scope",
        "---\nname: wide-scope\ndescription: d\nscope: user-global\n---\nX\n")
    check("R128-3: local upsert refuses non-project-local scope",
          _bad_sc.get("ok") is False and "project-local" in str(_bad_sc.get("error") or ""))
    _dup_k = _li_v1.local_upsert(
        _ctx_v1, "dup-key",
        "---\nname: dup-key\ndescription: d\nscope: project-local\nscope: project-local\n---\nX\n")
    check("R128-3: duplicate reserved key refused",
          _dup_k.get("ok") is False and "duplicate" in str(_dup_k.get("error") or ""))

with _Env73() as _e_abs:
    _ctx_abs = sc.resolve_store(_e_abs.proj)
    from control_plane import ABSENT as _ABSENT, transact as _tx_abs
    _ghost = _e_abs.store / "created-during.md"
    def _mut_abs(conn, temps):
        del conn
        temps[str(_ghost)] = "stolen\n"
        return {"dest_modes": {str(_ghost): "create"},
                "expected_revisions": {str(_ghost): _ABSENT}}
    _ghost.write_text("external\n", encoding="utf-8")
    _refused_abs = False
    try:
        _tx_abs(_ctx_abs, "local-upsert", {"stem": "created-during"}, _mut_abs,
                expected_revisions={str(_ghost): _ABSENT})
    except sc.WriteRefused:
        _refused_abs = True
    check("R128-4: ABSENT dest that appears before publish is refused, not overwritten",
          _refused_abs and _ghost.read_text(encoding="utf-8") == "external\n")

with _Env73() as _e_ar:
    _ctx_ar = sc.resolve_store(_e_ar.proj)
    import local_ingress as _li_ar
    import index_admission as _ia_ar
    _ship = ["# Shipped", ""] + [
        f"- [arch-{i}](arch-{i}.md) — done" for i in range(1000)]
    (_e_ar.store / "SHIPPED.md").write_text("\n".join(_ship) + "\n", encoding="utf-8")
    (_e_ar.store / "arch-new.md").write_text(
        "---\nname: arch-new\ndescription: freshly shipped\n---\nB\n", encoding="utf-8")
    (_e_ar.store / "MEMORY.md").write_text(
        "# Memory Index\n\n- [arch-new](arch-new.md) — freshly shipped [project-local]\n",
        encoding="utf-8")
    _adm_ar = _ia_ar.archive_index((_e_ar.store / "SHIPPED.md").read_text(encoding="utf-8"))
    _adm_mem = _ia_ar.project_index("\n".join(_ship) + "\n")
    _up_ar = _li_ar.local_archive(_ctx_ar, "arch-new")
    check("R128-5: 1000 archived pointers do not hit the native MEMORY.md cliff",
          _adm_ar["admitted"] is True
          and _adm_mem["admitted"] is False
          and _up_ar.get("ok") is True
          and "](arch-new.md)" in (_e_ar.store / "SHIPPED.md").read_text(encoding="utf-8")
          and "](arch-new.md)" not in (_e_ar.store / "MEMORY.md").read_text(encoding="utf-8"))

with _Env73() as _e_rb2:
    _ctx_rb2 = sc.resolve_store(_e_rb2.proj)
    import local_ingress as _li_rb2
    (_e_rb2.store / "good-rb.md").write_text(
        "---\nname: good-rb\ndescription: keep me\n---\nG\n", encoding="utf-8")
    (_e_rb2.store / "bad-rb.md").write_text("not a fact\n", encoding="utf-8")
    (_e_rb2.store / "MEMORY.md").write_text(
        "# Memory Index\n\n- [good-rb](good-rb.md) — keep me\n"
        "- [bad-rb](bad-rb.md) — was indexed\n", encoding="utf-8")
    _plan_rb = _li_rb2.local_rebuild_index(_ctx_rb2)
    _apply_rb = _li_rb2.local_rebuild_index(_ctx_rb2, apply=True,
                                           confirm="rebuild-local-index")
    _idx_rb2 = (_e_rb2.store / "MEMORY.md").read_text(encoding="utf-8")
    check("R128-6: invalid facts fail closed; index unchanged without --skip-invalid",
          _plan_rb.get("ok") is False
          and any(r.get("stem") == "bad-rb" for r in _plan_rb.get("invalid") or [])
          and _apply_rb.get("ok") is False
          and "](bad-rb.md)" in _idx_rb2
          and "](good-rb.md)" in _idx_rb2)
    _skip_rb = _li_rb2.local_rebuild_index(
        _ctx_rb2, apply=True, skip_invalid=True, confirm="rebuild-local-index")
    _idx_skip = (_e_rb2.store / "MEMORY.md").read_text(encoding="utf-8")
    check("R128-6: --skip-invalid enumerates omitted stems and drops only those pointers",
          _skip_rb.get("ok") is True
          and "bad-rb" in (_skip_rb.get("omitted") or [])
          and "](good-rb.md)" in _idx_skip
          and "](bad-rb.md)" not in _idx_skip)

with _Env73() as _e_clk:
    _ctx_clk = sc.resolve_store(_e_clk.proj)
    from control_plane import count_probative_after as _cpa, record_usage_window as _ruw
    (_e_clk.store / ".consolidation-state.json").write_text(
        '{"commit": "aa", "timestamp": "2026-01-01T00:00:00Z"}\n', encoding="utf-8")
    _ruw(_ctx_clk, cycle_id="c|0", started_at="2026-01-01T00:00:00Z", probative=True)
    _st_hi = ms.run_justify_demotion(_e_clk.proj, ["cadence-fact"], force=True,
                                     now_iso="2026-01-01T00:00:00Z")
    seq0 = int((_st_hi.get("stamped") or [{}])[0].get("sequence") or 0)
    for _i in range(1, 6):
        _ruw(_ctx_clk, cycle_id=f"c|{_i}",
             started_at=f"2026-02-0{_i}T00:00:00Z", probative=True)
    check("R128-1: exactly five later probative windows expire a sequence stamp",
          _st_hi.get("ok") is True
          and _cpa(_ctx_clk, seq0) == 5
          and ms._justify_remaining(
              seq0, None, 1, [], sequence=seq0, n_after_seq=_cpa(_ctx_clk, seq0)) is None)
    check("R128-1: four later windows still suppress (compaction-proof clock)",
          ms._justify_remaining(seq0, None, 1, [], sequence=seq0, n_after_seq=4) is not None)
    _nogo = ms.run_justify_demotion(_e_clk.proj, ["not-a-candidate"])
    check("R128-2: default justify-demotion refuses a non-candidate stem",
          _nogo.get("ok") is False and "not a current demotion candidate" in str(_nogo.get("error") or ""))

# ── Phase 2: journal terminal cleanup / schema split ──
with _Env73() as _e_js:
    _ctx_js = sc.resolve_store(_e_js.proj)
    _j_js = cp.connect_journal(_ctx_js)
    _names_js = cp.journal_table_names(_j_js)
    _j_js.close()
    _r_js = cp.connect(cp.db_path(_ctx_js))
    _rnames = {str(r[0]) for r in _r_js.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()}
    _ver_r = int(_r_js.execute("PRAGMA user_version").fetchone()[0])
    _r_js.close()
    check("P0-2/P1-4: fresh journal.sqlite has only journal schema",
          _names_js <= cp.JOURNAL_TABLES
          and "projects" not in _names_js and "facts" not in _names_js)
    check("P1-5: control.sqlite has PRAGMA user_version and no journal table",
          _ver_r == cp.REGISTRY_USER_VERSION
          and "journal" not in _rnames)

with _Env73() as _e_cu:
    _ctx_cu = sc.resolve_store(_e_cu.proj)
    _dest_cu = _e_cu.store / "cleanup-body.md"
    _old_ca = _osB.environ.get("CM_CLEANUP_FAIL")
    _osB.environ["CM_CLEANUP_FAIL"] = "1"
    _cu_err = ""
    try:
        cp.transact(_ctx_cu, "probe-cleanup", {"k": 1},
                    lambda c, t: t.__setitem__(str(_dest_cu), "SECRET-FORGET\n") or {})
    except cp.WriteRefused as e:
        _cu_err = str(e)
    except cp.CrashSimulated:
        pass
    finally:
        if _old_ca is None:
            _osB.environ.pop("CM_CLEANUP_FAIL", None)
        else:
            _osB.environ["CM_CLEANUP_FAIL"] = _old_ca
    _j_cu = cp.connect_journal(_ctx_cu)
    _row_cu = _j_cu.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _st_cu = str(_row_cu["status"] if _row_cu is not None else "")
    _oid_cu = str((_j_cu.execute(
        "SELECT op_id FROM journal ORDER BY rowid DESC LIMIT 1").fetchone() or {"op_id": ""})["op_id"])
    _j_cu.close()
    check("P0-2: cleanup failure is never recorded as complete",
          "committed cleanup pending" in _cu_err
          and _st_cu == cp.JOURNAL_CLEANUP_PENDING)
    _j_cu2 = cp.connect_journal(_ctx_cu)
    _rec_cu = cp.recover_pending(_j_cu2, ctx=_ctx_cu)
    _row_cu2 = cp.journal_row(_j_cu2, _oid_cu)
    _j_cu2.close()
    check("P0-2: recover finishes committed-cleanup-pending to complete",
          _oid_cu in _rec_cu
          and str((_row_cu2 or {}).get("status") or "") == "complete")

with _Env73() as _e_fg:
    _ctx_fg = sc.resolve_store(_e_fg.proj)
    import local_ingress as _li_fg
    _up_fg = _li_fg.local_upsert(
        _ctx_fg, "forget-me",
        "---\nname: forget-me\ndescription: secret body\n---\nPREVIOUS-BODY\n")
    _fg = _li_fg.local_forget(_ctx_fg, "forget-me")
    _trash_fg = list(_e_fg.store.glob(".cm-trash-*"))
    _rec_fg = _ctx_fg.plugin_data_dir / "recovery"
    _rec_left = []
    if _rec_fg.is_dir():
        _rec_left = [p for p in _rec_fg.rglob("*") if p.is_file()]
    check("P0-2: successful forget leaves no original body in trash or recovery",
          _up_fg.get("ok") is True and _fg.get("ok") is True
          and not (_e_fg.store / "forget-me.md").exists()
          and _trash_fg == []
          and not any("PREVIOUS-BODY" in p.read_text(encoding="utf-8", errors="replace")
                      for p in _rec_left))

with _Env73() as _e_ab:
    _ctx_ab = sc.resolve_store(_e_ab.proj)
    _j_ab = cp.connect_journal(_ctx_ab)
    _oid_ab = "op_abandontrash01"
    _trash_ab = _e_ab.store / ".cm-trash-op_abandontrash01-0"
    _e_ab.store.mkdir(parents=True, exist_ok=True)
    _trash_ab.write_text("STILL-HERE\n", encoding="utf-8")
    _j_ab.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (_oid_ab, "local-forget",
         _json_xp.dumps({"deletes": [{"path": str(_e_ab.store / "x.md"),
                                      "trash": str(_trash_ab),
                                      "preimage": "ab" * 32}]}),
         "after_trash", "pending", "2026-09-01T00:00:00Z"))
    _j_ab.commit()
    _j_ab.close()
    _ab_err = ""
    try:
        cp.journal_abandon(_ctx_ab, _oid_ab)
    except sc.WriteRefused as e:
        _ab_err = str(e)
    check("P0-2: journal abandon refuses while trash is present",
          "trash/recovery still present" in _ab_err
          and _trash_ab.is_file())
    _ab_ok = cp.journal_abandon(_ctx_ab, _oid_ab, accept_fs=True)
    check("P0-2: journal abandon --accept-fs records the operator verification",
          _ab_ok.get("ok") is True and _ab_ok.get("accepted_fs") is True)

with _Env73() as _e_rbk:
    _ctx_rbk = sc.resolve_store(_e_rbk.proj)
    _j_rbk = cp.connect_journal(_ctx_rbk)
    _oid_rbk = "op_restorefail01"
    _j_rbk.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (_oid_rbk, "probe", _json_xp.dumps({"deletes": []}),
         "cleanup_pending", cp.JOURNAL_CLEANUP_PENDING, "2026-09-01T00:00:00Z"))
    _j_rbk.commit()
    _j_rbk.close()
    _rbk_err = ""
    try:
        cp.journal_rollback(_ctx_rbk, _oid_rbk)
    except sc.WriteRefused as e:
        _rbk_err = str(e)
    _j_rbk2 = cp.connect_journal(_ctx_rbk)
    _st_rbk = str((cp.journal_row(_j_rbk2, _oid_rbk) or {}).get("status") or "")
    _j_rbk2.close()
    check("P0-2: failed restoration is not silently abandoned",
          "cannot rollback after registry commit" in _rbk_err
          and _st_rbk == cp.JOURNAL_CLEANUP_PENDING)

with _Env73() as _e_st:
    _ctx_st = sc.resolve_store(_e_st.proj)
    _p_st = _ctx_st.canonical_domain_dir / "status-race.md"
    _p_st.parent.mkdir(parents=True, exist_ok=True)
    _p_st.write_text(
        "---\nname: status-race\ndescription: d\nstatus: active\n"
        "schema_version: 3\n---\nOLD\n", encoding="utf-8")
    _snap_st = cp.read_snapshot(_p_st)
    _p_st.write_text(
        "---\nname: status-race\ndescription: d\nstatus: active\n"
        "schema_version: 3\n---\nCONCURRENT\n", encoding="utf-8")
    _st_err = ""
    try:
        cp.transact(
            _ctx_st, "canonical-status", {"stem": "status-race"},
            lambda c, t: t.__setitem__(str(_p_st), "FROM-OLD\n") or {},
            expected_revisions={str(_p_st): _snap_st.sha256})
    except sc.WriteRefused as e:
        _st_err = str(e)
    check("P0-3: snapshot hash refuses a concurrent dest edit (no bless-new-hash)",
          "source changed" in _st_err
          and "CONCURRENT" in _p_st.read_text(encoding="utf-8"))

with _Env73() as _e_rc:
    _ctx_rc = sc.resolve_store(_e_rc.proj)
    _old_rc = _osB.environ.get("CM_CRASH_AFTER")
    _osB.environ["CM_CRASH_AFTER"] = "cleanup_pending"
    try:
        cp.transact(_ctx_rc, "probe-crash-cu", {"k": 1},
                    lambda c, t: t.__setitem__(
                        str(_e_rc.store / "c.md"), "body\n") or {})
        _crashed_rc = False
    except cp.CrashSimulated:
        _crashed_rc = True
    finally:
        if _old_rc is None:
            _osB.environ.pop("CM_CRASH_AFTER", None)
        else:
            _osB.environ["CM_CRASH_AFTER"] = _old_rc
    _j_rc = cp.connect_journal(_ctx_rc)
    _row_rc = _j_rc.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _j_rc.close()
    check("P0-2: crash after cleanup_pending leaves committed-cleanup-pending",
          _crashed_rc and str(_row_rc["status"] if _row_rc else "") == cp.JOURNAL_CLEANUP_PENDING)

with _Env73() as _e_crg:
    _ctx_crg = sc.resolve_store(_e_crg.proj)
    _old_crg = _osB.environ.get("CM_CRASH_AFTER")
    _osB.environ["CM_CRASH_AFTER"] = "commit_registry"
    try:
        cp.transact(_ctx_crg, "probe-crash-cr", {"k": 1},
                    lambda c, t: t.__setitem__(
                        str(_e_crg.store / "cr.md"), "body\n") or {})
        _crashed_crg = False
    except cp.CrashSimulated:
        _crashed_crg = True
    finally:
        if _old_crg is None:
            _osB.environ.pop("CM_CRASH_AFTER", None)
        else:
            _osB.environ["CM_CRASH_AFTER"] = _old_crg
    _j_crg = cp.connect_journal(_ctx_crg)
    _row_crg = _j_crg.execute(
        "SELECT status FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
    _j_crg.close()
    check("P0-2: crash after registry COMMIT is committed-cleanup-pending (no republish)",
          _crashed_crg
          and str(_row_crg["status"] if _row_crg else "") == cp.JOURNAL_CLEANUP_PENDING)

with _Env73() as _e_rcpt:
    _ctx_rcpt = sc.resolve_store(_e_rcpt.proj)
    _j_rcpt = cp.connect_journal(_ctx_rcpt)
    _oid_rcpt = "op_oldcomplete0001"
    _j_rcpt.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at, completed_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (_oid_rcpt, "local-forget",
         _json_xp.dumps({"publishes": [{"dest": "x.md", "sha256": "ab" * 32}]}),
         "journal_complete", "complete",
         "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"))
    _j_rcpt.commit()
    _j_rcpt.close()
    _cout_r = cp.compact_journal(_ctx_rcpt)
    _j_rcpt2 = cp.connect_journal(_ctx_rcpt)
    _shown_r = cp.journal_show(_j_rcpt2, _oid_rcpt)
    _j_rcpt2.close()
    _pl_r = (_shown_r or {}).get("payload") or {}
    check("P1-9: complete rows older than 90 days collapse to a receipt",
          _cout_r.get("ok") is True
          and int(_cout_r.get("receipts") or 0) >= 1
          and _pl_r.get("receipt") is True
          and "publishes" not in _pl_r)

with _Env73() as _e_or:
    _ctx_or = sc.resolve_store(_e_or.proj)
    _j_or = cp.connect_journal(_ctx_or)
    _oid_hold = "op_pendingtrash01"
    _trash_hold = _e_or.store / (".cm-trash-%s-0" % _oid_hold)
    _trash_hold.write_text("COMPLETE-OLD-BODY\n", encoding="utf-8")
    _orphan = _e_or.store / ".cm-trash-op_orphan00000001-0"
    _orphan.write_text("ORPHAN-BODY\n", encoding="utf-8")
    _j_or.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (_oid_hold, "local-forget",
         _json_xp.dumps({"origin_project_id": "p_other",
                         "origin_domain_id": "other",
                         "deletes": [{"path": str(_e_or.store / "gone.md"),
                                      "trash": str(_trash_hold),
                                      "preimage": "ab" * 32}]}),
         "after_trash", "pending", "2026-09-01T00:00:00Z"))
    _j_or.commit()
    _j_or.close()
    _plan_or = cp.journal_cleanup(_ctx_or, apply=False)
    check("P0-2: journal cleanup plan omits pending complete-old trash",
          str(_trash_hold) not in (_plan_or.get("trash") or [])
          and str(_orphan) in (_plan_or.get("trash") or []))
    _app_or = cp.journal_cleanup(_ctx_or, apply=True)
    check("P0-2: journal cleanup apply does not unlink pending trash",
          _app_or.get("ok") is True
          and _trash_hold.is_file()
          and _trash_hold.read_text(encoding="utf-8") == "COMPLETE-OLD-BODY\n"
          and not _orphan.exists())
    check("P0-2: journal cleanup apply scavenges true orphan trash",
          not _orphan.exists())

# ── v0.4.2 P2: journal scale (merged compact pass + scan reuse + export leg) ────
with _Env73() as _e_p2:
    _ctx_p2 = sc.resolve_store(_e_p2.proj)
    _j_p2 = cp.connect_journal(_ctx_p2)
    # one RECENT row with a body (redact-only) + one OLD row (receipt-collapse;
    # its under-whitelisted publishes item is also a redact-change)
    _j_p2.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at, completed_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("op_legacy_p2", "canonical-upsert",
         _json_xp.dumps({"stem": "x", "text": "BODY-P2\n",
                         "dest_preimages": [{"dest": "x.md", "bytes_b64": "Qk9EWQ==",
                                             "sha256": "ab" * 32, "absent": False}]}),
         "journal_complete", "complete", "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"))
    _j_p2.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at, completed_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("op_old_p2", "local-forget",
         _json_xp.dumps({"publishes": [{"dest": "y.md", "sha256": "cd" * 32}]}),
         "journal_complete", "complete", "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"))
    _j_p2.commit()
    _j_p2.close()
    _cout1_p2 = cp.compact_journal(_ctx_p2)
    _j_p2b = cp.connect_journal(_ctx_p2)
    _shown_legacy = cp.journal_show(_j_p2b, "op_legacy_p2")
    _shown_old = cp.journal_show(_j_p2b, "op_old_p2")
    _j_p2b.close()
    check("v0.4.2 P2: the merged pass redacts bodies AND collapses old rows in one walk",
          int(_cout1_p2.get("redacted") or 0) == 2
          and int(_cout1_p2.get("receipts") or 0) == 1
          and "text" not in ((_shown_legacy or {}).get("payload") or {})
          and ((_shown_old or {}).get("payload") or {}).get("receipt") is True)
    _cout2_p2 = cp.compact_journal(_ctx_p2)
    check("v0.4.2 P2: a second compact reports 0 redacted + 0 receipts (dirty-flag idempotence)",
          int(_cout2_p2.get("redacted") or 0) == 0
          and int(_cout2_p2.get("receipts") or 0) == 0)

# the merged pass on a twin journal == the old three-pass result, counts AND bytes
with _Env73() as _e_tw:
    _ctx_tw = sc.resolve_store(_e_tw.proj)
    _seed_rows_tw = [
        ("op_legacy_tw", "canonical-upsert",
         {"stem": "x", "text": "BODY-TW\n",
          "dest_preimages": [{"dest": "x.md", "bytes_b64": "Qk9EWQ==",
                              "sha256": "ab" * 32, "absent": False}]},
         "complete", "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        ("op_old_tw", "local-forget",
         {"publishes": [{"dest": "y.md", "sha256": "cd" * 32}]},
         "complete", "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
        ("op_pend_tw", "local-forget", {"deletes": []},
         "pending", "2026-01-01T00:00:00Z", ""),
    ]
    def _seed_tw(conn):
        for _r in _seed_rows_tw:
            conn.execute(
                "INSERT INTO journal(op_id, kind, payload, step, status, created_at, completed_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (_r[0], _r[1], _json_xp.dumps(_r[2]), "journal_complete",
                 _r[3], _r[4], _r[5]))
        conn.commit()
    _jA_tw = cp.connect_journal(_ctx_tw)
    _seed_tw(_jA_tw)
    _passA_tw = cp._compact_pass(_jA_tw, max_rows=0)
    _payA_tw = {r["op_id"]: r["payload"]
                for r in _jA_tw.execute("SELECT op_id, payload FROM journal").fetchall()}
    _jA_tw.close()
    _jB_tw = cp.connect_journal(_ctx_tw)
    _jB_tw.execute("DELETE FROM journal")
    _seed_tw(_jB_tw)
    _redB_tw = cp.redact_journal_payloads(_jB_tw)
    _recB_tw = cp.bound_journal_rows(_jB_tw)
    _payB_tw = {r["op_id"]: r["payload"]
                for r in _jB_tw.execute("SELECT op_id, payload FROM journal").fetchall()}
    _jB_tw.close()
    check("v0.4.2 P2: the merged pass result == the old three-pass result (counts AND payload bytes)",
          int(_passA_tw.get("redacted") or 0) == int(_redB_tw or 0)
          and int(_passA_tw.get("receipts") or 0) == int(_recB_tw or 0)
          and _payA_tw == _payB_tw)

# the export leg: the snapshot's redaction is reported + the CLI prints the progress line
with _Env73() as _e_ex:
    _ctx_ex = sc.resolve_store(_e_ex.proj)
    _j_ex = cp.connect_journal(_ctx_ex)
    _j_ex.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at, completed_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("op_export_ex", "canonical-upsert",
         _json_xp.dumps({"stem": "x", "text": "EXPORT-BODY\n"}),
         "journal_complete", "complete", "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"))
    _j_ex.commit()
    _j_ex.close()
    _dest_ex = _e_ex.proj / "export-test.tgz"
    _out_ex, _err_ex = _io73.StringIO(), _io73.StringIO()
    with _ctx73.redirect_stdout(_out_ex), _ctx73.redirect_stderr(_err_ex):
        _rc_ex = cmo.main(["data", "export", "--dest", str(_dest_ex),
                           "--project", str(_e_ex.proj)])
    _exp_res_ex = _json_xp.loads(_out_ex.getvalue() or "{}")
    check("v0.4.2 P2: the export reports the snapshot's journal redaction + the CLI "
          "prints the progress line on stderr",
          _rc_ex == 0 and int(_exp_res_ex.get("journal_redacted") or 0) == 1
          and "journal redacted 1 row(s)" in _err_ex.getvalue())

# the row cap is shrinkable (bound_journal_rows max_rows is the live knob)
with _Env73() as _e_cap:
    _ctx_cap = sc.resolve_store(_e_cap.proj)
    _j_cap = cp.connect_journal(_ctx_cap)
    for _i in range(5):
        _j_cap.execute(
            "INSERT INTO journal(op_id, kind, payload, step, status, created_at, completed_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (f"op_cap{_i}", "bench", _json_xp.dumps({"receipt": True}),
             "journal_complete", "complete",
             "2026-01-01T00:%02d:00Z" % _i, "2026-01-01T00:%02d:00Z" % _i))
    _j_cap.commit()
    _b_cap = cp.bound_journal_rows(_j_cap, max_rows=3)
    _n_cap = cp.journal_count(_j_cap)
    _j_cap.close()
    check("v0.4.2 P2: the row cap is shrinkable (max_rows=3 deletes the 2 oldest terminal rows; "
          "the cap-delete counts 1 — the documented operation-count convention)",
          int(_b_cap or 0) == 1 and _n_cap == 3)

# R4 (v0.4.2): compact_journal enforces the advertised JOURNAL_MAX_ROWS cap (it used to pass
# max_rows=0 — the cap was dormant on the compact path). Patched to a small value to prove the wiring.
with _Env73() as _e_r4:
    _ctx_r4 = sc.resolve_store(_e_r4.proj)
    _j_r4 = cp.connect_journal(_ctx_r4)
    for _i in range(6):
        _j_r4.execute(
            "INSERT INTO journal(op_id, kind, payload, step, status, created_at, completed_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("op_r4%d" % _i, "bench", _json_xp.dumps({"receipt": True}),
             "journal_complete", "complete",
             "2026-01-01T00:%02d:00Z" % _i, "2026-01-01T00:%02d:00Z" % _i))
    _j_r4.commit()
    _j_r4.close()
    _old_cap_r4 = cp.JOURNAL_MAX_ROWS
    cp.JOURNAL_MAX_ROWS = 3
    try:
        cp.compact_journal(_ctx_r4)
    finally:
        cp.JOURNAL_MAX_ROWS = _old_cap_r4
    _j_r4b = cp.connect_journal(_ctx_r4)
    _n_r4 = cp.journal_count(_j_r4b)
    _j_r4b.close()
    check("v0.4.2 R4: compact_journal enforces JOURNAL_MAX_ROWS (6 rows, patched cap 3 → 3 remain)",
          int(_n_r4) == 3)

# --apply runs exactly TWO orphan scans (pre-lock plan + under-lock rescan)
with _Env73() as _e_sc:
    _ctx_sc = sc.resolve_store(_e_sc.proj)
    _j_sc = cp.connect_journal(_ctx_sc)
    _trash_sc = _e_sc.store / ".cm-trash-op_orphan_sc01-0"
    _trash_sc.write_text("ORPHAN\n", encoding="utf-8")
    _j_sc.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("op_orphan_sc01", "local-forget", _json_xp.dumps({"deletes": []}),
         "journal_complete", "complete", "2026-01-01T00:00:00Z"))
    _j_sc.commit()
    _j_sc.close()
    _scans_p2 = [0]
    _orig_scan_p2 = cp.scan_orphan_artifacts
    def _counting_scan_p2(*a, **k):
        _scans_p2[0] += 1
        return _orig_scan_p2(*a, **k)
    cp.scan_orphan_artifacts = _counting_scan_p2
    try:
        _app_sc = cp.journal_cleanup(_ctx_sc, apply=True)
    finally:
        cp.scan_orphan_artifacts = _orig_scan_p2
    check("v0.4.2 P2: --apply runs exactly ONE orphan scan (the under-lock scan2; the "
          "post-cleanup rescan is gone — remaining is scan2 minus the unlinked) and the "
          "orphan is unlinked",
          _scans_p2[0] == 1 and _app_sc.get("ok") is True and not _trash_sc.exists())

# ── Phase 3: domain lifecycle / inactive ack / resurrect / purge fence ──
with _Env73() as _e_p3:
    _ctx_p3 = sc.resolve_store(_e_p3.proj)
    _up_p3 = ci.upsert(_ctx_p3, "keep-p3", _v3_canon("keep-p3", description="live"))
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_pg3 = cmo.main(["data", "purge", "--project", str(_e_p3.proj),
                            "--scope", "domain-canonicals", "--domain", "personal",
                            "--apply", "--confirm", "purge-domain-canonicals"])
    _ctx_p3b = sc.resolve_store(_e_p3.proj)
    _st_p3 = cmo.domain_purge_status(_ctx_p3b, "personal")
    check("P0-1: after domain purge former members are local-only",
          _up_p3.get("ok") is True and _rc_pg3 == 0
          and _ctx_p3b.enrolled is False
          and _ctx_p3b.cross_project_allowed is False
          and _st_p3.get("lifecycle") == "deleted"
          and _st_p3.get("enrolled_projects") == [])
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_en_w = cmo.main(["project", "enroll", str(_e_p3.proj), "--domain", "work",
                             "--apply", "--confirm", "enroll-work"])
    _ctx_p3c = sc.resolve_store(_e_p3.proj)
    check("P0-1: former member can enroll in another domain",
          _rc_en_w == 0 and _ctx_p3c.enrolled is True
          and _ctx_p3c.domain_id == "work"
          and _ctx_p3c.cross_project_allowed is True)
    _en_del = _io73.StringIO()
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_en_del):
        _rc_en_dead = cmo.main(["project", "enroll", str(_e_p3.proj), "--domain", "personal",
                                "--apply", "--confirm", "enroll-personal"])
    check("P0-1: enroll into a deleted domain is refused",
          _rc_en_dead == 2 and "deleted" in _en_del.getvalue())

with _Env73() as _e_can:
    _ctx_can = sc.resolve_store(_e_can.proj)
    ci.upsert(_ctx_can, "still-here", _v3_canon("still-here"))
    def _mark_del(_c, _t):
        del _c, _t
        return {"registry_ops": [
            {"op": "domain_status_set", "domain_id": "personal", "status": "deleting"}]}
    cp.transact(_ctx_can, "domain-deleting", {"domain_id": "personal"}, _mark_del,
                extra_domains=["personal"])
    _st_can = cmo.domain_purge_status(_ctx_can, "personal")
    _can_out = cmo.domain_purge_cancel(_ctx_can, "personal")
    _st_can2 = cmo.domain_purge_status(sc.resolve_store(_e_can.proj), "personal")
    check("P0-1: interrupted purge can be cancelled back to active",
          _st_can.get("lifecycle") == "deleting"
          and _can_out.get("ok") is True
          and _st_can2.get("lifecycle") == "active")

with _Env73() as _e_rsu:
    _ctx_rsu = sc.resolve_store(_e_rsu.proj)
    ci.upsert(_ctx_rsu, "rsu-fact", _v3_canon("rsu-fact"))
    def _mark_rsu(_c, _t):
        del _c, _t
        return {"registry_ops": [
            {"op": "domain_status_set", "domain_id": "personal", "status": "deleting"}]}
    cp.transact(_ctx_rsu, "domain-deleting", {"domain_id": "personal"}, _mark_rsu,
                extra_domains=["personal"])
    _rsu = cmo.domain_purge_resume(_ctx_rsu, "personal")
    _st_rsu = cmo.domain_purge_status(sc.resolve_store(_e_rsu.proj), "personal")
    check("P0-1: interrupted purge can be resumed to deleted with zero enrolled",
          _rsu.get("ok") is True
          and _st_rsu.get("lifecycle") == "deleted"
          and _st_rsu.get("enrolled_projects") == [])

with _Env73() as _e_tb:
    _ctx_tb = sc.resolve_store(_e_tb.proj)
    ci.upsert(_ctx_tb, "gone-body", _v3_canon("gone-body", description="secret"))
    _fg_tb = ci.forget(_ctx_tb, "gone-body")
    _rx_tb = ci.set_canonical_status(_ctx_tb, "gone-body", "active")
    check("P1-2: reactivate of a tombstone stub is refused",
          _fg_tb.get("ok") is True
          and _rx_tb.get("ok") is False
          and "tombstone stub" in str(_rx_tb.get("error") or ""))
    _new_tb = _v3_canon("gone-body", description="new-life", body="RESURRECTED\n")
    _rs_tb = ci.resurrect(_ctx_tb, "gone-body", _new_tb)
    _live_tb = (_ctx_tb.canonical_domain_dir / "gone-body.md").read_text(encoding="utf-8")
    check("P1-2: resurrect --file writes a real active body",
          _rs_tb.get("ok") is True
          and "RESURRECTED" in _live_tb
          and "status: active" in _live_tb
          and "Previous body is not retained" not in _live_tb)

with _Env73() as _e_ex:
    _ctx_ex = sc.resolve_store(_e_ex.proj)
    ci.upsert(_ctx_ex, "will-expire", _v3_canon("will-expire", description="temp"))
    ci.upsert(_ctx_ex, "will-keep", _v3_canon("will-keep", description="keep"))
    _proj_b = Path(_e_ex._td.name) / "src" / "other"
    _proj_b.mkdir(parents=True)
    _enroll_personal(_proj_b)
    _ctx_bex = sc.resolve_store(_proj_b)
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_b1 = sg.run(_proj_b, pull=True)
    ci.set_canonical_status(_ctx_ex, "will-expire", "expired")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_b2 = sg.run(_proj_b, pull=True)
    _idx_b = (_ctx_bex.native_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    check("P1-1: expired facts disappear from receiving indexes on the next pull",
          _rc_b1 == 0 and _rc_b2 == 0
          and "will-keep.md" in _idx_b
          and "will-expire.md" not in _idx_b
          and not (_ctx_bex.native_memory_dir / "will-expire.md").exists())

with _Env73() as _e_su:
    _ctx_su = sc.resolve_store(_e_su.proj)
    ci.upsert(_ctx_su, "old-name", _v3_canon("old-name", description="old"))
    ci.upsert(_ctx_su, "new-name", _v3_canon("new-name", description="new"))
    _proj_s = Path(_e_su._td.name) / "src" / "sib"
    _proj_s.mkdir(parents=True)
    _enroll_personal(_proj_s)
    _ctx_sib = sc.resolve_store(_proj_s)
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        sg.run(_proj_s, pull=True)
    ci.set_canonical_status(_ctx_su, "old-name", "superseded", replacement_id="new-name")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_su = sg.run(_proj_s, pull=True)
    _idx_su = (_ctx_sib.native_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    check("P1-1: supersede installs replacement then drops the old pointer on pull",
          _rc_su == 0
          and "new-name.md" in _idx_su
          and "old-name.md" not in _idx_su
          and (_ctx_sib.native_memory_dir / "new-name.md").is_file()
          and not (_ctx_sib.native_memory_dir / "old-name.md").exists())

# ── Phase-5 testing-gaps closeout: the audit's PARTIAL scenarios in smoke ──────
# S12: reactivate-after-expire propagation (expire + supersede were covered; the
# reactivation return trip was not). S10: a failed trash restoration inside
# journal rollback (the pre-commit refusal was pinned; the mid-rollback
# _restore_trash error branch was not). S14: compaction after a high
# windows_full baseline, end-to-end — the justify verdict must follow the
# SQLite usage-window clock, never the compactable JSONL tail.

with _Env73() as _e_ra:
    _ctx_ra = sc.resolve_store(_e_ra.proj)
    ci.upsert(_ctx_ra, "reactivate-me", _v3_canon("reactivate-me", description="temp"))
    _proj_ra = Path(_e_ra._td.name) / "src" / "recv-ra"
    _proj_ra.mkdir(parents=True)
    _enroll_personal(_proj_ra)
    _ctx_bra = sc.resolve_store(_proj_ra)
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_ra1 = sg.run(_proj_ra, pull=True)
    ci.set_canonical_status(_ctx_ra, "reactivate-me", "expired")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_ra2 = sg.run(_proj_ra, pull=True)
    _idx_ra2 = (_ctx_bra.native_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    _mirror_ra_gone = not (_ctx_bra.native_memory_dir / "reactivate-me.md").exists()
    _react_ra = ci.set_canonical_status(_ctx_ra, "reactivate-me", "active")
    with _ctx73.redirect_stdout(_io73.StringIO()), _ctx73.redirect_stderr(_io73.StringIO()):
        _rc_ra3 = sg.run(_proj_ra, pull=True)
    _idx_ra3 = (_ctx_bra.native_memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    check("P1-1: reactivated facts reappear in receiving indexes on the next pull",
          _rc_ra1 == 0 and _rc_ra2 == 0 and _rc_ra3 == 0
          and _react_ra.get("ok") is True
          and "reactivate-me.md" not in _idx_ra2
          and _mirror_ra_gone
          and "reactivate-me.md" in _idx_ra3
          and (_ctx_bra.native_memory_dir / "reactivate-me.md").is_file())

with _Env73() as _e_rb:
    _ctx_rb = sc.resolve_store(_e_rb.proj)
    _store_rb = _ctx_rb.native_memory_dir
    _dest_rb = _store_rb / "rollback-probe.md"
    _dest_rb.write_text("preimage body\n", encoding="utf-8")

    def _mut_rb(conn, temps):
        del conn, temps
        return {"deletes": [str(_dest_rb)]}

    if _os73.name != "nt" and (not hasattr(_os73, "geteuid") or _os73.geteuid() != 0):
        _crashed_rb = False
        try:
            cp.transact(_ctx_rb, "probe-rb", {"k": 1}, _mut_rb, crash_after="after_trash")
        except cp.CrashSimulated:
            _crashed_rb = True
        _jconn_rb = cp.connect_journal(_ctx_rb)
        _row_rb = _jconn_rb.execute(
            "SELECT op_id FROM journal ORDER BY rowid DESC LIMIT 1").fetchone()
        _oid_rb = str(_row_rb["op_id"] if _row_rb else "")
        _jconn_rb.close()
        _roll_rb = None
        _old_mode_rb = _os73.stat(_store_rb).st_mode
        try:
            _os73.chmod(_store_rb, 0o500)  # real EACCES for the trash→dest rename
            try:
                cp.journal_rollback(_ctx_rb, _oid_rb)
            except sc.WriteRefused as e:
                _roll_rb = str(e)
        finally:
            _os73.chmod(_store_rb, _old_mode_rb)
        _jconn_rb2 = cp.connect_journal(_ctx_rb)
        _row_rb2 = _jconn_rb2.execute(
            "SELECT status FROM journal WHERE op_id=?", (_oid_rb,)).fetchone()
        _jconn_rb2.close()
        check("S10: a failed trash restore refuses the rollback — never abandoned, trash intact",
              _crashed_rb
              and _roll_rb is not None and "restore failed; not abandoned" in _roll_rb
              and str(_row_rb2["status"] or "") == "pending"
              and not _dest_rb.exists()
              and any(_store_rb.glob(".cm-trash-*")))

with _Env73() as _e_cp:
    import json as _json_s14
    _ctx_cp = sc.resolve_store(_e_cp.proj)
    _store_cp = _ctx_cp.native_memory_dir
    _fact_cp = _store_cp / "comp-fact.md"
    _fact_cp.write_text(
        "---\nname: comp-fact\ndescription: old hook\nmetadata:\n"
        "  node_type: memory\n  scope: project-local\n  type: project\n---\nbody\n",
        encoding="utf-8")
    # backdate to 2000-01-01 so every seeded window start post-dates the fact
    _os73.utime(_fact_cp, (946684800, 946684800))
    (_store_cp / "MEMORY.md").write_text(
        "# Memory Index\n\n- [comp-fact](comp-fact.md) — old hook\n", encoding="utf-8")
    # a sequence stamp on a fresh registry clock, then 5 later probative windows
    (_store_cp / ".consolidation-state.json").write_text(
        '{"demotion_justify": {"comp-fact": {"sequence": 0, "windows": 0, '
        '"at": "2026-01-01T00:00:00Z"}}}\n', encoding="utf-8")
    for _i in range(5):
        cp.record_usage_window(_ctx_cp, cycle_id="s14-w%d" % _i,
                               started_at="2026-02-01T00:%02d:00Z" % _i, probative=True)
    # a HIGH JSONL tail — the legacy windows-only clock's evidence — then justify:
    # the sequence stamp must see its rows and refire.
    _log_cp = _store_cp / ".consolidation-log.jsonl"
    _rec_cp = {"usage": {
        "transcripts": 2, "facts_read": 1,
        "per_fact": [{"name": "comp-fact", "reads": 0, "last": "2026-01-01T00:00:00Z"}],
        "window": "2026-01-01T00:00:00Z..2026-01-01T00:10:00Z",
        "misses": [], "mention_stems": []}}
    with _log_cp.open("w", encoding="utf-8") as _fh_cp:
        for _i in range(12):
            _fh_cp.write(_json_s14.dumps(_rec_cp) + "\n")
    _j1_s14 = ms.run_justify_demotion(_e_cp.proj, ["comp-fact"], force=True)
    # 5 MORE probative rows (SQLite ONLY), then compact the JSONL to 4 records:
    # windows_full collapses below REFIRE, so a JSONL-reading clock would now
    # suppress — the sequence clock must still see the rows and refire again.
    for _i in range(5, 10):
        cp.record_usage_window(_ctx_cp, cycle_id="s14-w%d" % _i,
                               started_at="2026-02-01T00:%02d:00Z" % _i, probative=True)
    _comp_cp = ret.compact_jsonl(_log_cp, keep=4)
    _wf_after = int((ms.usage_history(_store_cp) or {}).get("windows_full") or 0)
    _j2_s14 = ms.run_justify_demotion(_e_cp.proj, ["comp-fact"], force=True)
    check("S14: compaction cannot prolong or shorten a sequence justify stamp",
          _j1_s14.get("ok") is True
          and any(_s.get("stem") == "comp-fact" for _s in (_j1_s14.get("stamped") or []))
          and _comp_cp.get("kept") == 4
          and _wf_after < 5
          and _j2_s14.get("ok") is True
          and any(_s.get("stem") == "comp-fact" for _s in (_j2_s14.get("stamped") or []))
          and not (_j2_s14.get("skipped") or []))

with _Env73() as _e_fn:
    _ctx_fn = sc.resolve_store(_e_fn.proj)
    _pdata = _ctx_fn.plugin_data_dir
    _droot = _ctx_fn.config_root / "consolidate-memory" / "domains"
    (_pdata / "leftover.txt").write_text("STILL-HERE\n", encoding="utf-8")
    _fid = "all-resume0001"
    _fp = _ctx_fn.config_root / "consolidate-memory-purge" / (_fid + ".json")
    _fp.parent.mkdir(parents=True, exist_ok=True)
    _fp.write_text(_json_xp.dumps({
        "purge_id": _fid, "state": "plugin-data-deleting",
        "targets": {"plugin_data": str(_pdata), "domains": str(_droot / "_none_")},
        "domains": [], "projects": [],
    }), encoding="utf-8")
    _fn_out = cmo.run_all_plugin_data_purge(_ctx_fn, rows=[], seen_dom=[], pids=[])
    _fence = _json_xp.loads(_fp.read_text(encoding="utf-8"))
    check("P1-8: interrupted all-plugin-data purge resumes until paths are absent",
          _fn_out.get("ok") is True
          and _fence.get("state") == "complete"
          and not (_pdata / "leftover.txt").exists())

# v0.4.0 review: the purge lifecycle must be CLI-reachable (the acceptance pins
# above call the Python API directly) — pin data purge-status end-to-end.
with _Env73() as _e_ps:
    _ps_u = _io73.StringIO()
    with _ctx73.redirect_stdout(_ps_u):
        _rc_ps = cmo.main(["data", "purge-status", "--domain", "personal",
                           "--json", "--project", str(_e_ps.proj)])
    _ps_j = _json_xp.loads(_ps_u.getvalue().strip() or "{}")
    check("P0-3: data purge-status is CLI-reachable and reports the lifecycle",
          _rc_ps == 0 and _ps_j.get("lifecycle") in ("active", "absent")
          and isinstance(_ps_j.get("enrolled_projects"), list))


# ── v0.4.0 Phase-5: facts-manifest cache pins (facts_manifest.py) ─────────────────
with _Env73() as _e_fm:
    import facts_manifest as _fmx
    _d_fm = _e_fm.glob
    for _i in range(3):
        (_d_fm / f"m{_i}.md").write_text(_v3_canon(f"m{_i}"), encoding="utf-8")
    _old_gif = sg._global_is_fixture
    sg._global_is_fixture = lambda: False   # activate the manifest path in-process
    try:
        _ctx_fm = sc.resolve_store(_e_fm.proj)
        _recs = sg._admissible_records(_ctx_fm)
        _mp = _fmx.manifest_path(_ctx_fm.plugin_data_dir, "personal")
        check("facts-manifest: first enumeration builds the manifest and serves rows (text None)",
              len(_recs) == 3 and all(_t is None for _n, _fx, _t, _px in _recs)
              and _mp.is_file())
        check("facts-manifest: 0600 + schema_version 1 + row count",
              _mp.stat().st_mode & 0o777 == 0o600
              and _json_xp.loads(_mp.read_text(encoding="utf-8")).get("schema_version") == 1)
        # the no-read sentinel: fresh rows are served with ZERO canonical body reads
        _orig_srt = sg._safe_read_text
        def _boom_fm(pth):
            if "facts" in str(pth):
                raise AssertionError("canonical body read during fresh-row serve")
            return _orig_srt(pth)
        sg._safe_read_text = _boom_fm
        try:
            _recs2 = sg._admissible_records(_ctx_fm)
            check("facts-manifest: fresh rows served with zero canonical body reads",
                  len(_recs2) == 3)
        finally:
            sg._safe_read_text = _orig_srt
        # a same-size rewrite with restored mtime is DETECTED (ctime bumps) → re-read
        _t1 = (_d_fm / "m1.md").read_text(encoding="utf-8")
        _st1 = (_d_fm / "m1.md").stat()
        (_d_fm / "m1.md").write_text(_t1.replace("description: d",
                                                 "description: d EDITED"), encoding="utf-8")
        import os as _os_fm
        _os_fm.utime(_d_fm / "m1.md", (_st1.st_atime, _st1.st_mtime))
        _fm2 = {n: f for n, f, _t, _p in sg._admissible_records(_ctx_fm)}
        check("facts-manifest: a mtime-restoring rewrite is detected (ctime) and re-read",
              "EDITED" in str(_fm2.get("m1", {}).get("description") or ""))
        # corrupt manifest → fail-open / self-heal rebuild: the SERVED SET is
        # identical either way (a corrupt cache can slow you down, never serve
        # wrong facts).
        _mp.write_text("{not json", encoding="utf-8")
        _recs3 = sg._admissible_records(_ctx_fm)
        check("facts-manifest: corrupt manifest fails open (identical served set)",
              sorted(n for n, _f, _t, _p in _recs3) == ["m0", "m1", "m2"]
              and all(str(_f.get("description") or "") for _n, _f, _t, _p in _recs3))
        # per-domain isolation: a second domain's manifest is separate
        _wdir = _ctx_fm.config_root / "consolidate-memory" / "domains" / "work" / "facts"
        _wdir.mkdir(parents=True, exist_ok=True)
        (_wdir / "w0.md").write_text(_v3_canon("w0", domain="work"), encoding="utf-8")
        _rows_w, _ = _fmx.ensure(_wdir, _ctx_fm.plugin_data_dir)
        check("facts-manifest: per-domain isolation (personal rows never serve work stems)",
              _rows_w is not None and "w0" in _rows_w and "m0" not in _rows_w)
        # canonical upsert invalidates through the transact choke point
        _up_fm = ci.upsert(_ctx_fm, "m2", _v3_canon("m2", body="edited body\n"))
        check("facts-manifest: a canonical upsert unlinks the manifest (transact choke point)",
              _up_fm.get("ok") is True and not _mp.exists())
    finally:
        sg._global_is_fixture = _old_gif


# ── v0.4.2 P3: warm-pull margin (sync_global.py) ───────────────────────────────
# the payload fix: a mirror's synthesized `metadata:` anchor (empty parent key) no longer
# enters the semantic payload — so sem(mirror) == sem(canonical) when content matches,
# the equality the manifest fast path depends on (pre-fix the anchor made them differ by
# exactly one payload line and the fast path could NEVER fire)
_canon_p3 = _v3_canon("p0", scope="stack-general").replace(
    "applies_any: []", "stacks: mypy\napplies_any: []", 1)
_mirr_p3 = sg._as_mirror(_canon_p3, "p0", since="2026-01-01T00:00:00Z",
                         body_hash=sg._body_hash(_canon_p3))
check("v0.4.2 P3: the mirror's synthesized metadata anchor is not content — "
      "sem(mirror) == sem(canonical) (the fast-path equality)",
      mc.semantic_hash(_mirr_p3) == mc.semantic_hash(_canon_p3)
      and sg._body_hash(_mirr_p3) == sg._body_hash(_canon_p3))
with _Env73() as _e_p3:
    _d_p3 = _e_p3.glob
    (_e_p3.proj / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n", encoding="utf-8")
    # three stack-general canonicals SHARING a stacks line (the memo's shape: identical raw
    # strings) — relevance needs the project's detect_stacks to see mypy
    for _i in range(3):
        (_d_p3 / f"p{_i}.md").write_text(
            _v3_canon(f"p{_i}", scope="stack-general").replace(
                "applies_any: []", "stacks: mypy\napplies_any: []", 1), encoding="utf-8")
    _old_gif3 = sg._global_is_fixture
    sg._global_is_fixture = lambda: False   # activate the manifest path in-process
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()):
            sg.run(_e_p3.proj, pull=True)   # first pull: mirrors land, manifest builds
        # counting wrappers — both rebound at call time (`from control_plane import ...`
        # inside the hot loop re-reads the module attr; _as_mirror is a module-global call)
        _con_calls = [0]
        _orig_cife = cp.connect_if_exists
        def _counting_cife(*a, **k):
            _con_calls[0] += 1
            return _orig_cife(*a, **k)
        cp.connect_if_exists = _counting_cife
        _asm_calls = [0]
        _orig_asm = sg._as_mirror
        def _counting_asm(*a, **k):
            _asm_calls[0] += 1
            return _orig_asm(*a, **k)
        sg._as_mirror = _counting_asm
        try:
            with _ctx73.redirect_stdout(_io73.StringIO()) as _s_p3:
                sg.run(_e_p3.proj, pull=True)   # no-change: all in-sync via the manifest fast path
            check("v0.4.2 P3: a no-change pull computes ZERO _as_mirror wants (manifest fast path) "
                  "and renders all three in-sync",
                  _asm_calls[0] == 0 and _s_p3.getvalue().count("in-sync") == 3)
            _con_base = _con_calls[0]   # migration_mode_readonly's per-run connect — the unrelated baseline
            # a SIBLING project edits p1/p2 through the SOLE canonical writer (ci.upsert — the
            # transact choke point unlinks the facts manifest, the production invalidation path).
            # The sibling authors, so THIS project's holder base stays at the old revision → the
            # mirrors classify STALE (an author's own upsert bumps its OWN base and would STOP —
            # the author-protection case, not the stale case). Then the loop must share ONE conn.
            _projB_p3 = _e_p3.proj.parent.parent / "src" / "projB73"
            _projB_p3.mkdir(parents=True)
            _enroll_personal(_projB_p3)
            _ctxB_p3 = sc.resolve_store(_projB_p3)
            for _stem_p3, _body_p3 in (("p1", "edited one\n"), ("p2", "edited two\n")):
                _up_p3 = ci.upsert(_ctxB_p3, _stem_p3,
                                   _v3_canon(_stem_p3, scope="stack-general",
                                             body=_body_p3).replace(
                                       "applies_any: []", "stacks: mypy\napplies_any: []", 1))
                assert _up_p3.get("ok") is True, _up_p3
            _asm_calls[0] = 0
            _con_calls[0] = 0
            with _ctx73.redirect_stdout(_io73.StringIO()) as _s_p3b:
                sg.run(_e_p3.proj, pull=True)
            check("v0.4.2 P3: N=2 stale mirrors share ONE holder-base conn (a connect each before)",
                  _con_calls[0] - _con_base == 1)
            check("v0.4.2 P3: the stale pull refreshes exactly the two edited mirrors",
                  "refreshed 2" in _s_p3b.getvalue())
            # the carry fix: an in-sync fact pairs with its OWN manifest row — the leftover-local
            # bug fed the last stale item's semantic hash into every earlier in-sync holder record,
            # and the poisoned holder base classified REFRESH on the very next pull (churn)
            _asm_calls[0] = 0
            with _ctx73.redirect_stdout(_io73.StringIO()) as _s_p3c:
                sg.run(_e_p3.proj, pull=True)
            check("v0.4.2 P3: the carry fix holds — the post-refresh pull is in-sync again, "
                  "zero wants (a poisoned holder base would show refresh churn)",
                  "refreshed 0" in _s_p3c.getvalue() and _s_p3c.getvalue().count("in-sync") == 3
                  and _asm_calls[0] == 0)
        finally:
            cp.connect_if_exists = _orig_cife
            sg._as_mirror = _orig_asm
    finally:
        sg._global_is_fixture = _old_gif3

# P3 review fix: the fleet-dead shape — stack-general, the writer-normal EMPTY applies
# lists (raw "[]" literals), NO stacks — must stay IRRELEVANT (the explicit-applies
# guard tests the PARSED forms; raw-presence testing replicated these into every
# same-domain index)
with _Env73() as _e_p3d:
    _d_p3d = _e_p3d.glob
    (_e_p3d.proj / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n", encoding="utf-8")
    (_d_p3d / "zzfleet.md").write_text(
        _v3_canon("zzfleet", scope="stack-general"), encoding="utf-8")
    _old_gif3d = sg._global_is_fixture
    sg._global_is_fixture = lambda: False
    try:
        with _ctx73.redirect_stdout(_io73.StringIO()) as _s_p3d:
            sg.run(_e_p3d.proj, pull=True)
        check("v0.4.2 P3: the fleet-dead shape stays IRRELEVANT (empty applies lists are "
              "not explicit gating — no mirror, no pull)",
              "zzfleet" in _s_p3d.getvalue() and "irrelevant" in _s_p3d.getvalue()
              and not (_e_p3d.store / "zzfleet.md").exists())
    finally:
        sg._global_is_fixture = _old_gif3d

# ── v0.4.2 P4: archive embed budget (render_html.py) ───────────────────────────
with _tf73.TemporaryDirectory() as _td_p4:
    _store_p4 = Path(_td_p4) / "memory"
    _store_p4.mkdir()
    _ddir_p4 = _store_p4.parent / "dashboards" / "diffs"
    _ddir_p4.mkdir(parents=True)
    _hist_p4 = []
    for _i in range(120):
        _hist_p4.append({
            "marker": {"commit": "c%03d" % _i,
                       "timestamp": "2026-01-01T%02d:%02d:00Z" % (_i // 60, _i % 60)},
            "session": "s%03d" % _i,
            "project": "p",
            "budget": {"index": {"before_tokens": 100, "after_tokens": 110,
                                 "budget_tokens": 1500, "over": False},
                       "recall_facts": {"before": 1, "after": 2},
                       "claude_md": {"before_tokens": 1000, "after_tokens": 1010,
                                     "over": False}},
            "rigor": {"applied": "LIGHT", "prune_pressure": False},
            "scope": {"git_commits": 1, "memories_reviewed": 1, "session_candidates": 1},
            "entries": [{"action": "added", "name": "x", "reason": "r",
                         "tier": "always-loaded"}],
            "verification": {"confirmed": 1, "method": "inline"},
            "usage": {"archive_reads": 1},
            "dream": {"sleep": "*s*", "beats": ["*b*"], "wake": "*w*"},
            "audit": {"mutations": 0},
            "junk_never_read": {"payload": "x" * 2000},
            "registrar_working": {"candidates": [{"raw": "y" * 400}]},
        })
    # 30 sidecars for the NEWEST 30 cycles — only the newest 20 embed; each payload
    # carries the cycle index so the distinct-payload count is meaningful
    for _i in range(90, 120):
        _key_p4 = ms.diff_key(_hist_p4[_i]["marker"], "s%03d" % _i)
        (_ddir_p4 / (_key_p4 + ".json")).write_text(
            _json_xp.dumps({"verdict": "created", "commands": [{"t": "cmd%d" % _i}]}),
            encoding="utf-8")
    _cyc_p4, _tot_p4 = rhtml.assemble_cycles({}, _hist_p4)
    _html_p4 = rhtml.build_html({}, _hist_p4, "2026-09-02T00:00:00Z",
                                rhtml.read_diffs(_store_p4, _cyc_p4),
                                cycles=_cyc_p4, total=_tot_p4)
    _m_p4 = _re.search(r'<script type="application/json" id="cm-data">(.*?)</script>',
                       _html_p4, _re.S)
    _embed_p4 = _json_xp.loads(_m_p4.group(1).replace("\\u003c", "<")
                               .replace("\\u003e", ">").replace("\\u0026", "&")) if _m_p4 else {}
    _cyc_e_p4 = _embed_p4.get("cycles") or []
    _diffs_p4 = _embed_p4.get("diffs") or {}
    check("v0.4.2 P4: the embed trims every cycle to the template's read-whitelist "
          "(junk keys gone; budget.recall_facts.after survives — full subtree)",
          len(_cyc_e_p4) == 120
          and all(set(_c) <= set(rhtml._EMBED_KEYS) | {"_integrity", "_outcome"} for _c in _cyc_e_p4)
          and _cyc_e_p4[-1].get("budget", {}).get("recall_facts", {}).get("after") == 2
          and "junk_never_read" not in _html_p4)
    # the guard-strength pin (review finding): the whitelist comment promises the template
    # "must not grow an unlisted read" — this makes it true. Every RECORD-LEVEL read the JS
    # makes (g(CUR,..)/g(c,..)/g(r,..) first segments + direct CUR.* reads) must root in
    # _EMBED_KEYS or the injected _integrity/_outcome stamps (nested reads like e.action /
    # D.verdict / h.broken legitimately root elsewhere — they hang off whitelisted subtrees).
    _tpl_p4 = (ROOT / "plugins" / "consolidate-memory" / "scripts"
               / "dashboard.template.html").read_text(encoding="utf-8")
    _roots_p4 = {_mm.rsplit('"', 2)[1].split(".")[0]
                 for _mm in _re.findall(r'g\((?:CUR|c|r),"(?:[a-z_]+)\.', _tpl_p4)}
    _roots_p4 |= {_mm for _mm in _re.findall(r'\bCUR\.([a-z_]+)', _tpl_p4)}
    check("v0.4.2 P4: the whitelist guard has TEETH — every record-level template read roots "
          "in _EMBED_KEYS (or the injected _integrity/_outcome stamps)",
          bool(_roots_p4) and _roots_p4 <= set(rhtml._EMBED_KEYS) | {"_integrity", "_outcome"})
    check("v0.4.2 P4: only the newest 20 diff sidecars embed (30 written, 20 kept; "
          "counted as distinct SERIALIZED payloads — the aliased keys share one payload)",
          len({_json_xp.dumps(_v, sort_keys=True) for _v in _diffs_p4.values()}) == 20
          and any("c119__" in _k for _k in _diffs_p4)
          and not any("c099__" in _k for _k in _diffs_p4))
    check("v0.4.2 P4: the trimmed archive stays under the size bound (the fixture embeds "
          "~400KB untrimmed)",
          len(_html_p4) < 300 * 1024)

# ── v0.4.2 R1: stranded-global advisory (memory_status.py) ─────────────────────
with _tf73.TemporaryDirectory() as _td_r1:
    def _fact_r1(name, scope):
        return (f"---\nname: {name}\nscope: {scope}\nmetadata:\n  node_type: memory\n"
                f"  type: user\noriginSessionId: 00000000-0000-4000-8000-000000000001\n"
                f"---\nbody {name}\n")
    _m1_r1 = Path(_td_r1) / "g1.md"; _m1_r1.write_text(_fact_r1("g1", "user-global"), encoding="utf-8")
    _m2_r1 = Path(_td_r1) / "g2.md"; _m2_r1.write_text(_fact_r1("g2", "stack-general"), encoding="utf-8")
    _m3_r1 = Path(_td_r1) / "l1.md"; _m3_r1.write_text(_fact_r1("l1", "project-local"), encoding="utf-8")
    _m4_r1 = Path(_td_r1) / "gm.md"
    _m4_r1.write_text(sg._as_mirror(_fact_r1("gm", "user-global"), "gm"), encoding="utf-8")
    _files_r1 = [_m1_r1, _m2_r1, _m3_r1, _m4_r1]
    _d1_r1 = ms.schema_drift(_files_r1, {"g1", "g2", "l1", "gm"},
                             canonical_stems={"g2", "l1"})
    check("v0.4.2 R1: stranded-global advisory counts authored globals with no canonical "
          "(1 stranded — g1; the mirror exempt; drift_findings unchanged)",
          int(_d1_r1.get("advisory_stranded_globals") or 0) == 1
          and ms.drift_findings(_d1_r1) == 0)
    _d2_r1 = ms.schema_drift(_files_r1, {"g1", "g2", "l1", "gm"},
                             canonical_stems={"g1", "g2", "l1"})
    check("v0.4.2 R1: with a canonical for every stem the advisory is 0",
          int(_d2_r1.get("advisory_stranded_globals") or 0) == 0)


# ── v0.4.2 R2: fixture-store exclusion (sync_global.py) ────────────────────────
with _tf73.TemporaryDirectory() as _td_r2:
    _root_r2 = Path(_td_r2)
    (_root_r2 / ".claude" / "projects").mkdir(parents=True)
    _real_slug_r2 = _root_r2 / ".claude" / "projects" / "realproj" / "memory"
    _real_slug_r2.mkdir(parents=True)
    (_real_slug_r2 / "f.md").write_text("---\nname: f\nscope: project-local\n---\nbody\n",
                                        encoding="utf-8")
    # the marker sits at the SYNTH SLUG dir (make_fixture's production placement) — the
    # ancestor walk from the store finds it one hop up; the real store shares no marker
    _marked_r2 = _root_r2 / ".claude" / "projects" / "synth" / "memory"
    _marked_r2.mkdir(parents=True)
    (_marked_r2 / "g.md").write_text("---\nname: g\n---\nbody\n", encoding="utf-8")
    (_marked_r2.parent / ".cm-fixture").write_text("fixture\n", encoding="utf-8")
    # a registry-union row OUTSIDE the projects tree (and outside the marker's ancestry) —
    # excluded by the pinned slug pattern alone (the registry-union path)
    _reg_r2 = _root_r2 / "elsewhere" / "-tmp-bench-x" / "memory"
    _reg_r2.mkdir(parents=True)
    # review fix: the CURRENT-shape dash-slug fixture pattern (slug_for strips dots) — the
    # dot-bearing patterns alone missed the real pre-0.4.2 gate fixture dirs
    _dash_r2 = _root_r2 / "elsewhere2" / "-home-u--dream-beta-test-gate-repo" / "memory"
    _dash_r2.mkdir(parents=True)
    (_dash_r2 / "g.md").write_text("---\nname: g\n---\nbody\n", encoding="utf-8")
    _old_pr_r2 = sg._projects_root
    _old_rows_r2 = sg._registry_project_rows
    sg._projects_root = lambda: _root_r2 / ".claude" / "projects"
    sg._registry_project_rows = lambda: [{"native_memory_dir": str(_reg_r2)},
                                         {"native_memory_dir": str(_dash_r2)}]
    _err_r2 = _io73.StringIO()
    try:
        with _ctx73.redirect_stderr(_err_r2):
            _stores_r2 = sg.iter_native_stores()
    finally:
        sg._projects_root = _old_pr_r2
        sg._registry_project_rows = _old_rows_r2
    _keys_r2 = {sg._path_key(p) for p in _stores_r2}
    check("v0.4.2 R2: mixed tree — the marker, the -tmp- pattern, AND the dash-slug fixture "
          "pattern stores are all excluded; only the real store enumerates + the dim skip "
          "line keeps it visible",
          _keys_r2 == {sg._path_key(_real_slug_r2)}
          and "skipped 3 fixture store(s)" in _err_r2.getvalue())

# ── v0.4.2 R3: the oracle persist-gate family (beta_checks.py) ─────────────────
class _FakeCtxGate:
    skill_version = "0.4.1"
    skill = ROOT / "plugins" / "consolidate-memory" / "scripts"
_r_gate = _bc54.persist_gate(cast(_bc54.Ctx, _FakeCtxGate()))
check("v0.4.2 R3 beta family: the terminal gates fire on synthetic seeds "
      "(short arc → exit 4 ×1 line, duplicate re-fire, unstamped → exit 5)",
      len(_r_gate) == 1 and _r_gate[0].status == "PASS"
      and _r_gate[0].id == "CHK-PERSIST-GATE")
class _FakeCtxGateOld:
    skill_version = "0.4.0"
    skill = ROOT / "plugins" / "consolidate-memory" / "scripts"
check("v0.4.2 R3 beta family: pre-gate skill → SKIP-by-version (the vendored canary is covered)",
      _bc54.persist_gate(cast(_bc54.Ctx, _FakeCtxGateOld())) == [])

# ── v0.4.2 R5: release teeth (workflow + SBOM + committed pubkey) ──────────────
_wf_r5 = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
check("v0.4.2 R5: the release workflow carries the teeth (strict validates ×3, verify-tag, provenance)",
      "claude plugin validate . --strict" in _wf_r5
      and "claude plugin validate ./plugins/consolidate-memory --strict" in _wf_r5
      and "claude plugin validate ./plugins/dream-beta-tester --strict" in _wf_r5
      and "verify-tag" in _wf_r5
      and "attest-build-provenance" in _wf_r5
      and "id-token: write" in _wf_r5 and "attestations: write" in _wf_r5)
_pub_r5 = (ROOT / ".github" / "release-tag.pub").read_text(encoding="utf-8").strip()
check("v0.4.2 R5: the committed tag-verification key is the DocuFlow GitHub key (single line, ssh-ed25519)",
      _pub_r5.startswith("ssh-ed25519 ") and "\n" not in _pub_r5
      and _pub_r5.endswith("DocuFlow GitHub key"))
import subprocess as _sp_r5  # noqa: E402
with _tf73.TemporaryDirectory() as _td_r5:
    _sbom_r5 = Path(_td_r5) / "sbom.json"
    _pr_r5 = _sp_r5.run(
        [sys.executable, str(ROOT / "tools" / "make_sbom.py"),
         "--version", "0.4.2", "--out", str(_sbom_r5),
         str(ROOT / "plugins" / "consolidate-memory"),
         str(ROOT / "plugins" / "dream-beta-tester")],
        capture_output=True, text=True, timeout=120)
    _doc_r5 = _json_xp.loads(_sbom_r5.read_text(encoding="utf-8")) if _sbom_r5.is_file() else {}
    _pkgs_r5 = _doc_r5.get("packages") or []
    _files_r5 = _doc_r5.get("files") or []
    _hasfiles_r5 = [h for p in _pkgs_r5 for h in (p.get("hasFiles") or [])]
    check("v0.4.2 R5: the stdlib SBOM generator emits a valid SPDX-2.3 doc "
          "(both plugins, sha1+sha256 per file, version stamped, UNIQUE package-scoped "
          "SPDXIDs — the review's duplicate-plugin.json collision is structurally gone)",
          _pr_r5.returncode == 0
          and _doc_r5.get("spdxVersion") == "SPDX-2.3"
          and len(_pkgs_r5) == 2
          and (_pkgs_r5[0].get("versionInfo") if _pkgs_r5 else "") == "0.4.2"
          and all("SHA1" in {c.get("algorithm") for c in f.get("checksums") or []}
                  and "SHA256" in {c.get("algorithm") for c in f.get("checksums") or []}
                  for f in _files_r5)
          and len({f.get("SPDXID") for f in _files_r5}) == len(_files_r5)
          and len({f.get("fileName") for f in _files_r5}) == len(_files_r5)
          and all(f.get("SPDXID") in _hasfiles_r5 for f in _files_r5))


# ── 2026-09-03 cross-project audit (4 agents): the HIGH-fix pins ──────────────────────
# replacement-install clobber guard: a project-authored file at the replacement stem SURVIVES
# the inactive ack (P0-4 — pull and promote refuse this; reconcile must too)
with _Env73() as _e_cpa:
    _ctx_cpa = sc.resolve_store(_e_cpa.proj)
    _cp_cpa = cp.connect(cp.db_path(_ctx_cpa))
    try:
        cp.enroll_project(_cp_cpa, _ctx_cpa, "personal")
        _cp_cpa.commit()
    finally:
        _cp_cpa.close()
    _d_cpa = _ctx_cpa.canonical_domain_dir
    _d_cpa.mkdir(parents=True, exist_ok=True)
    (_d_cpa / "old.md").write_text(_v3_canon("old").replace(
        "status: active", "status: superseded\nreplacement_id: newer"), encoding="utf-8")
    (_d_cpa / "newer.md").write_text(_v3_canon("newer"), encoding="utf-8")
    _canon_ing = __import__("canonical_ingress")
    import sync_global as _sg_cpa
    _mirr_old = _sg_cpa._as_mirror((_d_cpa / "old.md").read_text(encoding="utf-8"),
                                    "old", since="2026-01-01T00:00:00Z",
                                    body_hash=_sg_cpa._body_hash((_d_cpa / "old.md").read_text(encoding="utf-8")))
    _store_cpa = _ctx_cpa.native_memory_dir
    (_store_cpa / "old.md").write_text(_mirr_old, encoding="utf-8")
    (_store_cpa / "newer.md").write_text("---\nname: newer\ndescription: authored locally\n---\nlocal\n",
                                         encoding="utf-8")
    _out_cpa = _canon_ing.reconcile_inactive_mirrors(_ctx_cpa)
    _newer_after = (_store_cpa / "newer.md").read_text(encoding="utf-8")
    check("cross-project audit: the inactive ack never clobbers a project-authored file at the "
          "replacement stem (P0-4 — the authored content survives, no mirror installed)",
          _out_cpa.get("ok") is True and "authored locally" in _newer_after
          and "global_ref:" not in _newer_after)

# fileless held stem — the crash-recovery edge (mirror deleted, pointer never reaped).
# The ack must strip the dangling pointer AND publish the index rewrite: pre-fix the strip
# happened in-memory but idx_changed stayed False, so MEMORY.md kept the dangling pointer
# forever. The surviving keep.md line proves the published file is the same index, rewritten.
with _Env73() as _e_fl:
    _ctx_fl = sc.resolve_store(_e_fl.proj)
    _cp_fl = cp.connect(cp.db_path(_ctx_fl))
    try:
        cp.enroll_project(_cp_fl, _ctx_fl, "personal")
        _cp_fl.commit()
    finally:
        _cp_fl.close()
    _d_fl = _ctx_fl.canonical_domain_dir
    _d_fl.mkdir(parents=True, exist_ok=True)
    (_d_fl / "old.md").write_text(_v3_canon("old"), encoding="utf-8")
    import canonical_ingress as _ci_fl
    _up_fl = _ci_fl.upsert(_ctx_fl, "old",
                           (_d_fl / "old.md").read_text(encoding="utf-8"))
    _st_fl = _ci_fl.set_canonical_status(_ctx_fl, "old", "superseded")
    _store_fl = _ctx_fl.native_memory_dir
    (_store_fl / "MEMORY.md").write_text(
        "- [old](old.md) — d [user-global]\n- [keep](keep.md) — d [user-global]\n",
        encoding="utf-8")
    _out_fl = _ci_fl.reconcile_inactive_mirrors(_ctx_fl)
    _idx_after_fl = (_store_fl / "MEMORY.md").read_text(encoding="utf-8")
    check("cross-project audit: the fileless-held-stem pointer reap PUBLISHES "
          "(idx_changed — the strip is discarded unless the flag is set)",
          _up_fl.get("ok") is True and _st_fl.get("ok") is True
          and _out_fl.get("ok") is True and "](old.md)" not in _idx_after_fl
          and "](keep.md)" in _idx_after_fl)

# holder base: a canonical upsert WITHOUT --origin must not advance the holder's own mirror base
with _Env73() as _e_hb:
    _ctx_hb = sc.resolve_store(_e_hb.proj)
    _cp_hb = cp.connect(cp.db_path(_ctx_hb))
    try:
        cp.enroll_project(_cp_hb, _ctx_hb, "personal")
        _cp_hb.commit()
    finally:
        _cp_hb.close()
    _d_hb = _ctx_hb.canonical_domain_dir
    _d_hb.mkdir(parents=True, exist_ok=True)
    (_d_hb / "hb.md").write_text(_v3_canon("hb"), encoding="utf-8")
    import canonical_ingress as _ci_hb
    _ci_hb.upsert(_ctx_hb, "hb", _v3_canon("hb"))
    from control_plane import holder_base_revision as _hbr_hb, stable_fact_id as _sfid_hb
    _conn_hb = cp.connect(cp.db_path(_ctx_hb))
    try:
        _base1 = _hbr_hb(_conn_hb, _sfid_hb("personal", "hb"), _ctx_hb.project_id)
        _conn_hb.close()
        # second upsert (no --origin) with a changed body: the holder's base must stay
        _ci_hb.upsert(_ctx_hb, "hb", _v3_canon("hb", body="changed body\n"))
        _conn_hb = cp.connect(cp.db_path(_ctx_hb))
        _base2 = _hbr_hb(_conn_hb, _sfid_hb("personal", "hb"), _ctx_hb.project_id)
    finally:
        _conn_hb.close()
    check("cross-project audit: upsert without --origin keeps the holder's three-way base "
          "(advancing it would classify the holder's own untouched mirror as a local edit)",
          _base1 == _base2)

# semantic_payload sees UNKNOWN metadata keys (a local edit there is never silently discarded)
_md_cp = """---\nschema_version: 3\nname: m\ndescription: d\ndomain: personal\nscope: user-global\nstatus: active\nmetadata:\n  node_type: memory\n  mynote: hello\n---\nbody\n"""
_md_cp2 = _md_cp.replace("mynote: hello", "mynote: CHANGED")
check("cross-project audit: a local edit to an UNKNOWN metadata key changes the semantic payload",
      mc.semantic_hash(_md_cp) != mc.semantic_hash(_md_cp2))

# compact_jsonl preserves the ledger's 0o600
with _tf72.TemporaryDirectory() as _td_cm:
    _lj = Path(_td_cm) / "ledger.jsonl"
    _lj.write_text(_json.dumps({"a": 1}) + "\n", encoding="utf-8")
    _os72.chmod(_lj, 0o600)
    from retention import compact_jsonl as _cj_cm
    _cj_cm(_lj, keep=1)
    _mode_cm = _os72.stat(_lj).st_mode & 0o777
    check("cross-project audit: compact_jsonl preserves the ledger's 0o600 mode",
          _mode_cm == 0o600)

# count_probative_after returns None on a registry-less store (never a suppress-forever 0).
# Deliberately NOT _Env73: that fixture enrolls and CREATES the registry DB, so the
# registry-less path would never run. A bare HOME-redirected project dir is the real shape.
with _tf73.TemporaryDirectory() as _td_np:
    _home_np = Path(_td_np)
    _proj_np = (_home_np / "src" / "proj-np").resolve()
    _proj_np.mkdir(parents=True)
    (_home_np / ".claude" / "projects" / ms.slug_for(_proj_np) / "memory").mkdir(parents=True)
    _home_prev_np = _os73.environ.get("HOME")
    _os73.environ["HOME"] = str(_home_np)
    try:
        _ctx_np = sc.resolve_store(_proj_np)
        check("cross-project audit: count_probative_after is None (not 0) with no registry",
              cp.count_probative_after(_ctx_np, 0) is None)
        check("cross-project audit: that None came from a genuinely missing DB (fixture honesty)",
              not cp.db_path(_ctx_np).exists())
    finally:
        if _home_prev_np is None:
            _os73.environ.pop("HOME", None)
        else:
            _os73.environ["HOME"] = _home_prev_np

# journal_cleanup ages out RESOLVED conflicts by created_at (the decision label never
# compares against a cutoff) and sweeps the quarantine pen — one cutoff, both sweeps.
# Pre-fix, the predicate keyed on `resolved` deleted nothing: the label rows all survive.
with _Env73() as _e_jc:
    _ctx_jc = sc.resolve_store(_e_jc.proj)
    _cp_jc = cp.connect(cp.db_path(_ctx_jc))
    try:
        cp.record_conflict(_cp_jc, "c-old", _ctx_jc.project_id,
                           {"action": "conflict"}, domain_id="personal")
        _cp_jc.execute(
            "UPDATE conflicts SET created_at=?, resolved='keep-canonical' "
            "WHERE fact_stem='c-old'",
            ("2026-08-01T00:00:00Z",))
        cp.record_conflict(_cp_jc, "c-open", _ctx_jc.project_id,
                           {"action": "conflict"}, domain_id="personal")
        _cp_jc.execute(
            "UPDATE conflicts SET created_at=? WHERE fact_stem='c-open'",
            ("2026-08-01T00:00:00Z",))
        _cp_jc.commit()
    finally:
        _cp_jc.close()
    _qdir_jc = _ctx_jc.native_memory_dir / "quarantine"
    _qdir_jc.mkdir(parents=True, exist_ok=True)
    _qf_jc = _qdir_jc / "held.md"
    _qf_jc.write_text("x\n", encoding="utf-8")
    _old_jc = _time70.time() - 2 * cp.RECOVERY_TTL_SEC
    _os72.utime(_qf_jc, (_old_jc, _old_jc))
    _out_jc = cp.journal_cleanup(_ctx_jc, apply=True)
    _cp_jc2 = cp.connect(cp.db_path(_ctx_jc))
    try:
        _rows_jc = _cp_jc2.execute(
            "SELECT fact_stem, resolved FROM conflicts ORDER BY fact_stem").fetchall()
    finally:
        _cp_jc2.close()
    check("cross-project audit: journal_cleanup ages out resolved conflicts by created_at, "
          "leaves open ones, and sweeps the quarantine pen",
          _out_jc.get("ok") is True and [tuple(r) for r in _rows_jc] == [("c-open", "")]
          and not _qf_jc.exists() and _out_jc.get("quarantine_swept") == 1)

# ── v0.4.5 (#152 code leg): SHA256SUMS in the release pipeline ─────────────────
_wf_cs = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
check("v0.4.5 #152: the release workflow generates + self-verifies + uploads SHA256SUMS beside the SBOM",
      "make_checksums.py --out SHA256SUMS" in _wf_cs
      and "sha256sum -c SHA256SUMS" in _wf_cs
      and 'gh release upload "$TAG" sbom.spdx.json SHA256SUMS --clobber' in _wf_cs)
with _tf73.TemporaryDirectory() as _td_cs:
    _cs_tmp = Path(_td_cs)
    (_cs_tmp / "a.txt").write_text("alpha\n", encoding="utf-8")
    (_cs_tmp / "sub").mkdir()
    (_cs_tmp / "sub" / "b.bin").write_bytes(b"\x00\x01\x02")
    # a symlink + a dir entry must never enter the manifest (make_sbom walk parity);
    # a platform without symlink permission degrades to the file-set assertion
    try:
        (_cs_tmp / "link.txt").symlink_to(_cs_tmp / "a.txt")
    except OSError:
        pass
    (_cs_tmp / "empty").mkdir()
    _cs_out = _cs_tmp / "SHA256SUMS"
    _pr_cs = _sp_r5.run(
        [sys.executable, str(ROOT / "tools" / "make_checksums.py"), "--out", str(_cs_out), "."],
        capture_output=True, text=True, timeout=60, cwd=str(_cs_tmp))
    _lines_cs = _cs_out.read_text(encoding="utf-8").splitlines() if _cs_out.is_file() else []
    import hashlib as _hl_cs  # noqa: E402
    _parsed_cs = []
    for _ln in _lines_cs:
        _hex_cs, _sep_cs, _rel_cs = _ln.partition("  ")
        if _sep_cs and _hex_cs:
            _parsed_cs.append((_hex_cs, _rel_cs))
    _verified_cs = all(
        _hl_cs.sha256((_cs_tmp / _rel_cs).read_bytes()).hexdigest() == _hex_cs
        for _hex_cs, _rel_cs in _parsed_cs)
    check("v0.4.5 #152: the stdlib checksum generator emits a sha256sum-verifiable manifest "
          "(every file listed, hashes match, the symlink and empty dir excluded)",
          _pr_cs.returncode == 0
          and {_rel_cs for _, _rel_cs in _parsed_cs} == {"a.txt", "sub/b.bin"}
          and _verified_cs)

# ── v0.4.2 L1/L3: help sweep + the first-seen nag + the honest no-diffs row ─────
import subprocess as _sp_l1  # noqa: E402
_h_l1 = _sp_l1.run([str(ROOT / "cm"), "help"], capture_output=True, text=True, timeout=60)
check("v0.4.2 L1: cm help lists the missing subcommands + the required --confirm phrases "
      "(data import · canonical catalog · project grants/grant-native/revoke-native/transfer-native "
      "· the M1 sentence completes)",
      "inventory|compact|export|import" in _h_l1.stdout
      and "canonical catalog" in _h_l1.stdout
      and "project grants [DIR]" in _h_l1.stdout
      and "revoke-native" in _h_l1.stdout and "transfer-native" in _h_l1.stdout
      and "--apply --confirm data-import" in _h_l1.stdout
      and "--confirm migrate-apply" in _h_l1.stdout
      and "--confirm enroll-<domain>" in _h_l1.stdout
      and "verified knowledge freely" in _h_l1.stdout
      and "command not found" not in _h_l1.stderr)   # the heredoc is quoted — no backtick exec
check("v0.4.2 L1: the SKILL Phase-5 --diffs step is MANDATORY before WAKE + the template "
      "renders the honest no-capture row",
      "MANDATORY before WAKE" in (ROOT / "plugins" / "consolidate-memory" / "skills"
                                  / "consolidate-memory" / "SKILL.md").read_text(encoding="utf-8")
      and "no diffs captured" in (ROOT / "plugins" / "consolidate-memory" / "scripts"
                                  / "dashboard.template.html").read_text(encoding="utf-8"))
with _tf73.TemporaryDirectory() as _td_l3:
    _home_l3 = Path(_td_l3) / "home"; _home_l3.mkdir()
    _proj_l3 = Path(_td_l3) / "proj"; _proj_l3.mkdir()
    _old_h_l3 = _os73.environ.get("HOME")
    _os73.environ["HOME"] = str(_home_l3)
    try:
        _ctx_l3 = sc.resolve_store(_proj_l3)   # never enrolled → local-only
        _ctx_l3.native_memory_dir.mkdir(parents=True, exist_ok=True)
        (_ctx_l3.native_memory_dir / ".consolidation-state.json").write_text(
            _json_xp.dumps({"commit": "abc", "timestamp": "2026-07-01T00:00:00Z"}),
            encoding="utf-8")
        _e1_l3 = _io73.StringIO()
        with _ctx73.redirect_stderr(_e1_l3):
            sc.warn_unenrolled_share(_ctx_l3)   # first: prints + writes the flag
        _st_l3 = _json_xp.loads(
            (_ctx_l3.native_memory_dir / ".consolidation-state.json").read_text(encoding="utf-8"))
        _e2_l3 = _io73.StringIO()
        with _ctx73.redirect_stderr(_e2_l3):
            sc.warn_unenrolled_share(_ctx_l3)   # second: silent
        check("v0.4.2 L3: the unenrolled nag prints ONCE + persists the first-seen flag "
              "(the second call is silent; the enroll phrase carries --confirm)",
              "UNENROLLED LOCAL-ONLY" in _e1_l3.getvalue()
              and "--apply --confirm enroll-<domain>" in _e1_l3.getvalue()
              and _st_l3.get("_warned_unenrolled") is True
              and _e2_l3.getvalue() == "")
        _proj2_l3 = Path(_td_l3) / "proj2"; _proj2_l3.mkdir()
        _ctx2_l3 = sc.resolve_store(_proj2_l3)
        _e3_l3 = _io73.StringIO()
        with _ctx73.redirect_stderr(_e3_l3):
            sc.warn_unenrolled_share(_ctx2_l3)
        check("v0.4.2 L3: the nag never mints a state file on an absent store (the O1 pin) "
              "and still prints",
              "UNENROLLED LOCAL-ONLY" in _e3_l3.getvalue()
              and not (_ctx2_l3.native_memory_dir / ".consolidation-state.json").exists())
        _doc_l3 = sc.doctor_report(_ctx_l3)
        check("v0.4.2 L3: doctor stays loud (its own UNENROLLED LOCAL-ONLY line, un-gated)",
              "UNENROLLED LOCAL-ONLY" in _doc_l3)
    finally:
        if _old_h_l3 is None:
            _os73.environ.pop("HOME", None)
        else:
            _os73.environ["HOME"] = _old_h_l3

# ── v0.4.2 L2/L4: renderer coherence (top commands + one outcome vocabulary) ────
# L4: the single source — the dashboard banner and the log column agree on EVERY ladder rung
_l4_matrix = [
    ({}, "NOTHING TO CONSOLIDATE"),
    ({"entries": [{"action": "added"}]}, "LIGHT PASS"),
    ({"entries": [{"action": "added"} for _ in range(3)]}, "SUBSTANTIAL PASS"),
    ({"scope": {"git_commits": 4}, "entries": []}, "NO-OP PASS · reviewed, nothing changed"),
    ({"maintenance": {"pivoted": True}, "entries": []}, "MAINTENANCE PASS · self-heal / cross-node enrichment"),
    ({"outcome": "heavy", "entries": []}, "HEAVY"),
]
check("v0.4.2 L4: the outcome ladder has ONE definition — ms.outcome_of == rd._outcome == "
      "rlog's OUTCOME column across the full matrix (override + pivoted included)",
      all(ms.outcome_of(cast(ms.CycleRecord, _r)) == _lbl
          and rd._outcome(cast(Mapping[str, Any], _r)) == _lbl
          and rlog._row(cast(dict, _r))[-1] == _lbl and rlog._HEAD[-1] == "OUTCOME"
          for _r, _lbl in _l4_matrix))
check("v0.4.2 L4: the template prefers the embedded single-source label (the JS ladder "
      "stays as the legacy fallback)",
      'g(c,"_outcome","")' in (ROOT / "plugins" / "consolidate-memory" / "scripts"
                               / "dashboard.template.html").read_text(encoding="utf-8"))
# L2: top-3 distill.top rows in the USAGE top: idiom (ASCII + template BODY list); legacy no-top unchanged
_rec_l2 = {"project": "p", "session": "s", "scope": {}, "entries": [],
           "distill": {"n_recurring": 4, "n_chains": 1,
                       "top": [{"t": f"cmd{i}", "n": 5 - i, "d": 2} for i in range(4)]}}
_out_l2 = rd.render(cast(ms.CycleRecord, _rec_l2))
check("v0.4.2 L2: the DISTILL top-3 render in the USAGE top: idiom (capped at 3, +1 more)",
      "cmd0 ×5 2d" in _out_l2 and "cmd2 ×3 2d" in _out_l2
      and "cmd3" not in _out_l2 and "+1 more" in _out_l2)
check("v0.4.2 L2: a legacy distill record without `top` renders byte-identically (no top: line)",
      "top:" not in rd.render(cast(ms.CycleRecord,
                                   {"project": "p", "session": "s", "scope": {}, "entries": [],
                                    "distill": {"n_recurring": 1, "n_chains": 0}})))
# L2 (2026-09-03 hotfix): the template list moved from the header's counts line into the BODY
# (dstl-top-list) — long command names were wrapping the two-column header across rows. The pin
# holds BOTH directions: the body list exists AND the header no longer appends a top: appendix.
_tpl_l2 = (ROOT / "plugins" / "consolidate-memory" / "scripts"
           / "dashboard.template.html").read_text(encoding="utf-8")
check("v0.4.2 L2: the template renders the top commands in the BODY list, never the header counts line",
      "dstl-top-list" in _tpl_l2 and "dtop.slice(0,3)" in _tpl_l2
      and 'el("dstl-counts").textContent=counts.join(" · ")' in _tpl_l2
      and '" · top: "' not in _tpl_l2)
check("v0.4.6 exposure: the template renders the contract's OTHER distill evidence (chains + skill usage) "
      "and the registrar's unjudged-evidence board (cards OR the split-naming counts-only note) + the "
      "decline lineage (the anchors the materially-new-evidence gate consults)",
      "dstl-chains-list" in _tpl_l2 and "dstl-used-list" in _tpl_l2
      and "D.top_chains" in _tpl_l2 and "D.used" in _tpl_l2
      and "unjudged — evidence, not a docket" in _tpl_l2
      and "counts-only by design" in _tpl_l2
      and "WP.decline_anchors" in _tpl_l2
      and "decline lineage — other nodes declined these" in _tpl_l2)
check("v0.4.6 header coherence: every section header's note carries its tallies — This Pass names the "
      "derived outcome + decision count (it was cleared-and-never-set)",
      'el("pass-note").textContent=outcomeOf(CUR)' in _tpl_l2
      and 'el("hist-note").textContent' in _tpl_l2 and 'el("ent-note").textContent' in _tpl_l2
      and 'el("net-note").textContent' in _tpl_l2 and 'el("a-note").textContent' in _tpl_l2)


# ── v0.4.0 Phase-5: journal inventory keyset pagination ─────────────────────────
with _Env73() as _e_jp:
    _ctx_jp = sc.resolve_store(_e_jp.proj)
    _jconn_jp = cp.connect_journal(_ctx_jp)
    # 300 rows, 5 per second, op ids in insertion order (created_at second-resolution)
    _ids_jp = []
    for _i in range(300):
        _oid_jp = "op_%04d" % _i
        _ids_jp.append(_oid_jp)
        _ts_jp = "2026-01-01T00:%02d:%02dZ" % (_i // 5, _i % 5)
        _jconn_jp.execute(
            "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (_oid_jp, "bench", '{"receipt":1}', "complete", "complete", _ts_jp))
    _jconn_jp.commit()
    # default page bounded + cursor
    _page1, _cur1 = cp.journal_inventory(_jconn_jp, limit=200)
    check("journal paging: default page bounded + next cursor when more remain",
          len(_page1) == 200 and _cur1 is not None)
    # --after continuation: full enumeration equals the complete ordered list
    _page2, _cur2 = cp.journal_inventory(_jconn_jp, limit=200,
                                            after=str(_cur1 or ""))
    _all_ids = [r["op_id"] for r in _page1] + [r["op_id"] for r in _page2]
    check("journal paging: cursor continuation has no dup and no gap (order preserved)",
          _all_ids == sorted(_all_ids)
          and len(set(_all_ids)) == len(_all_ids)
          and len(_page2) == 100 and _cur2 is None)
    check("journal paging: journal_count matches the full row count",
          cp.journal_count(_jconn_jp) == 300)
    _jconn_jp.close()
    # CLI: --json envelope + bounded default via the real parser
    _jp_u = _io73.StringIO()
    with _ctx73.redirect_stdout(_jp_u):
        _rc_jp = cmo.main(["journal", "inventory", "--project", str(_e_jp.proj),
                           "--limit", "5", "--json"])
    _jp_j = _json_xp.loads(_jp_u.getvalue().strip())
    check("journal paging: CLI --json envelope {ok, rows, next_after, total} + bounded page",
          _rc_jp == 0 and _jp_j.get("ok") is True
          and len(_jp_j.get("rows") or []) == 5
          and isinstance(_jp_j.get("next_after"), str) and bool(_jp_j["next_after"])
          and _jp_j.get("total") == 300)
    # CLI plain: the footer names the cursor for the next page
    _jp2_u = _io73.StringIO()
    with _ctx73.redirect_stdout(_jp2_u):
        _rc_jp2 = cmo.main(["journal", "inventory", "--project", str(_e_jp.proj),
                            "--limit", "5"])
    check("journal paging: CLI plain footer prints the next-page cursor",
          _rc_jp2 == 0 and "for the next page" in _jp2_u.getvalue()
          and _jp_j["next_after"] in _jp2_u.getvalue())

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
