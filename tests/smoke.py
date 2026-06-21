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

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
